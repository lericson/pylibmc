"""remove_failed=N means "failure limit N" on every libmemcached version."""

import pytest

import pylibmc

pytestmark = pytest.mark.skipif(
    pylibmc._pylibmc.libmemcached_version_hex < 0x00049000,
    reason="remove_failed needs libmemcached >= 0.49")


def make(**behaviors):
    return pylibmc.Client(["127.0.0.1:11211"], behaviors=behaviors)


def test_default_reads_failure_limit():
    b = make().get_behaviors()
    assert b["remove_failed"] == b["failure_limit"]


@pytest.mark.parametrize("n", [1, 3, 7])
def test_remove_failed_sets_failure_limit(n):
    b = make(remove_failed=n).get_behaviors()
    assert b["remove_failed"] == n
    assert b["failure_limit"] == n


def test_failure_limit_may_still_be_set_separately():
    b = make(remove_failed=1, failure_limit=4).get_behaviors()
    assert b["failure_limit"] == 4


def test_set_behaviors_roundtrip():
    mc = make()
    mc.set_behaviors({"remove_failed": 3})
    assert mc.get_behaviors()["remove_failed"] == 3
    assert mc.behaviors["failure_limit"] == 3
