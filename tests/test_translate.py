from pylibmc.client import translate_server_spec
import _pylibmc

def test_translate():
    assert (translate_server_spec("111.122.133.144")           == (_pylibmc.server_type_tcp, "111.122.133.144", 11211, 1))
    assert (translate_server_spec("111.122.133.144:5555")      == (_pylibmc.server_type_tcp, "111.122.133.144",  5555, 1))
    assert (translate_server_spec("udp:199.299.399.499:5555")  == (_pylibmc.server_type_udp, "199.299.399.499",  5555, 1))
    assert (translate_server_spec("udp:[abcd:abcd::1]:5555")   == (_pylibmc.server_type_udp, "abcd:abcd::1",     5555, 1))
    assert (translate_server_spec("111.122.133.144:5555:2")    == (_pylibmc.server_type_tcp, "111.122.133.144",  5555, 2))
    assert (translate_server_spec("111.122.133.144", weight=2) == (_pylibmc.server_type_tcp, "111.122.133.144", 11211, 2))
    assert (translate_server_spec("udp:[abcd:abcd::1]:5555:2") == (_pylibmc.server_type_udp, "abcd:abcd::1",     5555, 2))
