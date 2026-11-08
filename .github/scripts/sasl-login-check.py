"""Three SASL logins against memcached on 127.0.0.1:11211, which requires SASL.

Usage: sasl-login-check.py [PLUGIN_FILE]

Exits non-zero unless: no credentials are refused, a wrong password is refused,
and the correct login works. With PLUGIN_FILE (say libplain.so) it also demands
that this plugin was loaded from the wheel's own pylibmc/sasl2 directory, and
that exactly one libsasl2 is mapped into the process.
"""
import sys

import pylibmc

PLUGIN = sys.argv[1] if len(sys.argv) > 1 else None
failures = []


def attempt(label, should_work, **kw):
    try:
        c = pylibmc.Client(["127.0.0.1:11211"], binary=True, **kw)
        c.set("sasl-check", "ok")
        got = c.get("sasl-check")
        outcome = "worked (%r)" % (got,)
        worked = got == "ok"
    except Exception as e:
        outcome = "refused: %s: %s" % (type(e).__name__, e)
        worked = False
    verdict = "ok" if worked == should_work else "WRONG"
    print("RESULT %-30s -> %s [%s]" % (label, outcome, verdict))
    if worked != should_work:
        failures.append(label)


print(pylibmc.build_info())
attempt("no credentials", False)
attempt("wrong password", False, username="testuser", password="nope")
attempt("correct credentials", True, username="testuser", password="secretpw")

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
print("all three logins behaved")
