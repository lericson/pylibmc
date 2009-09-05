import os
from distutils.core import setup, Extension

incdirs = []
libdirs = []

if "LIBMEMCACHED_DIR" in os.environ:
    libdir = os.path.normpath(os.environ["LIBMEMCACHED_DIR"])
    incdirs.append(os.path.join(libdir, "include"))
    libdirs.append(os.path.join(libdir, "lib"))

readme_text = open("README.rst", "U").read()
 
BASE_CFLAGS = ["-O3"]
BASE_LDFLAGS = []

mac_snow_leopard = (os.path.exists("/Developer/SDKs/MacOSX10.6.sdk/") and
                    int(os.uname()[2].split('.')[0]) >= 8)

if mac_snow_leopard:
    # Only compile the 64bit version on Snow Leopard
    # libmemcached should also be compiled with make
    #    CFLAGS="-arch x86_64"
    # else one will expereince seg. faults
    BASE_LDFLAGS.extend(['-arch', 'x86_64'])
    BASE_CFLAGS.extend(['-arch', 'x86_64'])

pylibmc_ext = Extension("_pylibmc", ["_pylibmcmodule.c"],
                        extra_compile_args=BASE_CFLAGS,
                        extra_link_args=BASE_LDFLAGS,
                        libraries=["memcached"],
                        include_dirs=incdirs, library_dirs=libdirs)

setup(name="pylibmc", version="0.6.1",
      url="http://lericson.blogg.se/code/category/pylibmc.html",
      author="Ludvig Ericson", author_email="ludvig.ericson@gmail.com",
      license="3-clause BSD <http://www.opensource.org/licenses/bsd-license.php>",
      description="libmemcached wrapper", long_description=readme_text,
      ext_modules=[pylibmc_ext], py_modules=["pylibmc"])
