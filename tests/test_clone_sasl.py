"""Clones of an authenticated client must authenticate too.

There is no SASL server in the test suite, so a tiny fake binary-protocol
server records the opcode of the first request each connection sends. A client
with SASL credentials starts with SASL_LIST_MECHS (0x20) before anything else;
one without sends its command straight away.
"""

import socket
import struct
import threading

import pytest

import pylibmc
import _pylibmc
from pylibmc import ClientPool, ThreadMappedPool

OP_SASL_LIST_MECHS = 0x20

pytestmark = pytest.mark.skipif(not _pylibmc.support_sasl,
                                reason="built without SASL support")


class FirstOpcodeServer:
    def __init__(self):
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(16)
        self.port = self.sock.getsockname()[1]
        self.opcodes = []
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self.serve, args=(conn,), daemon=True).start()

    def serve(self, conn):
        first = True
        try:
            while True:
                hdr = b""
                while len(hdr) < 24:
                    chunk = conn.recv(24 - len(hdr))
                    if not chunk:
                        return
                    hdr += chunk
                magic, opcode, keylen, extlen, _, _, bodylen, opaque, _ = \
                    struct.unpack(">BBHBBHIIQ", hdr)
                body = b""
                while len(body) < bodylen:
                    chunk = conn.recv(bodylen - len(body))
                    if not chunk:
                        return
                    body += chunk
                if first:
                    first = False
                    with self.lock:
                        self.opcodes.append(opcode)
                # Status 0x81: unknown command. Enough to make the client give up.
                conn.sendall(struct.pack(">BBHBBHIIQ", 0x81, opcode, 0, 0, 0,
                                         0x81, 0, opaque, 0))
        except OSError:
            pass
        finally:
            conn.close()

    def first_opcode_of(self, mc):
        with self.lock:
            del self.opcodes[:]
        try:
            mc.get("key")
        except pylibmc.Error:
            pass
        mc.disconnect_all()
        with self.lock:
            assert len(self.opcodes) >= 1
            return self.opcodes[0]

    def close(self):
        self.sock.close()


@pytest.fixture
def server():
    srv = FirstOpcodeServer()
    yield srv
    srv.close()


def make(srv, **kw):
    return pylibmc.Client(["127.0.0.1:%d" % srv.port], binary=True, **kw)


def test_fake_server_sees_sasl_on_original(server):
    mc = make(server, username="testuser", password="secretpw")
    assert server.first_opcode_of(mc) == OP_SASL_LIST_MECHS


def test_unauthenticated_client_and_clone_skip_sasl(server):
    mc = make(server)
    assert server.first_opcode_of(mc) != OP_SASL_LIST_MECHS
    assert server.first_opcode_of(mc.clone()) != OP_SASL_LIST_MECHS


def test_clone_authenticates(server):
    mc = make(server, username="testuser", password="secretpw")
    assert server.first_opcode_of(mc.clone()) == OP_SASL_LIST_MECHS


def test_clone_outlives_original(server):
    mc = make(server, username="testuser", password="secretpw")
    clone = mc.clone()
    del mc
    assert server.first_opcode_of(clone) == OP_SASL_LIST_MECHS


def test_clone_of_clone_authenticates(server):
    mc = make(server, username="testuser", password="secretpw")
    assert server.first_opcode_of(mc.clone().clone()) == OP_SASL_LIST_MECHS


def test_many_clones_dealloc(server):
    mc = make(server, username="testuser", password="secretpw")
    for _ in range(200):
        mc.clone()
    assert server.first_opcode_of(mc) == OP_SASL_LIST_MECHS


def test_client_pool_clones_authenticate(server):
    mc = make(server, username="testuser", password="secretpw")
    pool = ClientPool(mc, 2)
    with pool.reserve() as pmc:
        assert server.first_opcode_of(pmc) == OP_SASL_LIST_MECHS


def test_thread_mapped_pool_clones_authenticate(server):
    mc = make(server, username="testuser", password="secretpw")
    pool = ThreadMappedPool(mc)
    with pool.reserve() as pmc:
        assert server.first_opcode_of(pmc) == OP_SASL_LIST_MECHS
