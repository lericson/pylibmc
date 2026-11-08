The ``verify_keys`` behavior is ignored. pylibmc now always checks keys itself
(see the ``ValueError`` for bad keys above), so setting ``verify_keys``, to any
value, in the constructor, with ``set_behaviors`` or through the ``behaviors``
mapping, emits a ``DeprecationWarning`` and does nothing, and ``get_behaviors()``
no longer lists it. Remove it from your code. Setting it to ``True`` used to
make libmemcached reject non-ASCII keys as well, and fail on a ``binary=True``
client with libmemcached 1.0.x; neither happens any more.
