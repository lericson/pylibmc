#!/bin/bash
# Make a copy of the apt-installed libmemcached development files whose
# configure.h says LIBMEMCACHED_WITH_SASL_SUPPORT 0, so that pylibmc's own
# "#if LIBMEMCACHED_WITH_SASL_SUPPORT" branches are compiled out. This tests
# pylibmc, not libmemcached's SASL code: the library itself still has SASL.
#
# Usage: nosasl-headers.sh PREFIX
# Afterwards build with LIBMEMCACHED=PREFIX (include/ is the patched copy,
# lib/libmemcached.so is a symlink to the system library).
set -euo pipefail
PREFIX=$1
mkdir -p "$PREFIX/include" "$PREFIX/lib"
for d in /usr/include/libmemcached* /usr/include/libhashkit*; do
  [ -e "$d" ] && cp -R "$d" "$PREFIX/include/"
done
conf=$PREFIX/include/libmemcached-1.0/configure.h
sed -i 's/^\(#define LIBMEMCACHED_WITH_SASL_SUPPORT\) .*/\1 0/' "$conf"
grep -n LIBMEMCACHED_WITH_SASL_SUPPORT "$conf"
grep -q '^#define LIBMEMCACHED_WITH_SASL_SUPPORT 0$' "$conf"
so=$(dpkg -L libmemcached-dev | grep '/libmemcached\.so$')
ln -sf "$so" "$PREFIX/lib/libmemcached.so"
ls -l "$PREFIX/lib"
