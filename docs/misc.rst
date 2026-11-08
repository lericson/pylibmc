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

.. _master-keys:

Master keys
===========

With several memcached servers, each key is hashed to pick its server, so a
:meth:`~pylibmc.Client.get_multi` of many keys talks to many servers. If the
keys belong together, say everything cached for one user, you can tell
libmemcached to hash a *master key* (libmemcached calls it the group key)
instead, so that they all land on one server and one multi-get is enough::

    mc.set_multi({"profile": profile, "prefs": prefs}, master_key="user:42")
    mc.get_multi(["profile", "prefs"], master_key="user:42")
    mc.delete("profile", master_key="user:42")

The master key only decides which server is used. The items are still called
``"profile"`` and ``"prefs"``. The keyword is explicit on every call, and
nothing is remembered on the client between calls.

.. warning:: The same key stored under different master keys, or with and
             without one, may be on different servers, so you must give the
             same master key when you read and delete it as when you wrote it.
             With a single server there is no difference, which makes this easy
             to get wrong in development: ``mc.get("profile")`` finds the item
             above only by luck once there are several servers.

If the master key's server is down, calls with that master key fail, even for
keys that would have hashed to a live server. The master key is only hashed
and is never sent to the server. If libmemcached's ``namespace`` is set, it is
added to item keys, and it is part of what is hashed for the server choice only
if the ``_hash_with_prefix_key`` behavior is on, for master keys as for any
key.

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

.. _verify-keys-notes:

Key checks and the `verify_keys` behavior
=========================================

With the text protocol, a key is written into a command line as it is. A key
containing a space or a control character confuses the exchange: the server's
replies no longer line up with the requests, and later calls on the same client
can get the wrong answers. A key containing ``\r\n`` lets whoever controls the
key send commands of their own, such as ``flush_all``. This is a threat
whenever unsanitized input can reach your key names.

Since version 1.8.0, :mod:`pylibmc` therefore checks every key itself, before
anything is sent, in every method that takes a key (``get``, ``set``,
``delete``, ``incr``, ``touch``, ``cas``, the ``*_multi`` methods with their
*key_prefix*, ``in`` and ``client[key]``). A bad key raises ``ValueError``,
which is also what a key that is too long has always done. What is checked
depends on the protocol:

* Text protocol: a key must be shorter than 250 bytes and must not contain a
  byte at or below ``0x20`` (NUL, tab, CR, LF, space and the other control
  characters) or ``0x7f`` (DEL). Bytes ``0x80`` and above are allowed, so UTF-8
  keys work.
* Binary protocol (``binary=True``): the length limit only. The key is
  length-prefixed, so any byte, a space included, is safe.

The master key (``master_key=``) is only hashed to pick a server and never sent,
so it is checked for length only, with either protocol.

The check costs well under a microsecond for a 100-byte key.

Older versions left this to libmemcached's `verify_keys` behavior, which was
off by default and, when on, also rejected non-ASCII keys. `verify_keys` is now
ignored: setting it, in the constructor, with ``set_behaviors`` or through the
``behaviors`` mapping, emits a :class:`DeprecationWarning` and has no other
effect, and ``get_behaviors()`` does not list it. Remove it from your code.
