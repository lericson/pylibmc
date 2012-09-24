#!/usr/bin/env python
"""Run nosetests with build/lib.* in sys.path"""

import sys

def build_lib_dirname():
    from distutils.dist import Distribution
    from distutils.command.build import build
    build_cmd = build(Distribution({"ext_modules": True}))
    build_cmd.finalize_options()
    return build_cmd.build_lib

# Nose plugin

import logging

import nose
from nose.plugins import Plugin

logger = logging.getLogger("nose.plugins.pylibmc")

def hack_sys_path():
    lib_dirn = build_lib_dirname()
    logger.info("path to dev build: %s", lib_dirn)
    sys.path.insert(0, lib_dirn)

    import pylibmc, _pylibmc
    if hasattr(_pylibmc, "__file__"):
        logger.info("loaded _pylibmc from %s", _pylibmc.__file__)
        if not _pylibmc.__file__.startswith(lib_dirn):
            logger.warn("double-check the source path")
            logger.warn("tests are not running on the dev build!")
    else:
        logger.warn("static _pylibmc: %s", _pylibmc)

class PylibmcPlugin(Plugin):
    name = "info"
    enableOpt = "info"

    def __init__(self):
        Plugin.__init__(self)

    def begin(self):
        hack_sys_path()
        from pylibmc import build_info
        logger.info("testing %s", build_info())

if __name__ == "__main__":
    nose.main(addplugins=[PylibmcPlugin()])
