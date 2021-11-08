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
    {   "enabled": true,
        "source" : "some.debian.server/path",
        "destination" : "/some/local/folder",
        "distributives" : [ "stable", "oldstable", "anything_else" ],
        "sections" : [ "main", "contrib", "non-free", "anything_else" ],
        "architectures" : ["amd64", "i386", "anything_else" ]
    }
]
```
**WARNINGS**: 
- all values are case-sensitive
- relative path in "destination" section may be used, but will be considered relative to *config* path, **not to current directory**

## RESIGN AND REMOVE-VALID-UNTIL FEATURES

You may use Your own *GPG* key to re-sign *Release* and *InRelease* files taken from origin. Use options:
```
    --resign-key path_to_private_key --key-passphrase passphrase_for_key
```
You **must** specify these two options correctly to use `--remove-valid-until` featrue. 
Latter removes *Valid-Until* header from *Release* and *InRelease* files - to get rid of outdating Your local mirror. **Do not use this feature unless You know what for.**

To use any of *GPG* - related features You **have to** install *Python* interface to *libgpgme*. It is not specified in *Dependencies* because it is not correctly available via **pip** usually. But packaged and provided by Your *Linux* distributive vendor.

## CREATING SOURCES LIST FOR APT

    $   python -m debian_local_mirror.sources_list -c config.json -o sources.list

List with *file:///* URLs will be created - is useful for local machine.
It is hard to predict FQDN or IP address of a machine and web-server settings to generate *sources.list* for network usage, but this may be done in the future.

## TODO:
- Delete empty directories after cleanup
- Add package filter support to the configuration
- Add *LVO* (*latest version only*) mode support to the configuration
- Add full *GPG* signature verification for sources
- Add more secure passphrase input for *GPG* key (**any ideas? STDIN?**).
