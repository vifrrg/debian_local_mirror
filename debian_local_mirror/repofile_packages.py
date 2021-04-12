import gzip
import bz2
import lzma

import os
import logging
import posixpath

from .repofile import RepoFile
from .metadata_parser import DebianMetaParser, FormatError

class RepoFilePackages(RepoFile, DebianMetaParser):
    """
    Specific Packages file processor
    """

    def __init__(self, remote, local, sub):
        self._data = None
        self._list_fields = list()
        super().__init__(
                remote = remote,
                local = local,
                sub = sub,
                extensions = [".gz", ".xz", ".bz2", ".lzma"],
                absent_ok = False)

    def check_before(self):
        """
        Override base class.
        Returns True if any of file (with any of possible extension) exists
        """
        for _ext in self._ext:
            _fullpth = self._local + _ext;

            if os.path.exists(_fullpth):
                return True

        raise FileNotFoundError(self._local)

    def check_after(self):
        """
        Override base class method.
        """
        return self.check_before()

    def open(self, mode="rt"):
        """
        Open file.
        Check the extension and unpack if needed.
        """
        self.close()
        self._data = None

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

        if not self._fd:
            raise NotImplementedError("Can not open %s" % self._local)
        
        self._data = self.parse()

    def get_subfiles(self):
        """
        Return files dictionary
        """
        if not isinstance(self._data, list):
            raise FormatError(self._remote, "Wrong format - parse result should be a list, but %s found" %
                    type(data))

        _result = list()

        for _fld in self._data:
            if "sub" not in _fld.keys():
                _fld["sub"] = _fld.get("Filename").split(posixpath.sep)
                logging.debug("Adding %s as subpath" % posixpath.sep.join(_fld["sub"]))

            _result.append(_fld)

        return _result

