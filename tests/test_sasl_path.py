"""The bundled SASL plugins directory is announced through SASL_PATH."""

import os

import pylibmc


def test_sets_sasl_path_when_plugins_are_bundled(tmp_path):
    (tmp_path / "sasl2").mkdir()
    env = {}
    result = pylibmc._point_sasl_at_bundled_plugins(env, str(tmp_path))
    expected = os.path.join(str(tmp_path), "sasl2")
    assert result == expected
    assert env == {"SASL_PATH": expected}


def test_never_overrides_the_users_sasl_path(tmp_path):
    (tmp_path / "sasl2").mkdir()
    env = {"SASL_PATH": "/somewhere/else"}
    assert pylibmc._point_sasl_at_bundled_plugins(env, str(tmp_path)) is None
    assert env == {"SASL_PATH": "/somewhere/else"}


def test_an_empty_sasl_path_counts_as_set(tmp_path):
    (tmp_path / "sasl2").mkdir()
    env = {"SASL_PATH": ""}
    assert pylibmc._point_sasl_at_bundled_plugins(env, str(tmp_path)) is None
    assert env == {"SASL_PATH": ""}


def test_does_nothing_without_a_bundled_directory(tmp_path):
    env = {}
    assert pylibmc._point_sasl_at_bundled_plugins(env, str(tmp_path)) is None
    assert env == {}


def test_a_file_named_sasl2_is_not_a_directory(tmp_path):
    (tmp_path / "sasl2").write_text("")
    env = {}
    assert pylibmc._point_sasl_at_bundled_plugins(env, str(tmp_path)) is None
    assert env == {}


def test_defaults_use_the_real_environment(tmp_path, monkeypatch):
    (tmp_path / "sasl2").mkdir()
    monkeypatch.delenv("SASL_PATH", raising=False)
    result = pylibmc._point_sasl_at_bundled_plugins(package_dir=str(tmp_path))
    assert os.environ["SASL_PATH"] == result
    monkeypatch.delenv("SASL_PATH")
