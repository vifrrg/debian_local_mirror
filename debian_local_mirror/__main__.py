#! /usr/bin/env python3

import argparse
import logging
import os
from .mirror_processor import MirrorProcessor

_ap = argparse.ArgumentParser(description="Create partail local debian mirror")
_ap.add_argument("--log-level", dest="log_level", type=int, default=50)
_ap.add_argument("-c", "--config", dest="config_fl", required=True)
_ag = _ap.parse_args()
logging.basicConfig(
    format="%(asctime)s: %(levelname)s: %(filename)s: %(funcName)s: %(lineno)d: %(message)s", 
    level=_ag.log_level)
_cfg = os.path.abspath(_ag.config_fl)
logging.info("Log level is set to %d" % _ag.log_level)
logging.info("Loading configuration: '%s'" % _cfg)

MirrorProcessor(config=_cfg).process()
