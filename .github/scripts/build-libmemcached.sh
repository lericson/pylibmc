#!/bin/sh
# Build and install libmemcached (the maintained awesomized fork) from a
# checksum-verified release tarball.
#
# Usage: build-libmemcached.sh PREFIX
#
# Environment (all optional):
#   LIBMEMCACHED_VERSION       version to build; only 1.1.4 is pinned below
#   SASL                       "on" or "off" (default off)
#   MACOSX_DEPLOYMENT_TARGET   macOS only: minimum macOS version (e.g. 11.0)
#   ARCHS                      macOS only: semicolon-separated architectures
#                              for CMAKE_OSX_ARCHITECTURES (e.g. "x86_64;arm64")
#   JOBS                       parallel build jobs (default: cmake's default)
#
# Needs: cmake (>= 3.5), a C++11 compiler, bison, flex, curl, tar and
# sha256sum or shasum. libevent is not needed (tests are not built).
set -eu

VERSION=${LIBMEMCACHED_VERSION:-1.1.4}
case $VERSION in
  1.1.4)
    # SHA-256 of https://github.com/awesomized/libmemcached/archive/refs/tags/1.1.4.tar.gz
    # (tag 1.1.4 -> commit 92d18858b417309f6bdee6bce464a4f3d6a375fd).
    SHA256=c477e1f6510e1dc698e84f3717ce690a8f65b94c616ecaa62306cce0f5e3116a
    ;;
  *)
    echo "build-libmemcached.sh: no pinned checksum for version $VERSION" >&2
    exit 2
    ;;
esac

if [ $# -ne 1 ]; then
  echo "usage: $0 PREFIX" >&2
  exit 2
fi
PREFIX=$1
SASL=${SASL:-off}

case $SASL in
  on|ON|1)   SASL_FLAG=ON ;;
  off|OFF|0) SASL_FLAG=OFF ;;
  *) echo "SASL must be on or off" >&2; exit 2 ;;
esac

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d' ' -f1
  else
    shasum -a 256 "$1" | cut -d' ' -f1
  fi
}

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

URL=https://github.com/awesomized/libmemcached/archive/refs/tags/$VERSION.tar.gz
echo "Downloading $URL"
curl --fail --silent --show-error --location --retry 3 --output "$WORK/src.tar.gz" "$URL"

GOT=$(sha256 "$WORK/src.tar.gz")
if [ "$GOT" != "$SHA256" ]; then
  echo "SHA-256 mismatch for libmemcached $VERSION: expected $SHA256, got $GOT" >&2
  exit 1
fi

tar -C "$WORK" -xzf "$WORK/src.tar.gz"
SRC=$WORK/libmemcached-$VERSION

set -- \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$PREFIX" \
  -DCMAKE_INSTALL_LIBDIR=lib \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DBUILD_TESTING=OFF \
  -DBUILD_DOCS=OFF \
  -DENABLE_MEMASLAP=OFF \
  -DENABLE_DTRACE=OFF \
  -DENABLE_SASL=$SASL_FLAG

if [ "$(uname -s)" = Darwin ]; then
  [ -z "${MACOSX_DEPLOYMENT_TARGET:-}" ] || set -- "$@" "-DCMAKE_OSX_DEPLOYMENT_TARGET=$MACOSX_DEPLOYMENT_TARGET"
  [ -z "${ARCHS:-}" ] || set -- "$@" "-DCMAKE_OSX_ARCHITECTURES=$ARCHS"
fi

cmake -S "$SRC" -B "$WORK/build" "$@"
cmake --build "$WORK/build" ${JOBS:+--parallel "$JOBS"}
cmake --install "$WORK/build"

echo "Installed libmemcached $VERSION (SASL=$SASL_FLAG) to $PREFIX"
