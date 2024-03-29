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

    def get_pure_fd(self):
        """
        Return file descriptor for copying data part
        File have to be opened prior to call this
        """
        return self._fd

    def get_signature(self):
        """
        Read signature and return it
        """
        if not os.path.exists(self._local + '.gpg'):
            logging.warning("Release file '%s' has no signature" % self._local)
            return ""

        _fd = open(self._local + '.gpg', mode='rt')
        _result = _fd.read()
        _fd.close()
        return _result

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

                if _path in ["Release", "Release.gpg", "InRelease"]:
                    logging.warning("File '%s' includes checksums for itself, and it will be skipped" % self._local)
                    continue

                _nval.append({"hash": _hash, "Size": int(_size), "Filename": _path})

            data[_key] = _nval
        
        return data

    def _convert_components(self, data_d):
        """
        Remove subpaths from 'Components' section list (provided by some security servers'
        """
        if any([not data_d.get("Components"), not isinstance(data_d.get("Components"), list)]):
            logging.warning("'Components' section absent in '%s'", self._local)
            return data_d

        data_d["Components"] = list(map(lambda x: posixpath.basename(x), data_d.get("Components")))
        data_d["Components"] = list(filter(lambda x: isinstance(x, str) and len(x)>0, data_d.get("Components")))
        return data_d

    def parse(self):
        """
        Overrides general 'parse'
        to convert list of files to processable something.
        """
        _data = self._convert_checksums(super().parse())
        _data = self._convert_components(_data)
        return _data

    def open(self, mode="rt"):
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

    def get_packages_file(self, section, arch):
        """
        Search for 'Packages' file with all possible variants (extensions)
        Return RepoFilePackages instance.
        """
        if self._data.get("Architectures") and arch not in self._data.get("Architectures"):
            logging.warning("Architecture '%s' is not covered by '%s'" % (arch, self._local))
            return None

        if self._data.get("Components") and section not in self._data.get("Components"):
            logging.warning("Section '%s' is not covered by '%s'" %(section, self._local))
            return None

        _packages = dict()

        for _file, _fdata in self.get_subfiles().items():
            _path, _ext = posixpath.splitext(_file)
            _filename = posixpath.basename(_path)

            if _filename != 'Packages':
                continue

            if not _path.startswith(posixpath.join(section, "binary-%s" % arch)):
                continue

            logging.debug("Found 'Packages': subpath='%s', ext='%s'" % (_path, _ext))

            if _path not in _packages.keys():
                _packages[_path] = dict()

            _packages[_path][_ext] = _fdata

        if len(list(_packages.keys())) != 1:

            if arch == 'all':
                return None

            raise ValueError("Found %d version(s) of 'Packages' in '%s'" % (len(list(_packages.keys())), self._local))

        _path = list(_packages.keys()).pop()
        _ext_subs = _packages.get(_path)

        return RepoFilePackages(
                remote = posixpath.join(posixpath.dirname(self._remote)),
                local = posixpath.join(posixpath.dirname(self._local)),
                sub = _path.split(posixpath.sep),
                checksums = _ext_subs, 
                extensions = list(_ext_subs.keys()))

    def strip_packages_versions(self, versions):
        """
        Download all Packages specified here and modify them by trimming old versions of each package.
        Leave 'versions' versions only
        """

        logging.debug("versions: '%d' for '%s'" % (versions, self._local))
        self.open()

        for _section in self._data.get("Components"):
            for _arch in self._data.get("Architectures"):
                _pkg_file = self.get_packages_file(_section, _arch)

                if not _pkg_file:
                    logging.warning("Not found 'Packages' for section '%s', architecture '%s'" % (_section, _arch))
                    continue

                _pkg_file.remove_from_disk()

                if not _pkg_file.synchronize():
                    logging.error("Unable to synchronize '%s'" % _path)
                    continue

                _pkg_file.strip_versions(versions=versions)
                _checksums_dict = _pkg_file.get_updated_checksums_sizes()
                self._update_checksums_pkg(_checksums_dict)

        self.close()
        self.write()

    def _update_checksums_pkg(self, checksums_dict):
        """
        update self._data with checksums_dict given - replace filename, size, hash
        This is special version for 'packages' file where keys are extensions
        """
        for _ext, _vals in checksums_dict.items():
            logging.debug('Updating checksums for extension "%s"' % _ext)
            self._update_checksums(_vals)

    def _update_checksums(self, checksums_dict):
        """
        update self._data with checksums_dict given - replace filename, size, hash
        This is general version
        """

        for _sumtype in checksums_dict.keys():
            # real key may be different case, thanks to format authors
            _real_sumtype = list(filter(lambda x: x.lower() == _sumtype.lower(), self._data.keys()))

            if not _real_sumtype:
                logging.debug("No field: '%s' - nothing to update" % (_sumtype)) 
                continue

            _real_sumtype = _real_sumtype.pop()
            logging.debug("Real sumtype is '%s' for '%s'" % (_real_sumtype, _sumtype))

            # here we are forced to use direct indexing instead of 'get' because we need an error if
            # something goes wrong
            _record = list(filter(lambda x: x.get('Filename') == checksums_dict.get(_sumtype).get('Filename'),
                self._data.get(_real_sumtype)))

            if _record:
                logging.debug("Removing record: '%s'" % _record)
                _record = _record.pop()
                self._data[_real_sumtype].remove(_record)

            logging.debug("Appending another record: '%s'" % checksums_dict.get(_sumtype))
            self._data[_real_sumtype].append(checksums_dict.get(_sumtype))

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

    def write_signature_footer(self, fd, signature):
        """
        Write GPG signature
        """
        with open(self._local + '.gpg', mode='wt') as _fd:
            _fd.write(signature)
            # signature should include newline character also

    def write_signature_header(self, fd):
        """
        Write GPG signature footer
        """
        # no need since signature is in separate file
        pass

    def create_from(self, rlfl):
        """
        Create a copy from other rlfl
        """
        self.close()
        rlfl.close()
        rlfl.open()
        with open(self._local, mode="wt") as _fd:
            self.write_signature_header(_fd)
            _src_fd = rlfl.get_pure_fd()
            _src_fd.seek(0, 0)
            _fd.write(_src_fd.read())
            self.write_signature_footer(_fd, rlfl.get_signature())
        rlfl.close()

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

    def strip_architectures(self, architectures):
        """
        Strip unused architectures
        :param architectures: list of architectures to leave
        :type architectures: list(str)
        """

        self.__strip_parameter(architectures, "Architectures", "all", '-%%s(\.|$|\%s)' % posixpath.sep)

    def strip_sections(self, sections):
        """
        Strip unused sections ("Components" key - thanks to authors for nice teminology)
        """
        self.__strip_parameter(sections, "Components", None, '^%%s\%s' % posixpath.sep)

    def strip_diff_directories(self):
        """
        Remove all .diff includes
        """
        logging.debug("Stripping .diffs")
        self.open()
        _rg = re.compile('\.diff(\%s|\s|$)' % posixpath.sep)

        for _cs_field in self._checksums_fields:
            logging.debug("Stripping .diff from field '%s'" % _cs_field)

            if not self._data.get(_cs_field):
                logging.debug("No checksum of type '%s' in '%s' - skipping" % (_cs_field, self._local))
                continue

            _records_to_remove = list(filter(lambda x: _rg.search(x.get("Filename")), self._data.get(_cs_field)))

            for _record in _records_to_remove:
                logging.debug("Removing record for '%s' from '%s'" % (_record.get("Filename"), _cs_field))
                self._data[_cs_field].remove(_record)

        self.close()
        self.write()

    def __strip_parameter(self, args_ls, data_key, add_value, regexp_filter):
        """
        Filter self parameter with regular expression template
        """
        if not data_key:
            raise ValueError("Data key not given")

        if not regexp_filter:
            raise ValueError("Regular expression filter template not specified")

        if not args_ls:
            raise ValueError("No filter list specified")

        if not isinstance(args_ls, list):
            raise TypeError("Filter list arg should be a list of str")

        logging.debug("%s to leave: '%s'" % (data_key, args_ls))
        self.open()
        _current_ls = self._data.get(data_key)

        if not _current_ls:
            logging.warning("Current '%s' list is empty, nothing to strip" % data_key)
            return

        args_ls = list(filter(lambda x: x in _current_ls, args_ls))

        logging.debug("Current %s: '%s'" % (data_key, _current_ls))
        _ls_flt = deepcopy(args_ls)

        if (add_value):
            _ls_flt.append(add_value)

        _ls_to_remove = list(filter(lambda x: x not in _ls_flt, _current_ls))

        if not _ls_to_remove:
            logging.debug("Nothing to remove in '%s'" % data_key)
            return

        logging.debug("'%s' to remove: '%s'" % (data_key, _ls_to_remove))

        for _cs_field in self._checksums_fields:
            logging.debug("Stripping '%s' from field '%s'" % (data_key, _cs_field))

            if not self._data.get(_cs_field):
                logging.debug("No checksum of type '%s' in '%s' - skipping" % (_cs_field, self._local))
                continue

            for _parm in _ls_to_remove:
                _rg = re.compile(regexp_filter % _parm)
                logging.debug("Removing files for %s '%s'" % (data_key, _parm))
                _records_to_remove = list(filter(lambda x: _rg.search(x.get("Filename")), self._data.get(_cs_field)))

                for _record in _records_to_remove:
                    logging.debug("Removing record for '%s' from '%s'" % (_record.get("Filename"), _cs_field))
                    self._data[_cs_field].remove(_record)

        self._data[data_key] = args_ls
        self.close()
        self.write()

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
        self._message_start = '-----BEGIN PGP SIGNED MESSAGE-----'
        self._signature_start = '-----BEGIN PGP SIGNATURE-----'
        self._signature_end = '-----END PGP SIGNATURE-----'
        self._signature = None

    def get_signature(self):
        return self._signature

    def open(self, mode="rt"):
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
                    _pgp_start = _line.startswith(self._message_start)

                    if not _pgp_start:
                        continue

                    while True: 
                        _line = _lfl.readline()

                        if not _line:
                            break

                        _line_t = _line.strip()

                        if not _line_t:
                            continue

                        if any([    _line_t.startswith('Hash:'),
                                    _line_t.startswith('Comment:')]):
                            # we do not need headers but save them for future use
                            continue

                        break

                if not _line:
                    break

                _pgp_end = _line.startswith(self._signature_start)

                if _pgp_end:
                    self._signature = ""
                    while True:
                        _line = _lfl.readline()

                        if _line.startswith(self._signature_end):
                            break

                        logging.debug("Adding signature line: '%s'" % _line)
                        self._signature += _line
                    break

                self._fd.write(_line)

            if not _pgp_start:
                logging.debug("InRelease file without PGP signature - opening as general Release")
                self._fd.seek(0, 0)
                _lfl.seek(0, 0)
                self._fd.write(_lfl.read())

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

    def write_signature_footer(self, fd, signature):
        """
        Write GPG signature
        """
        if not signature.startswith(self._signature_start):
            fd.write(self._signature_start)
            fd.write('\n')

        if all([    not signature.startswith('Version: '), 
                    not signature.startswith('Comment: '), 
                    not signature.startswith('\n')]):
            fd.write('\n')

        fd.write(signature)

        if all([    not signature.endswith(self._signature_end), 
                    not signature.endswith(self._signature_end + '\n')]):
            fd.write(self._signature_end)

    def write_signature_header(self, fd):
        """
        Write GPG signature footer
        """
        # no need since signature is in separate file
        fd.write(self._message_start)
        logging.warning("Using hardcoded Hash: SHA512, this may conflict with real one used")
        fd.write('\nHash: SHA512\n\n')
        fd.flush()
