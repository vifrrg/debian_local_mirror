from .repofile import RepoFile
from .metadata_parser import DebianMetaParser, FormatError
from tempfile import TemporaryFile
import logging
import re
import posixpath

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

        self._set_checksums_fields()

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

        _split_re = re.compile('\s+')
        logging.debug("Converting checksums fields: %s" % ', '.join(self._checksums_fields))

        for _key in self._checksums_fields:
            _value = data.get(_key)

            if not _value:
                continue

            _nval = list()

            for _tval in _value:
                (_hash, _size, _path) = _split_re.split(_tval, 2)
                _nval.append({"hash": _hash, "Size": int(_size), "Filename": _path})

            data[_key] = _nval

        return data

    def parse(self):
        """
        Overrides general 'parse'
        to convert list of files to processable something.
        """
        return self._convert_checksums(super().parse())

    def open(self, mode="r"):
        """
        Open file
        :param mode: open mode
        :type mode: str
        """
        self.close()
        self._data = None
        self._fd = open(self._local, mode)
        self._data = self.parse()

    def is_by_hash(self):
        """
        Return by-has acquiring, boolean
        """
        return self._data.get('Acquire-By-Hash', '').lower() in ['yes', 'true']

    def skip_all_architecture(self):
        """
        Should the archtecture "all" be skipped while processing
        """
        return self._data.get('No-Support-for-Architecture-all', '').lower() in ['yes', 'true']

    def get_sections(self):
        """
        Return sections list
        """
        return list(map(lambda x: posixpath.basename(x), self._data.get('Components')))

    def get_subfiles(self):
        """
        Return dictionary with files list
        """
        _result = dict()
        for _field in self._checksums_fields:
            _list = self._data.get(_field)

            if not _list:
                continue

            for _fl in _list:
                _key = _fl.get("Filename")
                _size = _fl.get("Size")
                _hash = _fl.get("hash")

                if _key not in _result.keys():
                    _result[_key] = dict()

                if "Size" in _result[_key].keys() and _result[_key]["Size"] != _size:
                    raise ValueError("Sizes not match for '%s' in '%s'" % (_key,self._local))

                _result[_key]["Size"] = _size
                _result[_key][_field] = _hash

                if "sub" not in _result[_key].keys():
                    _result[_key]["sub"] = self._sub[:-1] + _key.split(posixpath.sep)
                    logging.debug("Adding %s as subpath" % posixpath.sep.join(_result[_key]["sub"]))

                if not self.is_by_hash():
                    continue

                if "by-hash" not in _result[_key].keys():
                    _result[_key]["by-hash"] = list()

                _sub_hl = self._sub[:-1]
                _ppth_dirname = posixpath.dirname(_key).strip(posixpath.sep)

                if posixpath.sep in _ppth_dirname:
                    _sub_hl += _ppth_dirname.split(posixpath.sep)

                _sub_hl += ["by-hash", _field, _hash]

                logging.debug("Adding %s as sublink" % posixpath.sep.join(_sub_hl))

                _result[_key]["by-hash"].append(_sub_hl)

        return _result

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

    def open(self, mode="r"):
        """
        Open file. This version creates a temfile from the original
        with GPG-related data removed
        :param mode: open mode (not mandatory for this case, leaved for compatibility)
        :type mode: str
        """
        self._data = None
        self._fd = TemporaryFile(mode='w+')

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

