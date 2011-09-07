============
 Installing
============

Requirements
============

* Python 2.5 or later
* libmemcached 0.32 or later (last test with 0.51)
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

Since ``easy_install`` doesn't support passing arguments to the setup script,
you can also define environment variables::

    LIBMEMCACHED=/opt/local easy_install pylibmc
