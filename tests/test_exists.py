"""Client.exists(key, master_key=None) (#378).

libmemcached's memcached_exist asks the server with an ``add`` of an empty
item whose expiry is already in the past, so a present key answers without
its value being sent and a missing key stays missing. Clients that do not read
each reply (``buffer_requests``, ``_noreply``) fetch the item instead; see
_PylibMC_exists.
"""

import socket
import time
import uuid

import pytest

import pylibmc
from pylibmc.test import make_test_client
from tests import PylibmcTestCase, get_refcounts


def rnd():
    return "exists-" + uuid.uuid4().hex


def closed_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def server_stat(mc, name):
    ((_, stats),) = mc.get_stats()
    return int(stats[name])


class ExistsTests(PylibmcTestCase):
    binary = False
    behaviors = None

    def setUp(self):
        self.mc = make_test_client(binary=self.binary,
                                   behaviors=self.behaviors)
        # Stores go through a plain client, so they are on the server before
        # a buffering or noreply client under test looks.
        self.plain = make_test_client(binary=self.binary)

    def tearDown(self):
        self.plain.disconnect_all()
        super().tearDown()

    def test_present_and_absent(self):
        k = rnd()
        self.assertIs(self.mc.exists(k), False)
        self.plain.set(k, "v")
        self.assertIs(self.mc.exists(k), True)
        self.assertIs(self.mc.exists(rnd()), False)

    def test_values_that_count_as_present(self):
        # The same as `in`, which uses get(): any stored value is a hit.
        for value in (None, b"", "", 0, False, True, [], b"x" * 1000):
            k = rnd()
            self.assertTrue(self.plain.set(k, value))
            self.assertIs(self.mc.exists(k), True, value)
            self.assertIn(k, self.mc)

    def test_after_delete(self):
        k = rnd()
        self.plain.set(k, 1)
        self.assertIs(self.mc.exists(k), True)
        self.assertTrue(self.plain.delete(k))
        self.assertIs(self.mc.exists(k), False)

    def test_expired(self):
        k = rnd()
        self.plain.set(k, 1, time=1)
        self.assertIs(self.mc.exists(k), True)
        deadline = time.time() + 5
        while self.plain.get(k) is not None and time.time() < deadline:
            time.sleep(0.2)
        self.assertIs(self.mc.exists(k), False)

    def test_a_miss_stores_nothing(self):
        k = rnd()
        for _ in range(3):
            self.assertIs(self.mc.exists(k), False)
        self.assertIsNone(self.plain.get(k))
        self.assertTrue(self.plain.add(k, "a"))
        self.assertEqual(self.plain.get(k), "a")

    def test_a_miss_is_a_store_on_the_server_but_in_is_not(self):
        # What the documentation warns about: memcached counts the add that
        # asks. `in` keeps using get, which is a pure read.
        stats = make_test_client()
        before = server_stat(stats, "cmd_set")
        self.assertIs(self.mc.exists(rnd()), False)
        expected = 0 if self.behaviors else 1
        self.assertEqual(server_stat(stats, "cmd_set") - before, expected)
        before = server_stat(stats, "cmd_set")
        self.assertNotIn(rnd(), self.mc)
        self.assertEqual(server_stat(stats, "cmd_set") - before, 0)

    def test_a_hit_changes_nothing(self):
        k = rnd()
        self.plain.set(k, "v")
        (_, cas) = make_test_client(binary=self.binary,
                                    behaviors={"cas": True}).gets(k)
        self.assertIs(self.mc.exists(k), True)
        self.assertEqual(self.plain.get(k), "v")
        (_, cas2) = make_test_client(binary=self.binary,
                                     behaviors={"cas": True}).gets(k)
        self.assertEqual(cas, cas2)

    def test_str_and_bytes_keys(self):
        k = rnd()
        self.plain.set(k, 1)
        self.assertIs(self.mc.exists(k.encode()), True)
        self.assertIs(self.mc.exists(k), True)

    def test_empty_key_is_a_miss(self):
        # get("") returns the default without asking the server.
        self.assertIs(self.mc.exists(""), False)
        self.assertIs(self.mc.exists(b""), False)
        self.assertNotIn("", self.mc)

    def test_bad_keys_raise_like_get(self):
        bad = [1, None, object(), "x" * 251]
        if not self.binary:
            bad += ["a b", "a\nb", b"a\x00b"]
        for key in bad:
            with self.assertRaises(Exception) as from_get:
                self.mc.get(key)
            with self.assertRaises(type(from_get.exception)):
                self.mc.exists(key)

    def test_text_only_key_rules_do_not_apply_to_binary(self):
        if not self.binary:
            self.skipTest("binary protocol only")
        k = rnd() + " with space"
        self.plain.set(k, 1)
        self.assertIs(self.mc.exists(k), True)

    def test_arguments(self):
        with self.assertRaises(TypeError):
            self.mc.exists()
        with self.assertRaises(TypeError):
            self.mc.exists(rnd(), "positional master key")
        with self.assertRaises(TypeError):
            self.mc.exists(rnd(), bogus=1)
        with self.assertRaises(ValueError):
            self.mc.exists(rnd(), master_key=b"")
        self.assertIs(self.mc.exists(rnd(), master_key=None), False)

    def test_master_key(self):
        k = rnd()
        group = "group-" + rnd()
        self.plain.set(k, 1, master_key=group)
        self.assertIs(self.mc.exists(k, master_key=group), True)
        self.assertIs(self.mc.exists(rnd(), master_key=group), False)

    def test_no_value_is_transferred(self):
        # The server counts the bytes it writes. A get of a 500 kB value
        # writes more than that; exists writes a short status line (plus
        # the stats reply that measures it).
        k = rnd()
        self.plain.set(k, b"x" * 500000, min_compress_len=0)
        stats = make_test_client()
        before = server_stat(stats, "bytes_written")
        self.assertIs(self.mc.exists(k), True)
        written = server_stat(stats, "bytes_written") - before
        if self.behaviors:
            # buffer_requests and _noreply fall back to a get.
            self.assertGreater(written, 500000)
        else:
            self.assertLess(written, 50000)
        before = server_stat(stats, "bytes_written")
        self.assertIsNotNone(self.plain.get(k))
        self.assertGreater(server_stat(stats, "bytes_written") - before,
                           500000)

    def test_dead_server_raises_like_get(self):
        # A fresh client each, as the first failure marks the server down
        # and the next call raises ServerDown instead.
        def client():
            return pylibmc.Client(["127.0.0.1:%d" % closed_port()],
                                  binary=self.binary,
                                  behaviors=self.behaviors)
        with self.assertRaises(pylibmc.Error) as from_get:
            client().get(rnd())
        with self.assertRaises(type(from_get.exception)):
            client().exists(rnd())

    def test_refcounts_do_not_drift(self):
        mc = self.mc
        hit = rnd()
        miss = rnd()
        group = ("g-" + rnd()).encode()
        self.plain.set(hit, rnd())
        self.plain.set(hit, rnd(), master_key=group)
        long_key = "x" * 300
        objs = [mc, hit, miss, group, long_key]

        def once():
            mc.exists(hit)
            mc.exists(miss)
            mc.exists(hit.encode())
            mc.exists(hit, master_key=group)
            mc.exists(miss, master_key=None)
            with self.assertRaises(ValueError):
                mc.exists(long_key)
            with self.assertRaises(TypeError):
                mc.exists(hit, bogus=1)

        once()
        before = get_refcounts(objs)
        for _ in range(500):
            once()
        self.assertEqual(before, get_refcounts(objs))


class ExistsBinaryTests(ExistsTests):
    binary = True


class ExistsBufferedTests(ExistsTests):
    behaviors = {"buffer_requests": True}

    def test_pending_buffered_store_does_not_skew_answers(self):
        # Measured without the fallback: on the binary protocol
        # memcached_exist read the reply of the queued set instead of its
        # own, so a present key came out missing and the other way round.
        present = rnd()
        self.plain.set(present, 1)
        self.mc.set(rnd(), 1)
        self.assertIs(self.mc.exists(present), True)
        self.mc.set(rnd(), 1)
        self.assertIs(self.mc.exists(rnd()), False)
        self.assertIs(self.mc.exists(present), True)


class ExistsBufferedBinaryTests(ExistsBufferedTests):
    binary = True


class ExistsNoreplyTests(ExistsTests):
    # On the binary protocol libmemcached 1.0.18's memcached_exist never
    # returns for a missing key with noreply on.
    behaviors = {"_noreply": True}


class ExistsNoreplyBinaryTests(ExistsNoreplyTests):
    binary = True


class ExistsRoutingTests(PylibmcTestCase):
    """The master key, not the item key, picks the server exists() asks."""
    binary = False

    def setUp(self):
        live = make_test_client(binary=self.binary)
        self.mc = pylibmc.Client(
            [live.addresses[0], "127.0.0.1:%d" % closed_port()],
            binary=self.binary)
        self.good_group = self.find(True)
        self.bad_group = self.find(False)
        self.good_item = self.find(True)
        self.bad_item = self.find(False)

    def find(self, live):
        for _ in range(200):
            k = "k-" + uuid.uuid4().hex
            try:
                ok = bool(self.mc.set(k, 1))
            except pylibmc.Error:
                ok = False
            if ok == live:
                return k
        self.fail("no key found")

    def test_good_master_key_makes_a_dead_item_key_work(self):
        item = self.bad_item
        with self.assertRaises(pylibmc.Error):
            self.mc.exists(item)
        self.assertIs(self.mc.exists(item, master_key=self.good_group), False)
        self.assertTrue(self.mc.set(item, 1, master_key=self.good_group))
        self.assertIs(self.mc.exists(item, master_key=self.good_group), True)

    def test_a_dead_master_key_makes_a_live_item_key_fail(self):
        item = self.good_item
        self.assertTrue(self.mc.set(item, 1))
        self.assertIs(self.mc.exists(item), True)
        with self.assertRaises(pylibmc.Error):
            self.mc.exists(item, master_key=self.bad_group)
        self.assertIs(self.mc.exists(item), True)


class ExistsRoutingBinaryTests(ExistsRoutingTests):
    binary = True


def test_udp_client_refuses_exists():
    # It needs the server's answer, which a UDP client never reads (#383).
    mc = pylibmc.Client(["udp:127.0.0.1:1"])
    with pytest.raises(pylibmc.NotSupportedError, match="UDP"):
        mc.exists(rnd())
