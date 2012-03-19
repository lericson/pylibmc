"""Ported cmemcached tests"""

import pylibmc
import _pylibmc
from nose.tools import eq_, assert_equals
from tests import PylibmcTestCase


class TestCmemcached(PylibmcTestCase):
    def testSetAndGet(self):
        self.mc.set("num12345", 12345)
        eq_(self.mc.get("num12345"), 12345)
        self.mc.set("str12345", "12345")
        eq_(self.mc.get("str12345"), "12345")

    def testDelete(self):
        self.mc.set("str12345", "12345")
        #delete return True on success, otherwise False
        assert self.mc.delete("str12345")
        assert self.mc.get("str12345") is None

        # This test only works with old memcacheds. This has become a "client
        # error" in memcached.
        try:
            assert not self.mc.delete("hello world")
        except pylibmc.ClientError:
            pass

    def testGetMulti(self):
        self.mc.set("a", "valueA")
        self.mc.set("b", "valueB")
        self.mc.set("c", "valueC")
        result = self.mc.get_multi(["a", "b", "c", "", "hello world"])
        eq_(result, {'a':'valueA', 'b':'valueB', 'c':'valueC'})

    def testBigGetMulti(self):
        count = 10 ** 4
        keys = ['key%d' % i for i in xrange(count)]
        pairs = zip(keys, ['value%d' % i for i in xrange(count)])
        for key, value in pairs:
            self.mc.set(key, value)
        result = self.mc.get_multi(keys)
        eq_(result, dict(pairs))

    def testFunnyDelete(self):
        assert not self.mc.delete("")

    def testAppend(self):
        self.mc.delete("a")
        self.mc.set("a", "I ")
        assert self.mc.append("a", "Do")
        eq_(self.mc.get("a"), "I Do")

    def testPrepend(self):
        self.mc.delete("a")
        self.mc.set("a", "Do")
        assert self.mc.prepend("a", "I ")
        eq_(self.mc.get("a"), "I Do")

    def testBehaviors(self):
        expected_behaviors = [
            'auto_eject', 'buffer_requests', 'cas', 'connect_timeout',
            'distribution', 'failure_limit', 'hash', 'ketama', 'ketama_hash',
            'ketama_weighted', 'no_block', 'num_replicas', 'receive_timeout',
            'retry_timeout', 'send_timeout', 'tcp_nodelay', 'verify_keys']

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

        assert_equals(sorted(expected_behaviors), sorted(actual_behaviors))
