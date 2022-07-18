import gzip
import bz2
import lzma

import os
import logging
import posixpath
from copy import deepcopy

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

    def __open(self, mode="rt"):
        """
        Open file - background version.
        Check the extension and unpack if needed.
        """
        for _ext in self._ext:
            _fullpth = self._local + _ext
            logging.debug("Try to open '%s'" % _fullpth)

            if not os.path.exists(_fullpth):
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

