import datetime

import pylibmc
import _pylibmc
from pylibmc.test import make_test_client
from tests import PylibmcTestCase
from tests import get_refcounts


class RefcountTests(PylibmcTestCase):
    """Test that refcounts are invariant under pylibmc operations.

    In general, pylibmc should not retain any references to keys or values,
    so the refcounts of operands should be the same before and after operations.
    Assert that this is so, using sys.getrefcount.

    Caveats:
    1. In general, calling sys.getrefcount will change the refcount, because
    passing the object as an argument creates an additional reference.
    Therefore it is necessary to always measure the refcounts in exactly the
    same way.
    2. The test code itself must not retain any references to the refcounted
    objects (basically, don't define locals).
    """

    def _test_get(self, key, val):
        bc = make_test_client(binary=True)
        refcountables = [key, val]
        initial_refcounts = get_refcounts(refcountables)
        bc.set(key, val)
        assert get_refcounts(refcountables) == initial_refcounts
        assert bc.get(key) == val
        assert get_refcounts(refcountables) == initial_refcounts

    def test_get_complex_type(self):
        self._test_get("refcountest", datetime.datetime.fromtimestamp(0))

    def test_get_simple(self):
        self._test_get(b"refcountest2", 485295)

    def test_get_singleton(self):
        self._test_get(b"refcountest3", False)

    def test_get_with_default(self):
        bc = make_test_client(binary=True)
        key = b'refcountest4'
        val = 'some_value'
        default = object()
        refcountables = [key, val, default]
        initial_refcounts = get_refcounts(refcountables)
        bc.set(key, val)
        assert get_refcounts(refcountables) == initial_refcounts
        assert bc.get(key) == val
        assert get_refcounts(refcountables) == initial_refcounts
        assert bc.get(key, default) == val
        assert get_refcounts(refcountables) == initial_refcounts
        bc.delete(key)
        assert bc.get(key) is None
        assert get_refcounts(refcountables) == initial_refcounts
        assert bc.get(key, default) is default
        assert get_refcounts(refcountables) == initial_refcounts

    def test_get_multi(self):
        bc = make_test_client(binary=True)
        keys = ["first", "second", "", b""]
        value = "first_value"
        refcountables = keys + [value]
        initial_refcounts = get_refcounts(refcountables)
        bc.set(keys[0], value)
        assert get_refcounts(refcountables) == initial_refcounts
        assert bc.get_multi(keys) == {keys[0]: value}
        assert get_refcounts(refcountables) == initial_refcounts

    def test_get_multi_bytes_and_unicode(self):
        bc = make_test_client(binary=True)
        keys = ["third", b"fourth"]
        value = "another_value"
        kv = {k: value for k in keys}
        refcountables = [keys] + [value]
        initial_refcounts = get_refcounts(refcountables)
        bc.set_multi(kv)
        assert get_refcounts(refcountables) == initial_refcounts
        assert bc.get_multi(keys)[keys[0]] == value
        assert get_refcounts(refcountables) == initial_refcounts

    def test_delete(self):
        bc = make_test_client(binary=True)
        keys = ["delone", b"deltwo"]
        values = [b"valone", "valtwo"]
        refcountables = keys + values
        initial_refcounts = get_refcounts(refcountables)

        bc.set(keys[0], values[0])
        assert get_refcounts(refcountables) == initial_refcounts
        bc.set(keys[1], values[1])
        assert get_refcounts(refcountables) == initial_refcounts
        bc.delete(keys[0])
        assert get_refcounts(refcountables) == initial_refcounts
        bc.delete(keys[1])
        assert get_refcounts(refcountables) == initial_refcounts
        bc.delete(keys[0])
        assert get_refcounts(refcountables) == initial_refcounts
        bc.delete(keys[1])
        assert get_refcounts(refcountables) == initial_refcounts

    def test_incr(self):
        bc = make_test_client(binary=True)
        keys = [b"increment_key", "increment_key_again"]
        refcountables = keys
        initial_refcounts = get_refcounts(refcountables)

        bc.set(keys[0], 1)
        assert get_refcounts(refcountables) == initial_refcounts
        bc.incr(keys[0])
        assert get_refcounts(refcountables) == initial_refcounts
        bc.set(keys[1], 5)
        assert get_refcounts(refcountables) == initial_refcounts
        bc.incr(keys[1])
        assert get_refcounts(refcountables) == initial_refcounts

    def test_set_and_delete_multi(self):
        bc = make_test_client(binary=True)
        keys = ["delone", b"deltwo", "delthree", "delfour"]
        values = [b"valone", "valtwo", object(), 2]
        refcountables = keys + values
        initial_refcounts = get_refcounts(refcountables)

        bc.set_multi(dict(zip(keys, values)))
        assert get_refcounts(refcountables) == initial_refcounts
        bc.delete_multi([keys[0]])
        assert get_refcounts(refcountables) == initial_refcounts
        bc.delete_multi([keys[1]])
        assert get_refcounts(refcountables) == initial_refcounts
        bc.set_multi(dict(zip(keys, values)))
        assert get_refcounts(refcountables) == initial_refcounts
        bc.delete_multi(keys)
        assert get_refcounts(refcountables) == initial_refcounts
        bc.delete_multi(keys)
        assert get_refcounts(refcountables) == initial_refcounts

    def test_prefixes(self):
        bc = make_test_client(binary=True)
        keys = ["prefixone", b"prefixtwo"]
        prefix = "testprefix-"
        values = [b"valone", "valtwo"]
        refcountables = keys + values + [prefix]
        initial_refcounts = get_refcounts(refcountables)

        bc.set_multi(dict(zip(keys, values)), key_prefix=prefix)
        assert get_refcounts(refcountables) == initial_refcounts
        bc.get_multi(keys, key_prefix=prefix)
        assert get_refcounts(refcountables) == initial_refcounts
        bc.delete_multi([keys[0]], key_prefix=prefix)
        assert get_refcounts(refcountables) == initial_refcounts
        bc.delete_multi([keys[1]], key_prefix=prefix)
        assert get_refcounts(refcountables) == initial_refcounts
        bc.set_multi(dict(zip(keys, values)), key_prefix=prefix)
        assert get_refcounts(refcountables) == initial_refcounts
        bc.delete_multi(keys, key_prefix=prefix)
        assert get_refcounts(refcountables) == initial_refcounts
        bc.delete_multi(keys, key_prefix=prefix)
        assert get_refcounts(refcountables) == initial_refcounts

    def test_get_invalid_key(self):
        bc = make_test_client(binary=True)
        key = object()
        initial_refcount = get_refcounts([key])
        raised = False
        try:
            bc.get(key)
        except TypeError:
            raised = True
        assert raised
        assert get_refcounts([key]) == initial_refcount

    def test_cas(self):
        k = "testkey"
        val = 1138478589238
        mc = make_test_client(binary=False, behaviors={'cas': True})
        refcountables = [k, val]
        initial_refcounts = get_refcounts(refcountables)

        assert mc.set(k, 0)
        assert get_refcounts(refcountables) == initial_refcounts
        while True:
            rv, cas = mc.gets(k)
            assert get_refcounts(refcountables) == initial_refcounts
            assert mc.cas(k, rv + 1, cas)
            assert get_refcounts(refcountables) == initial_refcounts
            if rv == 10:
                break
