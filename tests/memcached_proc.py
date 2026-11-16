"""Start a private memcached for tests that need a particular transport.

The shared server on 127.0.0.1:11211 speaks TCP only, so the UDP and unix
socket tests start their own on free ports. Without a ``memcached`` binary the
tests skip, unless PYLIBMC_TEST_MEMCACHED_REQUIRED=1, in which case that is a
failure (CI sets it on the legs that install memcached).
"""

import os
import shutil
import socket
import subprocess
import tempfile
import time
import unittest

REQUIRED = os.environ.get("PYLIBMC_TEST_MEMCACHED_REQUIRED") == "1"
DEADLINE = 10.0


class Unavailable(Exception):
    pass


def skip_or_fail(test, reason):
    if REQUIRED:
        test.fail(reason)
    test.skipTest(reason)


def free_port(kind=socket.SOCK_STREAM):
    s = socket.socket(socket.AF_INET, kind)
    try:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]
    finally:
        s.close()


def wait_until(predicate, timeout=DEADLINE):
    """Poll *predicate* until true or *timeout* seconds; return its last value."""
    end = time.monotonic() + timeout
    while True:
        value = predicate()
        if value or time.monotonic() >= end:
            return value
        time.sleep(0.02)


def _can_connect(family, address):
    s = socket.socket(family, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect(address)
        return True
    except OSError:
        return False
    finally:
        s.close()


class Memcached(object):
    """A memcached subprocess. Raises Unavailable if it cannot be started."""

    def __init__(self, unix=False, udp=False):
        exe = shutil.which("memcached")
        if exe is None:
            raise Unavailable("no memcached binary on PATH")
        self.tmpdir = None
        self.tcp_port = self.udp_port = self.path = None
        self.proc = None
        # (Another process may grab a port between probing and starting.)
        for attempt in range(3):
            args = [exe, "-l", "127.0.0.1", "-m", "16"]
            if unix:
                if self.tmpdir is None:
                    # Unix socket paths are short (104 bytes on macOS), and
                    # $TMPDIR on macOS is long; so use /tmp where it exists.
                    base = "/tmp" if os.path.isdir("/tmp") else None
                    self.tmpdir = tempfile.mkdtemp(prefix="pylibmc-", dir=base)
                    self.path = os.path.join(self.tmpdir, "mc.sock")
                if len(self.path.encode()) > 100:
                    self.close()
                    raise Unavailable("unix socket path too long: %r" % self.path)
                args += ["-s", self.path, "-a", "0700", "-p", "0"]
                ready = lambda: (os.path.exists(self.path) and
                                 _can_connect(socket.AF_UNIX, self.path))
            else:
                self.tcp_port = free_port()
                args += ["-p", str(self.tcp_port)]
                ready = lambda: _can_connect(
                    socket.AF_INET, ("127.0.0.1", self.tcp_port))
            if udp:
                self.udp_port = free_port(socket.SOCK_DGRAM)
                args += ["-U", str(self.udp_port)]
            self.proc = subprocess.Popen(
                args, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            if wait_until(lambda: self.proc.poll() is not None or ready()) \
                    and self.proc.poll() is None:
                return
            err = b""
            if self.proc.poll() is None:
                self.proc.kill()
            err = self.proc.stderr.read()
            self.proc.wait()
            self.proc.stderr.close()
            self.proc = None
        self.close()
        raise Unavailable("memcached did not start: %s"
                          % err.decode("utf-8", "replace").strip())

    def close(self):
        if self.proc is not None:
            self.proc.kill()
            self.proc.wait()
            self.proc.stderr.close()
            self.proc = None
        if self.tmpdir is not None:
            shutil.rmtree(self.tmpdir, ignore_errors=True)
            self.tmpdir = None


class MemcachedTestCase(unittest.TestCase):
    """Base class: self.server is set up per class by subclasses' ``flavor``."""

    flavor = {}

    @classmethod
    def setUpClass(cls):
        cls.server = None
        cls.unavailable = None
        try:
            cls.server = Memcached(**cls.flavor)
        except Unavailable as exc:
            cls.unavailable = str(exc)

    @classmethod
    def tearDownClass(cls):
        if cls.server is not None:
            cls.server.close()

    def setUp(self):
        if self.unavailable:
            skip_or_fail(self, self.unavailable)
