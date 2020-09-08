import sys
import time
import pylibmc
import _pylibmc
from pylibmc.test import make_test_client
from tests import PylibmcTestCase

PY3 = sys.version_info[0] >= 3

def requires_memcached_touch(arg):
    if _pylibmc.libmemcached_version_hex >= 0x01000002:
        return lambda func: func
    return unittest.skip("old memcached version")

class ClientTests(PylibmcTestCase):
    def test_zerokey(self):
        bc = make_test_client(binary=True)
        k = "\x00\x01"
        test_str = "test"
        self.assertTrue(bc.set(k, test_str))
        rk = next(iter(bc.get_multi([k])))
        self.assertEqual(k, rk)

    def test_cas(self):
        c = "cas"
        k = "testkey"
        mc = make_test_client(binary=False, behaviors={c: True})
        self.assertTrue(mc.set(k, 0))
        while True:
            rv, cas = mc.gets(k)
            self.assertTrue(mc.cas(k, rv + 1, cas))
            if rv == 10:
                break

    def testBehaviors(self):
        expected_behaviors = [
            'auto_eject', 'buffer_requests', 'cas', 'connect_timeout',
            'distribution', 'failure_limit', 'hash', 'ketama', 'ketama_hash',
            'ketama_weighted', 'no_block', 'num_replicas', 'pickle_protocol',
            'receive_timeout', 'retry_timeout', 'send_timeout',
            'tcp_keepalive', 'tcp_nodelay', 'verify_keys']

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
        self.assertEqual(sorted_list(expected_behaviors),
            sorted_list(actual_behaviors))

    @requires_memcached_touch
    def test_touch(self):
        touch_test  = "touch-test"
        touch_test2 = "touch-test-2"
        tval = "touch-val"
        self.assertTrue(self.mc.set(touch_test, tval, 1))
        self.assertEqual(tval, self.mc.get(touch_test))
        time.sleep(2)
        self.assertEqual(None, self.mc.get(touch_test))

        self.mc.set(touch_test, tval, 1)
        self.assertEqual(tval, self.mc.get(touch_test))
        self.assertTrue(self.mc.touch(touch_test, 5))
        time.sleep(2)
        self.assertEqual(tval, self.mc.get(touch_test))

        self.assertTrue(not self.mc.touch(touch_test2, 100))

    def test_exceptions(self):
        self.assertRaises(TypeError, self.mc.set, 1, "hi")
        self.assertRaises(_pylibmc.Error, _pylibmc.client, [])
        self.assertRaises(_pylibmc.NotFound, self.mc.incr_multi,
            ('a', 'b', 'c'), key_prefix='x', delta=1)

    def test_utf8_encoding(self):
        k = "a key with a replacement character \ufffd and something non-BMP \U0001f4a3"
        k_enc = k.encode('utf-8')
        mc = make_test_client(binary=True)
        self.assertTrue(mc.set(k, 0))
        self.assertTrue(mc.get(k_enc) == 0)

    def test_get_with_default(self):
        mc = make_test_client(binary=True)
        key = 'get-api-test'
        mc.delete(key)
        self.assertEqual(mc.get(key), None)
        default = object()
        assert mc.get(key, default) is default

    def test_none_values(self):
        mc = make_test_client(binary=True)
        mc.set('none-test', None)
        self.assertEqual(mc.get('none-test'), None)
        self.assertEqual(mc.get('none-test', 'default'), None)
        # formerly, this would raise a KeyError, which was incorrect
        self.assertEqual(mc['none-test'], None)
        assert 'none-test' in mc
