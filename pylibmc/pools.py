"""Pooling"""

from __future__ import with_statement

from contextlib import contextmanager
from Queue import Queue

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
    ThreadMappedPool = None
