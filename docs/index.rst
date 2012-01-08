==============================================
 :mod:`pylibmc` - Python client for memcached
==============================================

.. currentmodule:: pylibmc

:mod:`pylibmc` is a client in Python for memcached_. It is a wrapper around
TangentOrg_'s libmemcached_ library.

The interface is intentionally made as close to python-memcached_
as possible, so that applications can drop-in replace it.

:mod:`pylibmc` leverages among other things configurable behaviors, data
pickling, data compression, battle-tested GIL retention, consistent
distribution, and the binary memcached protocol.

.. _TangentOrg: http://tangent.org/
.. _memcached: http://memcached.org/
.. _libmemcached: http://libmemcached.org/libMemcached.html
.. _python-memcached: http://www.tummy.com/Community/software/python-memcached/

Example usage
=============

Create a memcached connection and configure it::

    >>> import pylibmc
    >>> mc = pylibmc.Client(["127.0.0.1"], binary=True,
    ...                     behaviors={"tcp_nodelay": True,
    ...                                "ketama": True})

.. hint:: In earlier versions ``behaviors`` was no keyword
   argument, only an attribute. To safe-guard version compatibility use
   ``mc.behaviors = {...}``

Basic memcached operations can be accomplished with the mapping interface::

    >>> mc["some_key"] = "Some value"
    >>> mc["some_key"]
    'Some value'
    >>> del mc["some_key"]
    >>> "some_key" in mc
    False

"Classic" style memcached operations allow for more control and clarity::

    >>> mc.set("some_key", "Some value")
    True
    >>> value = mc.get("some_key")
    >>> value
    'Some value'
    >>> mc.set("another_key", 3)
    True
    >>> mc.delete("another_key")
    True

Automatic pickling of complex Python types::

    >>> mc.set("complex_plane=awesome", 4+3j)
    True
    >>> mc.get("complex_plane=awesome")
    (4+3j)
    >>> import fractions
    >>> mc.set("structured", {"a": ("b", "c"),
    ...                       "a2": fractions.Fraction(1, 3)})
    True
    >>> mc.get("structured")
    {'a': ('b', 'c'), 'a2': Fraction(1, 3)}

Atomic memcached-side increments and decrements::

    >>> mc.set("key", "1")  # str or int is fine
    True
    >>> mc.incr("key")
    2L
    >>> mc.decr("key")
    1L

Batch operations lessen GIL contention and thus I/O is faster::

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

.. toctree::
   :maxdepth: 2

   install
   reference
   pooling
   behaviors
   misc

Links and resources
===================

* sendapatch.se: `sendapatch.se/`__
* GitHub: `github.com/lericson/pylibmc`__
* PyPI: `pypi.python.org/pypi/pylibmc`__
* libmemcached: `tangent.org/552/libmemcached.html`__
* memcached: `memcached.org/`__

__ http://sendapatch.se/
__ http://github.com/lericson/pylibmc
__ http://pypi.python.org/pypi/pylibmc
__ libmemcached_
__ http://memcached.org/
