#!/bin/sh
# Copy the Cyrus SASL mechanism plugins into the package, so the Linux wheels
# carry them (issue #289). auditwheel bundles libsasl2 but cannot know about
# the plugins libsasl2 dlopen()s at runtime from a directory compiled into it
# (/usr/lib64/sasl2 on AlmaLinux 8, which a Debian or Ubuntu host lacks).
#
# Usage: bundle-sasl-plugins.sh DESTDIR     (run inside the manylinux container)
#
# Wheels cannot hold symlinks, so the files are copied as regular files under
# the names libsasl2 looks for (lib<mech>.so).
set -eu
DEST=$1
# mechanism plugin : package that provides it
# These add about 180 kB to the wheel. They need nothing that the bundled
# libsasl2 does not already pull in (Kerberos, libcrypto, libcrypt), and they
# do not link libsasl2 themselves: they use the copy that dlopen()ed them.
# GSSAPI (libgssapiv2) is left out on purpose: Kerberos setups depend on the
# system's configuration and keytabs, so those users set SASL_PATH.
PLUGINS="plain:cyrus-sasl-plain login:cyrus-sasl-plain"
PLUGINS="$PLUGINS crammd5:cyrus-sasl-md5 digestmd5:cyrus-sasl-md5"
PLUGINS="$PLUGINS scram:cyrus-sasl-scram"
mkdir -p "$DEST"
for entry in $PLUGINS; do
  mech=${entry%%:*}
  pkg=${entry##*:}
  rpm -q "$pkg" >/dev/null 2>&1 || dnf install -y "$pkg"
  src=
  for d in /usr/lib64/sasl2 /usr/lib/sasl2; do
    [ -e "$d/lib$mech.so" ] && src=$d/lib$mech.so && break
  done
  [ -n "$src" ] || { echo "no lib$mech.so after installing $pkg" >&2; exit 1; }
  cp -L "$src" "$DEST/lib$mech.so"
done
ls -l "$DEST"
