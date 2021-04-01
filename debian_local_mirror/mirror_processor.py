import logging
from .mirror_config import MirrorsConfig
from .repofile_release import RepoFileRelease, RepoFileInRelease

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
        _rlfl = RepoFileRelease(
                local=mirror.get("destination"),
                remote=mirror.get("source"),
                sub=["dists", distr, "Release"])
        _irlfl = RepoFileInRelease(
                local=mirror.get("destination"),
                remote=mirror.get("source"),
                sub=["dists", distr, "InRelease"])

        _rlfl.synchronize()
        _irlfl.synchronize()
        _rlfl.open()
