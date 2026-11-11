"""Compression keeps a value over the 1 MB item size limit storable.

This was in doctests.txt, which cannot skip itself on a build without zlib.
"""
from hashlib import md5

import pytest

import _pylibmc
import pylibmc
from tests import make_test_client

pytestmark = pytest.mark.skipif(not pylibmc.support_compression,
                                reason="pylibmc built without zlib")

BIG = 1024 * 1024 + 1


@pytest.fixture
def c():
    return make_test_client(_pylibmc.client, binary=True)


def test_bytes_over_the_size_limit(c):
    assert c.set("foo", b"a" * BIG, min_compress_len=1)
    assert md5(c.get("foo")).hexdigest() == md5(b"a" * BIG).hexdigest()


@pytest.mark.parametrize("kwargs", [{}, {"compress_level": 1},
                                    {"compress_level": 9}])
def test_text_over_the_size_limit(c, kwargs):
    assert c.set("foo", "a" * BIG, min_compress_len=1, **kwargs)
    assert c.get("foo") == "a" * BIG


def test_small_value_is_left_alone(c):
    assert c.set("foo", "abc", min_compress_len=1, compress_level=9)
    assert c.get("foo") == "abc"


@pytest.mark.parametrize("kwargs", [{}, {"compress_level": 1},
                                    {"compress_level": 9}])
def test_set_multi(c, kwargs):
    assert c.set_multi({"a": 20, "b": "*" * 500}, min_compress_len=1,
                       **kwargs) == []
