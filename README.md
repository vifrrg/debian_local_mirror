# DEBIAN LOCAL MIRROR

This is a python module to create partial local mirrors of Debian-like repositories.

## INSTALLATION
From source:

    $   python setup.py install

Module is not (yet?) avaiable via *pip*.

## HOW TO USE
Since general executable script may be confused about python version, I prefere not to create it and run any python software as module:

    $   python -m debian_local_mirror

Python version desirable may be specified directly by this way:

    $   python3.5 -m debian_local_mirror

Short help on command line keys is available with traditional --help switch: 

    $   python -m debian_local_mirror --help

The only parameter required is a configuration file:

    $   python -m debian_local_mirror -c config.json


## CONFIGURATION

**JSON** format is used.
