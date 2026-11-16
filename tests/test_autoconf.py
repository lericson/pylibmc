from pytest import raises
from pylibmc import autoconf
from tests import PylibmcTestCase, server_address

class AutoConfTests(PylibmcTestCase):
    def test_no_autoconf(self):
        self.mc.delete('AmazonElastiCache:cluster')
        with raises(autoconf.NoAutoconfFound):
            mc = autoconf.elasticache(address=server_address())

    def test_autoconf(self):
        host, port = server_address().rsplit(':', 1)
        self.mc.set('AmazonElastiCache:cluster', ('12\nlocalhost|%s|%s' % (host, port)).encode('ascii'))
        mc = autoconf.elasticache(address=server_address())
        assert mc.set('a', 'b')
        assert mc.get('a') == 'b'

    def test_autoconf_only_cname(self):
        host, port = server_address().rsplit(':', 1)
        self.mc.set('AmazonElastiCache:cluster', ('12\n%s||%s' % (host, port)).encode('ascii'))
        mc = autoconf.elasticache(address=server_address())
        assert mc.set('a', 'b')
        assert mc.get('a') == 'b'
