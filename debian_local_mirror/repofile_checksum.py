from .repofile import RepoFile
import os
import logging
import hashlib

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
        self._set_checksums_fields()

    def _check_create_links(self):
        """
        Do create all links for the file
        """
        # if no base file present - return false
        # (or True if _absent_OK)
        self._links = list()

        if not os.path.exists(self._local):
            return self._absent_ok

        # if no "by-hash" given - no links needed
        if "by-hash" not in self._fdict:
            return True

        for _link_list in self._fdict.get("by-hash"):
            _link_path = os.path.join(self._base_local, os.path.sep.join(_link_list))
            logging.debug("Link components: '%s', '%s'" % (self._base_local, os.path.sep.join(_link_list)))
            logging.debug("Checking symlink: '%s' ==> '%s'" % (_link_path, self._local))
            self._check_create_local_path(_link_path)

            if os.path.exists(_link_path) or os.path.islink(_link_path):
                os.remove(_link_path)

            os.symlink(os.path.relpath(self._local, os.path.dirname(_link_path)), _link_path)
            self._links.append(_link_path)

        return True

    def _calculate_checksum(self, cs_type):
        """
        Calculate a checksum of a type given
        File is to be opened before calling this routine
        :param cs_type: type of checksum
        :type cs_type: str
        """
        self._fd.seek(0, 0)
        
        _hashobj = None
        if cs_type == "md5sum":
            _hashobj = hashlib.md5()
        elif cs_type == "sha1":
            _hashobj = hashlib.sha1()
        elif cs_type == "sha256":
            _hashobj = hashlib.sha256()
        
        if not _hashobj:
            raise ValueError("Checksum of type '%s' is not (yet?) supported" % cs_type)

        while True:
            _chunk = self._fd.read(1 * 1024 * 1024) # read in 1M chunks, 16M was too much

            if not _chunk: 
                break

            _hashobj.update(_chunk)

        return _hashobj.hexdigest()

    def _compare_checksums(self):
        """
        Compare all checksums given
        """
        if not os.path.exists(self._local):
            logging.debug("File '%s' does not exist, checksum verification failed" % self._local)
            return False

        _opened = bool(self._fd)

        if not _opened:
            self.open(mode="rb")

        for _field in self._checksums_fields:
            if _field not in self._fdict:
                logging.debug("Checksum type %s not found for '%s'" % (_field, self._local))
                continue

            _type = _field.lower()
            _hash = self._fdict.get(_field)
            
            if not _hash:
                if not _opened:
                    self.close()

                raise ValueError("Hash type '%s' is listed in file data but not given for '%s'" %
                        (_field, self._local))

            if _hash != self._calculate_checksum(_type):
                logging.debug("Hash of type '%s' comparison failed for '%s'" %
                        (_field, self._local))

                if not _opened:
                    self.close()

                return False

        if not _opened:
            self.close()

        logging.debug("All hashes match for '%s'" % self._local)

        return True

    def check_before(self):
        """
        Override to see if local file is OK
        """
        return self._check_create_links() and self._compare_checksums()

    def check_after(self):
        """
        Override to see if local file is OK
        """
        return super().check_after() and self.check_before()

    def get_local_paths(self):
        """
        Override to create full list with links
        """
        return super().get_local_paths() + self._links

