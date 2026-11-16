"""Unix domain socket servers (a server address starting with "/").

The round-trip tests start their own memcached on a socket in a short temporary
directory. They skip without a ``memcached`` binary, or fail when
PYLIBMC_TEST_MEMCACHED_REQUIRED=1.
"""

import uuid

import _pylibmc
import pylibmc
import pytest
from pylibmc.pools import ClientPool

from tests.memcached_proc import MemcachedTestCase


def key():
    return "unix-" + uuid.uuid4().hex


def test_unix_spec_translates_to_unix_type():
    from pylibmc.client import translate_server_spec
    assert translate_server_spec("/a/b.sock") == (
        _pylibmc.server_type_unix, "/a/b.sock", 0, 1)


def test_unix_socket_rejects_port():
    with pytest.raises(ValueError, match="can't set port on unix sockets"):
        pylibmc.Client([(_pylibmc.server_type_unix, "/tmp/x.sock", 11211)])


@pytest.mark.parametrize("other", ["127.0.0.1:2", "udp:127.0.0.1:2"])
def test_unix_cannot_mix_transports(other):
    with pytest.raises(ValueError, match="can't mix transport types"):
        pylibmc.Client(["/tmp/x.sock", other])
    with pytest.raises(ValueError, match="can't mix transport types"):
        pylibmc.Client([other, "/tmp/x.sock"])


@pytest.mark.parametrize("binary", [False, True])
def test_missing_socket_is_an_error_not_a_crash(binary, tmp_path):
    mc = pylibmc.Client([str(tmp_path / "nonexistent.sock")], binary=binary)
    with pytest.raises(pylibmc.Error):
        mc.set(key(), "v")
    with pytest.raises(pylibmc.Error):
        mc.get(key())


class UnixRoundTrip(object):
    binary = False
    flavor = {"unix": True}

    def make(self):
        return pylibmc.Client([self.server.path], binary=self.binary)

    def test_round_trip(self):
        mc = self.make()
        k, n, m = key(), key(), key()
        self.assertTrue(mc.set(k, "v"))
        self.assertEqual(mc.get(k), "v")
        mc.set(n, 5)
        self.assertEqual(mc.incr(n), 6)
        mc.set(m, [1, 2])
        self.assertEqual(mc.get_multi([k, n, m, key()]),
                         {k: "v", n: 6, m: [1, 2]})
        self.assertTrue(mc.delete(k))
        self.assertIsNone(mc.get(k))

    def test_clone_and_pool(self):
        mc = self.make()
        k = key()
        mc.set(k, "v")
        self.assertEqual(mc.clone().get(k), "v")
        self.assertEqual(mc.clone().clone().get(k), "v")
        pool = ClientPool(mc, 2)
        with pool.reserve() as c:
            self.assertEqual(c.get(k), "v")
        with pool.reserve() as c:
            c.set(k, "w")
        self.assertEqual(mc.get(k), "w")


class TestUnixText(UnixRoundTrip, MemcachedTestCase):
    pass


class TestUnixBinary(UnixRoundTrip, MemcachedTestCase):
    binary = True
