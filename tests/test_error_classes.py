"""Exception classes for more libmemcached return codes (#381).

ErrorReply (the server answering "ERROR") used to be called SocketCreateError;
the old name is the same class and still works, with a DeprecationWarning.
The AUTH_* codes against a real SASL server are in test_sasl_login.py.
"""

import socket
import struct
import threading
import warnings

import pytest

import _pylibmc
import pylibmc
from tests import server_address

# libmemcached's return codes, the same in 1.0.18 and 1.1.4 (return.h).
NEW_CLASSES = {
    "ErrorReply": 11,             # MEMCACHED_ERROR
    "SystemCallError": 26,        # MEMCACHED_ERRNO
    "InvalidArguments": 38,       # MEMCACHED_INVALID_ARGUMENTS
    "AuthProblem": 40,            # MEMCACHED_AUTH_PROBLEM
    "AuthFailure": 41,            # MEMCACHED_AUTH_FAILURE
    "InProgress": 46,             # MEMCACHED_IN_PROGRESS
    "ServerAllocationError": 48,  # MEMCACHED_SERVER_MEMORY_ALLOCATION_FAILURE
}


@pytest.mark.parametrize("name, retcode", sorted(NEW_CLASSES.items()))
def test_class(name, retcode):
    cls = getattr(pylibmc, name)
    assert cls is getattr(_pylibmc, name)
    assert issubclass(cls, pylibmc.Error)
    assert cls.retcode == retcode
    assert cls.__name__ == name
    assert (name, cls) in _pylibmc.exceptions
    assert cls in pylibmc.consts.errors


def test_exception_names_and_codes_are_unique():
    names = [name for name, _ in _pylibmc.exceptions]
    assert len(names) == len(set(names))
    codes = [cls.retcode for _, cls in _pylibmc.exceptions
             if hasattr(cls, "retcode")]
    assert len(codes) == len(set(codes))


def test_socket_create_error_is_error_reply():
    with pytest.warns(DeprecationWarning, match="ErrorReply"):
        old = pylibmc.SocketCreateError
    assert old is pylibmc.ErrorReply
    # The C module keeps the old name without a warning.
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert _pylibmc.SocketCreateError is pylibmc.ErrorReply
    assert "SocketCreateError" not in pylibmc.__all__
    assert "ErrorReply" in pylibmc.__all__
    with pytest.raises(AttributeError):
        pylibmc.NoSuchThing


def test_star_import_does_not_warn():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        namespace = {}
        exec("from pylibmc import *", namespace)
    assert "ErrorReply" in namespace
    assert "SocketCreateError" not in namespace


class FakeServer:
    """Accept one connection at a time and answer with handler(sock)."""

    def __init__(self, handler):
        self.handler = handler
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.port = self.sock.getsockname()[1]
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            with conn:
                try:
                    self.handler(conn)
                except OSError:
                    pass

    def close(self):
        self.sock.close()


def answer_error(conn):
    buf = b""
    while True:
        data = conn.recv(4096)
        if not data:
            return
        buf += data
        while b"\r\n" in buf:
            _, buf = buf.split(b"\r\n", 1)
            conn.sendall(b"ERROR\r\n")


@pytest.fixture
def error_server():
    server = FakeServer(answer_error)
    yield server
    server.close()


def test_error_reply_is_raised(error_server):
    mc = pylibmc.Client(["127.0.0.1:%d" % error_server.port])
    with pytest.raises(pylibmc.ErrorReply) as info:
        mc.set("key", "value")
    assert "ERROR was returned by server" in str(info.value)
    # Code that still catches the old name keeps working.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        with pytest.raises(pylibmc.SocketCreateError):
            mc.set("key", "value")


def answer_out_of_memory(conn):
    """Swallow command lines, answer each data block as memcached does when
    it cannot allocate the item."""
    buf, expect_data = b"", False
    while True:
        data = conn.recv(4096)
        if not data:
            return
        buf += data
        while b"\r\n" in buf:
            line, buf = buf.split(b"\r\n", 1)
            if expect_data:
                conn.sendall(b"SERVER_ERROR out of memory storing object\r\n")
            expect_data = not expect_data and line.startswith(b"set ")


def test_server_out_of_memory_raises_server_allocation_error():
    server = FakeServer(answer_out_of_memory)
    try:
        mc = pylibmc.Client(["127.0.0.1:%d" % server.port])
        with pytest.raises(pylibmc.ServerAllocationError):
            mc.set("key", "value")
    finally:
        server.close()


def binary_sasl_refusing_server(conn):
    """Offer PLAIN and CRAM-MD5, refuse every SASL_AUTH with AUTH_ERROR."""
    buf = b""
    while True:
        while len(buf) < 24:
            data = conn.recv(4096)
            if not data:
                return
            buf += data
        (magic, opcode, _keylen, _extlen, _dtype, _vb, bodylen, opaque,
         _cas) = struct.unpack(">BBHBBHIIQ", buf[:24])
        while len(buf) < 24 + bodylen:
            data = conn.recv(4096)
            if not data:
                return
            buf += data
        buf = buf[24 + bodylen:]
        if opcode == 0x20:                  # SASL_LIST_MECHS
            status, body = 0, b"PLAIN CRAM-MD5"
        elif opcode in (0x21, 0x22):        # SASL_AUTH, SASL_STEP
            status, body = 0x20, b"Auth failure"
        else:
            status, body = 0x20, b""
        conn.sendall(struct.pack(">BBHBBHIIQ", 0x81, opcode, 0, 0, 0, status,
                                 len(body), opaque, 0) + body)


@pytest.mark.skipif(not _pylibmc.support_sasl, reason="built without SASL")
def test_refused_sasl_login_raises_auth_failure():
    server = FakeServer(binary_sasl_refusing_server)
    try:
        mc = pylibmc.Client(["127.0.0.1:%d" % server.port], binary=True,
                            username="user", password="wrong")
        try:
            mc.set("key", "value")
        except pylibmc.AuthFailure:
            pass
        except pylibmc.AuthProblem as e:
            # The client's SASL library could not even start; that is the
            # other new class, but not what this test is about.
            pytest.skip("client SASL has neither PLAIN nor CRAM-MD5: %s" % e)
        else:
            pytest.fail("a refused SASL login did not raise")
    finally:
        server.close()


@pytest.mark.parametrize("server", [
    "/" + "a" * 5000,                      # unix socket path too long
    "a" * 2000 + ":11211",                 # host name too long
])
def test_invalid_server_raises_invalid_arguments(server):
    with pytest.raises(pylibmc.InvalidArguments):
        pylibmc.Client([server])


def test_unknown_stat_raises_invalid_arguments():
    mc = pylibmc.Client([server_address()])
    with pytest.raises(pylibmc.InvalidArguments):
        mc.get_stats("no-such-stat-group")
