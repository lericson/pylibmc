"""Tests. They want YOU!!"""

import os
import socket
import unittest
import _pylibmc, pylibmc
from textwrap import dedent

class NotAliveError(Exception):
    template = dedent("""
    test memcached %s:%s not alive

    consider setting MEMCACHED_HOST and/or MEMCACHED_PORT
    to something more appropriate.""").lstrip()

    def __init__(self, svr):
        (self.server_type, self.address, self.port) = svr

    def __str__(self):
        return self.template % (self.address, self.port)

def get_version(addr):
    (type_, host, port) = addr
    if (type_ != _pylibmc.server_type_tcp):
        raise NotImplementedError("test server can only be on tcp for now")
    else:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((host, port))
            s.send("version\r\n")
            version = s.recv(4096)
        finally:
            s.close()
        if not version.startswith("VERSION ") or not version.endswith("\r\n"):
            raise ValueError("unexpected version return: %r" % (version,))
        else:
            version = version[8:-2]
        return version

def is_alive(addr):
    try:
        version = get_version(addr)
    except (ValueError, socket.error):
        version = None
    return (bool(version), version)

def make_test_client(cls=pylibmc.Client, env=None, server_type="tcp",
                     host="127.0.0.1", port=11211, **kwds):
    """Make a test client. `env` overrides keyword arguments.

    >>> make_test_client() is not None
    True
    """
    server_types = {"tcp": _pylibmc.server_type_tcp,
                    "udp": _pylibmc.server_type_udp,
                    "unix": _pylibmc.server_type_unix}

    if env is None:
        env = os.environ

    styp = env.get("MEMCACHED_TYPE", server_type)
    host = env.get("MEMCACHED_HOST", host)
    port = env.get("MEMCACHED_PORT", port)

    test_server = (server_types[styp], str(host), int(port))
    alive, version = is_alive(test_server)

    if alive:
        return cls([test_server], **kwds)
    else:
        raise NotAliveError(test_server)

class PylibmcTestCase(unittest.TestCase):
    memcached_client = pylibmc.Client
    memcached_server_type = "tcp"
    memcached_host = "127.0.0.1"
    memcached_port = "11211"

    def setUp(self):
        self.mc = make_test_client(cls=self.memcached_client,
                                   server_type=self.memcached_server_type,
                                   host=self.memcached_host,
                                   port=self.memcached_port)

    def tearDown(self):
        self.mc.disconnect_all()
        del self.mc

def dump_infos():
    if hasattr(_pylibmc, "__file__"):
        print "Starting tests with _pylibmc at", _pylibmc.__file__
    else:
        print "Starting tests with static _pylibmc:", _pylibmc
    print "Reported libmemcached version:", _pylibmc.libmemcached_version
    print "Reported pylibmc version:", _pylibmc.__version__
    print "Support compression:", _pylibmc.support_compression
