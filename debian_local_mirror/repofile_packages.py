import gzip
import bz2
import lzma

import os
import logging
import posixpath
from copy import deepcopy
from packaging import version
from tempfile import NamedTemporaryFile

from .repofile import RepoFile
from .repofile_checksum import RepoFileWithCheckSum
from .metadata_parser import DebianMetaParser, FormatError

class RepoFilePackages(RepoFile, DebianMetaParser):
    """
    Specific Packages file processor
    """

    def __init__(self, remote, local, sub, checksums=None, extensions=[".gz", ".xz", ".bz2", ".lzma"]):
        self._data = None
        self._list_fields = list()
        self._checksums = checksums
        super().__init__(
                remote = remote,
                local = local,
                sub = sub,
                extensions = extensions,
                absent_ok = True)

    def unpack_if_needed(self):
        """
        Do an unpack no-extension version if its checksum is given
        """

        if not self._checksums:
            logging.debug("Unpacking is not necessary - no checksums")
            return

        if '' not in self._ext:
            logging.debug("Unpacking is not necessary - no empty version in checksums")
            return

        if os.path.exists(self._local):
            logging.debug("Unpacking is not necessary - '%s' exists" % self._local)
            return

        self.__open()
        # path should exist this time
        _fd = open(self._local, mode='wt')
        _fd.write(self._fd.read())
        _fd.close()
        self.close()

    def _check_checksums(self):
        """
        Try to download all possible file versions with checksums specified
        """
        for _cs_ext in self._checksums.keys():
            logging.debug("Checking extension '%s'" % _cs_ext)
            _sub = deepcopy(self._sub)
            _sub[-1] = _sub[-1] + _cs_ext
            _cs = deepcopy(self._checksums.get(_cs_ext))
            _cs['sub'] = _sub

            _fl = RepoFileWithCheckSum(
                    remote=self._base_remote,
                    local=self._base_local,
                    fdict=_cs)

            if not _fl.check_before():
                return False

        return True

    def check_before(self):
        """
        Override base class.
        Returns True if any of file (with any of possible extension) exists
        """
        if self._checksums:
            return self._check_checksums()

        for _ext in self._ext:
            _fullpth = self._local + _ext;

            if os.path.exists(_fullpth):
                return True

        if self._absent_ok:
            return False

        raise FileNotFoundError(self._local)

    def check_after(self):
        """
        Override base class method.
        """
        return self.check_before()

    def __open(self, mode="rt", ext=None):
        """
        Open file - background version.
        Check the extension and unpack if needed.
        """
        if ext is None:
            ext = self._ext

        if isinstance(ext, str):
            ext = [ext]

        for _ext in ext:
            _fullpth = self._local + _ext
            logging.debug("Try to open '%s'" % _fullpth)

            if not os.path.exists(_fullpth) and 'w' not in mode:
                logging.debug("Not found: '%s'" % _fullpth)
                continue

            if _ext == "":
                self._fd = open(_fullpth, mode=mode)
            elif _ext == ".gz":
                self._fd = gzip.open(_fullpth, mode=mode)
            elif _ext == ".bz2":
                self._fd = bz2.open(_fullpth, mode=mode)
            elif _ext in [".xz", ".lzma"]:
                self._fd = lzma.open(_fullpth, mode=mode)

            if self._fd:
                break

        if not self._fd:
            raise NotImplementedError("Can not open %s" % self._local)

    def open(self, mode='rt'):
        """
        Open file.
        Check the extension and unpack if needed.
        """
        self.close()
        self._data = None
        self.__open(mode=mode)
        self._data = self._parse()

    def _parse(self):
        """
        Some additional checks to default 'parse'
        """
        _data = self.parse()

        # may be file is empty, so 'parse' will return a dictionary
        if not isinstance(_data, dict):
            logging.debug("Parsed data is not dictionary: '%s'" % type(_data))
            return _data

        _result = list()

        if _data and 'Filename' in _data.keys():
            # at least Filename is necessary for correct data
            _result.append(_data)

        logging.debug("Parsed data has been converted to list")
        return _result

    def get_subfiles(self):
        """
        Return files dictionary
        """

        if not isinstance(self._data, list):
            raise FormatError(self._remote, "Wrong format - parse result should be a list, but %s found" %
                    type(self._data))

        _result = list()

        for _fld in self._data:

            if not isinstance(_fld, dict):
                raise FormatError(self._remote, "Something wrong: list contains non-dictionary: '%s'. Bug?" % type(_fld))

            if "sub" not in _fld.keys():
                _fld["sub"] = _fld.get("Filename").split(posixpath.sep)
                logging.debug("Adding %s as subpath" % posixpath.sep.join(_fld["sub"]))

            _result.append(_fld)

        logging.debug("Returning list of '%d' files" % len(_result))
        return _result

    def strip_versions(self, versions):
        """
        Strip all packages versios
        :param versions: latest versions to leave
        :type versions: int
        """

        if not isinstance(versions, int):
            raise TypeError("Versions is not a number")

        if versions <= 0:
            raise ValueError("Illegal versions value: %d" % versions)

        self.open()
        logging.debug("Number of packages before stripping: %d" % len(self._data))
        _packages = list(set(list(map(lambda x: x.get("Package"), self._data))))

        for _package in _packages:
            logging.debug("Stripping package: '%s'" % _package)
            _all_package_records = list(filter(lambda x: x.get("Package") == _package, self._data))
            logging.debug("Type of _all_package_records: '%s'" % type(_all_package_records))
            _versions = list(map(lambda x: x.get("Version"), _all_package_records))
            logging.debug("Versions in source: '%s'" % _versions)
            _versions = list(map(lambda x: version.parse(x), _versions))
            _versions.sort(reverse=True)
            _versions = _versions[:versions]
            _versions = list(map(lambda x: str(x), _versions))
            logging.debug("Versions to leave: '%s'" % _versions)
            self._data = list(filter(lambda x: x.get("Package") != _package or 
                        (x.get("Package") == _package and x.get("Version")) in _versions, self._data))

        logging.debug("Number of packages after stripping: %d" % len(self._data))
        self.close()
        self.write()

    def write(self):
        """
        Save changed data to all local files
        """
        # write first to temporary file, then copy everything in by-extension mode
        _tmpf = NamedTemporaryFile(mode='w+t')
        logging.debug("Writing temporary file to '%s'" % _tmpf.name)
        self.unparse_and_write(self._data, _tmpf)

        for _ext in self._ext:
            self.close()
            self.__open(mode='wt', ext=_ext)
            logging.debug("Writing ext: '%s'" % _ext)
            _tmpf.seek(0, 0)
            self._fd.write(_tmpf.read())
            self.close()

        _tmpf.close()

