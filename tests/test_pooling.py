try:
    import queue
except ImportError:
    import Queue as queue

import pylibmc
from tests import PylibmcTestCase

class PoolTestCase(PylibmcTestCase):
    pass

class ClientPoolTests(PoolTestCase):
    def test_simple(self):
        a_str = "a"
        p = pylibmc.ClientPool(self.mc, 2)
        with p.reserve() as smc:
            self.assertTrue(smc)
            self.assertTrue(smc.set(a_str, 1))
            self.assertEqual(smc[a_str], 1)

    def test_exhaust(self):
        p = pylibmc.ClientPool(self.mc, 2)
        with p.reserve() as smc1:
            with p.reserve() as smc2:
                self.assertRaises(queue.Empty, p.reserve().__enter__)

class ThreadMappedPoolTests(PoolTestCase):
    def test_simple(self):
        a_str = "a"
        p = pylibmc.ThreadMappedPool(self.mc)
        with p.reserve() as smc:
            self.assertTrue(smc)
            self.assertTrue(smc.set(a_str, 1))
            self.assertEqual(smc[a_str], 1)
