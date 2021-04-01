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
        :param cfg: single mirror configuration
        :type cfg: dict
        """
        # type of cfg itself
        if not isinstance(cfg, dict):
            raise TypeError("Configuration of every mirror should be a dictionary, but %s found" % type (cfg))

        # these are required
        for _key in ["source", "destination"]:
            self._validate_value_type(cfg, _key, str)

        # these too, but value have to be list
        for _key in ["distributives", "sections"]:
            self._validate_value_type(cfg, _key, list)

        # and this one is optional, will copy all by default
        self._validate_value_type(cfg, "architectures", list, required=False)

    def _validate_value_type(self, cfg, key, value_type, required=True):
        """
        Validate key value for a cfg
        :param cfg: cfg to validate key for
        :type cfg: dict
        :param key: key in cfg dict
        :type key: str
        :param value_type: type of value expected for cfg[key]
        :type value_type: type
        :param required: is this key required or not
        :type reuqired: boolean
        """
        # if key is required then raise an error
        if key not in cfg.keys():
            if required: 
                raise KeyAbsenceError(key)

            logging.debug("Key '%s' not found in one of configs. Skipping sice not required" % key)
            return

        if not isinstance(cfg.get(key), value_type):
            raise TypeError("'%s' value is to be '%s', but '%s' found" % (key, value_type, type(cfg.get(key))))

        if not (value_type == list):
            return

        for _v in cfg.get(key):
            if isinstance(_v, str):
                continue

            raise TypeError("'%s' value is to be list of strings, but one of members has type '%s'" %
                (key, type(_v)))

    def get_mirrors(self):
        """
        Return list of mirror configurations
        """
        return self._cfg
            