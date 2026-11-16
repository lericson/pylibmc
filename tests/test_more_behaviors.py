"""tcp_keepidle, randomize_replica_read, server_timeout_limit and murmur3 (#380).

Also: get_behaviors() must not raise for a hash or distribution value that
pylibmc has no name for.
"""

import uuid

import pytest

import _pylibmc
import pylibmc
import pylibmc.consts
from tests import server_address

SERVER = server_address()


def make(binary=False, **behaviors):
    return pylibmc.Client([SERVER], binary=binary, behaviors=behaviors)


@pytest.mark.parametrize("binary", [False, True], ids=["text", "binary"])
@pytest.mark.parametrize("name, values", [
    ("tcp_keepidle", [30, 7200, 0]),
    ("randomize_replica_read", [1, 0]),
    ("server_timeout_limit", [3, 1, 0]),
])
def test_roundtrip(name, values, binary):
    assert name in pylibmc.all_behaviors
    assert make(binary=binary).get_behaviors()[name] == 0
    for value in values:
        assert make(binary=binary, **{name: value}).get_behaviors()[name] == value
        mc = make(binary=binary)
        mc.behaviors[name] = value
        assert mc.get_behaviors()[name] == value
        assert mc.clone().get_behaviors()[name] == value


@pytest.mark.parametrize("binary", [False, True], ids=["text", "binary"])
@pytest.mark.parametrize("name", ["tcp_keepidle", "server_timeout_limit"])
def test_client_still_works(name, binary):
    mc = make(binary=binary, **{name: 5})
    if name == "tcp_keepidle":
        mc.behaviors["tcp_keepalive"] = 1
    key, value = uuid.uuid4().hex, uuid.uuid4().hex
    assert mc.set(key, value)
    assert mc.get(key) == value


def test_randomize_replica_read_reads_back_from_replicas():
    # libmemcached only consults randomize_replica_read on binary-protocol
    # multi-gets with replicas; all of them sit on one server here, so every
    # read must still find the value.
    mc = make(binary=True, num_replicas=1, randomize_replica_read=1)
    keys = [uuid.uuid4().hex for _ in range(20)]
    assert mc.set_multi(dict.fromkeys(keys, "v")) == []
    for _ in range(5):
        assert mc.get_multi(keys) == dict.fromkeys(keys, "v")


def _murmur3(key):
    """libhashkit's hashkit_murmur3: MurmurHash3_x86_32, seed 0xdeadbeef * len."""
    def rotl(x, r):
        return ((x << r) | (x >> (32 - r))) & 0xffffffff
    data, n = key.encode(), len(key)
    h = (0xdeadbeef * n) & 0xffffffff
    c1, c2 = 0xcc9e2d51, 0x1b873593
    for i in range(0, n - n % 4, 4):
        k = int.from_bytes(data[i:i + 4], "little")
        k = rotl((k * c1) & 0xffffffff, 15) * c2 & 0xffffffff
        h = (rotl(h ^ k, 13) * 5 + 0xe6546b64) & 0xffffffff
    k = int.from_bytes(data[n - n % 4:], "little")
    k = rotl((k * c1) & 0xffffffff, 15) * c2 & 0xffffffff
    h ^= k ^ n
    h ^= h >> 16
    h = (h * 0x85ebca6b) & 0xffffffff
    h ^= h >> 13
    h = (h * 0xc2b2ae35) & 0xffffffff
    return h ^ (h >> 16)


# Client.hash() returns the index of the server the key maps to, so give it
# many (never contacted) servers and modula distribution to see the hash.
NSERVERS = 997
SERVERS = ["10.255.%d.%d:11211" % divmod(i, 256) for i in range(NSERVERS)]
needs_murmur3 = pytest.mark.skipif(
    "murmur3" not in pylibmc.hashers,
    reason="murmur3 is only exposed with libmemcached 1.1")


@needs_murmur3
@pytest.mark.parametrize("binary", [False, True], ids=["text", "binary"])
def test_murmur3_hashes_keys(binary):
    mc = pylibmc.Client(SERVERS, binary=binary, behaviors={"hash": "murmur3"})
    assert mc.get_behaviors()["hash"] == "murmur3"
    default = pylibmc.Client(SERVERS, binary=binary)
    murmur = pylibmc.Client(SERVERS, binary=binary, behaviors={"hash": "murmur"})
    keys = ["a", "ab", "abc", "abcd", "abcde"] + [uuid.uuid4().hex for _ in range(50)]
    got = [mc.hash(k) for k in keys]
    assert got == [mc.hash(k) for k in keys]
    assert got == [_murmur3(k) % NSERVERS for k in keys]
    assert got != [default.hash(k) for k in keys]
    assert got != [murmur.hash(k) for k in keys]


@needs_murmur3
@pytest.mark.parametrize("binary", [False, True], ids=["text", "binary"])
def test_murmur3_against_server(binary):
    mc = make(binary=binary, hash="murmur3")
    key = uuid.uuid4().hex
    assert mc.set(key, "x")
    assert mc.get(key) == "x"


@pytest.mark.skipif(_pylibmc.libmemcached_version_hex >= 0x01001000,
                    reason="libmemcached 1.0.x only")
def test_murmur3_not_offered_on_1_0():
    # 1.0.x accepts MURMUR3 but hashes with MURMUR and reports MURMUR back.
    assert "murmur3" not in pylibmc.hashers
    assert not hasattr(_pylibmc, "hash_murmur3")


@pytest.mark.parametrize("binary", [False, True], ids=["text", "binary"])
def test_unnamed_hash_is_reported_as_integer(monkeypatch, binary):
    # Simulate a libmemcached that reports a hash pylibmc has no name for.
    number = pylibmc.hashers["fnv1a_32"]
    monkeypatch.delitem(pylibmc.consts.hashers_rvs, number)
    mc = make(binary=binary, hash="fnv1a_32")
    behaviors = mc.get_behaviors()
    assert behaviors["hash"] == number
    # ...and what get_behaviors() returned can be set again.
    other = make(binary=binary)
    other.behaviors = behaviors
    assert other.get_behaviors()["hash"] == number
    other.behaviors["hash"] = number
    assert other.get_behaviors()["hash"] == number


def test_unnamed_distribution_is_reported_as_integer(monkeypatch):
    number = pylibmc.distributions["consistent"]
    monkeypatch.delitem(pylibmc.consts.distributions_rvs, number)
    mc = make(distribution="consistent")
    assert mc.get_behaviors()["distribution"] == number
    other = make()
    other.behaviors = mc.get_behaviors()
    assert other.get_behaviors()["distribution"] == number
