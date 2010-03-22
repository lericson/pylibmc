`pylibmc` is a quick and small Python client for memcached__ written in C.

__ http://memcached.org/

It builds on the famous `libmemcached`__ C client from TangentOrg__, notable for
its speed and flexibility.

__ http://tangent.org/552/libmemcached.html
__ http://tangent.org/

`libmemcached` must be installed separately, and be available to the compiler
and linker.

For installation instructions, usage notes and reference documentation, see
pylibmc__'s home at http://sendapatch.se/projects/pylibmc/.

__ http://sendapatch.se/projects/pylibmc/

Comparison to other libraries
=============================

Why use `pylibmc`? Because it's fast.

`See this (a bit old) speed comparison`__, or `amix.dk's comparison`__.

__ http://lericson.blogg.se/code/2008/november/pylibmc-051.html
__ http://amix.dk/blog/viewEntry/19471

Installation
============

Building needs libmemcached and optionally zlib, the path to which can be
specified using command-line options to ``setup.py``

``--with-libmemcached=DIR``
    Build against libmemcached in DIR
``--with-zlib=DIR``
    Build against zlib in DIR
``--without-zlib``
    Disable zlib (disables compression)

So for example, if one were to use MacPorts to install libmemcached, your
libmemcached would end up in ``/opt/local``, hence
``--with-libmemcached=/opt/local``.

IRC
===

``#sendapatch`` on ``chat.freenode.net``.

Change Log
==========

New in version 1.0
------------------

 - Lots of documentation fixes and other nice things like that.
 - Nailed what appears to be the last outstanding memory leak.
 - Explicitly require libmemcached 0.32 or newer.

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
