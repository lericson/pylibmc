"""cas compresses like set does (issue #285).

cas used to have its own code path that could not compress and took no
min_compress_len or compress_level. It now goes through the same serialization
and compression as set.
"""

import os
import socket
import time
import uuid

import pytest

import pylibmc
from pylibmc.test import make_test_client
from tests import get_refcounts

f_pickle, f_int, f_long, f_zlib, f_text = (1 << i for i in range(5))

needs_zlib = pytest.mark.skipif(not pylibmc.support_compression,
                                reason="pylibmc built without zlib")

BIG = "compressible " * 2000
THRESHOLD = 100


class RawClient(pylibmc.Client):
    """get() returns (bytes, flags). The C layer has already inflated
    compressed values by then, so the flags say what was stored and the bytes
    what the value is."""

    def deserialize(self, bytes_, flags):
        return bytes_, flags


def stored(key):
    """(flags, length) of what memcached holds, asking it over a socket."""
    sock = socket.create_connection((os.environ.get("MEMCACHED_HOST",
                                                    "127.0.0.1"),
                                     int(os.environ.get("MEMCACHED_PORT",
                                                        11211))))
    try:
        sock.sendall(b"get " + key.encode() + b"\r\n")
        buf = b""
        while not buf.endswith(b"END\r\n"):
            chunk = sock.recv(65536)
            assert chunk, buf
            buf += chunk
    finally:
        sock.close()
    _, _, flags, length = buf.split(b"\r\n", 1)[0].split()
    return int(flags), int(length)


@pytest.fixture(params=[False, True], ids=["text", "binary"])
def binary(request):
    return request.param


@pytest.fixture
def c(binary):
    return make_test_client(binary=binary, behaviors={"cas": True})


@pytest.fixture
def raw(binary):
    return make_test_client(RawClient, binary=binary, behaviors={"cas": True})


@pytest.fixture
def key():
    k = "cas-" + uuid.uuid4().hex
    yield k
    make_test_client().delete(k)


def swap(client, key, value, **kwds):
    """Store a first value, then cas value over it with a fresh token."""
    client.set(key, "first")
    _, token = client.gets(key)
    return client.cas(key, value, token, **kwds)


@needs_zlib
@pytest.mark.parametrize("value", [BIG, BIG.encode(), {"a": BIG}],
                         ids=["text", "bytes", "pickle"])
def test_large_value_is_stored_compressed(c, raw, key, value):
    assert swap(c, key, value, min_compress_len=THRESHOLD) is True
    flags, length = stored(key)
    assert flags & f_zlib
    assert length < len(BIG) // 4
    assert raw.get(key)[1] & f_zlib
    assert c.get(key) == value


@needs_zlib
def test_small_value_is_stored_uncompressed(c, raw, key):
    assert swap(c, key, "short", min_compress_len=THRESHOLD) is True
    flags, length = stored(key)
    assert not flags & f_zlib
    assert length == len(b"short")
    assert c.get(key) == "short"


@needs_zlib
def test_no_min_compress_len_means_no_compression(c, raw, key):
    assert swap(c, key, BIG) is True
    flags, length = stored(key)
    assert not flags & f_zlib
    assert length == len(BIG)


@needs_zlib
def test_compressed_cas_matches_compressed_set(c, raw, key):
    c.set(key, BIG, min_compress_len=THRESHOLD)
    from_set = stored(key)
    assert swap(c, key, BIG, min_compress_len=THRESHOLD)
    assert stored(key) == from_set


@needs_zlib
def test_stale_and_fresh_cas_with_compressed_values(c, key):
    c.set(key, "first")
    _, token = c.gets(key)
    assert c.cas(key, BIG, token, min_compress_len=THRESHOLD) is True
    # The token is now stale.
    assert c.cas(key, BIG + "x", token, min_compress_len=THRESHOLD) is False
    assert c.get(key) == BIG
    _, token = c.gets(key)
    assert c.cas(key, BIG + "x", token, min_compress_len=THRESHOLD) is True
    assert c.get(key) == BIG + "x"


@needs_zlib
def test_positional_arguments(c, raw, key):
    c.set(key, "first")
    _, token = c.gets(key)
    assert c.cas(key, BIG, token, 0, THRESHOLD, 9) is True
    assert stored(key)[0] & f_zlib


@needs_zlib
@pytest.mark.parametrize("level", [-2, 10, 100])
def test_compress_level_out_of_range(c, key, level):
    c.set(key, "first")
    _, token = c.gets(key)
    with pytest.raises(ValueError):
        c.cas(key, BIG, token, min_compress_len=THRESHOLD,
              compress_level=level)
    with pytest.raises(ValueError):
        c.set(key, BIG, min_compress_len=THRESHOLD, compress_level=level)
    assert c.get(key) == "first"


@needs_zlib
def test_compress_levels_all_work(c, raw, key):
    for level in (-1, 1, 9):
        assert swap(c, key, BIG, min_compress_len=THRESHOLD,
                    compress_level=level)
        assert stored(key)[0] & f_zlib
        assert c.get(key) == BIG


@pytest.mark.skipif(pylibmc.support_compression, reason="zlib is available")
def test_min_compress_len_without_zlib_is_a_type_error(c, key):
    c.set(key, "first")
    _, token = c.gets(key)
    with pytest.raises(TypeError):
        c.cas(key, BIG, token, min_compress_len=THRESHOLD)
    with pytest.raises(TypeError):
        c.set(key, BIG, min_compress_len=THRESHOLD)


@needs_zlib
def test_time_is_still_honored(c, key):
    assert swap(c, key, BIG, time=1, min_compress_len=THRESHOLD)
    assert c.get(key) == BIG
    time.sleep(2.2)
    assert c.get(key) is None


def test_negative_time_is_still_an_error(c, key):
    c.set(key, "first")
    _, token = c.gets(key)
    with pytest.raises(ValueError):
        c.cas(key, "x", token, -1)


def test_cas_without_compression_arguments_is_unchanged(c, key):
    c.set(key, "first")
    _, token = c.gets(key)
    assert c.cas(key, "second", token) is True
    assert c.cas(key, "third", token) is False
    assert c.get(key) == "second"
    _, token = c.gets(key)
    assert c.cas(key=key, val="fourth", cas=token, time=0) is True
    assert c.get(key) == "fourth"


def test_cas_on_missing_key_raises(c, key):
    with pytest.raises(pylibmc.Error):
        c.cas(key, "x", 1)


def test_cas_without_cas_behavior(binary, key):
    c = make_test_client(binary=binary)
    with pytest.raises(ValueError):
        c.cas(key, "x", 1)


@needs_zlib
def test_compressed_cas_does_not_leak_references(c, key):
    c.set(key, "first")
    value = uuid.uuid4().hex * 50
    k = key.encode()

    def churn(n):
        for _ in range(n):
            _, token = c.gets(key)
            assert c.cas(key, value, token, min_compress_len=THRESHOLD)

    churn(20)
    before = get_refcounts([k, value])
    churn(500)
    after = get_refcounts([k, value])
    assert after == before


@needs_zlib
def test_master_key_cas_compresses(c, raw, key):
    """cas with master_key= goes through memcached_cas_by_key and still
    compresses like set does."""
    mk = "mk-" + uuid.uuid4().hex
    c.set(key, "first", master_key=mk)
    _, token = c.gets(key, master_key=mk)
    assert c.cas(key, BIG, token, min_compress_len=THRESHOLD,
                 master_key=mk) is True
    flags, length = stored(key)
    assert flags & f_zlib
    assert length < len(BIG) // 4
    assert c.get(key, master_key=mk) == BIG
    # The old token is stale now, with a master key too.
    assert c.cas(key, BIG + "x", token, min_compress_len=THRESHOLD,
                 master_key=mk) is False
