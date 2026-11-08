"""Tests for bin/changelog, which builds change log entries from docs/changes.d/."""
import importlib.machinery
import importlib.util
import os
import unittest

import pytest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "bin", "changelog")

pytestmark = pytest.mark.skipif(
    not os.path.exists(SCRIPT), reason="bin/changelog not in this tree")


def load_script():
    loader = importlib.machinery.SourceFileLoader("pylibmc_changelog", SCRIPT)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


cl = load_script()


@pytest.fixture
def frag_dir(tmp_path):
    def put(name, text):
        (tmp_path / name).write_text(text, encoding="utf-8")
    put.dir = str(tmp_path)
    return put


def build(frag_dir, version="1.8.0"):
    frags, errors = cl.load(frag_dir.dir)
    assert not errors
    return cl.build_section(version, frags)


def test_order_and_headings(frag_dir):
    frag_dir("5.docs.rst", "Docs thing.")
    frag_dir("4.build.rst", "Build thing.")
    frag_dir("3.fix.rst", "Fix thing.")
    frag_dir("2.new.rst", "New thing.")
    frag_dir("1.breaking.rst", "Breaking thing.")
    out = build(frag_dir)
    assert out.startswith("New in version 1.8.0\n--------------------\n\n")
    heads = ["Changes that can break existing code:", "New:", "Fixes:",
             "Build and platforms:", "Documentation:"]
    positions = [out.index(h) for h in heads]
    assert positions == sorted(positions)


def test_bullet_order_within_category(frag_dir):
    frag_dir("10.fix.rst", "ten")
    frag_dir("9.fix.rst", "nine")
    frag_dir("+zeta.fix.rst", "zeta")
    frag_dir("+alpha.fix.rst", "alpha")
    out = build(frag_dir)
    order = [out.index(w) for w in ("nine", "ten", "alpha", "zeta")]
    assert order == sorted(order)


def test_numbers(frag_dir):
    frag_dir("12.fix.rst", "Something broke.\n")
    frag_dir("13.fix.rst", "Already says (#13) here.")
    frag_dir("14.fix.rst", "Mentions #140 only")
    frag_dir("+nonum.fix.rst", "No number.")
    out = build(frag_dir)
    assert "- Something broke (#12).\n" in out
    assert out.count("#13") == 1
    assert "Mentions #140 only (#14)\n" in out
    assert "- No number.\n" in out


def test_wrapping(frag_dir):
    frag_dir("1.new.rst", "word " * 60 + "\n\nsecond   paragraph\n")
    out = build(frag_dir)
    bullet = [l for l in out.splitlines() if l.startswith(("- ", "  "))]
    assert bullet[0].startswith("- word")
    assert all(l.startswith("  ") for l in bullet[1:])
    assert all(len(l) <= 80 for l in bullet)
    assert len(bullet) > 3


def test_bad_names_and_contents(frag_dir):
    frag_dir("README.rst", "ignored")
    frag_dir(".hidden", "ignored")
    frag_dir("1.fix.rst", "ok")
    frag_dir("abc.fix.rst", "bad id")
    frag_dir("2.bogus.rst", "bad category")
    frag_dir("3.fix.txt", "bad extension")
    frag_dir("4.fix.rst", "  \n")
    frag_dir("5.fix.rst", "- starts with a marker")
    frags, errors = cl.load(frag_dir.dir)
    assert [f.name for f in frags] == ["1.fix.rst"]
    assert len(errors) == 5
    assert cl.main(["--dir", frag_dir.dir, "check"]) == 1


def test_check_ok(frag_dir):
    frag_dir("README.rst", "ignored")
    frag_dir("1.fix.rst", "ok")
    assert cl.main(["--dir", frag_dir.dir, "check"]) == 0


CHANGELOG = """Change Log
==========

New in version 1.8.0
--------------------

Intro text.

Fixes:

- Old fix.

New in version 1.7.0
--------------------

New:

- Ancient.
"""


def test_insert_new_section(frag_dir):
    frag_dir("1.new.rst", "Shiny.")
    frags, _ = cl.load(frag_dir.dir)
    out = cl.insert_into_changelog(CHANGELOG, "1.9.0", frags)
    assert out.startswith(
        "Change Log\n==========\n\nNew in version 1.9.0\n---")
    assert "- Shiny (#1).\n\nNew in version 1.8.0\n" in out
    assert out.endswith("- Ancient.\n")


def test_insert_merges_existing_section(frag_dir):
    frag_dir("2.fix.rst", "Another fix.")
    frag_dir("3.breaking.rst", "Breaks.")
    frags, _ = cl.load(frag_dir.dir)
    out = cl.insert_into_changelog(CHANGELOG, "1.8.0", frags)
    assert out.count("New in version 1.8.0") == 1
    assert "Intro text.\n\nChanges that can break existing code:\n\n- Breaks" \
        in out
    assert "Fixes:\n\n- Old fix.\n- Another fix (#2).\n\nNew in version 1.7.0" \
        in out


if __name__ == "__main__":
    unittest.main()
