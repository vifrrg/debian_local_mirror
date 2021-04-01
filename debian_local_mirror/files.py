import logging
import os
import posixpath
import requests
import shutil

class RepoFile(object):
    def __init__(self, remote, local, sub, absent_ok = False):
        """
        Synchronization of single file - basics
        :param remote: URI to exact remote
        :type remote: str
        :param local: Local path
        :type local: str
        """
        if not sub:
            raise ValueError("Subpath is required")
        self._remote = posixpath.join(remote, posixpath.sep.join(sub))
        self._local = os.path.join(os.path.abspath(local), os.path.sep.join(sub))
        self._absent_ok = absent_ok
        logging.debug("File: '%s' ==> '%s'" % (self._remote, self._local))

    def check_create_local_path(self):
        """
        Prepare local folder for downloading
        """
        if os.path.exists(self._local):
            logging.debug("'%s' exists, preparation skipped" % self._local)
            return

        _dirpath = os.path.dirname(self._local)

        if os.path.isdir(_dirpath):
            logging.debug("'%s' exists, preparation skipped" % _dirpath)
            return

        logging.debug("Creating folder: '%s'" % _dirpath)
        os.makedirs(_dirpath)

    def check(self):
        """
        Check if remote file content is the same as local,
        to be overriden in derived classes
        """
        logging.debug("Check returns false by default")
        return False

    def synchronize(self):
        """
        Synchronize from remote
        """
        self.check_create_local_path()

        if self.check():
            logging.debug("File data is OK, no need to donwload")
            return
        
        _web = requests.Session()
        _rsp = _web.get(self._remote, stream = True)

        if (os.path.exists(self._local)):
            os.remove(self._local)

        if _rsp.status_code != 200 and self._absent_ok: #HTTP OK
            # remove local file
            logging.debug("File '%s' not found, removing local copy also" % self._remote)
            return

        logging.info("'%s' ==> '%s'" % (self._remote, self._local))
        with open(self._local, 'wb') as _fl:
            shutil.copyfileobj(_rsp.raw, _fl)
            _fl.flush()

class RepoFileRelease(RepoFile):
    pass

class RepoFileInRelease(RepoFile):
    pass
