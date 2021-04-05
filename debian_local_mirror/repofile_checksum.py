from .repofile import RepoFile

class RepoFileWithCheckSum(RepoFile):
    """
    General file with checksum
    """
    def __init__(self, remote, local, fdict):
        self._data = None
        super().__init__(
                remote = remote,
                local = local,
                sub = fdict.get("sub"),
                extensions = [""],
                absent_ok = True)

        self._fdict = fdict
        self._links = list()

    def _create_links(self):
        """
        Do create all links for the file
        """

    def synchronize(self):
        """
        Override of base class - append to make links for by-hash cases
        """

        _result = super().synchronize()

        self._create_links()

        return _result
