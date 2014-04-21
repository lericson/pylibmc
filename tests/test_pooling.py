from __future__ import with_statement

try:
    import Queue
except ImportError:
    import queue as Queue
import pylibmc
from nose.tools import eq_, ok_
from tests import PylibmcTestCase
import six

class PoolTestCase(PylibmcTestCase):
    pass

class ClientPoolTests(PoolTestCase):
    def test_simple(self):
        a_str = "a"
        if six.PY3: a_str = b"a"
        p = pylibmc.ClientPool(self.mc, 2)
        with p.reserve() as smc:
            ok_(smc)
            ok_(smc.set(a_str, 1))
            eq_(smc[a_str], 1)

    def test_exhaust(self):
        p = pylibmc.ClientPool(self.mc, 2)
        with p.reserve() as smc1:
            with p.reserve() as smc2:
                self.assertRaises(Queue.Empty, p.reserve().__enter__)

# TODO Thread-mapped pool tests
