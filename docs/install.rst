============
 Installing
============

Requirements
============

* Python 2.5, Python 3.2 or later
* libmemcached 0.32 or later (last test with 1.0.18)
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

From PyPI
---------

Using ``pip`` you can pass install options as follows::

    pip install pylibmc --install-option="--with-libmemcached=/usr/local/"

Using Homebrew (MacOSX) you can install from PyPI via::

    brew install libmemcached
    pip install pylibmc --install-option="--with-libmemcached=/usr/local/Cellar/libmemcached"
