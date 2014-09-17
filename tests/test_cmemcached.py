"""Ported cmemcached tests"""

# NOTE Don't write new tests here.
# These are ported from cmemcached to ensure compatibility.

import pylibmc
from nose.tools import eq_
from tests import PylibmcTestCase

a           = "a"
I_          = b"I "
Do          = b"Do"
I_Do        = b"I Do"
n12345      = "12345"
num12345    = "num12345"
str12345    = "str12345"
hello_world = "hello world"


class TestCmemcached(PylibmcTestCase):
    def testSetAndGet(self):
        self.mc.set(num12345, 12345)
        eq_(self.mc.get(num12345), 12345)
        self.mc.set(str12345, n12345)
        eq_(self.mc.get(str12345), n12345)

    def testDelete(self):
        self.mc.set(str12345, n12345)
        #delete return True on success, otherwise False
        assert self.mc.delete(str12345)
        assert self.mc.get(str12345) is None

        # This test only works with old memcacheds. This has become a "client
        # error" in memcached.
        try:
            assert not self.mc.delete(hello_world)
        except pylibmc.ClientError:
            pass

    def testGetMulti(self):
        self.mc.set("a", "valueA")
        self.mc.set("b", "valueB")
        self.mc.set("c", "valueC")
        result = self.mc.get_multi(["a", "b", "c", "", "hello world"])
        eq_(result, {'a': 'valueA', 'b': 'valueB', 'c': 'valueC'})

    def testBigGetMulti(self):
        count = 10 ** 4
        # Python 2: .encode() is a no-op on these byte strings since they
        # only contain bytes that can be implicitly decoded as ASCII.
        keys = ['key%d' % i for i in range(count)]
        pairs = zip(keys, ['value%d' % i for i in range(count)])

        d = {}
        for key, value in pairs:
            d[key] = value
            self.mc.set(key, value)
        result = self.mc.get_multi(keys)
        eq_(result, d)

    def testFunnyDelete(self):
        s = ""
        assert not self.mc.delete(s)

    def testAppend(self):
        self.mc.delete(a)
        self.mc.set(a, I_)
        assert self.mc.append(a, Do)
        eq_(self.mc.get(a), I_Do)

    def testPrepend(self):
        self.mc.delete(a)
        self.mc.set(a, Do)
        assert self.mc.prepend(a, I_)
        eq_(self.mc.get(a), I_Do)
