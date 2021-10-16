from .repofile import RepoFile
from .metadata_parser import DebianMetaParser, FormatError
from tempfile import TemporaryFile
import logging
import re
import posixpath
import os
import datetime
import hashlib

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

    def remove_signature(self):
        """
        Removes GPG signature file
        """
        for _ext in self._ext:
            if not _ext:
                continue

            _fullpth = self._local + _ext

            if not os.path.exists(_fullpth):
                continue

            logging.debug("Removing '%s'" % _fullpth)

            os.remove(_fullpth)

    def remove_valid_until(self):
        """
        Remove 'Valid-Until' Tag
        Removes signature also
        """
        self.open()
        self.remove_signature()

        if "Valid-Until" in self._data.keys():
            del(self._data["Valid-Until"])

        self.close()
        self.write()

    def write(self):
        """
        Write modified content to disk, no signing
        """
        self.check_create_local_path()

        with open(self._local, mode="wt") as _fl_out:

            for _key in self._data.keys():
                logging.debug("Writing key value for '%s'" % _key)
                _value = self._data.get(_key)

                if not isinstance(_value, list):
                    _fl_out.write("%s: %s\n" % (_key, _value))
                    continue

                if not _key in self._checksums_fields:
                    _fl_out.write("%s: %s\n" %(_key, " ".join(_value)))
                    continue

                _fl_out.write("%s:\n" % _key)

                for _vl in _value:
                    _size = "%d" % _vl.get("Size")

                    while len(_size) < 10:
                        _size = " %s" % _size

                    _fl_out.write(" %s %s %s\n" % (_vl.get("hash"), _size, _vl.get("Filename")))

    def sign(self, gpg):
        """
        Sign ourselves with gpg object given
        :param gpg: GnuPG object
        :type gpg: pygpgme
        """
        self.close()
        for _ext in self._ext:
            if not _ext:
                continue

            _out = self._local + _ext
            gpg.sign_file(file_path=self._local, signature_output=_out)

        self.open()

    def create(self, distr, mirror, packages):
        """
        Create a file for mirror configuration with packages files hashsums
        :param distr: distributive codename
        :type distr: str
        :param mirror: mirror configuration
        :type mirror: MirrorConfig
        :param packages: list of local paths for packages file
        :type packages: list of str
        """
        self.close()
        logging.debug("Creation of local '%s' is started" % self._local)
        self._data = dict()
        self._data["Codename"] = distr
        self._data["Date"] = datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S UTC')
        self._data["Architectures"] = mirror.get("architectures")
        self._data["Components"] = mirror.get("sections")

        # collect sizes, SHA1, SHA256, MD5 checksums
        _checksums_fields = list()

        for _cs in self._checksums_fields:
            if _cs.lower() in list(map(lambda x: x.lower(), _checksums_fields)):
                continue

            _checksums_fields.append(_cs)
            self._data[_cs] = list()

        for _pkg in packages:
            # get relative path
            _relpth = os.path.relpath(_pkg, os.path.dirname(self._local))
            logging.debug("Packages '%s' relative path is '%s'" %(_pkg, _relpth))
            # get size
            _size = os.stat(_pkg).st_size

            # get checksums
            for _cs in _checksums_fields:
                _hashobj = None

                if _cs.lower() == "md5sum":
                    _hashobj = hashlib.md5()
                elif _cs.lower() == "sha1":
                    _hashobj = hashlib.sha1()
                elif _cs.lower() == "sha256":
                    _hashobj = hashlib.sha256()
                elif _cs.lower() == "sha512":
                    _hashobj = hashlib.sha512()

                with open(_pkg, mode="rb") as _fd:
                    while True:
                        _chunk = _fd.read(1 * 1024 * 1024)
                        
                        if not _chunk: 
                            break
                        
                        _hashobj.update(_chunk)

                self._data[_cs].append({
                    "Filename": _relpth,
                    "Size": _size,
                    "hash": _hashobj.hexdigest()})

        self.write()
        self.open()

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

    def sign(self, gpg):
        """
        Sign ourselves with gpg object given
        :param gpg: GnuPG object
        :type gpg: pygpgme
        """
        self.close()
        gpg.sign_file(file_path=self._local)
        self.open()
