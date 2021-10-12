#! /usr/bin/env python3

import argparse
import logging
import os
from .mirror_processor import MirrorProcessor

_ap = argparse.ArgumentParser(description="Create partail local debian mirror")
_ap.add_argument("--log-level", dest="log_level", type=int, default=50, help="Logging level")
_ap.add_argument("-c", "--config", dest="config_fl", required=True, help="JSON mirror configuration")
_ap.add_argument("--remove-valid-until", dest="remove_valid_until", default=False, action='store_true',
        help="Remove Valid-Until limit for Release and InRelease files, resigning with GPG key is necessary")
_ap.add_argument("--resign-key", dest="resign_key", default=None, 
        help="Path to private GPG key for resigning Release and InRelease files")
_ap.add_argument("--key-passphrase", dest="key_passphrase", default=None, 
        help="Passphrase for GPG key for resigning Release and InRelease files")
_ag = _ap.parse_args()
logging.basicConfig(
    format="%(asctime)s: %(levelname)s: %(filename)s: %(funcName)s: %(lineno)d: %(message)s", 
    level=_ag.log_level)
_cfg = os.path.abspath(_ag.config_fl)
logging.info("Log level is set to %d" % _ag.log_level)
logging.info("Loading configuration: '%s'" % _cfg)

MirrorProcessor(config=_cfg).process()
