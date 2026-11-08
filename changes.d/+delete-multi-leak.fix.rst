``delete_multi`` no longer leaks a reference to the key each time one of its
keys is rejected (too long, or with the new key check) or the underlying
``delete`` fails, which made the process grow by that much on every such call.
