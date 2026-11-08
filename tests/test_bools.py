"""Booleans round-trip as booleans (issue #245).

A bool was stored as an integer and came back as 1 or 0. It is still stored as
an integer, but with an extra flag (bit 31) that pylibmc reads back as a bool;
readers that do not know the flag see the integer.
"""

import uuid

import pylibmc
from pylibmc.test import make_test_client
from tests import PylibmcTestCase

f_int = 1 << 1
f_bool = 1 << 31


def key():
    return "t-" + uuid.uuid4().hex


class RawClient(pylibmc.Client):
    """get() returns what is stored: (bytes, flags)."""

    def deserialize(self, bytes_, flags):
        return bytes_, flags


class BoolTests(PylibmcTestCase):

    def test_bools_round_trip(self):
        for binary in (False, True):
            c = make_test_client(binary=binary, behaviors={"cas": True})
            for value in (True, False):
                k = key()
                c.set(k, value)
                self.assertIs(c.get(k), value)
                self.assertIs(c.get_multi([k])[k], value)
                self.assertIs(c.gets(k)[0], value)
                c.delete(k)

    def test_set_multi_round_trips_bools(self):
        c = make_test_client()
        k1, k2 = key(), key()
        c.set_multi({k1: True, k2: False})
        got = c.get_multi([k1, k2])
        self.assertIs(got[k1], True)
        self.assertIs(got[k2], False)

    def test_ints_are_still_ints(self):
        c = make_test_client()
        k = key()
        for value in (0, 1, -1, 2 ** 40):
            c.set(k, value)
            got = c.get(k)
            self.assertEqual(got, value)
            self.assertIs(type(got), int)

    def test_bool_is_an_integer_with_its_own_flag(self):
        c = make_test_client(RawClient)
        k = key()
        for value, payload in ((True, b'1'), (False, b'0')):
            c.set(k, value)
            self.assertEqual(c.get(k), (payload, f_int | f_bool))

    def test_readers_without_the_flag_see_the_integer(self):
        # A reader that ignores bit 31 (older pylibmc, python-memcached) sees
        # the stored payload as a plain integer.
        raw = make_test_client(RawClient)
        c = make_test_client()
        k = key()
        for value in (True, False):
            raw.set(k, value)
            data, flags = raw.get(k)
            got = c.deserialize(data, flags & ~f_bool)
            self.assertEqual(got, int(value))
            self.assertIs(type(got), int)

    def test_bool_flag_with_a_bad_payload_raises(self):
        c = make_test_client()
        for payload in (b'', b'2', b'11', b'True'):
            with self.assertRaises(ValueError):
                c.deserialize(payload, f_int | f_bool)
        with self.assertRaises(TypeError):
            c.deserialize(None, f_int | f_bool)
