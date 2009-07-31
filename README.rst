`pylibmc` is a Python wrapper around the accompanying C Python extension
`_pylibmc`, which is a wrapper around `libmemcached` from TangentOrg.

You have to install `libmemcached` separately, and have your compiler and
linker find the include files and libraries.

With `libmemcached` installed and this package set up, the following basic
usage example should work::

    >>> import pylibmc
    >>> mc = pylibmc.Client(["127.0.0.1:11211"])
    >>> mc.set("foo", "Hello world!")
    True
    >>> mc.get("foo")
    'Hello world!'

The API is pretty much `python-memcached`. Some parts of `libmemcached` aren't
exposed yet. I think.

Behaviors
=========

`libmemcached` has ways of telling it how to behave. You'll have to refer to
its documentation on what the different behaviors do.

To change behaviors, quite simply::

    >>> mc.behaviors["hash"] = "fnv1a_32"

For a list of the defined behavior key names, see what the keys of a client is.
For example::

    >>> mc.behaviors.keys()  # doctest: +NORMALIZE_WHITESPACE
    ['hash', 'connect timeout', 'cache lookups', 'buffer requests',
     'verify key', 'support cas', 'poll timeout', 'no block', 'tcp nodelay',
     'distribution', 'sort hosts']

The ``hash`` and ``distribution`` keys are mapped by the Python module to constant
integer values used by `libmemcached`. See ``pylibmc.hashers`` and
``pylibmc.distributions``.


Comparison to other libraries
=============================

Why use `pylibmc`? Because it's fast.

`See this (a bit old) speed comparison <http://lericson.blogg.se/code/2008/november/pylibmc-051.html>`_.

Change Log
==========

New in version 0.6
------------------

 - Added compatibility with `libmemcached` 0.26, WRT error return codes.
 - Added `flush_all` and `disconnect_all` methods.
 - Now using the latest pickling protocol.

New in version 0.5
------------------

 - Fixed lots of memory leaks, and added support for `libmemcached` 0.23.
 - Also made the code tighter in terms of compiler pedantics.

New in version 0.4
------------------

 - Renamed the C module to `_pylibmc`, and added lots of `libmemcached` constants
   to it, as well as implemented behaviors.
