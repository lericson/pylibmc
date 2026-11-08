"""Log in to a real memcached that requires SASL.

Skipped unless PYLIBMC_TEST_SASL_SERVER=host:port is set (together with
PYLIBMC_TEST_SASL_USER and PYLIBMC_TEST_SASL_PASSWORD); CI starts such a server
with .github/scripts/sasl-server.sh. The release job runs this very file
through .github/scripts/sasl-login-check.py, so there is one copy of the check.
It uses only unittest and pylibmc, so it also runs without pytest.

With PYLIBMC_TEST_SASL_REQUIRED=1 a missing server is a failure, not a skip.
"""

import os
import unittest

import pylibmc
from pylibmc.pools import ClientPool

SERVER = os.environ.get("PYLIBMC_TEST_SASL_SERVER")
USER = os.environ.get("PYLIBMC_TEST_SASL_USER")
PASSWORD = os.environ.get("PYLIBMC_TEST_SASL_PASSWORD")
REQUIRED = os.environ.get("PYLIBMC_TEST_SASL_REQUIRED") == "1"
CONFIGURED = bool(SERVER and USER and PASSWORD)


def roundtrip(client, key="sasl-login-test"):
    client.set(key, "ok")
    return client.get(key)


@unittest.skipUnless(REQUIRED, "PYLIBMC_TEST_SASL_REQUIRED is not set")
class SaslConfigured(unittest.TestCase):
    def test_server_configured(self):
        self.assertTrue(CONFIGURED, "PYLIBMC_TEST_SASL_* are not all set")


@unittest.skipUnless(CONFIGURED, "PYLIBMC_TEST_SASL_SERVER is not set")
class SaslLogin(unittest.TestCase):
    def make(self, **kw):
        return pylibmc.Client([SERVER], binary=True, **kw)

    def good(self):
        return self.make(username=USER, password=PASSWORD)

    def test_no_credentials_refused(self):
        with self.assertRaises(pylibmc.Error):
            roundtrip(self.make())

    def test_wrong_password_refused(self):
        with self.assertRaises(pylibmc.Error):
            roundtrip(self.make(username=USER, password=PASSWORD + "-wrong"))

    def test_correct_login_works(self):
        self.assertEqual(roundtrip(self.good()), "ok")

    def test_clone_authenticates(self):
        mc = self.good()
        self.assertEqual(roundtrip(mc), "ok")
        clone = mc.clone()
        self.assertEqual(roundtrip(clone), "ok")
        self.assertEqual(roundtrip(clone.clone()), "ok")

    def test_clone_of_fresh_client_authenticates(self):
        # Nothing has connected yet when the clone is made.
        self.assertEqual(roundtrip(self.good().clone()), "ok")

    def test_pool_of_clones_authenticates(self):
        pool = ClientPool(self.good(), 4)
        self.assertEqual(pool.qsize(), 4)
        for i in range(4):
            # The pool is a FIFO queue: each pass uses a different clone.
            with pool.reserve() as mc:
                self.assertEqual(roundtrip(mc, "sasl-pool-%d" % i), "ok")


if __name__ == "__main__":
    unittest.main()
