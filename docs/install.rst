============
 Installing
============

Requirements
============

* Python 3.6+
* libmemcached 1.0.8 or later (latest tested is 1.0.18)
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
