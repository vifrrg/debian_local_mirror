import json
import logging

class KeyAbsenceError(Exception):
    def __init__(self, key):
        super().__init__("Key '%s' is required, but it is absent" % key)

class MirrorsConfig(object):
    """
    Class for mirros configuration
    """
    def __init__(self, path):
        """
        Initialization.
        :param path: path to local mirroring configuration JSON
        :type path: str
        """

        with open(path) as _fl_in:
            self._cfg = json.load(_fl_in)

        self._validate()

    def _validate(self):
        """
        Validates self._cfg
        """
        if not isinstance(self._cfg, list):
            raise TypeError("Configuration should be a list, but %s found" % type(self._cfg))

        for _cfg in self._cfg:
            self._validate_cfg(_cfg)

    def _validate_cfg(self, cfg):
        """
        Validates single mirror cfg
        """
        # those are required
        if not isinstance(cfg, dict):
            raise TypeError("Configuration of every mirror should be a dictionary, but %s found" % type (cfg))

        for _key in ["source", "destination"]:
            if _key not in cfg.keys():
                raise KeyAbsenceError(_key)

        #"distributive" : "stable",
        #"sections" : [ "main", "contrib", "non-free", "anything_else" ],
        #"architectures"
