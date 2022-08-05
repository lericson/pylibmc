from pytest import raises
from pylibmc import autoconf
from tests import PylibmcTestCase

class AutoConfTests(PylibmcTestCase):
    def test_no_autoconf(self):
        self.mc.delete('AmazonElastiCache:cluster')
        with raises(autoconf.NoAutoconfFound):
            mc = autoconf.elasticache()

    def test_autoconf(self):
        addrtup = (self.memcached_host, self.memcached_port)
        self.mc.set('AmazonElastiCache:cluster', ('12\nlocalhost|%s|%s' % addrtup).encode('ascii'))
        mc = autoconf.elasticache(address=('%s:%s' % addrtup))
        assert mc.set('a', 'b')
        assert mc.get('a') == 'b'

    def test_autoconf_only_cname(self):
        addrtup = (self.memcached_host, self.memcached_port)
        self.mc.set('AmazonElastiCache:cluster', ('12\n%s||%s' % addrtup).encode('ascii'))
        mc = autoconf.elasticache(address=('%s:%s' % addrtup))
        assert mc.set('a', 'b')
        assert mc.get('a') == 'b'
