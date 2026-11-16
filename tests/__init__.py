"""Tests. They want YOU!!"""

import gc
import sys
import unittest
import pylibmc
from pylibmc.test import get_test_server, make_test_client


def server_address():
    """"host:port" of the shared test memcached.

    It is 127.0.0.1:11211 unless MEMCACHED_HOST or MEMCACHED_PORT say
    otherwise; tests that talk to the shared server use this (or
    make_test_client) and never spell out an address.
    """
    _, host, port = get_test_server()
    return "%s:%d" % (host, port)


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


def get_refcounts(refcountables):
    """Measure reference counts during testing.

    Measuring reference counts typically changes them (since at least
    one new reference is created as the argument to sys.getrefcount).
    Therefore, try to do it in a consistent and deterministic fashion.
    """
    if hasattr(sys, 'getrefcount'):
        gc.collect()
        return [sys.getrefcount(val) for val in refcountables]
