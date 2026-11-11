#!/usr/bin/env python3
"""Fail on compiler warnings that are not in the allowlist.

Usage: check-warnings.py BUILD_LOG ALLOWLIST

Each compiler warning in the log ("file:line:col: warning: text") is
normalised to "file: text" (line numbers dropped, so an unrelated edit that
moves code does not fail the build) and must appear in the allowlist, one per
line; "#" starts a comment. A new warning, even a second kind in the same
file, fails the job. A warning that went away is only reported: remove it
from the allowlist when you fix it.

It also insists that the strict flags were really used and that the
interpreter's -DNDEBUG was not, because the point of the strict build is that
assert()s are live.
"""
import re
import sys

WARN = re.compile(r"^\s*(?P<file>[^\s:]+):\d+(?::\d+)?: warning: (?P<msg>.*)$")


def main(log_path, allow_path):
    with open(log_path, errors="replace") as f:
        lines = f.read().splitlines()
    with open(allow_path) as f:
        allowed = {l.strip() for l in f
                   if l.strip() and not l.startswith("#")}

    seen = {}
    for line in lines:
        m = WARN.match(line)
        if m:
            seen["%s: %s" % (m["file"], m["msg"])] = line

    compile_lines = [l for l in lines
                     if "_pylibmcmodule.c" in l and " -c " in l]
    if not compile_lines:
        sys.exit("no compile line for _pylibmcmodule.c in the log: was "
                 "anything built?")
    for l in compile_lines:
        if "-Wall" not in l or "-Wextra" not in l:
            sys.exit("strict flags missing from compile line: %s" % l)
        if "-DNDEBUG" in l:
            sys.exit("-DNDEBUG on the compile line, asserts are off: %s" % l)
    print("compile line has -Wall -Wextra and no -DNDEBUG")

    print("%d distinct warning(s), %d allowed" % (len(seen), len(allowed)))
    for key in sorted(seen):
        print("  %s %s" % ("ok " if key in allowed else "NEW", key))
    new = sorted(set(seen) - allowed)
    for key in sorted(allowed - set(seen)):
        print("note: allowlisted warning no longer produced: %s" % key)
    if new:
        print("\nNew compiler warnings. Fix them, or (if harmless) add these "
              "lines to %s:" % allow_path)
        for key in new:
            print(key)
            print("::error::new compiler warning: %s" % key)
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
