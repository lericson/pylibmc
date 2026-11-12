#!/usr/bin/env python3
"""Print pylibmc.build_info() and fail if it is not what the leg expects.

Environment (an empty or unset value skips that check):
  EXPECT_LIBMEMCACHED   e.g. 1.0.18
  EXPECT_SASL           True or False
  EXPECT_COMPRESSION    True or False
"""
import os
import sys

import _pylibmc
import pylibmc

print(pylibmc.build_info())
print("runtime libmemcached:", _pylibmc.libmemcached_runtime_version)
print("from", pylibmc.__file__, _pylibmc.__file__)
got = {
    "EXPECT_LIBMEMCACHED": pylibmc.libmemcached_version,
    "EXPECT_SASL": str(pylibmc.support_sasl),
    "EXPECT_COMPRESSION": str(pylibmc.support_compression),
}
bad = False
for var, value in got.items():
    want = os.environ.get(var, "")
    if want:
        ok = want == value
        print("%-20s expected %-8s got %-8s %s"
              % (var, want, value, "ok" if ok else "MISMATCH"))
        bad = bad or not ok
sys.exit(1 if bad else 0)
