"""UDP servers ("udp:host:port").

Measured against libmemcached 1.0.18 and memcached 1.6: a UDP client can only
send. Stores, deletes, incr and flush are written as fire-and-forget datagrams
(pylibmc turns on the ``_noreply`` behavior), their return values mean "sent",
not "stored", and reads are refused with NotSupportedError.

The end-to-end tests start their own memcached with UDP enabled (modern
memcached disables it by default) and use a TCP client on the same server to
see what the datagrams did. They skip without a ``memcached`` binary, or fail
when PYLIBMC_TEST_MEMCACHED_REQUIRED=1.
"""

import uuid

import pylibmc
import pytest

from tests.memcached_proc import MemcachedTestCase, wait_until


def key():
    return "udp-" + uuid.uuid4().hex


def test_udp_client_needs_no_server():
    mc = pylibmc.Client(["udp:127.0.0.1:1"])
    # UDP has no replies, so pylibmc/libmemcached run the client in noreply mode.
    assert mc.get_behaviors()["_noreply"] == 1
    assert pylibmc.Client(["127.0.0.1:1"]).get_behaviors()["_noreply"] == 0


def test_udp_translate_marks_udp():
    from pylibmc.client import translate_server_spec
    import _pylibmc
    assert translate_server_spec("udp:127.0.0.1:99")[0] == _pylibmc.server_type_udp


@pytest.mark.parametrize("other", ["127.0.0.1:2", "/tmp/nonexistent.sock"])
def test_udp_cannot_mix_transports(other):
    with pytest.raises(ValueError, match="can't mix transport types"):
        pylibmc.Client(["udp:127.0.0.1:1", other])
    with pytest.raises(ValueError, match="can't mix transport types"):
        pylibmc.Client([other, "udp:127.0.0.1:1"])


def test_udp_to_closed_port_still_refuses_reads():
    mc = pylibmc.Client(["udp:127.0.0.1:1"])
    with pytest.raises(pylibmc.NotSupportedError):
        mc.get(key())


class UdpRoundTrip(object):
    binary = False
    flavor = {"udp": True}

    def setUp(self):
        super(UdpRoundTrip, self).setUp()
        s = self.server
        self.udp = pylibmc.Client(["udp:127.0.0.1:%d" % s.udp_port],
                                  binary=self.binary)
        self.tcp = pylibmc.Client(["127.0.0.1:%d" % s.tcp_port],
                                  binary=self.binary)

    def eventually(self, k, expected):
        """Wait (bounded) for TCP to see *expected* under *k*; UDP is async."""
        wait_until(lambda: self.tcp.get(k) == expected)
        self.assertEqual(self.tcp.get(k), expected)

    def test_set_arrives(self):
        k = key()
        self.assertTrue(self.udp.set(k, "v"))
        self.eventually(k, "v")

    def test_set_larger_than_a_packet_arrives(self):
        k, v = key(), "x" * 5000
        self.assertTrue(self.udp.set(k, v))
        self.eventually(k, v)

    def test_delete_and_incr_arrive(self):
        k, n = key(), key()
        self.udp.set(k, "v")
        self.eventually(k, "v")
        self.udp.delete(k)
        self.eventually(k, None)
        self.udp.set(n, "1")
        self.eventually(n, "1")
        self.udp.incr(n)
        self.eventually(n, "2")

    def test_reads_are_not_supported(self):
        k = key()
        self.tcp.set(k, "v")
        with self.assertRaises(pylibmc.NotSupportedError):
            self.udp.get(k)
        with self.assertRaises(pylibmc.NotSupportedError):
            self.udp.get_multi([k])


class TestUdpText(UdpRoundTrip, MemcachedTestCase):
    pass


class TestUdpBinary(UdpRoundTrip, MemcachedTestCase):
    binary = True
