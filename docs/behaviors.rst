.. _behaviors:

===========
 Behaviors
===========

libmemcached is a lot more flexible than python-memcached, and has provisions
for configuring so-called *behaviors*. :mod:`pylibmc` wraps these in a Python
interface.

Not all of the available behaviors make sense for Python, or are hard to make
use of, and as such some behaviors have been intentionally hidden or exposed in
some other way (UDP and the binary protocol are examples of this.)

Generally, a behavior's value should be an integer value. The exceptions are
hashing and distribution, which :mod:`pylibmc` translates with the C constants'
string equivalents, for readability.

Other than that, the behaviors are more or less one to one mappings of
libmemcached behavior constants.

.. _hash:

``"hash"``
   Specifies the default hashing algorithm for keys. See Hashing_ for more
   information and possible values.

.. _distribution:

``"distribution"``
   Specifies different means of distributing values to servers. See
   Distribution_ for more information and possible values.

.. _ketama:

``"ketama"``
   Setting this behavior to ``True`` is a shortcut for setting ``"hash"`` to
   ``"md5"`` and ``"distribution"`` to ``"consistent ketama"``.

.. _ketama_weighted:

``"ketama_weighted"``
   Exactly like the ``"ketama"`` behavior, but also enables the weighting
   support.

.. _ketama_hash:

``"ketama_hash"``
   Sets the hashing algorithm for host mapping on continuum. Possible values
   include those for the ``"hash"`` behavior.

.. _buffer_requests:

``"buffer_requests"``
   Enabling buffered I/O causes commands to "buffer" instead of being sent. Any
   action that gets data causes this buffer to be be sent to the remote
   connection. Quiting the connection or closing down the connection will also
   cause the buffered data to be pushed to the remote connection.

.. _cache_lookups:

``"cache_lookups"``
   Enables the named lookups cache, so that DNS lookups are made only once.

.. _no_block:

``"no_block"``
   Enables asychronous I/O. This is the fastest transport available for storage
   functions.

.. _tcp_nodelay:

``"tcp_nodelay"``
   Setting this behavior will enable the ``TCP_NODELAY`` socket option, which
   disables Nagle's algorithm. This obviously only makes sense for TCP
   connections.

.. _cas:

``"cas"``
   Enables support for CAS operations.

.. _verify_keys:

``"verify_keys"``
   Setting this behavior will test if the keys for validity before sending to
   memcached.

.. _connect_timeout:

``"connect_timeout"``
   In non-blocking, mode this specifies the timeout of socket connection.

.. _receive_timeout:

``"receive_timeout"``
   "This sets the microsecond behavior of the socket against the SO_RCVTIMEO
   flag.  In cases where you cannot use non-blocking IO this will allow you to
   still have timeouts on the reading of data."

.. _send_timeout:

``"send_timeout"``
   "This sets the microsecond behavior of the socket against the SO_SNDTIMEO
   flag.  In cases where you cannot use non-blocking IO this will allow you to
   still have timeouts on the sending of data."

.. _num_replicas:

``"num_replicas"``
   Poor man's high-availability solution. Specifies numbers of replicas that
   should be made for a given item, on different servers.

   "[Replication] does not dedicate certain memcached servers to store the
   replicas in, but instead it will store the replicas together with all of the
   other objects (on the 'n' next servers specified in your server list)."

.. _remove_failed:

``"remove_failed"``
   Remove a server from the server list after operations on it have failed for
   the specified number of times in a row. See the `section on failover <failover>`.

.. _failure_limit:

``"failure_limit"`` : deprecated
   Use ``"remove_failed"`` if at all possible.

   Remove a server from the server list after operations on it have failed for
   the specified number of times in a row.

.. _auto_eject:

``"auto_eject"`` : deprecated
   Use ``"remove_failed"`` if at all possible.

   With this behavior set, hosts which have been disabled will be removed from
   the list of servers after ``"failure_limit"``.

Hashing
-------

Basically, the hasher decides how a key is mapped to a specific memcached
server.

The available hashers are:

* ``"default"`` - libmemcached's home-grown hasher
* ``"md5"`` - MD5
* ``"crc"`` - CRC32
* ``"fnv1_64"`` - 64-bit FNV-1_
* ``"fnv1a_64"`` - 64-bit FNV-1a
* ``"fnv1_32"`` - 32-bit FNV-1
* ``"fnv1a_32"`` - 32-bit FNV-1a
* ``"murmur"`` - MurmurHash_

If :mod:`pylibmc` was built against a libmemcached using
``--enable-hash_hsieh``, you can also use ``"hsieh"``.

.. _hashing-and-python-memcached:

Hashing and python-memcached
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

python-memcached up until version 1.45 used a CRC32-based hashing algorithm not
reproducible by libmemcached. You can change the hasher for python-memcached
using the cmemcache_hash_ module, which will make it not only compatible with
cmemcache_, but also the ``"crc"`` hasher in libmemcached.

python-memcached 1.45 and later incorporated ``cmemcache_hash`` as its default
hasher, and so will interoperate with libmemcached provided the libmemcached
clients are told to use the CRC32-style hasher. This can be done in
:mod:`pylibmc` as follows::

    >>> mc.behaviors["hash"] = "crc"

.. _FNV-1: http://en.wikipedia.org/wiki/Fowler_Noll_Vo_hash
.. _MurmurHash: http://en.wikipedia.org/wiki/MurmurHash
.. _cmemcache_hash: http://pypi.python.org/pypi/cmemcache_hash
.. _cmemcache: http://gijsbert.org/cmemcache/
.. _hsieh: http://www.azillionmonkeys.com/qed/hash.html

Distribution
------------

When using multiple servers, there are a few takes on how to choose a server
from the set of specified servers.

The default method is ``"modula"``, which is what most implementations use.
You can enable consistent hashing by setting distribution to ``"consistent"``.

Modula-based distribution is very simple. It works by taking the hash value,
modulo the length of the server list. For example, consider the key ``"foo"``
under the ``"crc"`` hasher::

    >>> servers = ["a", "b", "c"]
    >>> crc32_hash(key)
    3187
    >>> 3187 % len(servers)
    1
    >>> servers[1]
    'b'

However, if one was to add a server or remove a server, every key would be
displaced by one - in effect, changing your server list would more or less
reset the cache.

Consistent hashing solves this at the price of a more costly key-to-server
lookup function, `last.fm's RJ explains how it works`__.

__ http://www.last.fm/user/RJ/journal/2007/04/10/rz_libketama_-_a_consistent_hashing_algo_for_memcache_clients

Failover
--------

Most people desire the classical "I don't really care" type of failover
support: if a server goes down, just use another one. This, sadly, is not an
option with libmemcached for the time being.

When libmemcached introduced a behavior called ``remove_failed``, two other
behaviors were deprecated in its stead called ``auto_eject`` and
``failure_limit`` -- this new behavior is a combination of the latter two. When
enabled, the numeric value is the number of times a server may fail before it
is ejected, and when not, no ejection occurs.

"Ejection" simply means *libmemcached will stop using that server without
trying any others.*

So, if you configure the behaviors ``remove_failed=4`` and ``retry_timeout=10``
and one of your four servers go down for some reason, then the first request to
that server will trigger whatever actual error occurred (connection reset, read
error, etc), then the subsequent requests to that server within 10 seconds will
all raise ``ServerDown``, then again an actual request is made and the cycle
repeats until four consequent errors have occurred, at which point
``ServerDead`` will be raised immediately.

In other words, ``ServerDown`` means that if the server comes back up, it goes
into rotation; ``ServerDead`` means that this key is unusable until the client
is reset.
