import os
from distutils.core import setup, Extension

use_zlib = True  # TODO Configurable somehow?

libs = ["memcached"]
defs = []
incdirs = []
libdirs = []

if "LIBMEMCACHED_DIR" in os.environ:
    libdir = os.path.normpath(os.environ["LIBMEMCACHED_DIR"])
    incdirs.append(os.path.join(libdir, "include"))
    libdirs.append(os.path.join(libdir, "lib"))

if use_zlib:
    libs.append("z")
    defs.append(("USE_ZLIB", None))
 
pylibmc_ext = Extension("_pylibmc", ["_pylibmcmodule.c"],
                        libraries=libs, include_dirs=incdirs,
                        library_dirs=libdirs, define_macros=defs)

readme_text = open("README.rst", "U").read()
version = open("pylibmc-version.h", "U").read().strip().split("\"")[1]

setup(name="pylibmc", version=version,
      url="http://lericson.blogg.se/code/category/pylibmc.html",
      author="Ludvig Ericson", author_email="ludvig@lericson.se",
      license="3-clause BSD <http://www.opensource.org/licenses/bsd-license.php>",
      description="libmemcached wrapper", long_description=readme_text,
      ext_modules=[pylibmc_ext], py_modules=["pylibmc"])
