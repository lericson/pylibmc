import pylibmc
from pylibmc.test import make_test_client
from tests import PylibmcTestCase
from nose.tools import eq_, ok_

class ClientTests(PylibmcTestCase):
    def test_zerokey(self):
        bc = make_test_client(binary=True)
        k = "\x00\x01"
        ok_(bc.set(k, "test"))
        rk = bc.get_multi([k]).keys()[0]
        eq_(k, rk)

    def test_cas(self):
        k = "testkey"
        mc = make_test_client(binary=False, behaviors={"cas": True})
        ok_(mc.set(k, 0))
        while True:
            rv, cas = mc.gets(k)
            ok_(mc.cas(k, rv + 1, cas))
            if rv == 10:
                break
