===========
 Reference
===========

.. class:: pylibmc.Client(servers[, binary=False, behaviors=None])

   Interface to a set of memcached servers.

   *servers* is a sequence of strings specifying the servers to use.

   *binary* specifies whether or not to use the binary protocol to talk to the
   memcached servers.

   *behaviors*, if given, is passed to :meth:`Client.set_behaviors` after
   initialization.

   Supported transport mechanisms are TCP, UDP and UNIX domain sockets. The
   default transport type is TCP.

   To specify UDP, the server address should be prefixed with ``"udp:"``, as in
   ``"udp:127.0.0.1"``.

   To specify UNIX domain socket, the server address must contain a slash, as
   in ``"./foo.sock"``.

   Mixing transport types is prohibited by :mod:`pylibmc` as this is not supported by
   libmemcached.

   .. method:: clone() -> clone

      Clone client, making new connections as necessary.

   .. Reading

   .. method:: get(key) -> value

      Get *key* if it exists, otherwise ``None``.

   .. method:: get_multi(keys[, key_prefix=None]) -> values

      Get each of the keys in sequence *keys*.
      
      If *key_prefix* is given, specifies a string to prefix each of the values
      in *keys* with.

      Returns a mapping of each unprefixed key to its corresponding value in
      memcached. If a key doesn't exist, no corresponding key is set in the
      returned mapping.

   .. Writing

   .. method:: set(key, value[, time=0, min_compress_len=0]) -> success

      Set *key* to *value*.

      :param key: Key to use
      :param value: Value to set
      :param time: Time until expiry
      :param min_compress_len: Minimum length before compression is triggered

      If *time* is given, it specifies the number of seconds until *key* will
      expire. Default behavior is to never expire (equivalent of specifying
      ``0``).

      If *min_compress_len* is given, it specifies the maximum number of actual
      bytes stored in memcached before compression is used. Default behavior is
      to never compress (which is what ``0`` means). See :ref:`compression`.

   .. method:: set_multi(mapping, [, time=0, key_prefix=None]) -> failed_keys

      Set multiple keys as given by *mapping*.

      If *key_prefix* is specified, each of the keys in *mapping* is prepended
      with this value.

      Returns a list of keys which were not set for one reason or another,
      without their optional key prefix.

   .. method:: add(key, value[, time, min_compress_len]) -> success

      Sets *key* if it does not exist.

      .. seealso:: :meth:`set`, :meth:`replace`

   .. method:: replace(key, value[, time, min_compress_len]) -> success

      Sets *key* only if it already exists.

      .. seealso:: :meth:`set`, :meth:`add`

   .. method:: append(key, value) -> success

      Append *value* to *key* (i.e., ``m[k] = m[k] + v``).

      .. note:: Uses memcached's appending support, and therefore should never
                be used on keys which may be compressed or non-string values.

   .. method:: prepend(key, value) -> success

      Prepend *value* to *key* (i.e., ``m[k] = v + m[k]``).

      .. note:: Uses memcached's prepending support, and therefore should never
                be used on keys which may be compressed or non-string values.

   .. method:: incr(key[, delta=1]) -> value

      Increment value at *key* by *delta*.

      Returns the new value for *key*, after incrementing.

      Works for both strings and integer types.

      .. note:: There is currently no way to set a default for *key* when
                incrementing.

   .. method:: decr(key[, delta=1]) -> value

      Decrement value at *key* by *delta*.

      Returns the new value for *key*, after decrementing.

      Works for both strings and integer types, but will never decrement below
      zero.

      .. note:: There is currently no way to set a default for *key* when
                decrementing.

   .. Deleting

   .. method:: delete(key[, time=0]) -> deleted

      Delete *key* if it exists.

      If *time* is non-zero, this is equivalent of setting an expiry time for a
      key, i.e., the key will cease to exist after that many seconds.

      Returns ``True`` if the key was deleted, ``False`` otherwise (as is the case if
      it wasn't set in the first place.)

      .. note:: Some versions of libmemcached are unable to set *time* for a
                delete. This is true of versions up until at least 0.38.

   .. method:: delete_multi(keys[, time=0, key_prefix=None]) -> deleted

      Delete each of key in the sequence *keys*.

      :param keys: Sequence of keys to delete
      :param time: Number of seconds until the keys are deleted
      :param key_prefix: Prefix for the keys to delete

      If *time* is zero, the keys are deleted immediately.

      Returns ``True`` if all keys were successfully deleted, ``False``
      otherwise (as is the case if it wasn't set in the first place.)

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

   .. data:: behaviors

      The behaviors used by the underlying libmemcached object. See
      :ref:`behaviors` for more information.
