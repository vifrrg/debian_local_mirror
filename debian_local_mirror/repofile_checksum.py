from .repofile import RepoFile
import os
import logging

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
            logging.debug("Checking symlink: '%s' ==> '%s'" % (_link_path, self._local))
            self._check_create_local_path(_link_path)

            if os.path.exists(_link_path) or os.path.islink(_link_path):
                os.remove(_link_path)

            os.symlink(os.path.relpath(self._local, os.path.dirname(_link_path)), _link_path)
            self._links.append(_link_path)

        return True

    def _compare_checksums(self):
        """
        Compare all checksums given
        """
        return False

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

