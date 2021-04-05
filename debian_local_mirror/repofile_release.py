from .repofile import RepoFile
from .metadata_parser import DebianMetaParser, FormatError
from tempfile import TemporaryFile
import logging
import re

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
                absent_ok = True)

        self._set_list_field()

    def _set_list_field(self):
        """
        Setting a list of list-fields for parser
        """
        self._list_fields = [
                "Architectures",
                "Components"
                ]

    def _convert_checksums(self, data):
        """
        Release-specific parsing of checksums list
        :param data: intermediate parsing result
        :type data: dict
        :return: modified data
        """
        if not isinstance(data, dict):
            raise FormatError(self._remote, "Wrong format - parse result should be a dictionary, but %s found" %
                    type(data))

        _fields = [
                "MD5Sum", 
                "SHA1", 
                "SHA256"
                ]

        _split_re = re.compile('\s+')
        logging.debug("Converting checksums fields: %s" % ', '.join(_fields))

        for _key in _fields:
            _value = data.get(_key)

            if not _value:
                continue

            _nval = list()

            for _tval in _value:
                (_hash, _size, _path) = _split_re.split(_tval, 2)
                _nval.append({"hash": _hash, "size": int(_size), "path": _path})

            data[_key] = _nval

        return data

    def parse(self):
        """
        Overrides general 'parse'
        to convert list of files to processable something.
        """
        return self._convert_checksums(super().parse())

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
                absent_ok = True)
        self._set_list_field()

    def open(self):
        """
        Open file. This version creates a temfile from the original
        with GPG-related data removed
        """
        self._data = None
        self._fd = TemporaryFile(mode = 'w+')

        with open(self._local, "r") as _lfl:
            _pgp_start = False
            _pgp_end = False

            while not _pgp_end:
                _line = _lfl.readline()
                
                if not _line:
                    break

                if not _pgp_start:
                    # search for PGP start
                    _pgp_start = _line.startswith('-----BEGIN PGP SIGNED MESSAGE-----')

                    if not _pgp_start:
                        continue

                    _line = _lfl.readline()

                    if not _line:
                        break;

                    if _line.startswith('Hash:'):
                        # we do not need Hash information
                        continue

                _pgp_end = _line.startswith('-----BEGIN PGP SIGNATURE-----')

                if _pgp_end:
                    break

                self._fd.write(_line)

        self._fd.seek(0, 0)
        self._data = self.parse()

