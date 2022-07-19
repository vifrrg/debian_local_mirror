from .repofile import RepoFile
from .repofile_checksum import RepoFileWithCheckSum
from .repofile_packages import RepoFilePackages
from .metadata_parser import DebianMetaParser, FormatError
from tempfile import TemporaryFile
import logging
import re
import posixpath
import os
import datetime
from copy import deepcopy

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

    def strip_packages_versions(self, local, remote, versions):
        """
        Download all Packages specified here and modify them by trimming old versions of each package.
        Leave 'versions' versions only
        :param local: local base directory
        :param remote: remote 
        """

        logging.debug("local: '%s', remote: '%s', versions: '%d'" % (
            local, remote,  versions))

        self.open()
        _packages = dict()

        for _file, _fdata in self.get_subfiles().items():
            _path, _ext = posixpath.splitext(_file)
            _filename = posixpath.basename(_path)

            if _filename != 'Packages':
                continue

            logging.debug("Found 'Packages': subpath='%s', ext='%s'" % (_path, _ext))

            if _path not in _packages.keys():
                _packages[_path] = dict()

            _packages[_path][_ext] = _fdata

        for _path, _ext_subs in _packages.items():
            _pkg_file = RepoFilePackages(
                    remote = remote,
                    local = local,
                    sub = deepcopy(self._sub)[:-1] + _path.split(posixpath.sep),
                    checksums = _ext_subs, 
                    extensions = list(_ext_subs.keys()))

            _pkg_file.remove_from_disk()

            if not _pkg_file.synchronize():
                logging.error("Unable to synchronize '%s'" % _path)
                continue

            _pkg_file.strip_versions(versions=versions)
            _checksums_dict = _pkg_file.get_updated_checksums_sizes()
            self._update_checksums_pkg(_checksums_dict)

        self.write()
        self.close()
        raise NotImplementedError("TODO: load all packages files and strip them")

    def _update_checksums_pkg(self, checksums_dict):
        """
        update self._data with checksums_dict given - replace filename, size, hash
        This is special version for 'packages' file where keys are extensions
        """
        raise NotImplementedError("TODO: paste it to self._data: '%s'" % checksums_dict)

    def _update_checksums(self, checksums_dict):
        """
        update self._data with checksums_dict given - replace filename, size, hash
        This is general version
        """
        raise NotImplementedError("TODO: paste it to self._data: '%s'" % checksums_dict)

    def write(self):
        """
        Write modified content to disk, no signing
        """
        self.check_create_local_path()

        with open(self._local, mode="wt") as _fl_out:
            self.unparse_and_write(self._data, _fl_out)

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
            _repo_file_cs = RepoFileWithCheckSum(
                    local=os.path.dirname(self._local),
                    remote=posixpath.dirname(self._remote),
                    absent_ok=False,
                    fdict={"sub": _relpth.split(os.path.sep)})
            _repo_file_cs.open()
            _checksums_dict = _repo_file_cs.get_path_checksum_size(_checksums_fields)
            _repo_file_cs.close()

            for _cs in _checksums_fields:
                self._data[_cs].append(_checksums_dict.get(_cs))

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

    def strip_architectures(self, architectures):
        """
        Strip unused architectures
        :param architectures: list of architectures to leave
        :type architectures: list(str)
        """
        raise NotImplementedError("TODO: open, modify architectures, save")
