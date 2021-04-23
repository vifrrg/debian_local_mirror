#!/usr/bin/env python3

from .mirror_config import MirrorsConfig
import logging
import os
import argparse

def main():
    """
    Parse mirror configuration and write sources.list for APT
    """
    _ap = argparse.ArgumentParser(description="Convert mirror configuration to APT-suitable sources.list")
    _ap.add_argument("--log-level", dest="log_level", type=int, default=50)
    _ap.add_argument("-c", "--config", dest="config_fl", required=True)
    _ap.add_argument("-o", "--output", dest="out_fl", required=True)
    _ag = _ap.parse_args()
    _cfg = os.path.abspath(_ag.config_fl)
    _out = os.path.abspath(_ag.out_fl)

    logging.basicConfig(
        format="%(asctime)s: %(levelname)s: %(filename)s: %(funcName)s: %(lineno)d: %(message)s", 
        level=_ag.log_level)

    logging.info("Log level is set to %d" % _ag.log_level)
    logging.info("Loading configuration: '%s'" % _cfg)
    logging.info("Sources list will be written to: '%s'" % _out)
    
    _cfg = MirrorsConfig(_cfg)

    with open(_out, 'w') as _fl_out:
        _fl_out.write('\n'.join(_cfg.make_sources_list()))
        _fl_out.write('\n')

if __name__ == "__main__":
    main()
