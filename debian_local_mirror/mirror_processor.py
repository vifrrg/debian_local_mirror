import logging
from .mirror_config import MirrorsConfig
from .repofile_release import RepoFileRelease, RepoFileInRelease
from .repofile_checksum import RepoFileWithCheckSum
from tempfile import NamedTemporaryFile

class MirrorError(Exception):
    def __init__(self, remote, local, message):
        super().__init__("Mirroring from '%s' to '%s' failed: %s" % (remote, local, message))

class MirrorProcessor(object):
    """
    The main processor class
    """
    def __init__(self, config):
        """
        Main process initialzation
        :param config: path to JSON configuration file
        :type config: str
        """
        logging.debug("Config path provided: '%s'" % config)
        self._config = MirrorsConfig(config)
        self._files = None
        logging.debug("Temporary files list: %s" % self._files.name)

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

        # loop by distributives and architectures
        self._files = NamedTemporaryFile(mode = 'w+')
        for _dist in mirror.get("distributives"):
            self._process_single_distributive(mirror, _dist)

        self._remove_trash(os.path.abspath(mirror.get("destination")))

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

        if not _rlfl:
            raise MirrorError(mirror.get("source"), mirror.get("destination"), 
            "Release files not found for distributive '%s'" % distr)

        self._process_release(mirror, _rlfl)

        _archs = mirror.get("architectures")

        if "all" not in _archs and not _rlfl.skip_all_architecture():
            logging.debug("Pseudo-architecture 'all' has been added to the list forcibly")
            _archs.append("all")

        for _section in mirror.get("sections"):
            for _arch in _archs:
                logging.info("Processing section '%s', architecture '%s'" % (_section, _arch))
                self._process_section_architecture(mirror, _section, _arch)
        
    def _get_release_file(self, mirror, distr):
        """
        Download Release / InRelease files from remote to local
        Perhaps both, but at least one
        :param mirror: mirror configuration
        :type mirror: dict
        :param distr: distributive name
        :type distr: str
        """
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

            if not _rlfl:
                _rlfl = _tmprlfl

            self._files.write('\n'.join(_rlfl.get_local_paths()))

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
                self._files.write('\n'.join(_subfl.get_local_paths()))

        rlfl.close()

    def _remove_trash(self, root):
        """
        Housekeeping for single mirror
        :param root: path to root folder to process
        :type root: str
        """
        return

    def _process_section_architecture(self, mirror, section, arch):
        """
        Get parse packages index and synchronize all packages
        :param mirror: full mirror configuration
        :type mirror: dict
        :param section: secton
        :type section: str
        :param arch: architecture
        :type arch: str
        """
        return

