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

There's also support for some other features not present in other Python
libraries, for example, the binary protocol::

    >>> mc = pylibmc.Client(["127.0.0.1"], binary=True)

That's it, the binary protocol will be used for that instance.

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

Pooling
=======

In multithreaded environments, accessing the same memcached client object is
both unsafe and counter-productive in terms of performance. `libmemcached`'s
take on this is to introduce pooling on C level, which is correspondingly
mapped to pooling on Python level in `pylibmc`::

    >>> mc = pylibmc.Client(["127.0.0.1"])
    >>> pool = pylibmc.ThreadMappedPool(mc)
    >>> # (in a thread...)
    >>> with pool.reserve() as mc:
    ...     mc.set("hello", "world")

For more information on pooling, see `my two`__ `long posts`__ about it.

__ http://lericson.blogg.se/code/2009/september/draft-sept-20-2009.html
__ http://lericson.blogg.se/code/2009/september/pooling-with-pylibmc-pt-2.html

Comparison to other libraries
=============================

Why use `pylibmc`? Because it's fast.

`See this (a bit old) speed comparison`__, or `amix.dk's comparison`__.

__ http://lericson.blogg.se/code/2008/november/pylibmc-051.html
__ http://amix.dk/blog/viewEntry/19471

IRC
===

``#sendapatch`` on ``chat.freenode.net``.

Change Log
==========

New in version 0.9
------------------

 - Added a ``get_stats`` method, which behaves exactly like
   `python-memcached`'s equivalent.
 - Gives the empty string for empty memcached values like `python-memcached`
   does.
 - Added exceptions for most `libmemcached` return codes.
 - Fixed an issue with ``Client.behaviors.update``.

New in version 0.8
------------------

 - Pooling helpers are now available. See ``pooling.rst`` in the distribution.
 - The binary protocol is now properly exposed, simply pass ``binary=True`` to
   the constructor and there you go.
 - Call signatures now match `libmemcached` 0.32, but should work with older
   versions. Remember to run the tests!

New in version 0.7
------------------

 - Restructured some of the code, which should yield better performance (if not
   for that, it reads better.)
 - Fixed some memory leaks.
 - Integrated changes from `amix.dk`, which should make pylibmc work under
   Snow Leopard.
 - Add support for the boolean datatype.
 - Improved test-runner -- now tests ``build/lib.*/_pylibmc.so`` if available,
   and reports some version information.
 - Support for x86_64 should now work completely.
 - Builds with Python 2.4, tests run fine, but not officially supported.
 - Fixed critical bugs in behavior manipulation.

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
