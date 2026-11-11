"""A cas token that does not fit in 64 bits raises OverflowError (issue #357).

Since #342 the token was parsed with PyArg's "K", which converts without
overflow checking and keeps the low 64 bits: 2**64 became 0, which on the binary
protocol means "no cas check", so the value was overwritten unconditionally.
The other unsigned arguments had the same problem with "I".
"""

import socket
import threading
import uuid

import pytest

import pylibmc
from pylibmc.test import make_test_client
from tests import PylibmcTestCase


def key():
    return "t-" + uuid.uuid4().hex


class CasTokenTests(PylibmcTestCase):

    def clients(self):
        for binary in (False, True):
            yield make_test_client(binary=binary, behaviors={"cas": True})

    def test_out_of_range_tokens_raise_and_store_nothing(self):
        for c in self.clients():
            other = make_test_client(binary=c.binary, behaviors={"cas": True})
            for bad in (2 ** 64, 2 ** 64 + 5, 2 ** 65, -1, -(2 ** 64)):
                k = key()
                c.set(k, "original")
                c.gets(k)
                with self.assertRaises(OverflowError):
                    c.cas(k, "OVERWRITE", bad)
                with self.assertRaises(OverflowError):
                    c.cas(k, "OVERWRITE", cas=bad)
                self.assertEqual(other.get(k), "original", bad)

    def test_stale_in_range_tokens_return_false(self):
        for c in self.clients():
            other = make_test_client(binary=c.binary, behaviors={"cas": True})
            k = key()
            c.set(k, "original")
            _, token = c.gets(k)
            for stale in (2 ** 64 - 1, 2 ** 63, 2 ** 63 - 1, 1,
                          token + 1000000):
                self.assertFalse(c.cas(k, "OVERWRITE", stale), stale)
                self.assertEqual(other.get(k), "original", stale)

    def test_current_token_returns_true(self):
        for c in self.clients():
            k = key()
            c.set(k, "original")
            _, token = c.gets(k)
            self.assertTrue(c.cas(k, "new", token))
            self.assertEqual(c.get(k), "new")
            self.assertFalse(c.cas(k, "newer", token))
            self.assertEqual(c.get(k), "new")

    def test_non_integers_raise_typeerror(self):
        for c in self.clients():
            k = key()
            c.set(k, "original")
            for bad in ("1", None, 1.5, [1]):
                with self.assertRaises(TypeError):
                    c.cas(k, "OVERWRITE", bad)
            self.assertEqual(c.get(k), "original")

    def test_master_key_cas_checks_range(self):
        for c in self.clients():
            k = key()
            c.set(k, "original", master_key="mk")
            with self.assertRaises(OverflowError):
                c.cas(k, "OVERWRITE", 2 ** 64, master_key="mk")
            self.assertEqual(c.get(k, master_key="mk"), "original")
            _, token = c.gets(k, master_key="mk")
            self.assertTrue(c.cas(k, "new", token, master_key="mk"))

    def test_other_unsigned_arguments_do_not_wrap(self):
        c = make_test_client(binary=True, behaviors={"cas": True})
        k = key()
        c.set(k, 1)
        for bad, exc in ((2 ** 32, OverflowError), (-1, ValueError)):
            with self.assertRaises(exc):
                c.incr_multi([k], delta=bad)
            with self.assertRaises(exc):
                c.set(k, "x", min_compress_len=bad)
            with self.assertRaises(exc):
                c.set_multi({k: "x"}, min_compress_len=bad)
            with self.assertRaises(exc):
                c.cas(k, "x", 1, min_compress_len=bad)
        self.assertEqual(c.get(k), 1)


class FakeCasServer(object):
    """Records the command lines of a text-protocol server that answers
    every storage command with EXISTS. This is how the exact token that
    reaches the wire is checked, since the real server only ever hands out
    small tokens."""

    def __init__(self):
        self.lines = []
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.thread = threading.Thread(target=self.run)
        self.thread.daemon = True
        self.thread.start()

    def run(self):
        conn, _ = self.sock.accept()
        buf = b""
        while True:
            data = conn.recv(65536)
            if not data:
                break
            buf += data
            while b"\r\n" in buf:
                line, buf = buf.split(b"\r\n", 1)
                if line.startswith(b"cas "):
                    self.lines.append(line)
                    # the data block follows the command line
                    while b"\r\n" not in buf:
                        buf += conn.recv(65536)
                    _, buf = buf.split(b"\r\n", 1)
                    conn.sendall(b"EXISTS\r\n")
        conn.close()
        self.sock.close()


# Not 2**64 - 1: libmemcached 1.0.18's text protocol never sends a 20-digit
# token (cas returns False without writing anything), and 0 is not sent as 0.
@pytest.mark.parametrize("token", [1, 2 ** 63 - 1, 2 ** 63, 10 ** 19 - 1])
def test_large_tokens_reach_the_wire_unchanged(token):
    server = FakeCasServer()
    c = pylibmc.Client(["127.0.0.1:%d" % server.port], binary=False,
                       behaviors={"cas": True})
    assert c.cas("k", "v", token) is False
    c.disconnect_all()
    server.thread.join(5)
    assert len(server.lines) == 1
    assert server.lines[0].split()[-1] == str(token).encode()
