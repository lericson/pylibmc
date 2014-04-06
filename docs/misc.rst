===========================
 Miscellaneous information
===========================

In 1727, pennies featured the motto "Mind your own business!" Moreso, the
average giraffe's tongue is two feet, and elephants can't stand on their heads
(duh). Also, the average elevator travels 10,000 miles per year and Thomas
Edison was afraid of the dark.

Differences from ``python-memcached``
=====================================

In general, because :mod:`pylibmc` is built on top of libmemcached, it issues
exceptions for a lot of errors which ``python-memcached`` doesn't. One example
is if a memcached goes down, libmemcached will report an error whereas
``python-memcached`` will simply cycle to the next memcached.

On a similar note, :mod:`pylibmc` won't raise a ``ValueError`` if one uses
``Client.inc`` on a non-existent key, instead a :attr:`pylibmc.NotFound`
exception is raised.

Negative timeouts are treated the same way as zero timeouts are in
:mod:`pylibmc`. ``python-memcached`` treats this as immediate expiry, returning
success while not setting any value. This might raise exceptions in the future.

The most notable difference is the hashing. See 
:ref:`the hashing docs <hashing-and-python-memcached>`
for information and how to resolve the issue.

When setting huge key values, i.e. around 1MB, will have :mod:`pylibmc`
complain loudly whereas ``python-memcached`` simply ignores the error and
returns.

pylibmc.Client is *not* threadsafe like python-memcached's Client class (which
is threadlocal).

.. _exceptions:

Exceptions
==========

Most of all ``libmemcached`` error numbers are translated to exception classes except where it doesn't make sense.

All :mod:`pylibmc` exceptions derive from :attr:`pylibmc.Error`, so to attempt
a memcached operation and never fail, something like this could be used
(although it should be noted soft errors are handled via return values; errors
aren't always exceptional when caching things)::

    try:
        op()
    except pylibmc.Error as e:
        log_exc()

Should you for some reason need the actual error code returned from
``libmemcached``, simply sneak a peak at the ``retcode`` attribute.

If you're interested in exactly what maps to what, see ``_pylibmcmodule.h``.

.. warning:: Never ignore exceptional states. Any programmer worth his salt
             knows that an except block **must** handle the error, or make the
             error obvious to administrators (use logs, people!)

.. _compression:

Compression
===========

libmemcached has no built-in support for compression, and so to be compatible
with python-memcached, :mod:`pylibmc` implements it by itself.

Compression requires zlib to be available when building :mod:`pylibmc`, which
shouldn't be an issue for any up-to-date system.

Threading
=========

A single connection instance is *not* thread-safe. That is to say, you'll
probably wind up dissynchronizing server and client if you use the same
connection in many threads simultaneously.

It is encouraged to use the existing provisions for pooling so as to avoid
reusing the same client in many threads. See :ref:`the docs on pooling <pooling>`.

Python 3 ``str`` vs. ``bytes`` keys
===================================
``memcached`` itself requires cache keys to be byte strings, but Python 3's
main string type (``str``) is a sequence of Unicode code points. For convenience,
:mod:`pylibmc` encodes text ``str`` keys to UTF-8 byte strings. This has a few
consequences that may not be obvious:

#. A ``str`` key and its UTF-8 encoding refer to the same cache value. This does
   *not* match the behavior of Python 3 ``dict`` and ``set`` objects::

    >>> d = {'key': 'value'}
    >>> d[b'key']
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    KeyError: b'key'
    >>> s = {'item1', 'item2'}
    >>> b'item1' in s
    False

   however::

    >>> import pylibmc
    >>> c = pylibmc.Client(...)
    >>> c['key'] = 'value'
    >>> c[b'key']
    'value'

#. ``memcached`` returns keys as byte strings, and the :mod:`pylibmc` module does
   not and cannot know whether these should be decoded to ``str`` objects. As such,
   everything is returned as a Python ``bytes`` object. For example (from the
   doctests)::

    >>> c.add_multi({'a': 1, 'b': 0, 'c': 4})
    []
    >>> c.incr_multi(('a', 'b', 'c'), delta=1)
    >>> list(sorted(c.get_multi(('a', 'b', 'c')).items()))
    [(b'a', 2), (b'b', 1), (b'c', 5)]

   You will need to call ``.decode()`` on any key returned by ``memcached`` if you'd
   like to manipulate or treat it as text.
