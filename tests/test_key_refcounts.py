"""Clients must release the normalized key on every early return.

_key_normalized_obj hands back a new reference (possibly to the very object
the caller passed in), so a return that forgets to release it leaks one
reference per call. A fresh key object makes the leak visible as drift that
grows with the number of calls.
"""

import uuid

from pylibmc.test import make_test_client
from tests import PylibmcTestCase, get_refcounts


class KeyRefcountTests(PylibmcTestCase):

    def test_gets_without_cas_behavior_releases_key(self):
        c = make_test_client(binary=False)  # no "cas" behavior
        key = uuid.uuid4().hex.encode()
        before = get_refcounts([key])
        for _ in range(1000):
            with self.assertRaises(ValueError):
                c.gets(key)
        assert get_refcounts([key]) == before

    def test_empty_key_releases_key(self):
        # The empty bytes object is a shared singleton (immortal on new
        # Pythons, where this cannot fail), but a drift shows on older ones.
        c = make_test_client(binary=False, behaviors={"cas": True})
        before = get_refcounts([b""])
        for _ in range(1000):
            assert c.get(b"") is None
            assert c.get("") is None
            assert c.gets(b"") == (None, None)
        assert get_refcounts([b""]) == before
