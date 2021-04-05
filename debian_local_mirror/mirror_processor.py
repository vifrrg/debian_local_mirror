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
        self._files = NamedTemporaryFile(mode = 'w+')
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
        for _dist in mirror.get("distributives"):
            self._process_single_distributive(mirror, _dist)

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
        logging.debug("Processin release file from '%s'" % ':'.join(rlfl.get_local_paths()))
        rlfl.open()

        # loop by-files from Release one
        _subfiles = rlfl.get_subfiles()

        if not _subfiles:
            # no files listed in this exact Release
            rlfl.close()
            return

        for _fl in _subfiles.keys():
            logging.info("Processing file: %s" % _fl)
            _subfl = RepoFileWithChecksum(
                local=mirror.get("destination"),
                remote=mirror.get("source"),
                fdict=_subfiles.get(_fl))

            _subfl.synchronize()

        rlfl.close()

