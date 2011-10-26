import os
import sys
from distutils.core import setup, Extension

## Command-line argument parsing

# --with-zlib: use zlib for compressing and decompressing
# --without-zlib: ^ negated
# --with-zlib=<dir>: path to zlib if needed
# --with-libmemcached=<dir>: path to libmemcached package if needed

cmd = None
use_zlib = True
pkgdirs = []  # incdirs and libdirs get these
libs = ["memcached"]
defs = []
incdirs = []
libdirs = []

def append_env(L, e):
    v = os.environ.get(e)
    if v and os.path.exists(v):
        L.append(v)

append_env(pkgdirs, "LIBMEMCACHED")
append_env(pkgdirs, "ZLIB")

# Hack up sys.argv, yay
unprocessed = []
for arg in sys.argv[1:]:
    if arg == "--with-zlib":
        use_zlib = True
        continue
    elif arg == "--without-zlib":
        use_zlib = False
        continue
    elif arg == "--with-sasl2":
        libs.append("sasl2")
        continue
    elif arg == "--gen-setup":
        cmd = arg[2:]
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

## OS X non-PPC workaround

# Apple OS X 10.6 with Xcode 4 have Python compiled with PPC but they removed
# support for compiling with that arch, so we have to override ARCHFLAGS.
if sys.platform == "darwin" and not os.environ.get("ARCHFLAGS"):
    compiler_dirn = "/usr/libexec/gcc/darwin"
    if os.path.exists(compiler_dirn):
        dir_items = os.listdir(compiler_dirn)
        if "ppc" not in dir_items:
            print >>sys.stderr, "enabling osx-specific ARCHFLAGS/ppc hack"
            os.environ["ARCHFLAGS"] = "-arch i386 -arch x86_64"

# There's a bug in <py3 with Py_True/False that will propagate with GCC's
# strict aliasing rules. Let's skip this flag for now.
cflags = ["-fno-strict-aliasing", ]

## Extension definitions

pylibmc_ext = Extension("_pylibmc", ["_pylibmcmodule.c"],
                        libraries=libs, include_dirs=incdirs,
                        library_dirs=libdirs, define_macros=defs,
                        extra_compile_args=cflags)

# Hidden secret: if environment variable GEN_SETUP is set, generate Setup file.
if cmd == "gen-setup":
    line = " ".join((
        pylibmc_ext.name,
        " ".join("-l" + lib for lib in pylibmc_ext.libraries),
        " ".join("-I" + incdir for incdir in pylibmc_ext.include_dirs),
        " ".join("-L" + libdir for libdir in pylibmc_ext.library_dirs),
        " ".join("-D" + name + ("=" + str(value), "")[value is None] for (name, value) in pylibmc_ext.define_macros)))
    open("Setup", "w").write(line + "\n")
    sys.exit(0)

readme_text = open("README.rst", "U").read()
version = open("pylibmc-version.h", "U").read().strip().split("\"")[1]

setup(name="pylibmc", version=version,
      url="http://sendapatch.se/projects/pylibmc/",
      author="Ludvig Ericson", author_email="ludvig@lericson.se",
      license="3-clause BSD <http://www.opensource.org/licenses/bsd-license.php>",
      description="Quick and small memcached client for Python",
      long_description=readme_text,
      ext_modules=[pylibmc_ext], packages=["pylibmc"])
