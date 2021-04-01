import logging
import os
import posixpath
import requests
import shutil

class HttpError(Exception):
    def __init__(self, code=0, url='', resp=None, text=''):
        self.code = code
        self.url = url
        self.resp = resp
        self.text = text

    def __str__(self):
        return self.text + ': Code ' + str(self.code) + ' ' + self.url


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

    def check_before(self):
        """
        Check if remote file content is the same as local before download,
        to be overriden in derived classes
        """
        logging.debug("Check returns false by default")
        return False

    def check_after(self):
        """
        Check if remote file content is the same as local after download,
        to be overriden in derived classes
        """
        logging.debug("Check returns true by default")
        return True

    def _download_remote(self, remote, local, absent_ok):
        """
        Do download a remote file
        :param remote: remote URL
        :type remote: str
        :param local: local path
        :type local: str
        :param absent_ok: do not raise an exception of file is absent in remote
        :type absent_ok: bool
        """
        _web = requests.Session()
        _rsp = _web.get(remote, stream = True)

        if (os.path.exists(local)):
            os.remove(local)

        if _rsp.status_code != 200:
            if absent_ok:
                # remove local file
                logging.debug("File '%s' not found, removing local copy also" % self._remote)
                return

            raise HttpError(_rsp.status_code, _rsp.url, _rsp, 'Error making request to server')

        logging.info("'%s' ==> '%s'" % (remote, local))
        with open(local, 'wb') as _fl:
            shutil.copyfileobj(_rsp.raw, _fl)
            _fl.flush()

    def synchronize(self):
        """
        Synchronize from remote
        """
        self.check_create_local_path()

        if self.check_before():
            logging.debug("File data is OK, no need to donwload")
            return

        self._download_remote(self._remote, self._local, self._absent_ok)       

        if not self.check_after():
            raise IOError("Downloading faied: '%s'" % self._remote)

class RepoFileRelease(RepoFile):
    def _check_signature(self):
        """
        Check gpg signature
        """
        return True

    def check_before(self):
        """
        Get signature file from remote and verify if local file fulfils it
        """
        if not os.path.exists(self._local):
            return False

        self._download_remote(
                remote = self._remote + ".gpg",
                local = self._local + ".gpg",
                absent_ok = False)

        return self._check_signature()

    def check_after(self):
        """
        Signature is to be downloaded already, check only
        """
        return self._check_signature()

class RepoFileInRelease(RepoFile):
    def check_after(self):
        """
        Check self-signed file after downloading
        """
        return True
