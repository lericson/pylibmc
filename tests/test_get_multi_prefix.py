"""get_multi with key_prefix: right keys, no leaked references.

get_multi used to build the prefixed key twice, the second time with
"%s%s", which stops at a NUL byte and does not check for failure. These
tests pin the observable behaviour and watch reference counts of fresh key
objects, so a leak shows up as drift that grows with the number of calls.
"""

import uuid

import pytest

from pylibmc.test import make_test_client
from tests import get_refcounts

REPEAT = 2000


@pytest.fixture(params=[False, True], ids=["ascii", "binary"])
def mc(request):
    c = make_test_client(binary=request.param)
    yield c
    c.disconnect_all()


def fresh(n):
    return [uuid.uuid4().hex for _ in range(n)]


def test_prefixed_hits_and_misses_come_back_unprefixed(mc):
    keys = fresh(6)
    mc.set_multi({k: i for i, k in enumerate(keys[:3])}, key_prefix="pfx_")
    got = mc.get_multi(keys, key_prefix="pfx_")
    assert got == {k: i for i, k in enumerate(keys[:3])}
    # The prefix really is applied on the wire.
    assert mc.get("pfx_" + keys[0]) == 0
    assert mc.get(keys[0]) is None


def test_prefixed_bytes_keys(mc):
    keys = [k.encode() for k in fresh(4)]
    mc.set_multi({k: 1 for k in keys}, key_prefix=b"pfx_".decode())
    assert mc.get_multi(keys, key_prefix="pfx_") == {k: 1 for k in keys}


def test_prefix_longer_than_key_and_empty_key(mc):
    k = uuid.uuid4().hex
    mc.set(("p" * 100) + k, 7)
    assert mc.get_multi([k, ""], key_prefix="p" * 100) == {k: 7}


@pytest.mark.parametrize("prefix", [None, "pfx_"])
@pytest.mark.parametrize("kind", ["str", "bytes"])
def test_get_multi_does_not_leak_key_references(mc, prefix, kind):
    kw = {"key_prefix": prefix} if prefix else {}
    keys = fresh(10)
    if kind == "bytes":
        keys = [k.encode() for k in keys]
    mc.set_multi({k: 1 for k in keys[:5]}, **kw)  # five hits, five misses
    mc.get_multi(keys, **kw)
    before = get_refcounts(keys)
    for _ in range(REPEAT):
        assert len(mc.get_multi(keys, **kw)) == 5
    assert get_refcounts(keys) == before


@pytest.mark.parametrize("prefix", [None, "pfx_"])
@pytest.mark.parametrize("kind", ["str", "bytes"])
def test_get_multi_with_failing_key_does_not_leak(mc, prefix, kind):
    kw = {"key_prefix": prefix} if prefix else {}
    keys = fresh(3) + ["x" * 300] + fresh(3)  # too long: ValueError
    if kind == "bytes":
        keys = [k.encode() for k in keys]
    before = get_refcounts(keys)
    for _ in range(REPEAT):
        with pytest.raises(ValueError):
            mc.get_multi(keys, **kw)
    assert get_refcounts(keys) == before


@pytest.mark.parametrize("prefix", [None, "pfx_"])
@pytest.mark.parametrize("kind", ["str", "bytes"])
def test_incr_multi_does_not_leak_key_references(mc, prefix, kind):
    kw = {"key_prefix": prefix} if prefix else {}
    keys = fresh(10)
    if kind == "bytes":
        keys = [k.encode() for k in keys]
    mc.set_multi({k: 1 for k in keys}, **kw)
    mc.incr_multi(keys, **kw)
    before = get_refcounts(keys)
    for _ in range(REPEAT):
        mc.incr_multi(keys, **kw)
    assert get_refcounts(keys) == before


@pytest.mark.parametrize("kind", ["str", "bytes"])
def test_delete_multi_with_failing_key_does_not_leak(mc, kind):
    keys = fresh(3) + ["x" * 300] + fresh(3)
    if kind == "bytes":
        keys = [k.encode() for k in keys]
    before = get_refcounts(keys)
    for _ in range(REPEAT):
        with pytest.raises(ValueError):
            mc.delete_multi(keys)
    assert get_refcounts(keys) == before


@pytest.mark.parametrize("method", ["get", "set", "delete", "incr", "gets"])
def test_single_key_methods_do_not_leak_a_failing_bytes_key(mc, method):
    key = b"x" * 300 + uuid.uuid4().hex.encode()
    args = (1,) if method == "set" else ()
    if method == "gets":
        mc = make_test_client(binary=False, behaviors={"cas": True})
    before = get_refcounts([key])
    for _ in range(REPEAT):
        with pytest.raises(ValueError):
            getattr(mc, method)(key, *args)
    assert get_refcounts([key]) == before


def test_failing_str_key_does_not_leak_the_encoded_key(mc):
    # The UTF-8 form of a str key is a temporary the caller never sees, so
    # only the allocator can tell whether it was released.
    import platform
    if platform.python_implementation() != "CPython":
        pytest.skip("tracemalloc measures CPython allocations")
    import tracemalloc
    key = "x" * 300
    for _ in range(100):
        with pytest.raises(ValueError):
            mc.get_multi([key])
    tracemalloc.start()
    try:
        before, _ = tracemalloc.get_traced_memory()
        for _ in range(5000):
            with pytest.raises(ValueError):
                mc.get_multi([key])
            with pytest.raises(ValueError):
                mc.get(key)
        after, _ = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    # A leak would be 10000 objects of ~350 bytes, over 3 MB.
    assert after - before < 200 * 1024
