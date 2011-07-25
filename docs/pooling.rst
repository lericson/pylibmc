.. currentmodule:: pylibmc.pools

=========
 Pooling 
=========

:Author: Ludvig Ericson <ludvig circled-a lericson dot se>
:See also: `Pooling with pylibmc`__ (this document, first revision)
:See also: `Pooling with pylibmc pt. 2`__ (follow-up)

__ http://lericson.blogg.se/code/2009/september/draft-sept-20-2009.html
__ http://lericson.blogg.se/code/2009/september/pooling-with-pylibmc-pt-2.html

.. note:: This was originally a blog post. Edited and provided here for your
          convenience.

I was discussing how to implement pooling for :mod:`pylibmc` when I realized
what `libmemcachedutil`'s pooling is - or rather, what it isn't.

It's not a magical solution for concurrently doing anything at all, it's not
anything like that -- it just helps you with thread-safety.

In Python, however, we've got the global interpreter lock, the GIL. This lock
must always be held by the thread that is dealing with anything Python. The
Python interpreter itself isn't thread-safe, or rather, it is with the GIL.

This means that whenever Python code is running, you'll be sure to have
exclusive access to all of Python's memory (unless something is misbehaving.)
In turn, this means that the usecase for using `libmemcachedutil` in a Python
library is rather slim.

An example with Werkzeug
========================

This is a Werkzeug-based WSGI application which would be run in multiple
threads concurrently and still not have issues with races:

.. code-block:: python

    # Configuration
    n_threads = 12
    mc_addrs = "10.0.1.1", "10.0.1.2", "10.0.1.3"
    mc_pool_size = n_threads

    # Application
    import pylibmc
    from contextlib import contextmanager
    from pprint import pformat
    from werkzeug.wrappers import Request, Response
    from werkzeug.exceptions import NotFound

    class ClientPool(list):
        @contextmanager
        def reserve(self):
            mc = self.pop()
            try:
                yield mc
            finally:
                self.append(mc)

    mc = pylibmc.Client(mc_addrs)
    mc_pool = ClientPool(mc.clone() for i in xrange(mc_pool_size))

    @Request.application
    def my_app(request):
        with mc_pool.reserve() as mc:
            key = request.path[1:].encode("ascii")
            val = mc.get(key)
            if not val:
                return NotFound(key)
            return Response(pformat(val))

    if __name__ == "__main__":
        from werkzeug.serving import run_simple
        run_simple("0.0.0.0", 5050, my_app)

It's fully-functional example of how one could implement pooling with
:mod:`pylibmc`, and very much so in the same way that people do with
`libmemcachedutil`. Paste it into a script file, it runs out of the box.

FIFO-like pooling
=================

The aforementioned type of pool is already implemented in :mod:`pylibmc` as
:class:`pylibmc.ClientPool`, with a couple of other bells & whistles as well as
tests (hint: don't implement it yourself.) Its documentation speaks for itself:

.. autoclass:: pylibmc.ClientPool

   .. automethod:: fill
   .. automethod:: reserve

The use is identical to what was demonstrated above, apart from initialization,
that would look like this:

.. code-block:: python

    mc = pylibmc.Client(mc_addrs)
    mc_pool = pylibmc.ClientPool(mc, mc_pool_size)

Thread-mapped pooling
=====================

Another possibility is to have a data structure that remembers the thread name
(i.e. key it by thread ID or so.)

Each thread would reserve its client in the dict on each request. If none
exists, it would clone a master instance. Again, the documentation:

.. autoclass:: pylibmc.ThreadMappedPool

   .. automethod:: reserve
   .. automethod:: relinquish

A note on relinquishing
-----------------------

You must be sure to call :meth:`ThreadMappedPool.relinquish` *before*
exiting a thread that has used the pool, *from that thread*! Otherwise, some
clients will never be reclaimed and you will have stale, useless connections.
