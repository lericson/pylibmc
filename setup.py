import os
import sys
from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext as _build_ext

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
lmc_dir = pkgdirs[0] if pkgdirs else None
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
            if arg.startswith("--with-libmemcached="):
                lmc_dir = arg.split("=", 1)[1]
            continue
    unprocessed.append(arg)
sys.argv[1:] = unprocessed

for pkgdir in pkgdirs:
    incdirs.append(os.path.join(pkgdir, "include"))
    libdirs.append(os.path.join(pkgdir, "lib"))

# When the user asked for a specific libmemcached, link that library by
# absolute path and give it an rpath. Merely adding -L<dir>/lib is not enough:
# the interpreter's own LDSHARED (e.g. pyenv on Homebrew systems) can carry
# -L/opt/homebrew/lib, which precedes ours, so "-lmemcached" would silently
# pick up a different libmemcached than the headers we compiled against.
extra_objects = []
extra_link_args = []
lmc_rpath = None
if lmc_dir and cmd != "gen-setup":
    for ext in (".dylib", ".so", ".a"):
        cand = os.path.join(lmc_dir, "lib", "libmemcached" + ext)
        if os.path.exists(cand):
            extra_objects.append(cand)
            libs.remove("memcached")
            if ext != ".a":
                lmc_rpath = os.path.join(lmc_dir, "lib")
            print("pylibmc: linking libmemcached from %s" % cand,
                  file=sys.stderr)
            break
    else:
        print("pylibmc: warning: no libmemcached found in %s/lib, falling "
              "back to -lmemcached" % lmc_dir, file=sys.stderr)

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
            print("enabling osx-specific ARCHFLAGS/ppc hack", file=sys.stderr)
            os.environ["ARCHFLAGS"] = "-arch i386 -arch x86_64"

# There's a bug in <py3 with Py_True/False that will propagate with GCC's
# strict aliasing rules. Let's skip this flag for now.
cflags = ["-fno-strict-aliasing", "-std=c99"]


class build_ext(_build_ext):
    """Put our rpath before whatever the interpreter's LDSHARED supplies.

    Dynamic libraries are searched along the rpath entries in order (and on
    macOS libmemcached 1.1's install name is @rpath/...), so e.g. pyenv's
    -Wl,-rpath,/opt/homebrew/lib would otherwise win at runtime too."""

    def build_extension(self, ext):
        if lmc_rpath:
            self.compiler.linker_so = (
                self.compiler.linker_so[:1] + ["-Wl,-rpath," + lmc_rpath]
                + self.compiler.linker_so[1:])
        super().build_extension(ext)

# Extension definitions

pylibmc_ext = Extension("_pylibmc", ["src/_pylibmcmodule.c"],
                        libraries=libs, include_dirs=incdirs,
                        library_dirs=libdirs, define_macros=defs,
                        extra_objects=extra_objects,
                        extra_link_args=extra_link_args,
                        extra_compile_args=cflags)

# Hidden secret: generate Setup file for statically compiling the extension.
if cmd == "gen-setup":
    line = " ".join((
        pylibmc_ext.name,
        " ".join("-l" + lib for lib in pylibmc_ext.libraries),
        " ".join("-I" + incdir for incdir in pylibmc_ext.include_dirs),
        " ".join("-L" + libdir for libdir in pylibmc_ext.library_dirs),
        " ".join("-D" + name + ("=" + str(value), "")[value is None] for (name, value) in pylibmc_ext.define_macros)))
    with open("Setup", "w") as s:
        s.write(line + "\n")
    sys.exit(0)

with open("README.rst", encoding="utf-8") as r:
    readme_text = r.read()
with open("src/pylibmc-version.h", encoding="utf-8") as r:
    version = r.read().strip().split("\"")[1]

setup(
    name="pylibmc",
    version=version,
    url="https://sendapatch.se/projects/pylibmc/",
    project_urls={
        "Source": "https://github.com/lericson/pylibmc",
    },
    author="Ludvig Ericson",
    author_email="ludvig@lericson.se",
    license="3-clause BSD <https://opensource.org/licenses/bsd-license.php>",
    description="Quick and small memcached client for Python",
    long_description=readme_text,
    long_description_content_type="text/x-rst",
    ext_modules=[pylibmc_ext],
    cmdclass={'build_ext': build_ext},
    package_dir={'': 'src'},
    packages=['pylibmc'],
    # SASL mechanism plugins, copied in by .github/scripts/bundle-sasl-plugins.sh
    # for the Linux wheels only. The glob matches nothing otherwise.
    package_data={'pylibmc': ['sasl2/*.so']},
    python_requires='>=3.8',
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Programming Language :: Python :: 3.14',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
)
