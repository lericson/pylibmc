from pylibmc import autoconf
from tests import PylibmcTestCase

class AutoConfTests(PylibmcTestCase):
    def test_no_autoconf(self):
        self.mc.delete('AmazonElastiCache:cluster')
        self.assertRaises(autoconf.NoAutoconfFound, autoconf.elasticache)

    def test_autoconf(self):
        addrtup = (self.memcached_host, self.memcached_port)
        self.mc.set('AmazonElastiCache:cluster', ('12\nlocalhost|%s|%s' % addrtup).encode('ascii'))
        mc = autoconf.elasticache(address=('%s:%s' % addrtup))
        self.assert_(mc.set('a', 'b'))
        self.assertEqual(mc.get('a'), 'b')

    def test_autoconf_only_cname(self):
        addrtup = (self.memcached_host, self.memcached_port)
        self.mc.set('AmazonElastiCache:cluster', ('12\n%s||%s' % addrtup).encode('ascii'))
        mc = autoconf.elasticache(address=('%s:%s' % addrtup))
        self.assert_(mc.set('a', 'b'))
        self.assertEqual(mc.get('a'), 'b')
