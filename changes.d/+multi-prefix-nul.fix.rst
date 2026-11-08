``key_prefix`` in the ``*_multi`` methods no longer cuts the key short at a NUL
byte. With ``binary=True``, where a key may contain a NUL, ``set_multi`` and
``incr_multi`` used to store such a key under a shorter name than ``get_multi``
looked for.
