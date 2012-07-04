"""Snappy libmemcached wrapper

pylibmc is a Python wrapper around TangentOrg's libmemcached library.

The interface is intentionally made as close to python-memcached as possible,
so that applications can drop-in replace it.

Example usage
=============

Create a connection and configure it::

    >>> import pylibmc
    >>> m = pylibmc.Client(["10.0.0.1"], binary=True)
    >>> m.behaviors = {"tcp_nodelay": True, "ketama": True}

Nevermind this doctest shim::

    >>> from pylibmc.test import make_test_client
    >>> mc = make_test_client(behaviors=m.behaviors)

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
    >>> mc.add_multi({"cats": ["on acid", "furry"], "dogs": True})
    []
    >>> mc.get_multi(["cats", "dogs"])
    {'cats': ['on acid', 'furry'], 'dogs': True}
    >>> mc.add_multi({"cats": "not set", "dogs": "definitely not set", "bacon": "yummy"})
    ['cats', 'dogs']
    >>> mc.get_multi(["cats", "dogs", "bacon"])
    {'cats': ['on acid', 'furry'], 'bacon': 'yummy', 'dogs': True}
    >>> mc.delete_multi(["cats", "dogs", "bacon"])
    True

Custom picklers::

    >>> mc.set("key", {"complex": True})
    True
    >>> mc.get("key")
    {'complex': True}
    >>> mc.set_pickler("json")
    True
    >>> mc.set("key", {"complex": True})
    True
    >>> mc.set_pickler()
    Traceback (most recent call last):
      ...
    TypeError: set_pickler() takes exactly one argument (0 given)
    >>> mc.set_pickler(None)
    True
    >>> mc.get("key")
    Traceback (most recent call last):
      ...
    UnpicklingError: invalid load key, '{'.
    >>> mc.set_pickler("phpserialize")
    True
    >>> mc.get("key")
    Traceback (most recent call last):
      ...
    ValueError: unexpected opcode
    >>> mc.set("key", {"complex": True})
    True
    >>> mc.get("key")
    {'complex': True}
    >>> mc.set_pickler("json")
    True
    >>> mc.get("key")
    Traceback (most recent call last):
      ...
    ValueError: No JSON object could be decoded
    >>> mc.set("key", {"complex": True})
    True
    >>> mc.get("key")
    {u'complex': True}
    >>> mc.set_pickler("time")
    Traceback (most recent call last):
      ...
    ImportError: Invalid pickler: time. The module must exist and must support both .loads() and .dumps() functions.
    >>> mc.get("key")
    '{"complex": true}'
    >>> mc.set("key", {"complex": True})
    False
    >>> mc.get("key")
    '{"complex": true}'

Further Reading
===============

See http://sendapatch.se/projects/pylibmc/
"""

import _pylibmc
from .consts import hashers, distributions
from .client import Client
from .pools import ClientPool, ThreadMappedPool

support_compression = _pylibmc.support_compression
support_sasl = _pylibmc.support_sasl

__version__ = _pylibmc.__version__
__all__ = ["hashers", "distributions", "Client",
           "ClientPool", "ThreadMappedPool"]
