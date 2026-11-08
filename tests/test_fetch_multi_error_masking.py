"""Regression test for error masking in _fetch_multi.

If the connection failed after the initial memcached_mget had already succeeded,
_fetch_multi would interpret the NULL return from memcached_fetch_result as EOF
and unconditionally overwrite the result's status with MEMCACHED_SUCCESS.
"""

import socket
import threading
import time
import unittest

import pytest

import pylibmc


def _mock_text_server():
    """Start a mock memcached that sends one VALUE then drops the connection.

    Returns (port, thread).  The server socket is cleaned up by the
    handler thread after a single accepted connection.
    """
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(("127.0.0.1", 0))
    port = server_sock.getsockname()[1]
    server_sock.listen(1)
    server_sock.settimeout(10)

    def handler():
        try:
            conn, _ = server_sock.accept()
            data = b""
            while b"\r\n" not in data:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            conn.sendall(b"VALUE key1 0 5\r\nhello\r\n")
            time.sleep(0.05)
            conn.close()
        except Exception:
            pass
        finally:
            server_sock.close()

    t = threading.Thread(target=handler, daemon=True)
    t.start()
    return port, t


class TestFetchMultiErrorMasking(unittest.TestCase):

    def test_get_multi_returns_error_on_connection_drop(self):
        port, server_thread = _mock_text_server()

        mc = pylibmc.Client([f"127.0.0.1:{port}"])
        try:
            result = mc.get_multi([b"key1", b"key2", b"key3"])
            pytest.fail(f"get_multi failed to raise pylibmc.Error. Partial results: {result!r}")
        except pylibmc.Error:
            return  # Correct: connection error raised.
        finally:
            server_thread.join()
