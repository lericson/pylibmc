"""Importing pylibmc must not disturb any other libsasl2 user (issue #358).

Usage: sasl-isolation-check.py

Run it in a venv with a Linux wheel installed, on a system that has the
system's own libsasl2 with its modules, including GSSAPI
(libsasl2-modules-gssapi-mit), and with SASL_PATH unset. Checks, after
``import pylibmc``:

1. os.environ has no SASL_PATH, and neither does a subprocess started from
   Python;
2. the extension was told to use the wheel's plugin directory;
3. a second libsasl2, the system's, loaded into the same process through
   ctypes, is a separate copy and still finds its own plugins: it can
   start ANONYMOUS, NTLM and GSSAPI, none of which the wheel bundles.

With the old behaviour (SASL_PATH pointing at the wheel's five plugins for
every libsasl2) checks 1 and 3 fail.
"""
import ctypes
import glob
import os
import subprocess
import sys

import pylibmc
import _pylibmc

failures = []


def check(ok, what):
    print("ok  " if ok else "FAIL", what)
    if not ok:
        failures.append(what)


check("SASL_PATH" not in os.environ, "os.environ has no SASL_PATH")
child = subprocess.check_output(
    [sys.executable, "-c",
     "import os; print(repr(os.environ.get('SASL_PATH')))"],
    universal_newlines=True).strip()
check(child == "None", "a subprocess sees no SASL_PATH (saw %s)" % child)

bundled = os.path.join(os.path.dirname(os.path.abspath(pylibmc.__file__)),
                       "sasl2")
print("sasl_plugin_dir =", getattr(_pylibmc, "sasl_plugin_dir", "<missing>"))
check(getattr(_pylibmc, "sasl_plugin_dir", None) == bundled,
      "the extension uses the wheel's plugin directory " + bundled)

candidates = sorted(glob.glob("/usr/lib/*/libsasl2.so.2")
                    + glob.glob("/usr/lib64/libsasl2.so.2")
                    + glob.glob("/usr/lib/libsasl2.so.2"))
check(bool(candidates), "the system has a libsasl2: %s" % candidates)
if candidates:
    system = ctypes.CDLL(candidates[0], mode=ctypes.RTLD_LOCAL)
    with open("/proc/self/maps") as f:
        mapped = sorted({line.split()[-1] for line in f
                         if "libsasl2" in line.split()[-1]})
    for p in mapped:
        print("MAPPED", p)
    check(len(mapped) == 2, "two separate libsasl2 copies are mapped")

    # Use the system copy exactly as python-ldap would.
    system.sasl_client_init.argtypes = [ctypes.c_void_p]
    rc = system.sasl_client_init(None)
    check(rc == 0, "system sasl_client_init rc=%d" % rc)

    def available(mech):
        conn = ctypes.c_void_p()
        rc = system.sasl_client_new(
            b"memcached", b"localhost", None, None, None, 0,
            ctypes.byref(conn))
        assert rc == 0, rc
        out = ctypes.c_char_p()
        n = ctypes.c_uint()
        chosen = ctypes.c_char_p()
        rc = system.sasl_client_start(
            conn, mech.encode(), None, ctypes.byref(out), ctypes.byref(n),
            ctypes.byref(chosen))
        print("   sasl_client_start(%s) rc=%d" % (mech, rc))
        system.sasl_dispose(ctypes.byref(conn))
        return rc != -4  # SASL_NOMECH

    for mech in ("ANONYMOUS", "NTLM", "GSSAPI"):
        check(available(mech),
              "the system libsasl2 still has its own %s plugin" % mech)

if failures:
    print("FAILED:", "; ".join(failures))
    sys.exit(1)
print("all SASL isolation checks passed")
