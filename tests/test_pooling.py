import queue

import pylibmc
from tests import PylibmcTestCase
from pytest import raises

class PoolTestCase(PylibmcTestCase):
    pass

class ClientPoolTests(PoolTestCase):
    def test_simple(self):
        a_str = "a"
        p = pylibmc.ClientPool(self.mc, 2)
        with p.reserve() as smc:
            assert smc
            assert smc.set(a_str, 1)
            assert smc[a_str] == 1

    def test_exhaust(self):
        p = pylibmc.ClientPool(self.mc, 2)
        with p.reserve() as mc1:
            assert mc1 is not None
            with p.reserve() as mc2:
                assert mc2 is not None
                assert mc2 is not mc1
                with raises(queue.Empty):
                    # This third time will fail.
                    with p.reserve():
                        pass

class ThreadMappedPoolTests(PoolTestCase):
    def test_simple(self):
        a_str = "a"
        p = pylibmc.ThreadMappedPool(self.mc)
        with p.reserve() as smc:
            assert smc
            assert smc.set(a_str, 1)
            assert smc[a_str] == 1
