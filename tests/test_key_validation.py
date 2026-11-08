"""pylibmc checks every key itself, whatever libmemcached would do.

With the text protocol a key goes into a command line, so a byte <= 0x20 or
0x7f (NUL, tab, CR, LF, space and the other control characters) would corrupt
the conversation with the server or let whoever controls the key send commands
of their own. Those keys raise ``ValueError``. Bytes >= 0x80 are fine. The
binary protocol length-prefixes keys and accepts any byte; only the length
limit applies. The master key is hashed, never sent, so only the length limit
applies to it with either protocol.
"""

import gc
import sys
import uuid
import warnings

import pytest

import pylibmc
from pylibmc.test import make_test_client


def fresh(prefix="kv-"):
    return prefix + uuid.uuid4().hex


def text(**kw):
    return make_test_client(**kw)


def client(**kw):
    """Built right here, so a warning's stack level can be checked."""
    return pylibmc.Client(["127.0.0.1"], **kw)


def binary(**kw):
    return make_test_client(binary=True, **kw)


# Every byte the text protocol forbids.
BAD_BYTES = [bytes([b]) for b in range(0x21)] + [b"\x7f"]
BAD_IDS = ["0x%02x" % b[0] for b in BAD_BYTES]
# Bytes that are fine, including everything non-ASCII.
GOOD_KEYS = [
    "café", "café".encode(), "☃-snowman",
    b"a\xffb", b"a\x80b", b"\xff", "~!@#$%^&*()_+-=[]{};:'\",.<>/?|\\`",
]


def with_bad(byte, where):
    """A fresh key with the forbidden *byte* at the start, middle or end."""
    base = fresh().encode()
    if where == "start":
        return byte + base
    if where == "end":
        return base + byte
    return base[:5] + byte + base[5:]


# One call per public way of using a single key; each gets a client and a key.
SINGLE_KEY_CALLS = {
    "set": lambda mc, k: mc.set(k, "v"),
    "add": lambda mc, k: mc.add(k, "v"),
    "replace": lambda mc, k: mc.replace(k, "v"),
    "append": lambda mc, k: mc.append(k, "v"),
    "prepend": lambda mc, k: mc.prepend(k, "v"),
    "cas": lambda mc, k: mc.cas(k, "v", 1),
    "get": lambda mc, k: mc.get(k),
    "gets": lambda mc, k: mc.gets(k),
    "delete": lambda mc, k: mc.delete(k),
    "touch": lambda mc, k: mc.touch(k, 10),
    "incr": lambda mc, k: mc.incr(k),
    "decr": lambda mc, k: mc.decr(k),
    "set_multi": lambda mc, k: mc.set_multi({k: "v"}),
    "set_multi_list": lambda mc, k: mc.set_multi({k: "v", fresh(): "w"}),
    "add_multi": lambda mc, k: mc.add_multi({k: "v"}),
    "get_multi": lambda mc, k: mc.get_multi([k]),
    "get_multi_among_good": lambda mc, k: mc.get_multi([fresh(), k, fresh()]),
    "delete_multi": lambda mc, k: mc.delete_multi([k]),
    "incr_multi": lambda mc, k: mc.incr_multi([k]),
    "getitem": lambda mc, k: mc[k],
    "setitem": lambda mc, k: mc.__setitem__(k, "v"),
    "delitem": lambda mc, k: mc.__delitem__(k),
    "contains": lambda mc, k: k in mc,
    "set_with_prefix_in_key": lambda mc, k: mc.set_multi({k: "v"},
                                                        key_prefix="p-"),
    "get_multi_prefix_in_key": lambda mc, k: mc.get_multi([k],
                                                         key_prefix="p-"),
    "delete_multi_prefix_in_key": lambda mc, k: mc.delete_multi(
        [k], key_prefix="p-"),
    "incr_multi_prefix_in_key": lambda mc, k: mc.incr_multi([k],
                                                           key_prefix="p-"),
    "with_master_key": lambda mc, k: mc.set(k, "v", master_key="m"),
    "get_with_master_key": lambda mc, k: mc.get(k, master_key="m"),
    "get_multi_with_master_key": lambda mc, k: mc.get_multi(
        [k], master_key="m"),
}

# Where the bad bytes are in the prefix, not in the key.
PREFIX_CALLS = {
    "set_multi": lambda mc, p: mc.set_multi({fresh(): "v"}, key_prefix=p),
    "add_multi": lambda mc, p: mc.add_multi({fresh(): "v"}, key_prefix=p),
    "get_multi": lambda mc, p: mc.get_multi([fresh()], key_prefix=p),
    "delete_multi": lambda mc, p: mc.delete_multi([fresh()], key_prefix=p),
    "incr_multi": lambda mc, p: mc.incr_multi([fresh()], key_prefix=p),
}


def test_every_forbidden_byte_is_rejected_by_every_method():
    mc = text(behaviors={"cas": True})
    missed = []
    for name, call in SINGLE_KEY_CALLS.items():
        for byte in BAD_BYTES:
            for where in ("start", "middle", "end"):
                for as_str in (False, True):
                    key = with_bad(byte, where)
                    if as_str:
                        key = key.decode("latin-1")
                    try:
                        call(mc, key)
                    except ValueError:
                        continue
                    except Exception as e:  # wrong exception
                        missed.append((name, key, repr(e)))
                    else:
                        missed.append((name, key, "no exception"))
    assert not missed, missed[:10]


@pytest.mark.parametrize("name", sorted(SINGLE_KEY_CALLS))
def test_rejected_in_each_method_and_names_the_problem(name):
    mc = text(behaviors={"cas": True})
    with pytest.raises(ValueError) as info:
        SINGLE_KEY_CALLS[name](mc, "bad key")
    # The key is shown with repr, never raw.
    assert "bad key'" in str(info.value)
    assert "0x20" in str(info.value)


@pytest.mark.parametrize("name", sorted(PREFIX_CALLS))
@pytest.mark.parametrize("bad", BAD_BYTES, ids=BAD_IDS)
def test_bad_key_prefix_is_rejected(name, bad):
    mc = text()
    with pytest.raises(ValueError):
        PREFIX_CALLS[name](mc, b"pre" + bad)


def test_control_bytes_are_not_echoed_raw():
    mc = text()
    with pytest.raises(ValueError) as info:
        mc.set("a\r\nflush_all", "x")
    msg = str(info.value)
    assert "\r" not in msg and "\n" not in msg and "\x00" not in msg
    with pytest.raises(ValueError) as info:
        mc.get("a\x00b")
    assert "\x00" not in str(info.value)


@pytest.mark.parametrize("key", GOOD_KEYS, ids=repr)
def test_non_ascii_keys_still_work_with_text(key):
    mc = text()
    k = key + fresh().encode() if isinstance(key, bytes) else key + fresh()
    assert mc.set(k, 1)
    assert mc.get(k) == 1
    assert mc.get_multi([k]) == {k: 1}
    assert mc.incr(k) == 2
    assert mc.delete(k)


def test_tilde_and_punctuation_keys_work_with_text():
    mc = text()
    k = "~!@#$%^&*()_+-=[]{};:'\",.<>/?|\\`" + fresh()
    assert mc.set(k, 1)
    assert mc.get(k) == 1
    assert mc.delete(k)


# --- what used to go wrong, and must stay impossible ------------------------

@pytest.mark.parametrize("bad", [
    "bad key", "tab\tkey", "ctl\x01key", "cr\rkey", "nl\nkey", "nul\x00key",
    "del\x7fkey", "a\r\nflush_all", "a\r\nflush_all\r\n", " leading",
])
def test_bad_key_does_not_desync_the_connection(bad):
    mc = text()
    for call in (lambda: mc.set(bad, "x"), lambda: mc.get(bad),
                 lambda: mc.delete(bad), lambda: mc.incr(bad),
                 lambda: mc.get_multi([bad])):
        with pytest.raises(ValueError):
            call()
        # The same client keeps working and sees its own replies.
        k = fresh()
        assert mc.set(k, 7)
        assert mc.get(k) == 7
        assert mc.get(fresh()) is None
        assert mc.delete(k)


def test_command_injection_cannot_flush_the_server():
    mc = text()
    victim = fresh("victim-")
    assert mc.set(victim, "alive")
    for evil in ("a\r\nflush_all", "a\r\nflush_all\r\n", "a\nflush_all",
                 "a\r\nflush_all noreply\r\n", "x \r\nflush_all\r\n"):
        for call in (lambda: mc.set(evil, "x"), lambda: mc.get(evil),
                     lambda: mc.delete(evil), lambda: mc.get_multi([evil]),
                     lambda: mc.set_multi({evil: "x"}),
                     lambda: mc.incr_multi([evil])):
            with pytest.raises(ValueError):
                call()
    assert text().get(victim) == "alive"
    assert mc.get(victim) == "alive"
    mc.delete(victim)


def test_set_multi_with_one_bad_key_stores_nothing_for_it():
    mc = text()
    good = fresh()
    with pytest.raises(ValueError):
        mc.set_multi({good: "v", "bad key": "w"})
    # And nothing got out of sync.
    assert mc.set(good, "v2")
    assert mc.get(good) == "v2"
    mc.delete(good)


def test_incr_multi_with_one_bad_key_changes_nothing():
    mc = text()
    good = fresh()
    mc.set(good, 1)
    with pytest.raises(ValueError):
        mc.incr_multi([good, "bad key"])
    assert mc.get(good) == 1
    mc.delete(good)


# --- length -----------------------------------------------------------------

@pytest.mark.parametrize("make", [text, binary], ids=["text", "binary"])
def test_length_limit_still_applies(make):
    mc = make()
    ok = "k" * 249
    assert mc.set(ok, 1)
    assert mc.get(ok) == 1
    assert mc.delete(ok)
    for n in (251, 300):
        with pytest.raises(ValueError, match="too long"):
            mc.set("k" * n, 1)
        with pytest.raises(ValueError, match="too long"):
            mc.get("k" * n)
        with pytest.raises(ValueError, match="too long"):
            mc.get_multi(["k" * n])


@pytest.mark.parametrize("make", [text, binary], ids=["text", "binary"])
def test_length_of_prefixed_key_is_checked(make):
    mc = make()
    key = "k" * 200
    with pytest.raises(ValueError, match="too long"):
        mc.get_multi([key], key_prefix="p" * 60)
    with pytest.raises(ValueError, match="too long"):
        mc.incr_multi([key], key_prefix="p" * 60)
    with pytest.raises(ValueError, match="too long"):
        mc.set_multi({key: 1}, key_prefix="p" * 60)
    with pytest.raises(ValueError, match="too long"):
        mc.delete_multi([key], key_prefix="p" * 60)


# --- the binary protocol allows any byte -------------------------------------

BINARY_OK = [b"a b", b"a\tb", b"a\rb", b"a\nb", b"a\x01b", b"a\x1fb",
             b"a\x7fb", b"a\r\nflush_all", b" lead", b"trail ", b"a\xffb",
             "café"]


@pytest.mark.parametrize("key", BINARY_OK, ids=repr)
def test_binary_protocol_accepts_any_byte(key):
    mc = binary()
    k = key + fresh().encode() if isinstance(key, bytes) else key + fresh()
    assert mc.set(k, 1)
    assert mc.get(k) == 1
    assert mc.get_multi([k]) == {k: 1}
    assert mc.incr(k) == 2
    assert mc.delete(k)
    assert mc.get(k) is None


def test_binary_protocol_accepts_nul():
    mc = binary()
    k = b"a\x00" + fresh().encode()
    assert mc.set(k, 1)
    assert mc.get(k) == 1
    assert mc.delete(k)


def test_binary_prefix_with_nul_is_not_truncated():
    # The prefixed key used to be built with "%s%s", which stops at a NUL.
    mc = binary()
    prefix = b"p\x00q" + fresh().encode()
    k = fresh()
    assert mc.set_multi({k: 1}, key_prefix=prefix) == []
    assert mc.get_multi([k], key_prefix=prefix) == {k: 1}
    assert mc.get(prefix + k.encode()) == 1
    assert mc.incr_multi([k], key_prefix=prefix) is None
    assert mc.get(prefix + k.encode()) == 2
    assert mc.delete_multi([k], key_prefix=prefix)
    assert mc.get(prefix + k.encode()) is None


def test_binary_clone_and_pool_clients_stay_binary():
    mc = binary()
    for c in (mc.clone(), mc.clone().clone()):
        k = "a b" + fresh()
        assert c.set(k, 1)
        assert c.delete(k)


def test_text_clone_and_pool_clients_stay_text():
    pool = pylibmc.ClientPool()
    pool.fill(text(), 2)
    with pool.reserve() as c:
        with pytest.raises(ValueError):
            c.set("a b", 1)
        with pytest.raises(ValueError):
            c.clone().set("a b", 1)


# --- the master key is hashed, never sent -----------------------------------

@pytest.mark.parametrize("make", [text, binary], ids=["text", "binary"])
@pytest.mark.parametrize("mk", [b"a b", b"a\r\nflush_all", b"a\x00b", b"a\tb",
                                "café"], ids=repr)
def test_master_key_may_hold_any_byte(make, mk):
    mc = make()
    k = fresh()
    assert mc.set(k, 1, master_key=mk)
    assert mc.get(k, master_key=mk) == 1
    assert mc.get_multi([k], master_key=mk) == {k: 1}
    assert mc.delete(k, master_key=mk)
    # Nothing went out of sync.
    assert mc.set(k, 2)
    assert mc.get(k) == 2
    mc.delete(k)


@pytest.mark.parametrize("make", [text, binary], ids=["text", "binary"])
def test_master_key_length_is_checked(make):
    mc = make()
    with pytest.raises(ValueError, match="too long"):
        mc.set(fresh(), 1, master_key="m" * 300)


# --- the verify_keys behavior is gone ---------------------------------------

def caught(fn):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        fn()
    return [x for x in w if issubclass(x.category, DeprecationWarning)
            and "verify_keys" in str(x.message)]


@pytest.mark.parametrize("value", [True, False, 0, 1])
def test_verify_keys_in_constructor_warns_and_is_ignored(value):
    w = caught(lambda: client(behaviors={"verify_keys": value}))
    assert len(w) == 1
    assert w[0].filename == __file__
    assert "always verifies keys" in str(w[0].message)
    # Ignored: keys are still verified, and non-ASCII keys still work.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mc = client(behaviors={"verify_keys": value})
    with pytest.raises(ValueError):
        mc.set("a b", 1)
    k = "café" + fresh()
    assert mc.set(k, 1)
    assert mc.delete(k)


@pytest.mark.parametrize("value", [True, False])
def test_verify_keys_set_behaviors_warns(value):
    mc = text()
    w = caught(lambda: mc.set_behaviors({"verify_keys": value, "ketama": 0}))
    assert len(w) == 1 and w[0].filename == __file__


@pytest.mark.parametrize("value", [True, False])
def test_verify_keys_behavior_mapping_warns(value):
    mc = text()

    def setitem():
        mc.behaviors["verify_keys"] = value

    def update():
        mc.behaviors.update({"verify_keys": value})

    for fn in (setitem, update):
        w = caught(fn)
        assert len(w) == 1 and w[0].filename == __file__
    assert "verify_keys" not in mc.get_behaviors()


def test_verify_keys_binary_constructor_does_not_error():
    # libmemcached 1.0.x refuses to set verify_keys on a binary client; the
    # behavior is ignored, so this must neither raise nor warn twice.
    for value in (True, False):
        w = caught(lambda: client(binary=True, behaviors={"verify_keys": value}))
        assert len(w) == 1
    mc = binary()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mc.set_behaviors({"verify_keys": True})
    k = "a b" + fresh()
    assert mc.set(k, 1)
    assert mc.delete(k)


def test_verify_keys_is_not_reported():
    assert "verify_keys" not in text().get_behaviors()
    assert "verify_keys" not in binary().get_behaviors()
    assert "verify_keys" not in text().clone().get_behaviors()


def test_other_behaviors_do_not_warn():
    assert not caught(lambda: text(behaviors={"tcp_nodelay": True}))


# --- reference counts --------------------------------------------------------

def refs(objs):
    gc.collect()
    return [sys.getrefcount(o) for o in objs]


def test_rejected_keys_do_not_leak_references():
    if not hasattr(sys, "getrefcount"):
        pytest.skip("needs sys.getrefcount")
    mc = text()
    # Fresh objects (not literals or interned strings) so that counts change
    # only if pylibmc leaks.
    key_str = fresh("a b ")
    key_bytes = fresh("a\tb-").encode()
    good = fresh()
    val = fresh("val-")
    prefix = fresh("pre ")
    group = fresh("g-")
    objs = [key_str, key_bytes, good, val, prefix, group]

    def once():
        for k in (key_str, key_bytes):
            for call in (
                lambda: mc.set(k, val), lambda: mc.add(k, val),
                lambda: mc.get(k), lambda: mc.gets(k),
                lambda: mc.delete(k), lambda: mc.touch(k, 1),
                lambda: mc.incr(k), lambda: mc.decr(k),
                lambda: mc.cas(k, val, 1),
                lambda: mc.append(k, val), lambda: mc.prepend(k, val),
                lambda: mc.set_multi({k: val}),
                lambda: mc.add_multi({k: val}),
                lambda: mc.get_multi([good, k]),
                lambda: mc.delete_multi([good, k]),
                lambda: mc.incr_multi([good, k]),
                lambda: mc.get_multi([good], key_prefix=prefix),
                lambda: mc.set_multi({good: val}, key_prefix=prefix),
                lambda: mc.incr_multi([good], key_prefix=prefix),
                lambda: mc.delete_multi([good], key_prefix=prefix),
                lambda: mc.set(k, val, master_key=group),
                lambda: mc[k], lambda: k in mc,
            ):
                try:
                    call()
                except ValueError:
                    pass
                else:
                    raise AssertionError("not rejected")

    once()
    before = refs(objs)
    for _ in range(300):
        once()
    assert refs(objs) == before
