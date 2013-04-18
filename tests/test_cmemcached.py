"""Ported cmemcached tests"""

# NOTE Don't write new tests here.
# These are ported from cmemcached to ensure compatibility.

import pylibmc
from nose.tools import eq_
from tests import PylibmcTestCase
import six

a           = "a"
I_          = "I "
Do          = "Do"
I_Do        = "I Do"
n12345      = "12345"
num12345    = "num12345"
str12345    = "str12345"
hello_world = "hello world"
if six.PY3:
    a     = bytes(a,   'utf-8')
    I_    = bytes(I_,   'utf-8')
    Do    = bytes(Do,  'utf-8')
    I_Do  = bytes(I_Do, 'utf-8')
    n12345   = bytes(n12345,  'utf-8')
    num12345 = bytes(num12345, 'utf-8')
    str12345 = bytes(str12345,'utf-8')
    hello_world = bytes(hello_world, 'utf-8')


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
        if six.PY3:
            self.mc.set(b"a", b"valueA")
            self.mc.set(b"b", b"valueB")
            self.mc.set(b"c", b"valueC")
            result = self.mc.get_multi([b"a", b"b", b"c", b"", b"hello world"])
            eq_(result, {b'a':b'valueA', b'b':b'valueB', b'c':b'valueC'})
        else:
            self.mc.set("a", "valueA")
            self.mc.set("b", "valueB")
            self.mc.set("c", "valueC")
            result = self.mc.get_multi(["a", "b", "c", "", "hello world"])
            eq_(result, {'a':'valueA', 'b':'valueB', 'c':'valueC'})

    def testBigGetMulti(self):
        count = 10 ** 4
        if six.PY3:
            keys = [bytes('key%d' % i, 'ascii') for i in range(count)]
            pairs = zip(keys, [bytes('value%d' % i, 'ascii') for i in range(count)])
        else:
            keys = ['key%d' % i for i in xrange(count)]
            pairs = zip(keys, ['value%d' % i for i in xrange(count)])

        d = {}
        for key, value in pairs:
            d[key] = value
            self.mc.set(key, value)
        result = self.mc.get_multi(keys)
        eq_(result, d)

    def testFunnyDelete(self):
        s = ""
        if six.PY3: s = b""
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
