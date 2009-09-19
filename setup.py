import os
from distutils.core import setup, Extension

incdirs = []
libdirs = []

if "LIBMEMCACHED_DIR" in os.environ:
    libdir = os.path.normpath(os.environ["LIBMEMCACHED_DIR"])
    incdirs.append(os.path.join(libdir, "include"))
    libdirs.append(os.path.join(libdir, "lib"))

readme_text = open("README.rst", "U").read()
version = open("pylibmc-version.h", "U").read().strip().split("\"")[1]
 
pylibmc_ext = Extension("_pylibmc", ["_pylibmcmodule.c"],
                        libraries=["memcached"],
                        include_dirs=incdirs, library_dirs=libdirs)

setup(name="pylibmc", version=version,
      url="http://lericson.blogg.se/code/category/pylibmc.html",
      author="Ludvig Ericson", author_email="ludvig@lericson.se",
      license="3-clause BSD <http://www.opensource.org/licenses/bsd-license.php>",
      description="libmemcached wrapper", long_description=readme_text,
      ext_modules=[pylibmc_ext], py_modules=["pylibmc"])
