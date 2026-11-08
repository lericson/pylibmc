"""pylibmc and python-memcached can read each other's values.

Both clients talk to the same memcached and agree on what the 32-bit flags
field means (pickle 1, integer 2, long 4, compressed 8, text 16). This test
stores a range of values with one client and reads them with the other, in both
directions, and with pylibmc's text and binary protocol.

The one value that does not survive as itself is a bool written by pylibmc:
python-memcached reads it as the integer 1 or 0, which is accepted (pylibmc
reads python-memcached's bools as bools). Skipped if python-memcached is not
installed.
"""

import os
import uuid

import pytest

from pylibmc.test import make_test_client

memcache = pytest.importorskip("memcache")


def address():
    return "%s:%s" % (os.environ.get("MEMCACHED_HOST", "127.0.0.1"),
                      os.environ.get("MEMCACHED_PORT", "11211"))


# (id, value): each must come back equal, and of the same type, from the other
# client. Bools are tested separately.
VALUES = [
    ("bytes", b"\x00\xff abc"),
    ("empty-bytes", b""),
    ("text", "åäö €"),
    ("empty-text", ""),
    ("zero", 0),
    ("int", 42),
    ("negative-int", -42),
    ("big-int", 2 ** 70),
    ("float", 1.5),
    ("none", None),
    ("list", [1, "a", None, b"b"]),
    ("tuple", (1, 2, "three")),
    ("dict", {"a": [1, 2], "b": {"c": None}}),
]
IDS = [i for i, _ in VALUES]
LARGE = "compressible " * 2000


@pytest.fixture(params=[False, True], ids=["text", "binary"])
def binary(request):
    return request.param


@pytest.fixture
def lmc(binary):
    return make_test_client(binary=binary)


@pytest.fixture
def pm():
    client = memcache.Client([address()])
    yield client
    client.disconnect_all()


@pytest.fixture
def key():
    k = "interop-" + uuid.uuid4().hex
    yield k
    make_test_client().delete(k)


def fetched_by_python_memcached(pm, key):
    """(found, value): get() cannot tell a stored None from a miss."""
    found = pm.get_multi([key])
    return key in found, found.get(key)


@pytest.mark.parametrize("value", [v for _, v in VALUES], ids=IDS)
def test_pylibmc_reads_what_python_memcached_wrote(lmc, pm, key, value):
    assert pm.set(key, value)
    got = lmc.get(key, "MISSING")
    assert got != "MISSING" or value == "MISSING"
    assert got == value and type(got) is type(value)


@pytest.mark.parametrize("value", [v for _, v in VALUES], ids=IDS)
def test_python_memcached_reads_what_pylibmc_wrote(lmc, pm, key, value):
    assert lmc.set(key, value)
    found, got = fetched_by_python_memcached(pm, key)
    assert found
    assert got == value and type(got) is type(value)


def test_pylibmc_reads_python_memcached_bools_as_bools(lmc, pm, key):
    for value in (True, False):
        assert pm.set(key, value)
        assert lmc.get(key) is value


def test_python_memcached_reads_pylibmc_bools_as_ints(lmc, pm, key):
    # Accepted: pylibmc stores a bool as an integer, so another client that
    # does not know about pylibmc's bool flag sees 1 or 0.
    for value in (True, False):
        assert lmc.set(key, value)
        got = pm.get(key)
        assert got == int(value) and type(got) is int


def test_pylibmc_reads_python_memcached_compressed_values(lmc, pm, key):
    pm.set(key, LARGE, min_compress_len=100)
    assert lmc.get(key) == LARGE
    pm.set(key, LARGE.encode(), min_compress_len=100)
    assert lmc.get(key) == LARGE.encode()


def test_python_memcached_reads_pylibmc_compressed_values(lmc, pm, key):
    lmc.set(key, LARGE, min_compress_len=100)
    assert pm.get(key) == LARGE
    lmc.set(key, LARGE.encode(), min_compress_len=100)
    assert pm.get(key) == LARGE.encode()


def test_pylibmc_reads_python_memcached_compressed_cas(lmc, pm, key):
    assert pm.set(key, "first")
    assert pm.gets(key) == "first"
    assert pm.cas(key, LARGE, min_compress_len=100)
    assert lmc.get(key) == LARGE


def test_python_memcached_reads_pylibmc_compressed_cas(binary, pm, key):
    lmc = make_test_client(binary=binary, behaviors={"cas": True})
    lmc.set(key, "first")
    _, token = lmc.gets(key)
    assert lmc.cas(key, LARGE, token, min_compress_len=100)
    assert pm.get(key) == LARGE


def test_multi_calls_interoperate(lmc, pm):
    keys = ["interop-" + uuid.uuid4().hex for _ in VALUES]
    mapping = {k: v for k, (_, v) in zip(keys, VALUES) if v is not None}
    try:
        assert pm.set_multi(mapping) == []
        assert lmc.get_multi(list(mapping)) == mapping
        assert lmc.set_multi(mapping) == []
        assert pm.get_multi(list(mapping)) == mapping
    finally:
        lmc.delete_multi(list(mapping))
