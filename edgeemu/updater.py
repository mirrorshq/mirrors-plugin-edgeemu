#!/usr/bin/python3
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: t -*-

import os
import re
import sys
import time
import json
import manpa
import shutil
import string
import random
import socket
import subprocess
import urllib.request


class Main:

    def __init__(self, sock):
        args = json.loads(sys.argv[1])

        self.sock = sock
        self.dataDir = args["data-directory"]
        self.logDir = args["log-directory"]
        self.isDebug = (args["debug-flag"] != "")
        self.mp = manpa.Manpa(isDebug=self.isDebug)
        self.p = InfoPrinter()

    def run(self):
        # download MAME .216 ROMs
        self.p.print("Processing MAME .216 ROMs.")
        self.p.incIndent()
        try:
            postfixList = ["num"] + list(string.ascii_uppercase)
            for postfix in postfixList:
                gameInfoList = []
                with self.mp.open_selenium_client() as driver:
                    driver.get_and_wait("https://edgeemu.net/browse-mame-%s.htm" % (postfix))
                    for atag in driver.find_elements_by_xpath("/html/body/div/div[4]/center/table/tbody//a"):
                        romUrl = atag.get_attribute("href")
                        romName = atag.text
                        romId = re.match(".*id=([0-9]+)", romUrl).group(1)
                        gameInfoList.append((romId, romName, romUrl))
                infoList = []
                for romId, romName, romUrl in Util.randomSorted(gameInfoList):
                    targetDir = os.path.join(self.dataDir, romId)
                    if not os.path.exists(targetDir):
                        infoList.append([romId, romName, romUrl, targetDir])
                    else:
                        self.p.print("Check game \"%s\" (id: %s)." % (romName, romId))
                        self.checkGame(romId, romName, romUrl, targetDir)
                if len(infoList) > 0:
                    for romId, romName, romUrl, targetDir in infoList:
                        self.p.print("Download game \"%s\" (id: %s)." % (romName, romId))
                    self.downloadGameList(infoList)
        finally:
            self.p.decIndent()

    def removeDownloadTmpDir(self, romId):
        downloadTmpDir = self._getDownloadTmpDir(romId)
        assert os.path.realpath(downloadTmpDir).startswith(self.dataDir)
        Util.shellCall("/bin/rm -rf %s" % (downloadTmpDir))

    def downloadGameList(self, infoList):
        # infoList: [[romId, romName, romUrl, targetDir]]
        # there's no need to delete _aria2.input and _aria2.result, at least currently

        # create download tmpdir
        for i in infoList:
            downloadTmpDir = self._getDownloadTmpDir(i[0])
            Util.ensureDir(downloadTmpDir)
            with open(os.path.join(downloadTmpDir, "ROM_NAME"), "w") as f:
                f.write(i[1])
            i.append(downloadTmpDir)

        # create aria2 input file
        inputFile = os.path.join(self.dataDir, "_aria2.input")
        with open(inputFile, "w") as f:
            for i in infoList:
                romUrl = i[2]
                downloadTmpDir = i[4]
                buf = ""
                buf += "%s\n" % (romUrl)
                buf += " dir=%s\n" % (downloadTmpDir)
                buf += " out=%s\n" % (urllib.request.urlopen(urllib.request.Request(romUrl, method='HEAD')).info().get_filename())  # it seems aria2 can't use filename from server, sucks
                f.write(buf)

        # download
        resultBuf = ""
        if True:
            resultFile = os.path.join(self.dataDir, "_aria2.result")
            subprocess.run("/usr/bin/aria2c -i \"%s\" -c --save-session=\"%s\" --auto-file-renaming false -j10" % (inputFile, resultFile), shell=True)
            resultBuf = Util.readFile(resultFile)

        # save to target directory
        for i in infoList:
            romUrl = i[2]
            targetDir = i[3]
            downloadTmpDir = i[4]
            if romUrl not in resultBuf.split("\n"):     # only save successful download result
                Util.forceDelete(targetDir)
                Util.ensureDir(os.path.dirname(targetDir))
                Util.shellCall("/bin/mv %s %s" % (downloadTmpDir, targetDir))

    def checkGame(self, romId, romName, romUrl, targetDir):
        pass

    def _getDownloadTmpDir(self, romId):
        return os.path.join(self.dataDir, "_tmp_" + romId.replace("/", "_"))


class MUtil:

    @staticmethod
    def connect():
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect("/run/mirrors/api.socket")
        return sock

    @staticmethod
    def progress_changed(sock, progress):
        sock.send(json.dumps({
            "message": "progress",
            "data": {
                "progress": progress,
            },
        }).encode("utf-8"))
        sock.send(b'\n')

    @staticmethod
    def error_occured(sock, exc_info):
        sock.send(json.dumps({
            "message": "error",
            "data": {
                "exc_info": "abc",
            },
        }).encode("utf-8"))
        sock.send(b'\n')


class Util:

    @staticmethod
    def readFile(filename):
        with open(filename) as f:
            return f.read()

    @staticmethod
    def forceDelete(filename):
        if os.path.islink(filename):
            os.remove(filename)
        elif os.path.isfile(filename):
            os.remove(filename)
        elif os.path.isdir(filename):
            shutil.rmtree(filename)

    @staticmethod
    def randomSorted(tlist):
        return sorted(tlist, key=lambda x: random.random())

    @staticmethod
    def wgetCommonDownloadParam():
        return "-t 0 -w 60 --random-wait -T 60 --passive-ftp"

    @staticmethod
    def ensureDir(dirname):
        if not os.path.exists(dirname):
            os.makedirs(dirname)

    @staticmethod
    def shellExec(cmd):
        ret = subprocess.run(cmd, shell=True, universal_newlines=True)
        if ret.returncode > 128:
            time.sleep(1.0)
        ret.check_returncode()

    @staticmethod
    def shellCall(cmd):
        # call command with shell to execute backstage job
        # scenarios are the same as Util.cmdCall

        ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             shell=True, universal_newlines=True)
        if ret.returncode > 128:
            # for scenario 1, caller's signal handler has the oppotunity to get executed during sleep
            time.sleep(1.0)
        if ret.returncode != 0:
            ret.check_returncode()
        return ret.stdout.rstrip()


class InfoPrinter:

    def __init__(self):
        self.indent = 0

    def incIndent(self):
        self.indent = self.indent + 1

    def decIndent(self):
        assert self.indent > 0
        self.indent = self.indent - 1

    def print(self, s):
        line = ""
        line += "\t" * self.indent
        line += s
        print(line)


###############################################################################

if __name__ == "__main__":
    sock = MUtil.connect()
    try:
        Main(sock).run()
        MUtil.progress_changed(sock, 100)
    except Exception:
        MUtil.error_occured(sock, sys.exc_info())
        raise
    finally:
        sock.close()
