"""SASL login checks against memcached on 127.0.0.1:11211, which requires SASL.

Usage: sasl-login-check.py [PLUGIN_FILE]

Runs tests/test_sasl_login.py (the one copy of the login checks: no
credentials refused, wrong password refused, correct login works, clones and
pools authenticate) against the server that sasl-server.sh started, and exits
non-zero unless they all pass and none is skipped. With PLUGIN_FILE (say
libplain.so) it also demands that this plugin was loaded from the wheel's own
pylibmc/sasl2 directory, and that exactly one libsasl2 is mapped into the
process.

Needs only unittest, not pytest, so it runs in a bare wheel venv.
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = os.path.join(HERE, "..", "..", "tests")

os.environ.setdefault("PYLIBMC_TEST_SASL_SERVER", "127.0.0.1:11211")
os.environ.setdefault("PYLIBMC_TEST_SASL_USER", "testuser")
os.environ.setdefault("PYLIBMC_TEST_SASL_PASSWORD", "secretpw")
os.environ["PYLIBMC_TEST_SASL_REQUIRED"] = "1"

import pylibmc

PLUGIN = sys.argv[1] if len(sys.argv) > 1 else None
failures = []

print(pylibmc.build_info())
suite = unittest.defaultTestLoader.discover(
    TESTS, pattern="test_sasl_login.py", top_level_dir=TESTS)
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    failures.append("the login tests failed")
if result.skipped or result.testsRun < 7:
    failures.append("login tests were skipped or missing (ran %d)"
                    % result.testsRun)

with open("/proc/self/maps") as f:
    maps = {line.split()[-1] for line in f if "sasl" in line}
for path in sorted(maps):
    print("MAPPED", path)
if PLUGIN is not None:
    if not any(p.endswith("/pylibmc/sasl2/" + PLUGIN) for p in maps):
        failures.append("%s was not loaded from the wheel" % PLUGIN)
    n = len([p for p in maps if "libsasl2" in p.rsplit("/", 1)[-1]])
    if n != 1:
        failures.append("%d libsasl2 copies are mapped, expected 1" % n)

if failures:
    print("FAILED:", "; ".join(failures))
    sys.exit(1)
print("all SASL login checks passed")
