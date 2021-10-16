#!/usr/bin/env python3

import gpg
import tempfile
import logging
import os

class GPGSigner(object):
    def __init__(self, keyfile, passphrase):
        """
        Main signer initialization
        :param keyfile: path to file with private key
        :type keyfile: str
        :param passphrase: passphrase for a key
        :type passphrase: str
        """
        if not keyfile:
            raise ValueError("Private GPG key file is not specified")

        if not passphrase:
            raise ValueError("Passphrase for GPG privat key is not specified")

        self._keyfile = os.path.abspath(keyfile)
        self._passphrase = passphrase
        self._gpg_home = tempfile.TemporaryDirectory(prefix="debian_local_mirror_", suffix="_gpg")
        self._key_fpr = None
        logging.debug("Initializing GPG with key '%s' in '%s'" % (self._keyfile, self._gpg_home.name))
        self._gpg_context = gpg.Context(
                armor=True,
                textmode=True,
                offline=True,
                pinentry_mode=gpg.constants.PINENTRY_MODE_LOOPBACK,
                home_dir=self._gpg_home.name)

        self._import_key()
        self._set_signer()

    def _import_key(self):
        """
        Do try to import privat key to use for signing
        """

        if not self._gpg_context:
            raise ValueError("GPG context has not been created yet")

        logging.debug("Importing key: '%s'" % self._keyfile)

        with open(self._keyfile, mode='rb') as _key_in:
            _import_result = self._gpg_context.key_import(_key_in.read())

        if type(_import_result) != gpg.results.ImportResult:
            raise TypeError("Importing key failed with unknown error: %s" % _import_result)

        logging.debug("Key secret reads: '%d'" % _import_result.secret_read)
        logging.debug("Key secret imports: '%d'" % _import_result.secret_imported)

        if _import_result.secret_read != 1 or _import_result.secret_imported != 1:
            raise ValueError("'%s' seems to be wrong secret key" % _self._keyfile)

        for _import in _import_result.imports:
            _fpr = _import.fpr

            if _fpr == self._key_fpr:
                continue

            if self._key_fpr and self._key_fpr != _fpr:
                raise ValueError("'%s' seems contain more then one secret key" % self._keyfile)

            if _import.result != gpg.errors.NO_ERROR:
                logging.error("'%s' import error, code: '%d'" % (self._keyfile, _import.result))
                continue

            logging.info("Found key fingerprint: '%s'" % _fpr)
            self._key_fpr = _fpr

    def _set_signer(self):
        """
        Set context signers
        """
        if not self._gpg_context:
            raise ValueError("GPG context has not been created yet")

        if not self._key_fpr:
            raise ValueError("GPG private key has not been imported yet")

        self._gpg_context.signers = [self._gpg_context.get_key(fpr=self._key_fpr, secret=True)]

    def _passphrase_cb(self, hint, desc, prev_bad, hook=None):
        """
        A general passphrase callback required to enter key passphrase while signing
        """
        return self._passphrase

    def sign_file(self, file_path, signature_output=None):
        """
        Sign the file
        :param file_path: path to a file to be signed
        :type file_path: str
        :param signature_output: path to a file for signature
        :type signature_output: str
        """
        logging.debug("Try to sign a file '%s'" % file_path)
        _sign_mode = gpg.constants.SIG_MODE_CLEAR
        _rslt_output = file_path

        if signature_output:
            logging.debug("Detached mode set")
            _sign_mode = gpg.constants.SIG_MODE_DETACH
            _rslt_output = signature_output

        logging.debug("Reslut signature will be written to: '%s'" % _rslt_output)

        self._gpg_context.set_passphrase_cb(self._passphrase_cb)

        with open(file_path, mode='rb') as _fl_in:
            _signed_data, _result = self._gpg_context.sign(_fl_in.read(), mode=_sign_mode)

        if len(_result.signatures) != 1:
            raise ValueError(
                    "File should be signed with one key exactly, but '%d' found" % len(_result.signatures))

        _fpr = _result.signatures.pop()
        _fpr = _fpr.fpr
        logging.debug("Signed with fingerprint '%s'" % _fpr)

        if _fpr != self._key_fpr:
            raise ValueError("Different fingerprings: signed with '%s', bug signer: '%s'" %
                    (_fpr, self._key_fpr))

        with open(_rslt_output, mode='wb') as _fl_out:
            _fl_out.write(_signed_data)
