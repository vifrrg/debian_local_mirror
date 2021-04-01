#!/usr/bin/env python3

from setuptools import setup

setup(
    author = "Aleksey Knyazev",
    author_email = "ctj_yebbs@inbox.ru",
    description = "Simple debian local mirroring",
    license = "GPL",
    name = "debian_local_mirror",
    packages = ["debian_local_mirror"],
    version = "0.0.0",
    python_requires = ">=3.6.0",
    install_requires = [
        "requests"
    ]
)
