"""MEMCACHED_TIMEOUT is exposed as pylibmc.Timeout."""

import socket
import threading

import pytest

import pylibmc


def test_timeout_class():
    assert issubclass(pylibmc.Timeout, pylibmc.Error)
    assert pylibmc.Timeout.retcode == 31
    assert "Timeout" in dict(pylibmc.exceptions)
    # Must not shadow the builtin of the same flavour.
    assert pylibmc.Timeout is not TimeoutError


@pytest.fixture
def blackhole():
    """A server that accepts connections and never replies."""
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    conns = []

    def accept():
        while True:
            try:
                conns.append(srv.accept()[0])
            except OSError:
                return

    threading.Thread(target=accept, daemon=True).start()
    yield srv.getsockname()[1]
    srv.close()
    for c in conns:
        c.close()


@pytest.mark.parametrize("binary", [False, True])
def test_get_timeout(blackhole, binary):
    mc = pylibmc.Client(["127.0.0.1:%d" % blackhole], binary=binary,
                        behaviors={"_poll_timeout": 300})
    try:
        r = mc.get("k")
    except pylibmc.Timeout:
        return  # libmemcached >= 1.1 reports timeouts
    except pylibmc.Error as e:
        pytest.fail("expected Timeout, got %r" % e)
    assert r is None
    pytest.skip("this libmemcached turns a get timeout into a silent miss")
