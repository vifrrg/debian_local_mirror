import logging
from .mirror_config import MirrorsConfig

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
        return
