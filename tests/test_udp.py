"""UDP servers ("udp:host:port").

Measured against libmemcached 1.0.18 and memcached 1.6: a UDP client can only
send. libmemcached runs it in noreply mode, so the server's answers are never
read. Stores, deletes and flush are written as fire-and-forget datagrams and
their return values mean "sent", not "stored". Reads are refused with
NotSupportedError by libmemcached; calls whose result would come from a reply
(incr, decr, incr_multi, cas, gets, exists) are refused by pylibmc with the same
NotSupportedError instead of returning a made-up value (#377).

The end-to-end tests start their own memcached with UDP enabled (modern
memcached disables it by default) and use a TCP client on the same server to
see what the datagrams did. They skip without a ``memcached`` binary, or fail
when PYLIBMC_TEST_MEMCACHED_REQUIRED=1.
"""

import time
import uuid

import pylibmc
import pytest
from pylibmc.pools import ClientPool, ThreadMappedPool

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


class UdpRoundTrip:
    binary = False
    flavor = {"udp": True}

    def setUp(self):
        super().setUp()
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

    def test_a_value_beyond_any_datagram_fails_loudly(self):
        # Larger than the 64 kB a UDP datagram can carry. (On the binary
        # protocol libmemcached then marks the server failed for a while.)
        with self.assertRaises(pylibmc.WriteError):
            self.udp.set(key(), "x" * 100000)

    def test_delete_arrives(self):
        k = key()
        self.udp.set(k, "v")
        self.eventually(k, "v")
        self.udp.delete(k)
        self.eventually(k, None)

    def test_reads_are_not_supported(self):
        k = key()
        self.tcp.set(k, "v")
        with self.assertRaises(pylibmc.NotSupportedError):
            self.udp.get(k)
        with self.assertRaises(pylibmc.NotSupportedError):
            self.udp.get_multi([k])


    def refused(self, mc):
        """Every call that would need the server's answer is refused."""
        k = key()
        calls = [
            lambda: mc.get(k),
            lambda: mc.get(k, "default"),
            lambda: mc.get_multi([k]),
            lambda: k in mc,
            lambda: mc.exists(k),
            lambda: mc.exists(k, master_key="g"),
            lambda: mc[k],
            lambda: mc.touch(k, 10),
            lambda: mc.get_stats(),
            lambda: mc.incr(k),
            lambda: mc.decr(k, 2),
            lambda: mc.incr(k, initial=1),
            lambda: mc.decr(k, 1, initial=5, expire=10),
            lambda: mc.incr_multi([k]),
            lambda: mc.cas(k, "v", 1),
            lambda: mc.gets(k),
        ]
        for call in calls:
            with self.assertRaises(pylibmc.NotSupportedError):
                call()

    def test_calls_needing_an_answer_raise(self):
        self.refused(self.udp)

    def test_cas_and_gets_raise_with_cas_behavior_too(self):
        mc = pylibmc.Client(["udp:127.0.0.1:%d" % self.server.udp_port],
                            binary=self.binary, behaviors={"cas": True})
        with self.assertRaises(pylibmc.NotSupportedError):
            mc.cas(key(), "v", 1)
        with self.assertRaises(pylibmc.NotSupportedError):
            mc.gets(key())

    def test_incr_refusal_names_udp(self):
        with self.assertRaisesRegex(pylibmc.NotSupportedError, "UDP"):
            self.udp.incr(key())

    def test_refused_calls_send_nothing(self):
        n = key()
        self.tcp.set(n, "1")
        for call in (lambda: self.udp.incr(n), lambda: self.udp.decr(n),
                     lambda: self.udp.incr_multi([n])):
            with self.assertRaises(pylibmc.NotSupportedError):
                call()
        time.sleep(0.2)
        self.assertEqual(self.tcp.get(n), "1")

    def test_clone_keeps_the_rule(self):
        self.refused(self.udp.clone())
        k = key()
        self.assertTrue(self.udp.clone().set(k, "c"))
        self.eventually(k, "c")

    def test_pools_keep_the_rule(self):
        pool = ClientPool(self.udp, 2)
        for _ in range(2):
            with pool.reserve() as mc:
                self.refused(mc)
        mapped = ThreadMappedPool(self.udp)
        with mapped.reserve() as mc:
            self.refused(mc)

    def test_fire_and_forget_writes_return_true(self):
        """True means "sent": it is returned even when the server would say no."""
        existing, missing = key(), key()
        self.tcp.set(existing, "v")
        u = self.udp
        self.assertTrue(u.add(existing, "other"))     # server: NOT_STORED
        self.assertTrue(u.replace(missing, "v"))      # server: NOT_STORED
        self.assertTrue(u.append(missing, "v"))
        self.assertTrue(u.prepend(missing, "v"))
        self.assertTrue(u.delete(missing))            # server: NOT_FOUND
        self.assertEqual(u.set_multi({key(): 1, key(): 2}), [])
        self.assertEqual(u.add_multi({key(): 1}), [])
        self.assertTrue(u.delete_multi([key(), key()]))
        u[key()] = 1
        del u[key()]
        time.sleep(0.2)
        self.assertEqual(self.tcp.get(existing), "v")
        self.assertIsNone(self.tcp.get(missing))

    def test_writes_do_arrive(self):
        a, b, c, d = key(), key(), key(), key()
        self.assertEqual(self.udp.set_multi({a: "1", b: "2"}), [])
        self.eventually(a, "1")
        self.eventually(b, "2")
        self.assertTrue(self.udp.add(c, "x"))
        self.eventually(c, "x")
        self.assertTrue(self.udp.append(c, "y"))
        self.eventually(c, "xy")
        self.assertTrue(self.udp.prepend(c, "w"))
        self.eventually(c, "wxy")
        self.assertTrue(self.udp.replace(c, "r"))
        self.eventually(c, "r")
        self.assertTrue(self.udp.delete_multi([a, b]))
        self.eventually(a, None)
        self.eventually(b, None)
        self.tcp.set(d, "v")
        self.assertTrue(self.udp.flush_all())
        self.eventually(d, None)

    def test_disconnect_all_and_hash_work(self):
        self.assertIsNone(self.udp.disconnect_all())
        self.assertIsInstance(self.udp.hash(key()), int)
        self.assertTrue(self.udp.set(key(), "v"))

    def test_noreply_cannot_be_turned_off(self):
        with self.assertRaises(pylibmc.Error):
            self.udp.set_behaviors({"_noreply": 0})
        self.assertEqual(self.udp.get_behaviors()["_noreply"], 1)


class TestUdpText(UdpRoundTrip, MemcachedTestCase):
    pass


class TestUdpBinary(UdpRoundTrip, MemcachedTestCase):
    binary = True
