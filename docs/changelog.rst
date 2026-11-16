Change Log
==========

New in version 1.8.0
--------------------

This release is mostly about keys and correctness. pylibmc now checks every key
itself, as the memcached protocol says it should, so a stray space or newline
can no longer corrupt a connection or inject a command. Booleans come back as
booleans, numbers that do not fit are refused instead of wrapping around, and
the Linux wheels can log in with SASL. New are master keys, ``exists()``,
``incr`` and ``decr`` with an initial value, and more behaviors and exception
classes. pylibmc now needs Python 3.11 or later. Read the changes that can
break existing code before upgrading.

Changes that can break existing code:

- pylibmc needs CPython 3.11 or later, or PyPy 3.11: Python 3.8 to 3.10 and
  PyPy 3.9 and 3.10 have reached end of life. pip on an older Python keeps
  installing pylibmc 1.7.x; pin ``pylibmc<1.8`` if your environment resolves
  packages some other way. Building from source needs libmemcached 1.0.18 or
  later, the oldest version that was ever tested (the documentation said
  1.0.8); an older one stops the build with an error (#362). The wheels are not
  affected.
- With the text protocol (the default), a key that contains whitespace or a
  control character (the bytes ``0x00`` to ``0x20`` and ``0x7f``) raises
  ``ValueError`` in every method, before anything is sent (#351). Such keys used
  to reach the server: a space or a newline made later replies go to the wrong
  call on the same client, ``\r\n`` could inject commands such as
  ``flush_all``, and some calls quietly reported a miss. This is the memcached
  protocol's rule, and the one ``python-memcached`` enforces. UTF-8 and other
  non-ASCII bytes are still fine, as is any byte with ``binary=True``; hash or
  percent-encode keys that break the rule. The ``verify_keys`` behavior is
  therefore ignored: setting it emits a ``DeprecationWarning``, and
  ``get_behaviors()`` no longer lists it.
- ``True`` and ``False`` come back as booleans, not as ``1`` and ``0`` (#245).
  They are stored as the integer with an extra flag (bit 31), so older pylibmc
  and ``python-memcached`` still read the integer. Booleans stored by earlier
  versions still read back as integers, and a stored bool that the server
  changes with ``incr``, ``decr``, ``append`` or ``prepend`` reads back as the
  number it now is.
- Numbers that do not fit are refused instead of silently wrapping around. An
  expiry time that is negative or does not fit in 32 bits raises
  ``ValueError`` in every method that takes one (#202); the text protocol used
  to expire such a key at once and the binary protocol to store it forever. A
  ``cas`` token outside 64 bits raises ``OverflowError``, as do a too large
  ``min_compress_len``, ``delta`` of ``incr_multi`` and ``decr_multi``, and
  ``flags`` of ``deserialize``; negative values of those raise ``ValueError``
  (#357).
- A ``udp:`` client is write-only: libmemcached sends without reading replies.
  ``incr``, ``decr``, ``incr_multi``, ``cas`` and ``exists`` on such a client
  now raise ``NotSupportedError`` instead of returning made-up values, as reads
  already did, and the other writes return ``True``, which means "sent" (#377).
- ``SocketCreateError`` is now called ``ErrorReply``: it has always meant that
  the server answered ``ERROR``, not a socket failure. The old name is the very
  same class, so catching it keeps working, but using it emits a
  ``DeprecationWarning``. Errors that used to be a plain ``pylibmc.Error`` now
  have subclasses of their own (see below), which matters only to code that
  checks ``type(exc) is pylibmc.Error``.

New:

- Every data method takes a keyword-only ``master_key=`` argument (#53, #176).
  When given, it is hashed instead of the key to pick the server, so related
  keys can live on one server and a ``get_multi`` of them reaches only that
  server. Pass the same master key to read, change and delete an item as to
  write it. See :ref:`master-keys`.
- ``Client.exists(key, master_key=None)`` tells whether a key is stored without
  transferring the value (#378). It is not free: libmemcached asks with an
  ``add`` of an empty item that expires at once, so on a full cache a miss can
  evict another item. ``key in client`` therefore keeps using ``get``.
- ``incr`` and ``decr`` take ``initial=`` and ``expire=``, which create a
  missing key with that value in one round trip instead of a racy ``add``
  followed by ``incr`` (#379). This needs ``binary=True``; a text-protocol
  client raises ``NotSupportedError``. A key created this way holds plain
  digits, so ``get`` returns ``bytes``. ``delta`` may now be up to
  ``2**32 - 1``.
- ``cas`` takes ``min_compress_len`` and ``compress_level`` and compresses like
  ``set``, and cas tokens of ``2**63`` and above work (#285).
- New behaviors ``tcp_keepidle``, ``randomize_replica_read`` and
  ``server_timeout_limit``, and the ``murmur3`` hash, which needs libmemcached
  1.1 or later (the wheels have it) (#380).
- New exception classes, all subclasses of ``pylibmc.Error``: ``AuthFailure``
  (SASL login refused), ``AuthProblem`` (the login could not be attempted),
  ``InvalidArguments``, ``ServerAllocationError`` (the server is out of
  memory), ``InProgress`` and ``SystemCallError`` (#381).

Fixes:

- SASL logins work with the Linux wheels on Debian, Ubuntu and other systems
  where they failed with "no mechanism available" (#289). The wheels ship the
  ``PLAIN``, ``LOGIN``, ``CRAM-MD5``, ``DIGEST-MD5`` and ``SCRAM-SHA-1`` plugins
  and point only their own copy of libsasl2 at them, so other SASL users in the
  process are not affected. A ``SASL_PATH`` you set is used instead. For
  Kerberos (GSSAPI), set ``SASL_PATH`` to your system's plugin directory.
- Reference leaks: ``incr_multi`` and ``decr_multi`` leaked every key on every
  call, ``delete_multi`` leaked a key whenever a delete failed, and ``get``,
  ``gets``, ``get_multi`` and ``delete_multi`` leaked rejected keys.
- ``key_prefix`` in the ``*_multi`` methods no longer cuts a key short at a NUL
  byte, which with ``binary=True`` stored keys under the wrong name.
- ``get_behaviors()`` no longer raises ``KeyError`` for a hash or distribution
  pylibmc has no name for; it returns the number, and setting a number works.
- ``Client.clone()`` raises ``MemoryError`` instead of returning an unusable
  client.
- For packagers: the test suite again runs against a memcached at any address
  given by ``MEMCACHED_HOST`` and ``MEMCACHED_PORT``, as in 1.6.3 (#376).

Build and platforms:

- Python 3.15 is supported.
- The extension's leftover code for Python 2 and Pythons older than 3.11 is
  gone. The only difference you could notice is that it imports ``pickle``
  directly instead of first trying a module called ``cPickle``.

Documentation:

- The ``pickle_protocol`` behavior suggests pinning the protocol when more than
  one Python version shares a cache, and the pooling example no longer uses
  ``xrange``.

Thanks to Tim Graham for dropping the end-of-life Pythons, restoring the
commented-out doctests and much other cleanup, and to @mxamin, whose testing
and review of the release candidates found problems that were fixed before
1.8.0.

New in version 1.7.0
--------------------

After a hiatus, we are back. A big welcome to @mxamin as a collaborator,
hopefully this will prevent further hiata down the line. Also, LLMs have
slashed the time investment to near zero, hoo-rah. The biggest change is that we
now build against libmemcached 1.1.4 for the wheels. Also the LLM found many
memory safety problems, and likely many yet more to come.

New:

- New exception ``pylibmc.Timeout`` (a subclass of ``pylibmc.Error``, with
  ``retcode`` 31) for libmemcached's ``MEMCACHED_TIMEOUT``.
- ``_pylibmc.libmemcached_runtime_version`` reports the version of the
  libmemcached library that is actually loaded. Importing pylibmc emits a
  ``RuntimeWarning`` if its major.minor differs from the libmemcached the
  extension was compiled against.
- ``remove_failed=N`` means a failure limit of ``N`` with every supported
  libmemcached.
- Error messages now include libmemcached's description of the error, for
  example ``error 3 from memcached_get(somekey): CONNECTION FAILURE``. The
  exception classes and ``retcode`` are unchanged, but code that matches the
  exact text of a message needs updating (#296).

Build and platforms:

- libmemcached 1.1.x (the awesomized/libmemcached fork, tested with 1.1.4) is
  supported, in addition to 1.0.x. The test suite runs against both.
- The wheels are built against libmemcached 1.1.4 and bundle it.
- Python 3.12, 3.13 and 3.14 are supported. Python 3.7 is no longer supported:
  pylibmc requires Python 3.8 or newer.
- Building with ``LIBMEMCACHED`` or ``--with-libmemcached`` now links the
  library you named, even when the interpreter's own link flags mention another
  libmemcached first. The build prints which library it picked.
- The source distribution includes the doctests and the test runner.
- Every wheel is installed and tested by the release pipeline. No wheel is
  built for CPython 3.8 on macOS arm64, which could not be tested; CPython 3.8
  to 3.14 are built everywhere else.

Fixes:

- Fixed a use-after-free in ``gets`` with a ``str`` key, which could look up
  the wrong key (#300).
- ``get_multi`` raises on a connection failure after the request was sent,
  instead of returning partial results (#301).
- Zero-length values no longer abort assert-enabled builds, and a subclass that
  overrides ``deserialize()`` receives ``b""`` for them instead of ``None``
  (#291).
- ``deserialize()`` raises ``TypeError`` for non-bytes input with the integer
  flags instead of reading invalid memory.
- Fixed reference leaks in ``incr_multi``, ``delete_multi``, ``set_multi``,
  ``get_stats``, ``get``, ``gets`` and at import time (#307 to #312).
- Fixed a use-after-free in ``get``: when it reported an error for a ``str``
  key, the key in the message was read from freed memory.
- With the ``buffer_requests`` behavior, ``set``, ``set_multi``, ``delete``,
  ``delete_multi``, ``touch`` and ``cas`` no longer raise ``error 32`` when
  libmemcached only queued the request (#180).
- ``set_multi`` and ``incr_multi`` raise ``MemoryError`` when an allocation
  fails; previously they returned without setting an exception.
- Python 3.13 no longer prints ``Exception ignored in PyMapping_HasKeyString()``
  when a client is created without behaviors (#297).

Documentation:

- New "Error codes" section. Expiry times over 30 days are absolute Unix
  timestamps, and negative times behave differently with the text and the
  binary protocol; both are now documented, as are ``tcp_keepalive`` and
  ``_poll_timeout`` (#115, #273, #56).

Thanks to Christian Clauss, David Szotten, Nikolas Nyby, Miro Hrončok and Bryan
C. Mills for their contributions since 1.6.3, and to @mxamin, whose fork
supplied several of the ideas behind the build and test changes in this
release.

New in version 1.6.0
--------------------

Though no major feature overhauls have taken place, this release is partially
incompatible with 1.5.0. This stems from the fact that python-memcached is now
using a flag that pylibmc has been using for some years. python-memcached uses
it for a different purpose, and an incompatible one. We deemed that it would be
better to support this interoperability. The change also means that Unicode
strings are now stored as UTF-8 rather than pickled, which may or may not
result in a slight performance improvement for this type of data.

We have also introduced a `pickle_protocol` behavior to enable seamless
interoperability between Python 2.x and 3.x. Also, this release introduces a
ManyLinux wheel, making installation a breeze on ManyLinux systems (which I
suppose is many linuxes.)

New in version 1.5.0
--------------------

This release fixes critical memory leaks in common code paths introduced in
1.4.2. Also fixes a critical bug in a corner of the zlib inflation code, where
prior memory errors would trigger a double free. Thank you to everybody
involved in the making of this release, and especially `Eau de Web`__, without
their contributions, this release and the bug fixes it contains wouldn't have
been so expedient.

__ http://www.eaudeweb.ro/

New in version 1.4.0
--------------------

Brace yourself, Python 3.x support has come!

Thanks to everybody involved in this project; this release involves less
authors but **a lot** more work per person. Thanks especially to Harvey Falcic
for the work he put in, without which there wouldn't be any Python 3.x support.
Also thanks to Sergey Pashinin for the initial stab at the problem.

Other than that, we had miscellaneous bug fixes, testing improvements, and
documentation updates.

Last but not least I would like to ask for your support in this project, either
by helping out with development, testing, documentation or anything at all; or
simply by donating some `magic internet money`__ to the project's Bitcoin
address `12dveKhqiJWCY8zXT4kaHdHELXPeGAUo9h`__

__ http://static.adzerk.net/Advertisers/5af77cf0094d4303bb308b955dd05992.jpg
__ bitcoin:12dveKhqiJWCY8zXT4kaHdHELXPeGAUo9h

New in version 1.3.0
--------------------

Because there ain't nothing better than releasing software in the spring time.

Lots of improvements have come about in just about every corner of the library,
thanks to *eighteen different authors* over almost *20 pull requests*. Amazing.

- Added touch support
- Added compress_level
- Added weighted distribution
- Added automated benchmarking utility
- Added Travis CI and build status
- Added behavior dead_timeout
- Added behaviors tcp_keepalive
- Added behavior callback_prefix_key
- Lots of bug tuning, fixes, tests, and documentation

Lastly, thanks in particular to the authors of this release: Abramowitz,
Baklanov, Bergström, Borisov, Branson, Brown, Ericson, Hansche, Hlodversson,
King, Kowalak, McFague, Moura, Noguchi, Shurter, Williams and Wong.

New in version 1.2.0
--------------------

This release is for the people behind `reddit.com`__, for helping push
development forward. Keep doing your thing.

__ http://code.reddit.com/

- `semver.org`__ versioning scheme
- Fixed GIL issues
- Added CAS support (ketralnis)
- Added SASL authentication (Remoun)
- Added more detail to errors (spladug)
- Added mapping-like behavior for clients
- Fixed build errors on Mac OS X
- Moved to nose__ for testing
- Added ``auto_eject`` behavior
- Added ``num_replicas`` behavior
- Added ``remove_failed`` behavior
- Removed ``cache_lookups`` behavior
- Improved repr of clients (noah256)
- Improved IPv6 support (JshWright)
- Improved pooling behavior so it doesn't cause lock-ups
- Improved tests and testing foundation
- Improved documentation and structure
- Internalized Sphinx documentation
- Bunch of other stuff

__ http://semver.org/
__ http://somethingaboutorange.com/mrl/projects/nose/

New in version 1.1
------------------

- Removed deprecated space-based behavior names.
- Acquire and release the GIL properly, thanks ketralnis__
- Add support for ``libmemcached 0.40``
- Included a more useful command-line interface
- Fixed handling of NUL-byte keys in ``get_multi`` in binary protocol
- Fixed some valgrind-reported memory warnings
- Fixed bogus usage of time argument for delete.
- 1.1.1: Fixed tests under Python 2.5

__ http://www.ketralnis.com/

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
