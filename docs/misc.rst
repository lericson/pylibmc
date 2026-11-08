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

A negative expiry time (the *time* argument) raises :exc:`ValueError`, where
``python-memcached`` treats it as an immediate expiry. See
:meth:`pylibmc.Client.set` for the details, including how times over 30 days
are interpreted.

The most notable difference is the hashing. See 
:ref:`the hashing docs <hashing-and-python-memcached>`
for information and how to resolve the issue.

``python-memcached`` pickles booleans, which pylibmc reads back as booleans.
pylibmc stores them as the integer ``1`` or ``0`` with an extra flag that only
it understands, so ``python-memcached`` reads them back as integers.

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

.. _error-codes:

Error codes
-----------

An exception raised for a libmemcached error has a message of the form
``error N from FUNCTION(KEY): TEXT``, for example::

    error 3 from memcached_get(somekey): (0x...) CONNECTION FAILURE,  host: 127.0.0.1:11211 -> ...

``N`` is libmemcached's numeric return code, ``FUNCTION`` is the libmemcached
function that failed, ``(KEY)`` is present for single-key operations, and
``TEXT`` is what libmemcached's ``memcached_strerror`` says about the code
(``CONNECTION FAILURE`` above), followed by or replaced with libmemcached's more
specific description (such as the host involved) when it has one. The exact
wording of the specific description depends on the libmemcached version.

The number is also available as the ``retcode`` attribute of the exception
class, so ``pylibmc.ConnectionError.retcode == 3``. The module-level list
``pylibmc.exceptions`` holds ``(name, class)`` pairs for all exception classes.
``pylibmc.Error`` and ``pylibmc.CacheMiss`` have no ``retcode``, and a
libmemcached error without an exception class of its own (``MEMCACHED_ERRNO``,
for instance, whose message carries the C library's ``strerror`` text) is raised
as a plain :exc:`pylibmc.Error`. ``TooBig`` is raised with an empty message.

.. warning:: The numbers belong to libmemcached, not to :mod:`pylibmc`. They
             are not guaranteed to be the same between libmemcached versions,
             so match on exception classes rather than numbers. When a number
             in an old log needs decoding, look it up in the
             ``libmemcached/return.h`` header of the version that produced it.

The table below was generated from ``pylibmc.exceptions`` and
``memcached_strerror`` on libmemcached 1.0.18 and 1.1.4; the two were identical
for every row. Other versions were not checked.

============================  ====  =============================================================
Exception                     Code  libmemcached text
============================  ====  =============================================================
``Failure``                   1     FAILURE
``HostLookupError``           2     getaddrinfo() or getnameinfo() HOSTNAME LOOKUP FAILURE
``ConnectionError``           3     CONNECTION FAILURE
``ConnectionBindError``       4     CONNECTION BIND FAILURE
``WriteError``                5     WRITE FAILURE
``ReadError``                 6     READ FAILURE
``UnknownReadFailure``        7     UNKNOWN READ FAILURE
``ProtocolError``             8     PROTOCOL ERROR
``ClientError``               9     CLIENT ERROR
``ServerError``               10    SERVER ERROR
``SocketCreateError``         11    ERROR was returned by server
``DataExists``                12    CONNECTION DATA EXISTS
``DataDoesNotExist``          13    CONNECTION DATA DOES NOT EXIST
``NotFound``                  16    NOT FOUND
``AllocationError``           17    MEMORY ALLOCATION FAILURE
``SomeErrors``                19    SOME ERRORS WERE REPORTED
``NoServers``                 20    NO SERVERS DEFINED
``UnixSocketError``           27    COULD NOT OPEN UNIX SOCKET
``NotSupportedError``         28    ACTION NOT SUPPORTED
``FetchNotFinished``          30    FETCH WAS NOT COMPLETED
``Timeout``                   31    A TIMEOUT OCCURRED
``BadKeyProvided``            33    A BAD KEY WAS PROVIDED/CHARACTERS OUT OF RANGE
``InvalidHostProtocolError``  34    THE HOST TRANSPORT PROTOCOL DOES NOT MATCH THAT OF THE CLIENT
``ServerDead``                35    SERVER IS MARKED DEAD
``ServerDown``                47    SERVER HAS FAILED AND IS DISABLED UNTIL TIMED RETRY
``TooBig``                    37    ITEM TOO BIG
``UnknownStatKey``            36    ENCOUNTERED AN UNKNOWN STAT KEY
============================  ====  =============================================================

.. exception:: pylibmc.Timeout

   Raised for ``MEMCACHED_TIMEOUT`` (``retcode`` 31); a subclass of
   :exc:`pylibmc.Error`. With libmemcached 1.1.x, ``get`` and ``get_multi``
   raise this when the server does not answer in time (see the
   ``receive_timeout`` and ``send_timeout`` behaviors). libmemcached 1.0.x
   instead reports such a timeout as a plain cache miss (``None`` / ``{}``),
   so code that must tell the two apart should be prepared for both.

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

#. Many of the ``_multi`` calls to :mod:`pylibmc` return keys as well as
   values. :mod:`pylibmc` will match the types of the keys that were provided,
   returning each key as ``bytes`` or ``str`` as appropriate::

    >>> c.add_multi({'key1': 1, 'key2': 2})
    []
    >>> c.get_multi((b'key1', 'key2'))
    {b'key1': 1, 'key2': 2}

`verify_keys` ⋁ ¬ `verify_keys`
===============================

Security researchers have noted that disabling the `verify_keys` behavior is a
potential threat when accepting unsanitized input. This is most troublesome as
the default configuration disables this behavior. However, we have in fact
**not** specified this as the default, it comes as a sort of heritage from
libmemcached.

For this reason, you are urged to enable `verify_keys` if you have the
slightest doubt about user input getting through to your key names.
