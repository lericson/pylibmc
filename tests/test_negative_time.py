"""A negative expiry time raises ValueError (issues #202 and #154).

PyArg's "I" and "k" convert without overflow checking, so a negative *time*
silently became a huge unsigned number, which the text protocol treated as
already expired and the binary protocol as no expiry.
"""

import uuid

from pylibmc.test import make_test_client
from tests import PylibmcTestCase


def key():
    return "t-" + uuid.uuid4().hex


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
