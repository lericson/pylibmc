"""Master keys: pick the server by a group key instead of the item key.

Every data method takes a keyword-only ``master_key=``. The routing tests use a
client with a live server and a dead one: an item that hashes to the dead
server cannot be stored, unless a master key that hashes to the live server
picks the server.
"""

import socket
import uuid

import pylibmc
from pylibmc.test import make_test_client
from tests import PylibmcTestCase, get_refcounts


def rnd():
    return uuid.uuid4().hex


def closed_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def works(f):
    """True if f() succeeds, False if it fails or raises a pylibmc error."""
    try:
        return bool(f())
    except pylibmc.Error:
        return False


class Exercise:
    """One sequence of calls on every data method, with or without a master key.

    Keys are made unique per run, and the results are returned with the run's
    tag stripped so that runs are comparable. A pylibmc error becomes its
    class name: the binary protocol raises where the text protocol returns
    False (replace of a missing key, say), and both must match between runs.
    """

    def __init__(self, mc, kw):
        self.mc = mc
        self.kw = kw
        self.tag = rnd()

    def c(self, method, *args, **kw):
        kw.update(self.kw)
        try:
            return getattr(self.mc, method)(*args, **kw)
        except pylibmc.Error as e:
            return type(e).__name__

    def k(self, name):
        return self.tag + name

    def untag(self, d):
        return dict((k[len(self.tag):], v) for (k, v) in d.items())

    def run(self):
        c = self.c
        k = self.k
        out = []
        out.append(c("set", k("a"), 1))
        out.append(c("get", k("a")))
        out.append(c("get", k("nope")))
        out.append(c("get", k("nope"), "dflt"))
        out.append(c("add", k("a"), 2))
        out.append(c("add", k("b"), 2))
        out.append(c("replace", k("b"), 3))
        out.append(c("replace", k("nope"), 3))
        out.append(c("set", k("s"), b"mid"))
        out.append(c("append", k("s"), b"+"))
        out.append(c("prepend", k("s"), b"-"))
        out.append(c("get", k("s")))
        (value, cas) = c("gets", k("a"))
        out.append(value)
        out.append(c("gets", k("nope")))
        out.append(c("cas", k("a"), 10, cas))
        out.append(c("cas", k("a"), 11, cas))
        out.append(c("get", k("a")))
        out.append(c("touch", k("a"), 100))
        out.append(c("touch", k("nope"), 100))
        out.append(c("set", k("n"), 5))
        out.append(c("incr", k("n")))
        out.append(c("incr", k("n"), 10))
        out.append(c("decr", k("n"), 2))
        out.append(c("get", k("n")))
        out.append(c("set", k("m"), 1))
        out.append(c("incr_multi", [k("n"), k("m")], delta=3))
        out.append(self.untag(c("get_multi", [k("n"), k("m"), k("nope")])))
        out.append(c("set_multi", {k("x"): "X", k("y"): "Y"}))
        out.append([f[len(self.tag):] for f in
                    c("add_multi", {k("x"): "X2", k("z"): "Z"})])
        out.append(self.untag(c("get_multi", [k("x"), k("y"), k("z")])))
        out.append(c("get_multi", ["x", "y"], key_prefix=self.tag))
        out.append(c("delete_multi", [k("x"), k("y")]))
        out.append(c("delete_multi", ["z"], key_prefix=self.tag))
        out.append(c("delete", k("a")))
        out.append(c("delete", k("a")))
        return out


class MasterKeyTests(PylibmcTestCase):
    binary = False

    def setUp(self):
        self.mc = make_test_client(binary=self.binary,
                                   behaviors={"cas": True})
        self.group = "group-" + rnd()

    def test_keyword_matches_plain_on_every_method(self):
        plain = Exercise(self.mc, {}).run()
        kword = Exercise(self.mc, {"master_key": self.group}).run()
        self.assertEqual(plain, kword)
        # Sanity: the sequence did something, with hits, misses and results.
        self.assertIn(True, plain)
        self.assertIn(None, plain)
        self.assertIn(1, plain)

    def test_data_stored_under_a_master_key_is_found_with_it(self):
        # With one server it is also found without. With several it need not
        # be: the same key under another master key may be elsewhere.
        k = rnd()
        self.assertTrue(self.mc.set(k, "v", master_key=self.group))
        self.assertEqual(self.mc.get(k, master_key=self.group), "v")
        self.assertEqual(self.mc.get_multi([k], master_key=self.group),
                         {k: "v"})
        self.assertTrue(self.mc.delete(k, master_key=self.group))
        self.assertIsNone(self.mc.get(k, master_key=self.group))

    def test_str_and_bytes_master_keys_are_the_same(self):
        k = rnd()
        self.assertTrue(self.mc.set(k, 1, master_key="gé"))
        self.assertEqual(self.mc.get(k, master_key="gé".encode()), 1)

    def test_none_is_the_default(self):
        k = rnd()
        self.mc.set(k, 1, master_key=None)
        self.assertEqual(self.mc.get(k, master_key=None), 1)
        self.assertEqual(self.mc.get_multi([k], master_key=None), {k: 1})
        self.assertEqual(self.mc.get(k), 1)

    # Errors.

    def test_bad_master_keys(self):
        k = rnd()
        for bad, exc in ((b"", ValueError), ("", ValueError),
                         (123, TypeError), (1.5, TypeError),
                         ([b"a"], TypeError),
                         ("x" * 251, ValueError), (b"x" * 4000, ValueError)):
            with self.assertRaises(exc):
                self.mc.set(k, 1, master_key=bad)
            with self.assertRaises(exc):
                self.mc.get(k, master_key=bad)
            with self.assertRaises(exc):
                self.mc.get_multi([k], master_key=bad)
            with self.assertRaises(exc):
                self.mc.delete_multi([k], master_key=bad)
            with self.assertRaises(exc):
                self.mc.incr(k, master_key=bad)

    def test_master_key_is_only_hashed(self):
        # The master key never goes on the wire, so characters that item keys
        # may not have are not a protocol problem for it. Whether libmemcached
        # accepts them is its business; what matters is that nothing breaks.
        k = rnd()
        for group in ("a b", "a\nb", "a\x00b".encode()):
            try:
                self.mc.set(k, 1, master_key=group)
            except pylibmc.Error:
                pass
            self.assertTrue(self.mc.set(k, 2))
            self.assertEqual(self.mc.get(k), 2)

    def test_other_keywords_still_rejected(self):
        k = rnd()
        for name in ("get", "delete", "touch", "incr", "decr", "gets"):
            with self.assertRaises(TypeError):
                getattr(self.mc, name)(k, bogus=1)
            with self.assertRaises(TypeError):
                getattr(self.mc, name)(k, bogus=1, master_key=self.group)
        with self.assertRaises(TypeError):
            self.mc.set(k, 1, bogus=1, master_key=self.group)
        with self.assertRaises(TypeError):
            self.mc.get_multi([k], bogus=1, master_key=self.group)

    def test_master_key_is_keyword_only_on_get(self):
        with self.assertRaises(TypeError):
            self.mc.get(rnd(), None, self.group)

    def test_nothing_is_left_on_the_client(self):
        k = rnd()
        self.mc.set(k, 1, master_key=self.group)
        for attr in dir(self.mc):
            self.assertNotIn("group", attr)
            self.assertNotIn("master", attr)
        with self.assertRaises(TypeError):
            self.mc.get(k, bogus=1, master_key=self.group)
        with self.assertRaises(ValueError):
            self.mc.set(k, 1, master_key=b"")
        self.assertEqual(self.mc.get(k, master_key=self.group), 1)
        self.assertEqual(self.mc.get(k), 1)

    # Refcounts: fresh objects, many repetitions, no drift.

    def test_refcounts_do_not_drift(self):
        mc = self.mc
        group = ("g-" + rnd()).encode()
        key = rnd()
        key2 = rnd()
        value = rnd()
        kw = {"master_key": group}
        objs = [mc, group, key, key2, value]

        def once():
            mc.set(key, value, **kw)
            mc.get(key, **kw)
            mc.gets(key, **kw)
            mc.add(key2, value, **kw)
            mc.get_multi([key, key2], **kw)
            mc.set_multi({key: value}, **kw)
            mc.touch(key, 10, **kw)
            mc.delete_multi([key, key2], **kw)
            mc.delete(key, **kw)
            mc.get(key, master_key=None)
            with self.assertRaises(ValueError):
                mc.get(key, master_key=b"")
            with self.assertRaises(TypeError):
                mc.get(key, bogus=1, **kw)
            with self.assertRaises(TypeError):
                mc.set(key, value, master_key=1)

        once()
        before = get_refcounts(objs)
        for _ in range(500):
            once()
        self.assertEqual(before, get_refcounts(objs))


class MasterKeyBinaryTests(MasterKeyTests):
    binary = True


class RoutingTests(PylibmcTestCase):
    """The master key, not the item key, decides which server is used."""
    binary = False

    def setUp(self):
        live = make_test_client(binary=self.binary)
        # One live server and one that refuses connections.
        self.mc = pylibmc.Client(
            [live.addresses[0], "127.0.0.1:%d" % closed_port()],
            binary=self.binary, behaviors={"cas": True})
        self.good_group = self.find(True)
        self.bad_group = self.find(False)
        self.good_item = self.find(True)
        self.bad_item = self.find(False)

    def find(self, live):
        """A random key that a plain set stores (or fails to store)."""
        for _ in range(200):
            k = "k-" + rnd()
            if works(lambda: self.mc.set(k, 1)) == live:
                return k
        self.fail("no key found")

    def test_setup_has_a_live_and_a_dead_server(self):
        self.assertTrue(self.mc.set(self.good_item, 1))
        self.assertFalse(works(lambda: self.mc.set(self.bad_item, 1)))

    def test_good_master_key_makes_a_dead_item_key_work(self):
        item = self.bad_item
        mk = self.good_group
        mc = self.mc
        self.assertTrue(mc.set(item, "v", master_key=mk))
        self.assertEqual(mc.get(item, master_key=mk), "v")
        self.assertEqual(mc.get_multi([item], master_key=mk), {item: "v"})
        (value, cas) = mc.gets(item, master_key=mk)
        self.assertEqual(value, "v")
        self.assertTrue(mc.cas(item, "w", cas, master_key=mk))
        self.assertTrue(mc.touch(item, 100, master_key=mk))
        self.assertTrue(mc.delete(item, master_key=mk))
        self.assertIsNone(mc.get(item, master_key=mk))
        self.assertTrue(mc.add(item, "a", master_key=mk))
        self.assertTrue(mc.replace(item, "r", master_key=mk))
        self.assertTrue(mc.append(item, "!", master_key=mk))
        self.assertTrue(mc.prepend(item, "<", master_key=mk))
        self.assertEqual(mc.get(item, master_key=mk), "<r!")
        self.assertTrue(mc.delete(item, master_key=mk))
        self.assertEqual(mc.set_multi({item: 1, item + "2": 2},
                                      master_key=mk), [])
        self.assertEqual(mc.get_multi([item, item + "2"], master_key=mk),
                         {item: 1, item + "2": 2})
        self.assertEqual(mc.incr(item, master_key=mk), 2)
        self.assertEqual(mc.decr(item, master_key=mk), 1)
        self.assertIsNone(mc.incr_multi([item, item + "2"], master_key=mk))
        self.assertTrue(mc.delete_multi([item, item + "2"], master_key=mk))
        self.assertEqual(mc.get_multi([item, item + "2"], master_key=mk), {})
        self.assertEqual(mc.add_multi({item: 1}, master_key=mk), [])

    def test_the_plain_client_still_hashes_the_item_key(self):
        item = self.bad_item
        self.assertTrue(self.mc.set(item, "v", master_key=self.good_group))
        # The item lives on the live server, but plain calls look at the dead
        # one, as before: nothing stuck to the client.
        self.assertFalse(works(lambda: self.mc.get(item) == "v"))
        self.assertFalse(works(lambda: self.mc.set(item, 1)))
        self.assertTrue(self.mc.set(self.good_item, 1))
        self.assertEqual(self.mc.get(item, master_key=self.good_group), "v")
        self.assertFalse(works(lambda: self.mc.set(item, 1)))

    def test_a_dead_master_key_makes_a_live_item_key_fail(self):
        item = self.good_item
        mk = self.bad_group
        mc = self.mc
        self.assertTrue(mc.set(item, 1))
        self.assertFalse(works(lambda: mc.set(item, 1, master_key=mk)))
        self.assertFalse(works(lambda: mc.get(item, master_key=mk)))
        self.assertFalse(works(lambda: mc.get_multi([item], master_key=mk)))
        self.assertFalse(works(lambda: mc.delete(item, master_key=mk)))
        # and plain works again straight afterwards
        self.assertTrue(mc.set(item, 2))
        self.assertEqual(mc.get(item), 2)

    def test_key_prefix_applies_to_item_keys_not_the_master_key(self):
        # A prefix on the items must not change which server is picked.
        item = self.bad_item
        mk = self.good_group
        mc = self.mc
        self.assertEqual(mc.set_multi({item: 1}, key_prefix="p-",
                                      master_key=mk), [])
        self.assertEqual(mc.get_multi([item], key_prefix="p-",
                                      master_key=mk), {item: 1})
        self.assertEqual(mc.get("p-" + item, master_key=mk), 1)
        self.assertTrue(mc.delete_multi([item], key_prefix="p-",
                                        master_key=mk))

    def test_namespace_is_not_part_of_the_master_key_by_default(self):
        # libmemcached adds its namespace to item keys. It hashes it into the
        # server choice only with the hash_with_prefix_key behavior, which is
        # off here, so the master key alone decides.
        ns = pylibmc.Client(self.mc.addresses, binary=self.binary,
                            behaviors={"namespace": b"ns:"})
        self.assertTrue(ns.set(self.good_item, 1, master_key=self.good_group))
        self.assertFalse(works(lambda: ns.set(
            self.good_item, 1, master_key=self.bad_group)))

    def test_a_group_wide_get_multi_hits_one_server(self):
        # Many items that would hash to both servers all live on one.
        mk = self.good_group
        items = {"i-%d-%s" % (i, rnd()): i for i in range(40)}
        self.assertEqual(self.mc.set_multi(items, master_key=mk), [])
        self.assertEqual(self.mc.get_multi(list(items), master_key=mk), items)
        self.assertTrue(self.mc.delete_multi(list(items), master_key=mk))


class RoutingBinaryTests(RoutingTests):
    binary = True
