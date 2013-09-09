import functools
import time
import pylibmc
import _pylibmc
from pylibmc.test import make_test_client
from tests import PylibmcTestCase
from nose import SkipTest
from nose.tools import eq_, ok_

def requires_memcached_touch(test):
    @functools.wraps(test)
    def wrapper(*args, **kwargs):
        if _pylibmc.libmemcached_version_hex >= 0x01000002:
            return test(*args, **kwargs)
        raise SkipTest

    return wrapper

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

    def testBehaviors(self):
        expected_behaviors = [
            'auto_eject', 'buffer_requests', 'cas', 'connect_timeout',
            'distribution', 'failure_limit', 'hash', 'ketama', 'ketama_hash',
            'ketama_weighted', 'no_block', 'num_replicas', 'receive_timeout',
            'retry_timeout', 'send_timeout', 'tcp_keepalive', 'tcp_nodelay',
            'verify_keys']

        # Since some parts of pyblibmc's functionality depend on the
        # libmemcached version, programatically check for the expected values
        # (see _pylibmcmodule.h for the complete list of #ifdef versions)
        if _pylibmc.libmemcached_version_hex >= 0x00049000:
            expected_behaviors.append("remove_failed")
        if _pylibmc.libmemcached_version_hex >= 0x01000003:
            expected_behaviors.append("dead_timeout")

        # Filter out private keys
        actual_behaviors = [
                behavior for behavior in self.mc.behaviors
                if not behavior.startswith('_')]

        sorted_list = lambda L: list(sorted(L))
        eq_(sorted_list(expected_behaviors),
            sorted_list(actual_behaviors))

    @requires_memcached_touch
    def test_touch(self):
        ok_(self.mc.set("touch-test", "touch-val", 1))
        eq_("touch-val", self.mc.get("touch-test"))
        time.sleep(2)
        eq_(None, self.mc.get("touch-test"))

        self.mc.set("touch-test", "touch-val", 1)
        eq_("touch-val", self.mc.get("touch-test"))
        ok_(self.mc.touch("touch-test", 5))
        time.sleep(2)
        eq_("touch-val", self.mc.get("touch-test"))

        ok_(not self.mc.touch("touch-test-2", 100))
