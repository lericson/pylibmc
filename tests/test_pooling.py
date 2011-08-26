from __future__ import with_statement

import Queue
import pylibmc
from nose.tools import eq_, ok_
from tests import PylibmcTestCase

class PoolTestCase(PylibmcTestCase):
    pass

class ClientPoolTests(PoolTestCase):
    def test_simple(self):
        p = pylibmc.ClientPool(self.mc, 2)
        with p.reserve() as smc:
            ok_(smc)
            ok_(smc.set("a", 1))
            eq_(smc["a"], 1)

    def test_exhaust(self):
        p = pylibmc.ClientPool(self.mc, 2)
        with p.reserve() as smc1:
            with p.reserve() as smc2:
                self.assertRaises(Queue.Empty, p.reserve().__enter__)

# TODO Thread-mapped pool tests
