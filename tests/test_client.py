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


    def test_override_deserialize(self):
        class MyClient(pylibmc.Client):
            ignored = []
            def deserialize(self, bytes):
                try:
                    return super(MyClient, self).deserialize(bytes)
                except Exception, error:
                    self.ignored.append(error)
                    raise pylibmc.CacheMiss

        global MyObject # Needed by the pickling system.
        class MyObject(object):
            def __getstate__(self):
                return dict(a=1)
            def __eq__(self, other):
                return type(other) is type(self)
            def __setstate__(self, d):
                assert d['a'] == 1

        c = make_test_client(MyClient)
        eq_(c.get('notathing'), None)

        c['foo'] = 'foo'
        c['myobj'] = MyObject()
        c['noneobj'] = None

        # Show that everything is initially regular.
        eq_(c.get('myobj'), MyObject())
        eq_(c.get_multi(['foo', 'myobj', 'noneobj', 'cachemiss']),
                dict(foo='foo', myobj=MyObject(), noneobj=None))

        # Show that the subclass can transform unpickling issues into a cache misses.
        del MyObject # Break unpickling

        eq_(c.get('myobj'), None)
        eq_(c.get_multi(['foo', 'myobj', 'noneobj', 'cachemiss']),
                dict(foo='foo', noneobj=None))

        # The ignored errors are "AttributeError: test.test_client has no MyObject"
        eq_(len(MyClient.ignored), 2)
        assert all(isinstance(error, AttributeError) for error in MyClient.ignored)


# vim:et:sts=4:sw=4:
