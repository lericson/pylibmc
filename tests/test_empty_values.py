"""Zero-length values must round-trip through every retrieval path.

libmemcached returns a NULL pointer for an empty value. Builds with asserts
enabled (no -DNDEBUG) used to abort in _PylibMC_deserialize_native; see
issue #291.
"""

import pylibmc
from pylibmc.test import make_test_client
from tests import PylibmcTestCase

f_pickle, f_int, f_long, f_zlib, f_text = (1 << i for i in range(5))

SERVERS = ["127.0.0.1:11211"]


class CustomDeserializeClient(pylibmc.Client):
    """Overriding deserialize() routes through the Python-level callback."""

    seen = None

    def deserialize(self, bytes_, flags):
        type(self).seen = (bytes_, flags)
        return super().deserialize(bytes_, flags)


class RawFlagsClient(pylibmc.Client):
    """Stores an empty payload with whatever flags are set on the client."""

    flags = 0

    def serialize(self, value):
        return b"", self.flags


class EmptyValueTests(PylibmcTestCase):

    def test_empty_roundtrip(self):
        for binary in (False, True):
            c = make_test_client(binary=binary, behaviors={"cas": True})
            for value in ("", b""):
                c.set("empty", value)
                self.assertEqual(c.get("empty"), value)
                self.assertIs(type(c.get("empty")), type(value))
                self.assertEqual(c.get_multi(["empty"]), {"empty": value})
                got, cas = c.gets("empty")
                self.assertEqual(got, value)
                self.assertIs(type(got), type(value))
            c.delete("empty")

    def test_empty_raw_flags(self):
        for binary in (False, True):
            c = RawFlagsClient(SERVERS, binary=binary, behaviors={"cas": True})
            keys = ("empty_text", "empty_long", "empty_pickle")
            try:
                c.flags = f_text
                c.set("empty_text", "x")
                self.assertEqual(c.get("empty_text"), "")
                self.assertEqual(c.get_multi(["empty_text"]),
                                 {"empty_text": ""})
                self.assertEqual(c.gets("empty_text")[0], "")
                # An empty integer is not valid; it must raise, not abort.
                c.flags = f_long
                c.set("empty_long", "x")
                with self.assertRaises(ValueError):
                    c.get("empty_long")
                # Likewise an empty pickle.
                c.flags = f_pickle
                c.set("empty_pickle", "x")
                with self.assertRaises(Exception):
                    c.get("empty_pickle")
            finally:
                for k in keys:
                    c.delete(k)

    def test_empty_with_custom_deserialize(self):
        for binary in (False, True):
            c = CustomDeserializeClient(SERVERS, binary=binary, behaviors={"cas": True})
            try:
                c.set("empty", b"")
                CustomDeserializeClient.seen = None
                self.assertEqual(c.get("empty"), b"")
                self.assertEqual(CustomDeserializeClient.seen, (b"", 0))
                self.assertEqual(c.get_multi(["empty"]), {"empty": b""})
                self.assertEqual(c.gets("empty")[0], b"")
            finally:
                c.delete("empty")
