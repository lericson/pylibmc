"""`pylibmc` is a Python wrapper around the accompanying C Python extension
`_pylibmc`, which is a wrapper around `libmemcached` from TangentOrg.

You have to install `libmemcached` separately, and have your compiler and
linker find the include files and libraries.

With `libmemcached` installed and this package set up, the following basic
usage example should work::

    >>> import pylibmc
    >>> mc = pylibmc.Client(["127.0.0.1:11211"])
    >>> mc.set("foo", "Hello world!")
    True
    >>> mc.get("foo")
    'Hello world!'

The API is pretty much `python-memcached`. Some parts of `libmemcached` aren't
exposed yet. I think.

Behaviors
=========

`libmemcached` has ways of telling it how to behave. You'll have to refer to
its documentation on what the different behaviors do.

To change behaviors, quite simply::

    >>> mc.behaviors["hash"] = "fnv1a_32"

Comparison to other libraries
=============================

Why use `pylibmc`? Because it's fast.

http://lericson.blogg.se/code/2008/november/pylibmc-051.html

Change Log
==========

New in version 0.6
------------------

Added compatibility with `libmemcached` 0.26, WRT error return codes.

Added `flush_all` and `disconnect_all` methods.

Now using the latest pickling protocol.

New in version 0.5
------------------

Fixed lots of memory leaks, and added support for `libmemcached` 0.23.

Also made the code tighter in terms of compiler pendatics.

New in version 0.4
------------------

Renamed the C module to `_pylibmc`, and added lots of `libmemcached` constants
to it, as well as implemented behaviors.
"""

import os
from distutils.core import setup, Extension

incdirs = []
libdirs = []

if "LIBMEMCACHED_DIR" in os.environ:
    libdir = os.path.normpath(os.environ["LIBMEMCACHED_DIR"])
    incdirs.append(os.path.join(libdir, "include"))
    libdirs.append(os.path.join(libdir, "lib"))

pylibmc_ext = Extension("_pylibmc", ["_pylibmcmodule.c"],
                        libraries=["memcached"],
                        include_dirs=incdirs, library_dirs=libdirs)

setup(name="pylibmc", version="0.6.1",
      url="http://lericson.blogg.se/code/category/pylibmc.html",
      author="Ludvig Ericson", author_email="ludvig.ericson@gmail.com",
      license="3-clause BSD <http://www.opensource.org/licenses/bsd-license.php>",
      description="libmemcached wrapper", long_description=__doc__,
      ext_modules=[pylibmc_ext], py_modules=["pylibmc"])
