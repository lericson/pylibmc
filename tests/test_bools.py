"""Booleans round-trip as booleans (issue #245).

A bool was stored as an integer and came back as 1 or 0. It is still stored as
an integer, but with an extra flag (bit 31) that pylibmc reads back as a bool;
readers that do not know the flag see the integer.
"""

import sys
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
        for payload in (b'', b'abc', b'1x', b'True', b'1.5', b'- 1'):
            with self.assertRaises(ValueError):
                c.deserialize(payload, f_int | f_bool)
        with self.assertRaises(TypeError):
            c.deserialize(None, f_int | f_bool)

    def test_bool_flag_with_another_number_is_an_int(self):
        # The server keeps the flags when it changes a value (issue #356).
        c = make_test_client()
        for payload, value in ((b'2', 2), (b'-1', -1), (b'10', 10),
                               (b'9 ', 9), (b'42', 42),
                               (b'18446744073709551616', 2 ** 64)):
            got = c.deserialize(payload, f_int | f_bool)
            self.assertEqual(got, value)
            self.assertIs(type(got), int)
        self.assertIs(c.deserialize(b'1', f_int | f_bool), True)
        self.assertIs(c.deserialize(b'0', f_int | f_bool), False)

    def test_deserialize_error_does_not_leak(self):
        c = make_test_client()
        n = 2000
        # Fresh bytes objects of the payload type, many times over.
        refs = []
        for _ in range(n):
            payload = uuid.uuid4().hex.encode()
            refs.append(sys.getrefcount(payload))
            with self.assertRaises(ValueError):
                c.deserialize(payload, f_int | f_bool)
            self.assertEqual(sys.getrefcount(payload), refs[-1])


class ChangedByServerTests(PylibmcTestCase):
    """The server changes the value but keeps the bool flag (issue #356)."""

    def clients(self):
        for binary in (False, True):
            yield make_test_client(binary=binary)

    def check(self, c, prepare, expected):
        k, other = key(), key()
        c.set(other, "healthy")
        c.set(k, True)
        prepare(c, k)
        for got in (c.get(k), c.get_multi([k, other])[k],
                    c.get_multi([other, k])[k]):
            self.assertEqual(got, expected)
            self.assertIs(type(got), int)
        self.assertEqual(c.get_multi([k, other])[other], "healthy")
        c.delete_multi([k, other])

    def test_incr(self):
        for c in self.clients():
            self.check(c, lambda c, k: c.incr(k), 2)
            self.check(c, lambda c, k: c.incr(k, 41), 42)

    def test_decr(self):
        for c in self.clients():
            # 1 + 9 = 10, then 10 - 1 = 9 (memcached may pad with a space)
            self.check(c, lambda c, k: (c.incr(k, 9), c.decr(k)), 9)

    def test_append(self):
        for c in self.clients():
            self.check(c, lambda c, k: c.append(k, "5"), 15)

    def test_prepend(self):
        for c in self.clients():
            self.check(c, lambda c, k: c.prepend(k, "2"), 21)

    def test_zero_and_one_are_still_bools(self):
        for c in self.clients():
            k = key()
            c.set(k, True)
            c.decr(k)
            self.assertIs(c.get(k), False)
            c.incr(k)
            self.assertIs(c.get(k), True)
            self.assertIs(c.get_multi([k])[k], True)
            c.delete(k)

    def test_non_numeric_append_is_a_value_error(self):
        for c in self.clients():
            k, other = key(), key()
            c.set(other, "healthy")
            c.set(k, True)
            c.append(k, "x")
            with self.assertRaises(ValueError):
                c.get(k)
            with self.assertRaises(ValueError):
                c.get_multi([k])
            # Same error as for a corrupt integer payload.
            raw = make_test_client(RawClient, binary=False)
            self.assertEqual(raw.get(k), (b'1x', f_int | f_bool))
            with self.assertRaises(ValueError):
                c.deserialize(b'1x', f_int)
            self.assertEqual(c.get(other), "healthy")
            c.delete_multi([k, other])
