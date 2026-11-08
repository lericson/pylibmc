"""The headers we compiled against must match the library we loaded."""
import _pylibmc


def test_runtime_version_matches_headers():
    compiled = _pylibmc.libmemcached_version.split(".")[:2]
    loaded = _pylibmc.libmemcached_runtime_version.split(".")[:2]
    assert compiled == loaded
