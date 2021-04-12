
class RepoFilePackages(RepoFile, DebianMetaParser):
    """
    Specific Packages file processor
    """

    def __init__(self, remote, local, sub):
        self._data = None
        super().__init__(
                remote = remote,
                local = local,
                sub = sub,
                extensions = [".gz", ".xz", ".bz2", ".lzma"],
                absent_ok = False)

    def check_before(self):
        """
        Override base class for synchronization.
        Returns True if any of file (with any of possible extension) exists
        """
        for _ext in self._ext:
            _fullpth = self._local + _ext;

            if os.path.exists(_fullpth):
                return True

        raise FileNotFoundError(self._local)

    def check_after(self):
        return self.check_before()

