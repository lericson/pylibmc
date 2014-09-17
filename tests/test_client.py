import functools
import sys
import time
import pylibmc
import _pylibmc
from pylibmc.test import make_test_client
from tests import PylibmcTestCase
from nose import SkipTest
from nose.tools import eq_, ok_

PY3 = sys.version_info[0] >= 3

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
        test_str = "test"
        ok_(bc.set(k, test_str))
        rk = next(iter(bc.get_multi([k])))
        eq_(k, rk)

    def test_cas(self):
        c = "cas"
        k = "testkey"
        mc = make_test_client(binary=False, behaviors={c: True})
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
        touch_test  = "touch-test"
        touch_test2 = "touch-test-2"
        tval = "touch-val"
        ok_(self.mc.set(touch_test, tval, 1))
        eq_(tval, self.mc.get(touch_test))
        time.sleep(2)
        eq_(None, self.mc.get(touch_test))

        self.mc.set(touch_test, tval, 1)
        eq_(tval, self.mc.get(touch_test))
        ok_(self.mc.touch(touch_test, 5))
        time.sleep(2)
        eq_(tval, self.mc.get(touch_test))

        ok_(not self.mc.touch(touch_test2, 100))

    def test_exceptions(self):
        self.assertRaises(TypeError, self.mc.set, 1, "hi")
        self.assertRaises(_pylibmc.Error, _pylibmc.client, [])
        self.assertRaises(_pylibmc.NotFound, self.mc.incr_multi,
            ('a', 'b', 'c'), key_prefix='x', delta=1)

    def test_utf8_encoding(self):
        k = "a key with a replacement character \ufffd and something non-BMP \U0001f4a3"
        k_enc = k.encode('utf-8')
        mc = make_test_client(binary=True)
        ok_(mc.set(k, 0))
        ok_(mc.get(k_enc) == 0)
