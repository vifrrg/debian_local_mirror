import logging
from .mirror_config import MirrorsConfig
from .repofile_release import RepoFileRelease, RepoFileInRelease
from .repofile_checksum import RepoFileWithCheckSum
from .repofile_packages import RepoFilePackages
from .trash_remover import TrashRemover
from tempfile import NamedTemporaryFile, TemporaryDirectory
import os

class MirrorError(Exception):
    def __init__(self, remote, local, message):
        super().__init__("Mirroring from '%s' to '%s' failed: %s" % (remote, local, message))

class MirrorProcessor(object):
    """
    The main processor class
    """
    def __init__(self, args):
        """
        Main process initialzation
        :param args: arguments for processing
        :type config: argparse.NameSpace
        """
        self._args = args
        _cfg = os.path.abspath(self._args.config_fl)
        logging.info("Config path provided: '%s'" % _cfg)
        self._config = MirrorsConfig(_cfg)
        self._files = None
        self.__gpg_signer = None

    def process(self):
        """
        The main mirroring process
        """
        for _mirror in self._config.get_mirrors():
            self._process_single_mirror(_mirror)

    def _process_single_mirror(self, mirror):
        """
        Process single mirror record
        :param mirror: mirror configuration
        :type mirror: dict
        """

        if not mirror.get("enabled", True):
            logging.info("Mirroring '%s' is disabled" % mirror.get("source"))
            return

        logging.info("Processing mirror for '%s'" % mirror.get("source"))

        # loop by distributives and architectures
        self._files = NamedTemporaryFile(mode = 'w+')
        for _dist in mirror.get("distributives"):
            self._process_single_distributive(mirror, _dist)

        self._remove_trash(mirror.get("destination"))
        self._files.close()
        self._files = None


    def _process_single_distributive(self, mirror, distr):
        """
        Process single distirbutive record
        :param mirror: mirror configuration
        :type mirror: dict
        :param distr: distributive name
        :type distr: str
        """
        # First of all: 
        # To download packages from a repository apt would download a InRelease or Release 
        # file from the $ARCHIVE_ROOT/dists/$DISTRIBUTION directory.
        # InRelease files are signed in-line while Release files should have an accompanying Release.gpg file
        _rlfl = self._get_release_file(mirror, distr)
        self._process_release(mirror, _rlfl);
        _archs = mirror.get("architectures")

        if "all" not in _archs and not _rlfl.skip_all_architecture():
            logging.debug("Pseudo-architecture 'all' has been added to the list forcibly")
            _archs.append("all")

        for _section in mirror.get("sections"):
            for _arch in _archs:
                logging.info("Processing distr '%s', section '%s', architecture '%s'" % (distr, _section, _arch))
                self._process_section_architecture(mirror, _section, _arch, _rlfl)

    @property
    def _gpg(self):
        """
        Init GnuPG object
        """
        if self.__gpg_signer:
            return self.__gpg_signer

        logging.debug("Creating new GPG context")
        from .gpg_signer import GPGSigner
        self.__gpg_signer = GPGSigner(keyfile=self._args.resign_key, passphrase=self._args.key_passphrase)

        return self.__gpg_signer
        
    def _get_release_file(self, mirror, distr):
        """
        Download Release / InRelease files from remote to local
        Perhaps both, but at least one
        :param mirror: mirror configuration
        :type mirror: dict
        :param distr: distributive name
        :type distr: str
        """
        if mirror.get("versions") and not self._args.resign_key:
            raise MirrorError(mirror.get("source"), mirror.get("destination"), 
                    "'versions' parameter specified, but no --resign-key given")

        _rlfl = None
        _candidates = [
            RepoFileRelease(
                local=mirror.get("destination"),
                remote=mirror.get("source"),
                sub=["dists", distr, "Release"]),
            RepoFileInRelease(
                local=mirror.get("destination"),
                remote=mirror.get("source"),
                sub=["dists", distr, "InRelease"]) ]

        for _tmprlfl in _candidates:
            if not _tmprlfl.synchronize():
                continue

            if self._args.resign_key:
                if _rlfl:
                    _tmprlfl.create_from(_rlfl)
                else:
                    _tmprlfl.strip_architectures(mirror.get("architectures"))
                    _tmprlfl.strip_sections(mirror.get("sections"))

                    if mirror.get("versions"):
                        _tmprlfl.strip_packages_versions(versions=mirror.get("versions"))

                    if self._args.remove_valid_until:
                        _tmprlfl.remove_valid_until()

                    _tmprlfl.sign(self._gpg)

            if not _rlfl:
                _rlfl = _tmprlfl

            self._files.write('\n' + '\n'.join(_tmprlfl.get_local_paths()))

        if _rlfl:
            return _rlfl

        _all_packages = list()

        for _sect in mirror.get("sections"):
            for _arch in mirror.get("architectures"):
                logging.debug("Try to get Packages for section '%s', architecture '%s'" % (_sect, _arch))
                _packages = RepoFilePackages(
                        local=mirror.get("destination"),
                        remote=mirror.get("source"),
                        sub=["dists", distr, _sect, "binary-%s" % _arch, "Packages"])

                _packages.remove_from_disk()

                if not _packages.synchronize():
                    continue

                logging.info("Packages synchronization OK for '%s'-'%s'-'%s'" % (distr, _sect, _arch))

                if mirror.get("versions"):
                    _packages.strip_versions(versions=mirror.get("versions"))

                _all_packages += _packages.get_local_paths()

        if not len(_all_packages):
            raise MirrorError(mirror.get("source"), mirror.get("destination"), 
                    "All files not found for distributive '%s': Release, InRelease, Packages" % distr)

        if not self._args.resign_key:
            logging.info("InRelease creation will be skipped since no key provided for signing")
            _candidates = list(filter(lambda x: not isinstance(x, RepoFileInRelease), _candidates))

        logging.debug("Candidates left: %d" % len(_candidates))

        for _tmprlfl in _candidates:
            _tmprlfl.create(distr, mirror, _all_packages)

            if self._args.resign_key:
                _tmprlfl.sign(self._gpg)

            if not _rlfl:
                _rlfl = _tmprlfl

            self._files.write('\n' + '\n'.join(_tmprlfl.get_local_paths()))

        return _rlfl

    def _process_release(self, mirror, rlfl):
        """
        Do process single release file
        :param mirror: mirror configuration
        :type mirror: dict
        :param rlfl: Release file
        :type rlfl: RepoFileRelease
        """
        logging.debug("Processing release file from '%s'" % ':'.join(rlfl.get_local_paths()))
        rlfl.open()

        # loop by-files from Release one
        _subfiles = rlfl.get_subfiles()

        if not _subfiles:
            # no files listed in this exact Release
            rlfl.close()
            return

        for _fl in _subfiles.keys():
            logging.info("Processing file: %s" % _fl)
            _subfl = RepoFileWithCheckSum(
                local=mirror.get("destination"),
                remote=mirror.get("source"),
                fdict=_subfiles.get(_fl))

            if(_subfl.synchronize()):
                self._files.write('\n' + '\n'.join(_subfl.get_local_paths()))
                self._files.flush()

        rlfl.close()

    def _remove_trash(self, root):
        """
        Housekeeping for single mirror
        :param root: path to root folder to process
        :type root: str
        """
        logging.debug("Removing obsolete files preparation...")
        _tr = TrashRemover(self._files, root)
        _tr.remove_trash()
        self._files = _tr.get_temp()

    def _process_section_architecture(self, mirror, section, arch, rlfl):
        """
        Get parse packages index and synchronize all packages
        :param mirror: full mirror configuration
        :type mirror: dict
        :param section: secton
        :type section: str
        :param arch: architecture
        :type arch: str
        :param rlfl: release file instance
        """
        rlfl.open()
        _pkgs = rlfl.get_packages_file(section, arch)
        rlfl.close()
        _pkgs.open()
        
        for _fl in _pkgs.get_subfiles():
            logging.info("Processing file: %s" % _fl.get("Filename"))
            _subfl = RepoFileWithCheckSum(
                local=mirror.get("destination"),
                remote=mirror.get("source"),
                fdict=_fl)

            if(_subfl.synchronize()):
                self._files.write('\n' + '\n'.join(_subfl.get_local_paths()))
                self._files.flush()

        _pkgs.close()

