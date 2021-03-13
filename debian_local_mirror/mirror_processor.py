import logging

class MirrorProcessor(object):
    def __init__(self, config):
        """
        Main process initialzation
        :param config: path to JSON configuration file
        :type config: str
        """
        logging.debug("Config path provided: '%s'" % config)
        self._config = config

    def process(self):
        """
        The main mirroring process
        """
        return
