"""Regression tests for issue #180: with the ``buffer_requests`` behavior,
libmemcached answers a queued command with MEMCACHED_BUFFERED (error code
32), which is a status and not a failure.  It used to be raised as
``pylibmc.Error: error 32 from memcached_set``.
"""

import uuid

import pytest

import pylibmc
import _pylibmc

HOST = "127.0.0.1:11211"

# memcached_get() flushes queued writes first on 1.1.x only; on 1.0.x a read
# neither flushes them nor sees them.
READ_FLUSHES = _pylibmc.libmemcached_version_hex >= 0x01001000


@pytest.fixture(params=[False, True], ids=["text", "binary"])
def binary(request):
    return request.param


@pytest.fixture
def pair(binary):
    """A (buffered writer, plain reader) pair of clients and a key maker."""
    buffered = pylibmc.Client([HOST], binary=binary,
                              behaviors={"buffer_requests": True})
    reader = pylibmc.Client([HOST], binary=binary)
    tag = uuid.uuid4().hex
    yield buffered, reader, lambda name: "bufreq-%s-%s" % (tag, name)
    buffered.disconnect_all()
    for name in ("a", "b", "c", "n"):
        reader.delete(name_key(tag, name))
    reader.disconnect_all()


def name_key(tag, name):
    return "bufreq-%s-%s" % (tag, name)


def send(buffered):
    # Closing the connection is what reliably pushes out queued requests on
    # every libmemcached version.
    buffered.disconnect_all()


def test_set_reports_success_and_data_arrives(pair):
    mc, reader, key = pair
    assert mc.set(key("a"), "bar") is True
    send(mc)
    assert reader.get(key("a")) == "bar"


def test_set_multi_reports_success_and_data_arrives(pair):
    mc, reader, key = pair
    assert mc.set_multi({key("a"): 1, key("b"): 2}) == []
    send(mc)
    assert reader.get_multi([key("a"), key("b")]) == {key("a"): 1, key("b"): 2}


def test_add_and_replace(pair):
    mc, reader, key = pair
    assert mc.add(key("a"), "x") is True
    send(mc)
    assert reader.get(key("a")) == "x"
    assert mc.replace(key("a"), "y") is True
    send(mc)
    assert reader.get(key("a")) == "y"


def test_delete_reports_success_and_data_goes(pair):
    mc, reader, key = pair
    reader.set(key("a"), "bar")
    assert mc.delete(key("a")) is True
    send(mc)
    assert reader.get(key("a")) is None


def test_delete_multi(pair):
    mc, reader, key = pair
    reader.set_multi({key("a"): 1, key("b"): 2})
    assert mc.delete_multi([key("a"), key("b")]) is True
    send(mc)
    assert reader.get_multi([key("a"), key("b")]) == {}


def test_touch(pair):
    mc, reader, key = pair
    reader.set(key("a"), "bar")
    assert mc.touch(key("a"), 100) is True


def test_incr_decr(pair):
    mc, reader, key = pair
    reader.set(key("n"), "5")
    assert mc.incr(key("n"), 2) == 7
    assert mc.decr(key("n")) == 6
    assert reader.get(key("n")) == "6"


def test_cas(binary):
    mc = pylibmc.Client([HOST], binary=binary,
                        behaviors={"buffer_requests": True, "cas": True})
    reader = pylibmc.Client([HOST], binary=binary, behaviors={"cas": True})
    k = "bufreq-cas-" + uuid.uuid4().hex
    try:
        reader.set(k, "v1")
        _, cas = reader.gets(k)
        assert mc.cas(k, "v2", cas) is True
        mc.disconnect_all()
        assert reader.get(k) == "v2"
    finally:
        reader.delete(k)
        mc.disconnect_all()
        reader.disconnect_all()


def test_failed_conditional_still_false(pair):
    # Only a queued command counts as success; a command the server
    # rejected must still say so.
    mc, reader, key = pair
    reader.set(key("a"), "bar")
    assert mc.add(key("a"), "other") is False


@pytest.mark.skipif(not READ_FLUSHES,
                    reason="reads flush queued writes on libmemcached >= 1.1 only")
def test_read_flushes_queued_set(pair):
    mc, reader, key = pair
    assert mc.set(key("a"), "bar") is True
    assert mc.get(key("a")) == "bar"
    assert reader.get(key("a")) == "bar"


@pytest.mark.skipif(READ_FLUSHES,
                    reason="reads do not flush queued writes on libmemcached 1.0.x")
def test_read_does_not_see_queued_set_on_10x(pair):
    # Upstream behavior of libmemcached 1.0.x, recorded here and not
    # endorsed: this is why the first get after a buffered set returned None
    # in issue #180. (Such a read also discards the queued write, so nothing
    # is asserted about delivery.)
    mc, reader, key = pair
    assert mc.set(key("a"), "bar") is True
    assert mc.get(key("a")) is None
