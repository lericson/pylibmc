from pylibmc.client import translate_server_spec
import _pylibmc
from tests import PylibmcTestCase

class TranslateTests(PylibmcTestCase):
    def test_translate(self):
        self.assertEqual(translate_server_spec("111.122.133.144"),
                         (_pylibmc.server_type_tcp, "111.122.133.144", 11211, 1))
    
    def test_translate(self):
        self.assertEqual(translate_server_spec("111.122.133.144:5555"),
                         (_pylibmc.server_type_tcp, "111.122.133.144", 5555, 1))
    
    def test_udp_translate(self):
        self.assertEqual(translate_server_spec("udp:199.299.399.499:5555"),
                         (_pylibmc.server_type_udp, "199.299.399.499", 5555, 1))
    
    def test_udp_translate_ipv6(self):
        self.assertEqual(translate_server_spec("udp:[abcd:abcd::1]:5555"),
                         (_pylibmc.server_type_udp, "abcd:abcd::1", 5555, 1))
    
    def test_translate_with_weight_string(self):
        self.assertEqual(translate_server_spec("111.122.133.144:5555:2"),
                         (_pylibmc.server_type_tcp, "111.122.133.144", 5555, 2))
    
    def test_translate_with_weight_kwd(self):
        self.assertEqual(translate_server_spec("111.122.133.144", weight=2),
                         (_pylibmc.server_type_tcp, "111.122.133.144", 11211, 2))
    
    def test_udp_translate_ipv6_with_weight(self):
        self.assertEqual(translate_server_spec("udp:[abcd:abcd::1]:5555:2"),
                         (_pylibmc.server_type_udp, "abcd:abcd::1", 5555, 2))

