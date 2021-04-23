# DEBIAN LOCAL MIRROR

This is a python module designed to create partial local mirrors of Debian-like repositories.

## INSTALLATION
From source:

    $   python setup.py install

Module is not (yet?) avaiable via *pip*.

## HOW TO USE
No executable script is provided with a package. It may be confused about Python version to use. So run as module only is available:

    $   python -m debian_local_mirror

Python version desirable may be specified directly by this way:

    $   python3.5 -m debian_local_mirror

Short help on command line parameters is available with traditional --help switch: 

    $   python -m debian_local_mirror --help

The only parameter required is a configuration file:

    $   python -m debian_local_mirror -c config.json


## CONFIGURATION

**JSON** format is used. Here is an example:
```
[
    {   "source" : "some.debian.server/path",
        "destination" : "/some/local/folder",
        "distributives" : [ "stable", "oldstable", "anything_else" ],
        "sections" : [ "main", "contrib", "non-free", "anything_else" ],
        "architectures" : ["amd64", "i386", "anything_else" ]
    }
]
```
**WARNINGS**: 
- all values are case-sensitive
- relative path in "destination" section may be used, but will be considered relative to *config* path, **not to corrent directory**

## CREATING SOURCES LIST FOR APT

    $   python -m debian_local_mirror.sources_list -c config.json -o sources.list

List with *file:///* URLs will be created - is useful for local machine.
It is hard to predict FQDN or IP address of a machine and web-server settings to generate *sources.list* for network usage, but this may be done in the future.
