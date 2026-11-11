#!/bin/bash
# Build and install pylibmc for a CI leg, with the options the leg asks for.
#
# Environment:
#   CI_MODE      "tree" (default): pip install . ; "sdist": build an sdist,
#                install it into a fresh venv, unpack it elsewhere
#   CI_ZLIB      "off" builds with --without-zlib
#   CI_STRICT    "1": CFLAGS="-Wall -Wextra -Wno-unused-parameter" (this
#                replaces the interpreter's flags, -DNDEBUG included, so asserts
#                are on) and the compiler output is checked against the
#                allowlist for CI_STRICT_KEY (see check-warnings.py)
#   CI_STRICT_KEY  names the allowlist, e.g. 1.0.18
#   RUNNER_TEMP  scratch directory
#   GITHUB_PATH, GITHUB_ENV  (optional) so later steps use the venv
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
mode=${CI_MODE:-tree}
tmp=${RUNNER_TEMP:-/tmp}
args=()
if [ "${CI_ZLIB:-on}" = off ]; then
  args+=(--config-settings=--build-option=--without-zlib)
fi
if [ "${CI_STRICT:-}" = 1 ]; then
  export CFLAGS="-Wall -Wextra -Wno-unused-parameter"
fi

# A stale build/ would silently reuse objects built with other flags.
rm -rf build src/pylibmc.egg-info
log=$tmp/pylibmc-build.log

case $mode in
tree)
  pip install -v . ${args[@]+"${args[@]}"} 2>&1 | tee "$log"
  ;;
sdist)
  pip install build
  rm -rf "$tmp/sdist" "$tmp/sdist-venv" "$tmp/sdist-src"
  python -m build --sdist --outdir "$tmp/sdist" .
  sdist=$(ls "$tmp"/sdist/pylibmc-*.tar.gz)
  echo "sdist: $sdist"
  tar tzf "$sdist"
  python -m venv "$tmp/sdist-venv"
  "$tmp/sdist-venv/bin/pip" install pytest setuptools
  # Install the archive itself, never the tree.
  "$tmp/sdist-venv/bin/pip" install -v "$sdist" ${args[@]+"${args[@]}"} 2>&1 | tee "$log"
  grep -F "$sdist" "$log" | head -3
  mkdir -p "$tmp/sdist-src"
  tar -C "$tmp/sdist-src" -xzf "$sdist" --strip-components=1
  if [ -n "${GITHUB_PATH:-}" ]; then
    echo "$tmp/sdist-venv/bin" >> "$GITHUB_PATH"
    echo "CI_TEST_DIR=$tmp/sdist-src" >> "$GITHUB_ENV"
  fi
  ;;
*)
  echo "unknown CI_MODE $mode" >&2
  exit 2
  ;;
esac

if [ "${CI_STRICT:-}" = 1 ]; then
  python3 "$here/check-warnings.py" "$log" "$here/strict-warnings-${CI_STRICT_KEY}.txt"
fi
