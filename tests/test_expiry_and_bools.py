"""Negative expiry times raise, and booleans round-trip as booleans.

Issues #202 (and #154): PyArg's "I" and "k" convert without overflow checking,
so a negative *time* silently became a huge unsigned number, which the text
protocol treated as already expired and the binary protocol as no expiry.

Issues #245 and #265: a bool was stored as an integer and came back as 1 or 0.
python-memcached stores it pickled (it checks the exact type, so bool is not
int there), and so does pylibmc now.
"""

import pickle
import uuid

import pylibmc
from pylibmc.test import make_test_client
from tests import PylibmcTestCase

f_pickle = 1 << 0


def key():
    return "t-" + uuid.uuid4().hex


class RawClient(pylibmc.Client):
    """get() returns what is stored: (bytes, flags)."""

    def deserialize(self, bytes_, flags):
        return bytes_, flags


class NegativeTimeTests(PylibmcTestCase):

    def clients(self):
        for binary in (False, True):
            yield make_test_client(binary=binary, behaviors={"cas": True})

    def test_negative_time_raises_and_stores_nothing(self):
        for c in self.clients():
            k = key()
            for op in (lambda: c.set(k, 1, -1),
                       lambda: c.add(k, 1, -1),
                       lambda: c.replace(k, 1, -1),
                       lambda: c.append(k, "x", -1),
                       lambda: c.prepend(k, "x", -1),
                       lambda: c.set(k, 1, time=-1),
                       lambda: c.set_multi({k: 1}, -1),
                       lambda: c.add_multi({k: 1}, time=-1)):
                with self.assertRaises(ValueError):
                    op()
            self.assertIsNone(c.get(k))

    def test_negative_time_raises_for_cas_and_touch(self):
        for c in self.clients():
            k = key()
            c.set(k, 1)
            _, cas = c.gets(k)
            with self.assertRaises(ValueError):
                c.cas(k, 2, cas, -1)
            with self.assertRaises(ValueError):
                c.touch(k, -1)
            # Neither touched nor changed the key.
            self.assertEqual(c.get(k), 1)
            c.delete(k)

    def test_too_large_time_raises(self):
        for c in self.clients():
            with self.assertRaises(ValueError):
                c.set(key(), 1, 2 ** 32)

    def test_zero_and_positive_times_still_work(self):
        for c in self.clients():
            k = key()
            self.assertTrue(c.set(k, 1, 0))
            self.assertTrue(c.set(k, 2, 100))
            self.assertEqual(c.get(k), 2)
            self.assertTrue(c.touch(k, 100))
            c.delete(k)


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

    def test_bool_is_stored_pickled_like_python_memcached(self):
        c = make_test_client(RawClient)
        k = key()
        for value in (True, False):
            c.set(k, value)
            data, flags = c.get(k)
            self.assertEqual(flags, f_pickle)
            self.assertIs(pickle.loads(data), value)
