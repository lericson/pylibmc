import os
import sys
from distutils.core import setup, Extension

# --with-zlib: use zlib for compressing and decompressing
# --without-zlib: ^ negated
# --with-zlib=<dir>: path to zlib if needed
# --with-libmemcached=<dir>: path to libmemcached package if needed

use_zlib = True
pkgdirs = []  # incdirs and libdirs get these
libs = ["memcached"]
defs = []
incdirs = []
libdirs = []

# Hack up sys.argv, yay
unprocessed = []
for arg in sys.argv[1:]:
    if arg == "--with-zlib":
        use_zlib = True
        continue
    elif arg == "--without-zlib":
        use_zlib = False
        continue
    elif "=" in arg:
        if arg.startswith("--with-libmemcached=") or \
           arg.startswith("--with-zlib="):
            pkgdirs.append(arg.split("=", 1)[1])
            continue
    unprocessed.append(arg)
sys.argv[1:] = unprocessed

for pkgdir in pkgdirs:
    incdirs.append(os.path.join(pkgdir, "include"))
    libdirs.append(os.path.join(pkgdir, "lib"))

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
