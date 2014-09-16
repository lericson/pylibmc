#!/usr/bin/env python
# coding: utf-8

import platform

if platform.python_implementation() == "PyPy":
    import pypylibmc as _pylibmc
else:
    import _pylibmc