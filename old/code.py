    def downloadGame(self, romId, romName, romUrl, targetDir):
        downloadTmpDir = self._getDownloadTmpDir(romId)
        Util.ensureDir(downloadTmpDir)

        # download
        with open(os.path.join(downloadTmpDir, "ROM_NAME"), "w") as f:
            f.write(romName)
        Util.shellExec("/usr/bin/wget --trust-server-names --content-disposition -c %s -P \"%s\" \"%s\"" % (Util.wgetCommonDownloadParam(), downloadTmpDir, romUrl))

        # save to target directory
        Util.forceDelete(targetDir)
        Util.ensureDir(os.path.dirname(targetDir))
        Util.shellCall("/bin/mv %s %s" % (downloadTmpDir, targetDir))

