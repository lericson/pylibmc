"""The bundled SASL plugins directory is handed to our own libsasl2 only.

Importing pylibmc must never touch the SASL_PATH environment variable, which
every libsasl2 in the process, and every child process, would obey (#358).
"""

import os
import subprocess
import sys

import pylibmc
import _pylibmc

PKG = os.path.dirname(os.path.abspath(pylibmc.__file__))
BUNDLED = os.path.join(PKG, "sasl2")


def run(code, **env_changes):
    env = dict(os.environ)
    env.pop("SASL_PATH", None)
    env.update(env_changes)
    return subprocess.check_output(
        [sys.executable, "-c", code], env=env, cwd=os.path.dirname(PKG),
        universal_newlines=True).strip()


def test_import_leaves_sasl_path_alone():
    code = "import pylibmc, os; print(repr(os.environ.get('SASL_PATH')))"
    assert run(code) == "None"
    assert run(code, SASL_PATH="/somewhere/else") == "'/somewhere/else'"
    assert run(code, SASL_PATH="") == "''"


def test_children_do_not_inherit_a_sasl_path():
    code = ("import pylibmc, subprocess, sys; "
            "print(subprocess.check_output([sys.executable, '-c', "
            "'import os; print(repr(os.environ.get(\"SASL_PATH\")))'], "
            "universal_newlines=True).strip())")
    assert run(code) == "None"


def test_plugin_dir_is_only_set_when_bundled():
    code = "import _pylibmc; print(_pylibmc.sasl_plugin_dir)"
    if not _pylibmc.support_sasl or not os.path.isdir(BUNDLED):
        assert _pylibmc.sasl_plugin_dir is None
        assert run(code) == "None"
    elif sys.platform.startswith("linux") and "SASL_PATH" not in os.environ:
        assert _pylibmc.sasl_plugin_dir == BUNDLED
        assert run(code) == BUNDLED


def test_an_explicit_sasl_path_wins():
    code = "import _pylibmc; print(_pylibmc.sasl_plugin_dir)"
    assert run(code, SASL_PATH="/somewhere/else") == "None"
    assert run(code, SASL_PATH="") == "None"
