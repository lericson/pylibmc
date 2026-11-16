===========
 Reference
===========

.. class:: pylibmc.Client(servers[, binary=False, username=None, password=None, behaviors=None])

   Interface to a set of memcached servers.

   *servers* is a sequence of strings specifying the servers to use.

   *binary* specifies whether or not to use the binary protocol to talk to the
   memcached servers.

   *username* and *password* are credentials for SASL authentication. It requires support
   in libmemcached, and binary=True. Test for local support with pylibmc.support_sasl.

   *behaviors*, if given, is passed to :meth:`Client.set_behaviors` after
   initialization.

   Supported transport mechanisms are TCP, UDP and UNIX domain sockets. The
   default transport type is TCP.

   To specify UDP, the server address should be prefixed with ``"udp:"``, as in
   ``"udp:127.0.0.1"``. A UDP client is **write-only**, see below.

   To specify UNIX domain socket, the server address must start with a slash, as
   in ``"/run/foo.sock"``.

   Mixing transport types is prohibited by :mod:`pylibmc` as this is not supported by
   libmemcached.

   .. rubric:: UDP is write-only

   libmemcached runs a UDP client in noreply mode (``get_behaviors()["_noreply"]``
   is ``1`` and cannot be turned off): commands are sent as datagrams and the
   server's answers are never read. So a UDP client can only send.

   * Reads raise :exc:`pylibmc.NotSupportedError`: ``get``, ``gets``,
     ``get_multi``, ``key in mc``, ``mc[key]``, ``touch`` and ``get_stats``.
   * Calls whose result would be taken from the server's answer also raise
     :exc:`pylibmc.NotSupportedError`, rather than return something made up:
     ``incr``, ``decr``, ``incr_multi``, ``cas`` and ``exists``. Nothing is
     sent.
   * Writes are fire and forget: ``set``, ``add``, ``replace``, ``append``,
     ``prepend``, ``delete``, ``set_multi``, ``add_multi``, ``delete_multi``
     and ``flush_all`` return ``True`` (``set_multi`` and ``add_multi`` return
     an empty list), and that means *sent*, not *stored*. ``add`` returns
     ``True`` although the key exists, and ``delete`` although it does not;
     the server's refusal is not seen. Use a TCP client to read the result.
   * The rules also hold for clones and for the pools in :mod:`pylibmc.pools`.

   memcached must listen for UDP, which is off by default since memcached 1.5.6:
   start it with ``-U <port>`` (it can serve TCP and UDP at once, for example
   ``memcached -p 11211 -U 11211``). A datagram has to hold the whole command,
   so large values do not work: about 5 kB arrives, but values of 100 kB fail
   with :exc:`pylibmc.WriteError` (the limit is what the operating system
   accepts in one datagram, not measured per platform), and on the binary
   protocol the server is then marked failed and later calls raise
   :exc:`pylibmc.ServerDown` until the retry timeout has passed (measured with
   libmemcached 1.0.18).

   .. method:: clone() -> clone

      Clone client, making new connections as necessary.

      The clone has the same servers, behaviors (including ``pickle_protocol``),
      binary protocol setting and SASL credentials, and is of the same class,
      so overridden ``serialize()`` and ``deserialize()`` methods apply to it
      too. Attributes a subclass sets on the instance (for example in its own
      ``__init__``) are not copied. :class:`~pylibmc.ClientPool` and
      :class:`~pylibmc.ThreadMappedPool` hand out clones, so their clients
      authenticate like the original.

   .. Master keys

   .. note:: Every data method below (``get``, ``gets``, ``set``, ``add``,
             ``replace``, ``append``, ``prepend``, ``cas``, ``delete``,
             ``touch``, ``exists``, ``incr``, ``decr``, ``get_multi``,
             ``set_multi``,
             ``add_multi``, ``delete_multi`` and ``incr_multi``) takes a
             keyword-only *master_key* argument. The default, ``None``, is the
             usual behavior. When given, libmemcached hashes the master key
             instead of the item key to pick the server, but the item is still
             stored and fetched under its own key, so you must pass the same
             master key to read, change and delete an item as to write it.
             See :ref:`master-keys`.

             The master key is checked like a key (text or bytes, not empty,
             shorter than 250 bytes; ``ValueError`` or ``TypeError``
             otherwise). It is passed down with the call and never stored on
             the client. The *key_prefix* argument of the ``*_multi`` methods
             applies to the item keys only, not to the master key. ``touch``
             works with or without a master key.

   .. Keys

   .. note:: Keys are ``str`` (encoded as UTF-8) or ``bytes`` and must be
             shorter than 250 bytes. With the text protocol a key must also not
             contain whitespace or control characters (any byte at or below
             ``0x20``, or ``0x7f``); with ``binary=True`` any byte is allowed.
             A bad key raises ``ValueError`` in every method (and in ``in``
             and ``client[key]``), before anything is sent. See
             :ref:`verify-keys-notes`.

   .. Reading

   .. method:: get(key[, default, master_key=None]) -> value

      Get *key* if it exists, otherwise *default*. If *default* is not given,
      it defaults to ``None``.

   .. method:: get_multi(keys[, key_prefix=None, master_key=None]) -> values

      Get each of the keys in sequence *keys*.
      
      If *key_prefix* is given, specifies a string to prefix each of the values
      in *keys* with.

      Returns a mapping of each unprefixed key to its corresponding value in
      memcached. If a key doesn't exist, no corresponding key is set in the
      returned mapping.

   .. method:: exists(key[, master_key=None]) -> bool

      ``True`` if *key* is stored, ``False`` if not, without the value being
      sent over the network, which saves the transfer for large values. Any
      stored value counts, ``None`` and empty values included. As the value is
      never fetched, :meth:`deserialize` is not called, so a value it would
      turn into a miss (``CacheMiss``) counts as present. The empty key is
      ``False``, a bad key raises like it does in :meth:`get`, and a server
      error (a server that is down, say) raises.

      ``key in client`` still calls :meth:`get` and discards the value; it
      does not use ``exists``, for the reason in the note.

      .. note:: memcached has no command that only checks for a key, so
                libmemcached asks with an ``add`` of an empty item whose expiry
                is already in the past. A present key is left as it was and a
                missing key stays missing, but to the server a miss is a store
                of an item that expires at once. It counts in the
                ``cmd_set`` and ``total_items`` statistics, and when the cache
                is full it can evict a live item: with memcached 1.6.45 and a
                full cache of small items, every miss evicted one. A server run
                with ``-M`` (no evictions) answers a miss on a full cache with
                an out-of-memory error, which ``exists`` raises. A proxy in
                front of memcached sees a write. Where that matters, use
                :meth:`get`.

                With the ``buffer_requests`` or ``_noreply`` behavior on,
                ``exists`` fetches the item and drops the value instead, because
                libmemcached's answer cannot be trusted there: with
                ``buffer_requests`` on the binary protocol it reads the reply
                of an earlier buffered command, and with ``_noreply``
                libmemcached 1.0.18 can wait forever. It then answers what
                :meth:`get` would, including not seeing a store still in the
                buffer. A UDP client raises ``NotSupportedError``, see above.

   .. Writing

   .. method:: set(key, value[, time=0, min_compress_len=0, compress_level=-1, master_key=None]) -> success

      Set *key* to *value*.

      :param key: Key to use
      :param value: Value to set
      :param time: Time until expiry
      :param min_compress_len: Minimum length before compression is triggered

      If *time* is given, it specifies the number of seconds until *key* will
      expire. Default behavior is to never expire (equivalent of specifying
      ``0``).

      .. warning:: The *time* argument is passed on to memcached as is, and
                   memcached interprets it in two ways. A value up to and
                   including 30 days (``60 * 60 * 24 * 30`` = 2592000 seconds)
                   is a number of seconds from now. A larger value is taken
                   as an absolute Unix timestamp. So ``time=30 * 86400 + 1`` is
                   a moment in January 1970, and the key is already expired
                   when it is stored (the call still returns ``True``). To
                   expire a key more than 30 days from now, pass
                   ``int(time.time()) + seconds``.

                   A negative value raises :exc:`ValueError`, as does one that
                   does not fit in 32 bits. (Before 1.8.0 a negative value
                   was silently turned into a huge one, and the text protocol
                   then expired the key immediately while the binary protocol
                   stored it without expiry.) Use :meth:`delete` to remove a
                   key.

                   The same rules apply to every method below that takes
                   *time*.

      If *min_compress_len* is given, it specifies the maximum number of actual
      bytes stored in memcached before compression is used. Default behavior is
      to never compress (which is what ``0`` means). See :ref:`compression`.

      If *compress_level* is given, it specifies the compression level for the
      data. It accepts the same values as the :mod:`zlib` family, for which
      `zlib.Z_BEST_SPEED` and `zlib.Z_BEST_COMPRESSION` are commonly used
      constants. It accepts values between [0, 9] inclusively.

   .. method:: set_multi(mapping[, time=0, key_prefix=None, min_compress_len, compress_level, master_key=None]) -> failed_keys

      Set multiple keys as given by *mapping*. *time* is the same as for
      :meth:`set`, including the 30 day limit for relative times.

      If *key_prefix* is specified, each of the keys in *mapping* is prepended
      with this value.

      Returns a list of keys which were not set for one reason or another,
      without their optional key prefix.

   .. method:: add(key, value[, time, min_compress_len, compress_level, master_key=None]) -> success

      Sets *key* if it does not exist. *time* is the same as for :meth:`set`.

      .. seealso:: :meth:`set`, :meth:`replace`

   .. method:: replace(key, value[, time, min_compress_len, compress_level, master_key=None]) -> success

      Sets *key* only if it already exists. *time* is the same as for
      :meth:`set`.

      .. seealso:: :meth:`set`, :meth:`add`

   .. method:: append(key, value[, master_key=None]) -> success

      Append *value* to *key* (i.e., ``m[k] = m[k] + v``).

      .. note:: Uses memcached's appending support, and therefore should never
                be used on keys which may be compressed or non-string values.

   .. method:: prepend(key, value[, master_key=None]) -> success

      Prepend *value* to *key* (i.e., ``m[k] = v + m[k]``).

      .. note:: Uses memcached's prepending support, and therefore should never
                be used on keys which may be compressed or non-string values.

   .. method:: incr(key[, delta=1, master_key=None]) -> value

      Increment value at *key* by *delta*.

      Returns the new value for *key*, after incrementing.

      Works for both strings and integer types.

      .. note:: There is currently no way to set a default for *key* when
                incrementing.

   .. method:: decr(key[, delta=1, master_key=None]) -> value

      Decrement value at *key* by *delta*.

      Returns the new value for *key*, after decrementing.

      Works for both strings and integer types, but will never decrement below
      zero.

      .. note:: There is currently no way to set a default for *key* when
                decrementing.

   .. Atomic operations

   .. method:: gets(key[, master_key=None]) -> (value, cas_id)

      Get *key* and its compare-and-swap ID if it exists, otherwise ``(None,
      None)``.

      The so-called CAS token or ID is used with :meth:`cas` to update a value
      with the guarantee that no other value was written in between.

      .. seealso:: :meth:`get`, :meth:`cas`

   .. method:: cas(key, value, cas[, time=0, min_compress_len=0, compress_level=-1, master_key=None]) -> swapped

      Set *key* to *value* if *key* CAS token is *cas*.

      :param key: Key to use
      :param value: Value to set
      :param cas: Compare-and-swap token from :meth:`gets`
      :param time: Time until expiry
      :param min_compress_len: Minimum length before compression is triggered
      :param compress_level: zlib compression level, 0 to 9, or -1 for the
                             default

      If *time* is given, it specifies the number of seconds until *key* will
      expire. Default behavior is to never expire (equivalent of specifying
      ``0``). Times over 30 days are absolute timestamps and negative times raise
      :exc:`ValueError`, see :meth:`set`.

      *min_compress_len* and *compress_level* work exactly as they do for
      :meth:`set`, and a compressed value is read back by any client the same
      way. (Before 1.8.0, ``cas`` could not compress and did not take them.)

      Returns ``False`` if the token no longer matches, that is, if the key was
      written by someone else after :meth:`gets`.

   .. Deleting

   .. method:: delete(key[, master_key=None]) -> deleted

      Delete *key* if it exists.

      Returns ``True`` if the key was deleted, ``False`` otherwise (as is the case if
      it wasn't set in the first place.)

   .. method:: delete_multi(keys[, key_prefix=None, master_key=None]) -> deleted

      Delete each of key in the sequence *keys*.

      :param keys: Sequence of keys to delete
      :param key_prefix: Prefix for the keys to delete

      Returns ``True`` if all keys were successfully deleted, ``False``
      otherwise (as is the case if it wasn't set in the first place.)

   .. method:: touch(key, time[, master_key=None]) -> touched

      Touch a given *key* and set its expiry time to *time* seconds.

      :param key: Key to touch
      :param time: Number of seconds until the key expires.

      Times over 30 days are absolute Unix timestamps, and a negative *time*
      raises :exc:`ValueError`; see :meth:`set`.

      Returns ``True`` if the key was successfully touched. ``False``
      if the key did not exist (so touching is not possible.)

   .. Utilities

   .. method:: disconnect_all()

      Disconnect from all servers and reset internal state.

      Exposed mainly for compatibility with python-memcached, as there really
      is no logical reason to do this.

   .. method:: flush_all() -> success

      Flush all data from all servers.
      
      .. note:: This clears the specified memcacheds fully and entirely.

   .. method:: get_stats() -> [(name, stats), ...]

      Retrieve statistics from each of the connected memcached instances.

      Returns a list of two-tuples of the format ``(name, stats)``.
      
      *stats* is a mapping of statistics item names to their values. Whether or
      not a key exists depends on the version of libmemcached and memcached
      used.

   .. method:: serialize(value) -> bytestring, flag

      Serialize a Python value to bytes *bytestring* and an integer *flag* field
      for storage in memcached. The default implementation has special cases
      for bytes, text, ints/longs and bools, and falls back to pickle for all
      other objects. A bool is stored as the integer ``1`` or ``0`` with an
      extra flag (bit 31), so it comes back as a bool; a reader that does not
      know the flag, such as ``python-memcached``, sees the integer. Override this method to use a custom serialization format, or
      otherwise modify the behavior.

      *flag* is exposed by the memcached protocol. It adds flexibility
      in terms of encoding schemes: for example, objects *a* and *b* of
      different types may coincidentally encode to the same *bytestring*,
      just so long as they encode with different values of *flag*. If distinct
      values always encode to different byte strings (for example, when
      serializing all values with pickle), *flag* can simply be set to a
      constant.

   .. method:: deserialize(bytestring, flag) -> value

      Deserialize *bytestring*, stored with *flag*, back to a Python object.
      Override this method (in concert with ``serialize``) to use a custom
      serialization format, or otherwise modify the behavior.

      Raise ``CacheMiss`` in order to simulate a cache miss for the relevant
      key, i.e., ``get`` will return None and ``get_multi`` will omit the key
      from the returned mapping. This can be used to recover gracefully from
      version skew (e.g., retrieving a value that was pickled by a different,
      incompatible code version).

   .. data:: behaviors

      The behaviors used by the underlying libmemcached object. See
      :ref:`behaviors` for more information.
