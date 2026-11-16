"""incr and decr with initial= and expire= (#379).

memcached_increment_with_initial and friends create a missing key with the
initial value, in one round trip. Only the binary protocol has that command:
libmemcached returns MEMCACHED_INVALID_ARGUMENTS on the text protocol (1.0.18
and 1.1.4), so pylibmc refuses initial= there before sending anything.
"""

import socket
import time
import uuid

import pylibmc
from pylibmc.test import make_test_client
from tests import PylibmcTestCase, get_refcounts


def rnd():
    return "incrinit-" + uuid.uuid4().hex


def closed_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def wait_until(cond, timeout=5.0):
    deadline = time.time() + timeout
    while not cond():
        if time.time() > deadline:
            return False
        time.sleep(0.1)
    return True


class TextProtocolTests(PylibmcTestCase):
    def setUp(self):
        self.mc = make_test_client(binary=False)

    def test_initial_is_refused_up_front(self):
        for method in (self.mc.incr, self.mc.decr):
            k = rnd()
            with self.assertRaisesRegex(pylibmc.NotSupportedError,
                                        "binary protocol"):
                method(k, initial=5)
            with self.assertRaisesRegex(pylibmc.NotSupportedError,
                                        "binary protocol"):
                method(k, 1, 5, 10)
            self.assertIsNone(self.mc.get(k))

    def test_refused_for_an_existing_key_too(self):
        k = rnd()
        self.mc.set(k, 5)
        with self.assertRaises(pylibmc.NotSupportedError):
            self.mc.incr(k, initial=0)
        self.assertEqual(self.mc.get(k), 5)

    def test_without_initial_nothing_changes(self):
        k = rnd()
        with self.assertRaises(pylibmc.NotFound):
            self.mc.incr(k)
        with self.assertRaises(pylibmc.NotFound):
            self.mc.decr(k, initial=None)
        self.mc.set(k, 5)
        self.assertEqual(self.mc.incr(k), 6)
        self.assertEqual(self.mc.incr(k, delta=4), 10)
        self.assertEqual(self.mc.decr(key=k, delta=3), 7)

    def test_expire_without_initial_is_an_error(self):
        k = rnd()
        self.mc.set(k, 5)
        with self.assertRaisesRegex(ValueError, "initial="):
            self.mc.incr(k, expire=10)
        self.assertEqual(self.mc.incr(k, expire=0), 6)


class BinaryProtocolTests(PylibmcTestCase):
    behaviors = None

    def setUp(self):
        self.mc = make_test_client(binary=True, behaviors=self.behaviors)
        self.plain = make_test_client(binary=True)

    def tearDown(self):
        self.plain.disconnect_all()
        super().tearDown()

    def test_missing_key_is_created_with_initial(self):
        k = rnd()
        # The delta is not added to a key that was just created.
        self.assertEqual(self.mc.incr(k, 5, initial=10), 10)
        self.assertEqual(self.mc.incr(k, 5, initial=10), 15)
        self.assertEqual(self.mc.decr(k, 1, initial=10), 14)
        k = rnd()
        self.assertEqual(self.mc.decr(k, 5, initial=3), 3)
        self.assertEqual(self.mc.decr(k, 5, initial=3), 0)

    def test_created_value_is_digits_without_flags(self):
        # The server stores the counter as ASCII digits with flags 0, so get()
        # returns bytes, unlike a counter that set() stored as an int.
        k = rnd()
        self.mc.incr(k, initial=42)
        self.assertEqual(self.plain.get(k), b"42")

    def test_existing_key_ignores_initial(self):
        k = rnd()
        self.plain.set(k, 100)
        self.assertEqual(self.mc.incr(k, 1, initial=0), 101)
        self.assertEqual(self.mc.decr(k, 1, initial=0), 100)
        self.assertEqual(self.plain.get(k), 100)

    def test_without_initial_a_missing_key_still_raises(self):
        with self.assertRaises(pylibmc.NotFound):
            self.mc.incr(rnd())
        with self.assertRaises(pylibmc.NotFound):
            self.mc.decr(rnd(), 1, None)

    def test_full_ranges(self):
        self.assertEqual(self.mc.incr(rnd(), 0, initial=2**64 - 1), 2**64 - 1)
        self.assertEqual(self.mc.incr(rnd(), initial=0), 0)
        self.assertEqual(self.mc.incr(rnd(), initial=True), 1)
        k = rnd()
        self.mc.incr(k, initial=0)
        self.assertEqual(self.mc.incr(k, 2**32 - 1, initial=0), 2**32 - 1)
        k = rnd()
        self.mc.incr(k, initial=0, expire=2**32 - 2)
        self.assertEqual(self.plain.get(k), b"0")

    def test_bad_arguments(self):
        cases = [
            (dict(initial=-1), ValueError),
            (dict(initial=-2**70), ValueError),
            (dict(initial=2**64), OverflowError),
            (dict(initial=1.5), TypeError),
            (dict(initial="1"), TypeError),
            (dict(initial=0, expire=-1), ValueError),
            (dict(initial=0, expire=2**32 - 1), ValueError),
            (dict(initial=0, expire=2**32), ValueError),
            (dict(initial=0, expire=2**63), OverflowError),
            (dict(expire=5), ValueError),
            (dict(delta=-1), ValueError),
            (dict(delta=2**32), OverflowError),
            (dict(delta=-1, initial=0), ValueError),
            (dict(bogus=1), TypeError),
            (dict(bogus=1, initial=0), TypeError),
        ]
        for method in (self.mc.incr, self.mc.decr):
            for kwargs, exc in cases:
                k = rnd()
                with self.assertRaises(exc, msg=kwargs):
                    method(k, **kwargs)
                self.assertIsNone(self.plain.get(k), kwargs)

    def test_bad_keys(self):
        with self.assertRaises(ValueError):
            self.mc.incr("x" * 300, initial=0)
        with self.assertRaises(TypeError):
            self.mc.incr(1, initial=0)

    def test_expire_applies_to_a_created_key_only(self):
        created, existing = rnd(), rnd()
        self.plain.set(existing, 1)
        self.assertEqual(self.mc.incr(created, initial=1, expire=1), 1)
        self.assertEqual(self.mc.incr(existing, initial=1, expire=1), 2)
        self.assertEqual(self.plain.get(created), b"1")
        self.assertTrue(wait_until(lambda: self.plain.get(created) is None))
        time.sleep(1.1)
        self.assertEqual(self.plain.get(existing), 2)

    def test_bool_flagged_values(self):
        # #356: a counter stored as a bool reads back as an int after incr.
        k = rnd()
        self.plain.set(k, True)
        self.assertEqual(self.mc.incr(k, initial=0), 2)
        self.assertEqual(self.plain.get(k), 2)
        self.assertIs(type(self.plain.get(k)), int)
        k = rnd()
        self.plain.set(k, True)
        self.assertEqual(self.mc.decr(k, initial=5), 0)
        self.assertIs(self.plain.get(k), False)

    def test_master_key(self):
        k = rnd()
        group = "group-" + rnd()
        self.assertEqual(self.mc.incr(k, initial=7, expire=100,
                                      master_key=group), 7)
        self.assertEqual(self.mc.incr(k, initial=7, master_key=group), 8)
        self.assertEqual(self.mc.decr(k, 2, initial=7, master_key=group), 6)
        self.assertEqual(self.plain.get(k, master_key=group), b"6")

    def test_refcounts_do_not_drift(self):
        mc = self.mc
        k1, k2 = rnd(), rnd()
        group = ("g-" + rnd()).encode()
        initial = 2**40 + int(uuid.uuid4().int % 1000)
        objs = [mc, k1, k2, group, initial]

        def once():
            mc.incr(k1, 1, initial)
            mc.decr(k1, 1, initial=initial)
            mc.incr(k2, initial=initial, master_key=group)
            mc.incr(k2, initial=initial, expire=100, master_key=group)
            for kwargs in (dict(initial=-1), dict(expire=5),
                           dict(initial=initial, bogus=1)):
                try:
                    mc.incr(k1, **kwargs)
                except (ValueError, TypeError):
                    pass
                else:
                    self.fail(kwargs)

        once()
        before = get_refcounts(objs)
        for _ in range(500):
            once()
        self.assertEqual(before, get_refcounts(objs))


class BufferedBinaryTests(BinaryProtocolTests):
    behaviors = {"buffer_requests": True}


class NoreplyBinaryTests(PylibmcTestCase):
    """noreply: the counter is created, the return value is meaningless."""

    def test_key_is_created(self):
        mc = make_test_client(binary=True, behaviors={"_noreply": True})
        plain = make_test_client(binary=True)
        k = rnd()
        mc.incr(k, initial=42)
        self.assertTrue(wait_until(lambda: plain.get(k) == b"42"))
        mc.incr(k, initial=42)
        self.assertTrue(wait_until(lambda: plain.get(k) == b"43"))


class RoutingTests(PylibmcTestCase):
    """The master key, not the item key, picks the server."""

    def setUp(self):
        live = make_test_client(binary=True)
        self.mc = pylibmc.Client(
            [live.addresses[0], "127.0.0.1:%d" % closed_port()], binary=True)
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
            self.mc.incr(item, initial=5)
        mk = self.good_group
        self.assertEqual(self.mc.incr(item, initial=5, master_key=mk), 5)
        self.assertEqual(self.mc.decr(item, initial=5, master_key=mk), 4)
        self.assertEqual(self.mc.get(item, master_key=mk), b"4")

    def test_a_dead_master_key_makes_a_live_item_key_fail(self):
        item = self.good_item
        self.assertEqual(self.mc.incr(item, initial=5), 2)  # find() set it to 1
        with self.assertRaises(pylibmc.Error):
            self.mc.incr(item, initial=5, master_key=self.bad_group)
        self.assertEqual(self.mc.incr(item, initial=5), 3)
