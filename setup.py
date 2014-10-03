# -*- coding: utf-8 -*-
import os.path
import re
import warnings

try:
    from setuptools import setup, find_packages
except ImportError:
    from distribute_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

version = '0.0.1'

long_description = """
pkpcli is a simple shell-like software to keepass DB files.
 
It uses extensively the keepassdb module by Hans Lellelid (https://github.com/hozn/keepassdb)
"""

setup(
    name = "pkpcli", 
    version = version, 
    author = "Fabrizio Furnari", 
    author_email = "fabfur@fabfur.it",
    url = "",
    license = "GPLv3",
    description = "Simple shell client to keepass DB files",
    long_description = long_description,
    packages = ['keepassdb'],
    include_package_data=True,
    install_requires=['pycrypto>=2.6,<3.0dev'],
    use_2to3=True,
    zip_safe=False # Technically it should be fine, but there are issues w/ 2to3 
)
