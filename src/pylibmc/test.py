"""Test utils."""

import os
import socket

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
    if type_ != _pylibmc.server_type_tcp:
        raise NotImplementedError("test server can only be on tcp for now")
    else:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((host, port))
            s.send(b"version\r\n")
            version = s.recv(4096)
        finally:
            s.close()
        vstr = b"VERSION "
        rnstr = b"\r\n"
        if not version.startswith(vstr) or not version.endswith(rnstr):
            raise ValueError(f"unexpected version return: {version!r}")
        else:
            version = version[8:-2]
        return version

def is_alive(addr):
    try:
        version = get_version(addr)
    except (ValueError, OSError):
        version = None
    return bool(version), version

def get_test_server(env=None, server_type="tcp", host="127.0.0.1",
                    port=11211):
    """The (server type, host, port) of the test memcached.

    MEMCACHED_TYPE, MEMCACHED_HOST and MEMCACHED_PORT in `env` (by default
    os.environ) override the keyword arguments.

    >>> get_test_server({"MEMCACHED_PORT": "11299"})
    (1, '127.0.0.1', 11299)
    """
    server_types = {"tcp": _pylibmc.server_type_tcp,
                    "udp": _pylibmc.server_type_udp,
                    "unix": _pylibmc.server_type_unix}

    if env is None:
        env = os.environ

    styp = env.get("MEMCACHED_TYPE", server_type)
    host = env.get("MEMCACHED_HOST", host)
    port = env.get("MEMCACHED_PORT", port)

    return (server_types[styp], str(host), int(port))

def make_test_client(cls=pylibmc.Client, env=None, server_type="tcp",
                     host="127.0.0.1", port=11211, **kwds):
    """Make a test client. `env` overrides keyword arguments.

    >>> make_test_client() is not None
    True
    """
    test_server = get_test_server(env=env, server_type=server_type,
                                  host=host, port=port)
    alive, version = is_alive(test_server)

    if alive:
        return cls([test_server], **kwds)
    else:
        raise NotAliveError(test_server)
