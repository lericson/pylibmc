============
 Installing
============

Requirements
============

* Python 3.8+ (CPython, or PyPy 3.9+)
* libmemcached 1.0.8 or later (tested with 1.0.18 and 1.1.4; 1.1.x is the
  maintained `awesomized/libmemcached <https://github.com/awesomized/libmemcached>`_
  fork, which builds with CMake)
* zlib (required for compression support)
* libsasl2 (required for authentication support)

Building
========

Like any Python package, use ``setup.py``::

    $ python setup.py install --with-libmemcached=/opt/local

You only need to specify ``--with-libmemcached`` if libmemcached is not
available on your C compiler's include and library path. This is the case if
you use MacPorts or something like that.

So for example, if one were to use MacPorts to install libmemcached, your
libmemcached would end up in ``/opt/local``, hence
``--with-libmemcached=/opt/local``.

Using ``pip`` you achieve the same thing as follows::

    pip install pylibmc --install-option="--with-libmemcached=/opt/local"

Note that `/usr/local` is typically on the library search path. If it is not,
you'd probably want to fix that instead.

Homebrew and MacOS
------------------

    brew install libmemcached
    pip install pylibmc

Choosing a libmemcached
-----------------------

With several libmemcached installs on one machine, point the build at the one
you want, either with the ``LIBMEMCACHED`` environment variable or
``--with-libmemcached``::

    LIBMEMCACHED=/opt/libmemcached-1.1.4 pip install pylibmc

The build then links that exact library file and records its directory as an
rpath ahead of any library path supplied by the Python interpreter (some
Python builds, e.g. pyenv on Homebrew systems, put ``-L/opt/homebrew/lib``
first). Check what you got with ``pylibmc.build_info()``;
``_pylibmc.libmemcached_runtime_version`` is the version of the library
actually loaded, and importing pylibmc warns if its major.minor differs from
the headers it was compiled against.

When rebuilding, remove stale ``build/`` directories first, since ``pip``
builds in the source tree and may reuse objects compiled against other
headers.

SASL authentication
-------------------

libsasl2 loads its mechanisms (``PLAIN`` and so on) as plugins at runtime, from
a directory that was fixed when libsasl2 was built. The Linux wheels bundle
libsasl2 and therefore also ship the plugins for the ``PLAIN``, ``LOGIN``,
``CRAM-MD5``, ``DIGEST-MD5`` and ``SCRAM-SHA-1`` mechanisms, in the
``pylibmc/sasl2`` directory of the installed package. On import, pylibmc sets
the ``SASL_PATH`` environment variable to that directory, unless ``SASL_PATH``
is already set, in which case it is left alone.

The wheels do not ship the GSSAPI (Kerberos) plugin. If you rely on the
plugins installed on your system, for GSSAPI or any other mechanism, set
``SASL_PATH`` to the system's plugin directory (for example
``/usr/lib/x86_64-linux-gnu/sasl2`` on Debian and Ubuntu) before importing
pylibmc. ``SASL_PATH`` can list several directories separated by colons.

macOS wheels use the system's libsasl2, and a pylibmc built from source uses
the plugins of the libsasl2 it was built against; neither is affected.
