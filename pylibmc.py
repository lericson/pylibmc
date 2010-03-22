"""Snappy libmemcached wrapper

pylibmc is a Python wrapper around TangentOrg's libmemcached library.

The interface is intentionally made as close to python-memcached as possible,
so that applications can drop-in replace it.

Example usage
=============

Create a connection and configure it::

    >>> import pylibmc
    >>> mc = pylibmc.Client(["127.0.0.1"], binary=True)
    >>> mc.behaviors = {"tcp_nodelay": True, "ketama": True}

Basic operation::

    >>> mc.set("some_key", "Some value")
    True
    >>> value = mc.get("some_key")
    >>> value
    'Some value'
    >>> mc.set("another_key", 3)
    True
    >>> mc.delete("another_key")
    True
    >>> mc.set("key", "1")  # str or int is fine
    True

Atomic increments and decrements::

    >>> mc.incr("key")
    2L
    >>> mc.decr("key")
    1L

Batch operation::

    >>> mc.get_multi(["key", "another_key"])
    {'key': '1'}
    >>> mc.set_multi({"cats": ["on acid", "furry"], "dogs": True})
    []
    >>> mc.get_multi(["cats", "dogs"])
    {'cats': ['on acid', 'furry'], 'dogs': True}
    >>> mc.delete_multi(["cats", "dogs", "nonextant"])
    False

Further Reading
===============

See http://sendapatch.se/projects/pylibmc/
"""

import _pylibmc
from warnings import warn
from Queue import Queue

__all__ = ["hashers", "distributions", "Client"]
__version__ = _pylibmc.__version__
support_compression = _pylibmc.support_compression

errors = tuple(e for (n, e) in _pylibmc.exceptions)
# *Cough* Uhm, not the prettiest of things but this unpacks all exception
# objects and sets them on the very module object currently constructed.
import sys
modself = sys.modules[__name__]
for name, exc in _pylibmc.exceptions:
    setattr(modself, name, exc)

hashers, hashers_rvs = {}, {}
distributions, distributions_rvs = {}, {}
# Not the prettiest way of doing things, but works well.
for name in dir(_pylibmc):
    if name.startswith("hash_"):
        key, value = name[5:], getattr(_pylibmc, name)
        hashers[key] = value
        hashers_rvs[value] = key
    elif name.startswith("distribution_"):
        key, value = name[13:].replace("_", " "), getattr(_pylibmc, name)
        distributions[key] = value
        distributions_rvs[value] = key

class BehaviorDict(dict):
    def __init__(self, client, *args, **kwds):
        super(BehaviorDict, self).__init__(*args, **kwds)
        self.client = client

    def __setitem__(self, name, value):
        super(BehaviorDict, self).__setitem__(name, value)
        self.client.set_behaviors({name: value})

    def update(self, d):
        super(BehaviorDict, self).update(d)
        self.client.set_behaviors(d.copy())

class Client(_pylibmc.client):
    def __init__(self, servers, binary=False):
        """Initialize a memcached client instance.

        This connects to the servers in *servers*, which will default to being
        TCP servers. If it looks like a filesystem path, a UNIX socket. If
        prefixed with `udp:`, a UDP connection.

        If *binary* is True, the binary memcached protocol is used.
        """
        addr_tups = []
        for server in servers:
            addr = server
            port = 11211
            if server.startswith("udp:"):
                stype = _pylibmc.server_type_udp
                addr = addr[4:]
                if ":" in server:
                    (addr, port) = addr.split(":", 1)
                    port = int(port)
            elif ":" in server:
                stype = _pylibmc.server_type_tcp
                (addr, port) = server.split(":", 1)
                port = int(port)
            elif "/" in server:
                stype = _pylibmc.server_type_unix
                port = 0
            else:
                stype = _pylibmc.server_type_tcp
            addr_tups.append((stype, addr, port))
        super(Client, self).__init__(servers=addr_tups, binary=binary)

    def get_behaviors(self):
        """Gets the behaviors from the underlying C client instance.

        Reverses the integer constants for `hash` and `distribution` into more
        understandable string values. See *set_behaviors* for info.
        """
        bvrs = super(Client, self).get_behaviors()
        bvrs["hash"] = hashers_rvs[bvrs["hash"]]
        bvrs["distribution"] = distributions_rvs[bvrs["distribution"]]
        return BehaviorDict(self, bvrs)

    def set_behaviors(self, behaviors):
        """Sets the behaviors on the underlying C client instance.

        Takes care of morphing the `hash` key, if specified, into the
        corresponding integer constant (which the C client expects.) If,
        however, an unknown value is specified, it's passed on to the C client
        (where it most surely will error out.)

        This also happens for `distribution`.
        """
        behaviors = behaviors.copy()
        if any(" " in k for k in behaviors):
            warn(DeprecationWarning("space-delimited behavior names "
                                    "are deprecated"))
            for k in [k for k in behaviors if " " in k]:
                behaviors[k.replace(" ", "_")] = behaviors.pop(k)
        if behaviors.get("hash") is not None:
            behaviors["hash"] = hashers[behaviors["hash"]]
        if behaviors.get("ketama_hash") is not None:
            behaviors["ketama_hash"] = hashers[behaviors["ketama_hash"]]
        if behaviors.get("distribution") is not None:
            behaviors["distribution"] = distributions[behaviors["distribution"]]
        return super(Client, self).set_behaviors(behaviors)

    behaviors = property(get_behaviors, set_behaviors)
    @property
    def behaviours(self):
        raise AttributeError("nobody uses british spellings")

from contextlib import contextmanager

class ClientPool(Queue):
    """Client pooling helper.

    This is mostly useful in threaded environments, because a client isn't
    thread-safe at all. Instead, what you want to do is have each thread use
    its own client, but you don't want to reconnect these all the time.

    The solution is a pool, and this class is a helper for that.

    >>> mc = Client(["127.0.0.1"])
    >>> pool = ClientPool()
    >>> pool.fill(mc, 4)
    >>> with pool.reserve() as mc:
    ...     mc.set("hi", "ho")
    ...     mc.delete("hi")
    ... 
    True
    True
    """

    def __init__(self, mc=None, n_slots=None):
        Queue.__init__(self, n_slots)
        if mc is not None:
            self.fill(mc, n_slots)

    @contextmanager
    def reserve(self, timeout=None):
        """Context manager for reserving a client from the pool.

        If *timeout* is given, it specifiecs how long to wait for a client to
        become available.
        """
        mc = self.get(True, timeout=timeout)
        try:
            yield mc
        finally:
            self.put(mc)

    def fill(self, mc, n_slots):
        """Fill *n_slots* of the pool with clones of *mc*."""
        for i in xrange(n_slots):
            self.put(mc.clone())

class ThreadMappedPool(dict):
    """Much like the *ClientPool*, helps you with pooling.

    In a threaded environment, you'd most likely want to have a client per
    thread. And there'd be no harm in one thread keeping the same client at all
    times. So, why not map threads to clients? That's what this class does.

    If a client is reserved, this class checks for a key based on the current
    thread, and if none exists, clones the master client and inserts that key.

    >>> mc = Client(["127.0.0.1"])
    >>> pool = ThreadMappedPool(mc)
    >>> with pool.reserve() as mc:
    ...     mc.set("hi", "ho")
    ...     mc.delete("hi")
    ... 
    True
    True
    """

    def __new__(cls, master):
        return super(ThreadMappedPool, cls).__new__(cls)

    def __init__(self, master):
        self.master = master

    @contextmanager
    def reserve(self):
        """Reserve a client.

        Creates a new client based on the master client if none exists for the
        current thread.
        """
        key = thread.get_ident()
        mc = self.pop(key, None)
        if mc is None:
            mc = self.master.clone()
        try:
            yield mc
        finally:
            self[key] = mc

# This makes sure ThreadMappedPool doesn't exist with non-thread Pythons.
try:
    import thread
except ImportError:
    del ThreadMappedPool

if __name__ == "__main__":
    import doctest
    doctest.testmod()
