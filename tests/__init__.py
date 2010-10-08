"""Tests. They want YOU!!"""

import os
import socket
import unittest
import _pylibmc, pylibmc

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

def make_test_client(cls=pylibmc.Client, env=None, **kwds):
    """Make a test client.

    >>> make_test_client() is not None
    True
    """
    if env is None:
        env = os.environ

    test_server = (
        _pylibmc.server_type_tcp,
        str(env.get("MEMCACHED_HOST", "127.0.0.1")),
        int(env.get("MEMCACHED_PORT", "11211")))
    
    alive, version = is_alive(test_server)
    assert alive, "test TCP memcached %s not alive" % (test_server[1:],)
    return cls([test_server], **kwds)

class PylibmcTestCase(unittest.TestCase):
    def setUp(self):
        self.mc = make_test_client()

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
