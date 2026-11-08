Change Log
==========

New in version 1.8.0
--------------------

Changes that can break existing code:

- A negative expiry time now raises ``ValueError``, as does one that does not
  fit in 32 bits, in ``set``, ``add``, ``replace``, ``append``, ``prepend``,
  ``cas``, ``touch`` and the ``*_multi`` variants (#202). It used to be turned
  silently into a huge number: the text protocol then expired the key at once
  and the binary protocol stored it without expiry.
- ``True`` and ``False`` now come back as booleans and not as ``1`` and ``0``
  (#245). They are stored as the integer ``1`` or ``0`` with an extra flag
  (bit 31), so readers that do not know the flag, such as older pylibmc and
  ``python-memcached``, still see the integer. Booleans stored by earlier
  versions are integers and still read back as integers.

Fixes:

- ``incr_multi`` and ``decr_multi`` leaked a reference to every key on every
  call. A key that is rejected (for example one that is too long) no longer
  leaks in ``get``, ``gets``, ``get_multi`` and ``delete_multi``.

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
