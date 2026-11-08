"""Regression test for premature Py_DECREF in PylibMC_Client_gets.

The bug only triggered with str keys: _key_normalized_obj encodes the
str into a new bytes object, and the call to Py_DECREF
deallocated it immediately (BEFORE it was passed to memcached_mget),
causing a use-after-free and potential reads of arbitrary keys.

Requires a running memcached (see MEMCACHED_HOST/PORT env vars).
"""

import os
import subprocess
import sys
import textwrap

import pytest

from pylibmc.test import make_test_client
from tests import PylibmcTestCase


def _run_with_debug_malloc(script, timeout=10):
    """Run a Python script in a subprocess with PYTHONMALLOC=debug.

    The debug allocator fills freed memory with 0xDD, making
    use-after-free bugs deterministically detectable.
    """
    return subprocess.run(
        [sys.executable, "-c", script],
        env={**os.environ, "PYTHONMALLOC": "debug"},
        capture_output=True,
        text=True,
        timeout=timeout,
    )


class TestGetsUseAfterFree(PylibmcTestCase):

    def test_gets_str_key_reads_freed_buffer(self):
        """gets(str_key) sends garbage because the key buffer is freed first.

        With PYTHONMALLOC=debug the freed buffer becomes 0xDD bytes, so
        memcached_mget asks for a nonexistent key and returns a miss.
        get(str_key) works correctly as a control.

        This test runs in a subprocess so that PYTHONMALLOC=debug is
        active regardless of how the outer test runner was invoked.
        """
        host = os.environ.get("MEMCACHED_HOST", "127.0.0.1")
        port = os.environ.get("MEMCACHED_PORT", "11211")

        result = _run_with_debug_malloc(textwrap.dedent(f"""\
            import sys
            import pylibmc

            mc = pylibmc.Client(
                ["{host}:{port}"], behaviors={{"cas": True}},
            )

            key_str = "test_gets_uaf"
            key_bytes = key_str.encode("utf-8")
            assert mc.set(key_bytes, 42)

            # Control: get() Py_DECREFs AFTER memcached_get — no UAF.
            val = mc.get(key_str)
            if val != 42:
                print(f"get() failed: {{val!r}}", file=sys.stderr)
                sys.exit(2)

            # Bug: gets() Py_DECREFs BEFORE memcached_mget — UAF.
            value, cas = mc.gets(key_str)
            if value != 42:
                print(
                    f"BUG: gets({{key_str!r}}) = ({{value!r}}, {{cas!r}}), "
                    f"expected (42, <cas>)\\n"
                    f"     get({{key_str!r}})  = 42 (correct)\\n"
                    f"Key buffer was used after free in PylibMC_Client_gets.",
                    file=sys.stderr,
                )
                sys.exit(1)
        """))

        if result.returncode == 1:
            pytest.fail(
                f"gets() use-after-free confirmed:\n{result.stderr.strip()}"
            )
        elif result.returncode == 2:
            pytest.fail(
                f"get() failed (is memcached running?):\n"
                f"{result.stderr.strip()}"
            )
        elif result.returncode != 0:
            pytest.fail(
                f"Subprocess failed (exit {result.returncode}):\n"
                f"{result.stderr.strip()}"
            )

    def test_gets_bytes_key_not_affected(self):
        """gets(bytes_key) was not affected by the bug.
        
        This serves as a control case for the test.
        """
        mc = make_test_client(binary=False, behaviors={"cas": True})
        key = b"test_gets_bytes_ok"
        assert mc.set(key, 99)
        value, _cas = mc.gets(key)
        assert value == 99
