from .repofile import RepoFile
from .metadata_parser import DebianMetaParser

class RepoFileRelease(RepoFile, DebianMetaParser):
    """
    Specific release file processor
    """
    def __init__(self, remote, local, sub):
        self._data = None
        super().__init__(
                remote = remote,
                local = local,
                sub = sub,
                extensions = [".gpg"],
                absent_ok = False)

        self._set_list_field()

    def _set_list_field(self):
        """
        Setting a list of list-fields for parser
        """
        self._list_fields = [
                "Architectures",
                "Components"
                ]

    def open(self):
        """
        Open file
        """
        self._data = None
        self._fd = open(self._local, "r")
        self._data = self.parse()

    def get_data(self):
        return self._data

class RepoFileInRelease(RepoFileRelease):
    """
    Helper to process InRelease file with PGP signature removed
    """
    def __init__(self, remote, local, sub):
        self._data = None
        super(RepoFileRelease, self).__init__(
                remote = remote,
                local = local,
                sub = sub,
                extensions = [],
                absent_ok = False)
        self._set_list_field()

