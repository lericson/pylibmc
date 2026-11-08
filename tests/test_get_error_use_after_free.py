"""Regression test: Client.get used its key after releasing it.

When memcached_get failed, PylibMC_Client_get built the error message from the
normalized key after it had already dropped its reference. For a str key that
is a temporary bytes object nothing else keeps alive, so the message was built
from freed memory (the same class of bug as gets(), see
test_gets_use_after_free.py).

With PYTHONMALLOC=debug freed memory is filled with 0xDD, so the key in the
message turns into garbage and the check below fails deterministically. It
needs no memcached server: nothing listens on port 1, which gives a real
connection error from memcached_get.
"""

import os
import subprocess
import sys
import textwrap

import pytest

SCRIPT = textwrap.dedent("""\
    import sys
    import pylibmc

    key = "uaf-key-" + "k" * 12
    c = pylibmc.Client(["127.0.0.1:1"], binary=%(binary)s)
    try:
        c.get(key)
    except pylibmc.Error as e:
        msg = str(e)
    else:
        print("get() did not raise", file=sys.stderr)
        sys.exit(2)

    # The message reads "error N from memcached_get(KEY): ..."
    if "(" + key + ")" not in msg:
        print("key missing from error message: %%r" %% (msg,), file=sys.stderr)
        sys.exit(1)
""")


def _run_with_debug_malloc(script, timeout=30):
    return subprocess.run(
        [sys.executable, "-c", script],
        env={**os.environ, "PYTHONMALLOC": "debug"},
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@pytest.mark.parametrize("binary", [False, True])
def test_get_error_message_contains_key(binary):
    result = _run_with_debug_malloc(SCRIPT % {"binary": binary})
    if result.returncode == 1:
        pytest.fail("get() built its error from a freed key:\n"
                    + result.stderr.strip())
    elif result.returncode == 2:
        pytest.fail("expected a connection error from port 1:\n"
                    + result.stderr.strip())
    elif result.returncode != 0:
        pytest.fail("subprocess failed (exit %d):\n%s"
                    % (result.returncode, result.stderr.strip()))
