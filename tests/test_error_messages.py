"""Error messages say what went wrong, not just a libmemcached number."""

import re
import socket

import pytest

import pylibmc


def closed_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(params=[False, True], ids=["text", "binary"])
def dead_client(request):
    return pylibmc.Client(["127.0.0.1:%d" % closed_port()],
                          binary=request.param)


def test_connection_failure_message(dead_client):
    with pytest.raises(pylibmc.ConnectionError) as ei:
        dead_client.get("somekey")
    msg = str(ei.value)
    assert ei.value.retcode > 0
    # The prefix is unchanged: number, function and key.
    assert msg.startswith("error %d from memcached_get(somekey): "
                          % ei.value.retcode)
    # And the text from memcached_strerror follows.
    assert "CONNECTION FAILURE" in msg


def test_server_disabled_message(dead_client):
    with pytest.raises(pylibmc.Error):
        dead_client.get("somekey")
    # Now the server is marked as failed; the exception class is ServerDown
    # where libmemcached has that return code, with its own text.
    with pytest.raises(pylibmc.ServerDown) as ei:
        dead_client.set("somekey", 1)
    msg = str(ei.value)
    assert msg.startswith("error %d from memcached_set: "
                          % ei.value.retcode)
    assert "SERVER HAS FAILED" in msg


def test_message_after_prefix_is_never_empty(dead_client):
    with pytest.raises(pylibmc.Error) as ei:
        dead_client.get_multi(["a", "b"])
    m = re.match(r"error (\d+) from (\w+)(?:\([^)]*\))?: (.+)", str(ei.value),
                 re.S)
    assert m, str(ei.value)
    assert int(m.group(1)) == ei.value.retcode
    assert m.group(3).strip()


def test_retcode_matches_exceptions_list():
    for name, exc in pylibmc.exceptions:
        if hasattr(exc, "retcode"):
            assert getattr(pylibmc, name) is exc
