#!/bin/bash
# Install a pylibmc wheel from a directory into a clean venv on a Debian or
# Ubuntu system, WITHOUT SASL_PATH, and log in to a memcached that requires
# SASL, once per mechanism the wheel ships (issue #289: the wheel used to find
# no mechanism on these systems), and check that importing pylibmc leaves the
# system's own libsasl2 and SASL_PATH alone (issue #358).
#
# Usage: test-sasl-wheel.sh WHEELDIR
#
# Runs as root in a container or as a user with sudo. Picks the wheel that
# matches the python3 on the system.
set -eu
WHEELDIR=$(cd "$1" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
SUDO=
if [ "$(id -u)" != 0 ]; then SUDO=sudo; fi
export DEBIAN_FRONTEND=noninteractive

$SUDO apt-get update -qq
$SUDO apt-get install -y -qq memcached sasl2-bin libsasl2-modules \
    libsasl2-modules-gssapi-mit \
    python3 python3-venv netcat-openbsd >/dev/null
$SUDO pkill memcached 2>/dev/null || true
$SUDO systemctl stop memcached 2>/dev/null || true

tag=$(python3 -c 'import sys; print("cp%d%d" % sys.version_info[:2])')
wheel=$(ls "$WHEELDIR"/pylibmc-*-"$tag"-"$tag"-manylinux*x86_64*.whl | head -1)
echo "system: $(. /etc/os-release; echo "$PRETTY_NAME"), python $(python3 -V), wheel $wheel"
rm -rf /tmp/venv-sasl
python3 -m venv /tmp/venv-sasl
/tmp/venv-sasl/bin/pip install -q --no-index "$wheel"
unset SASL_PATH
PY=/tmp/venv-sasl/bin/python
site=$($PY -c 'import pylibmc, os; print(os.path.dirname(pylibmc.__file__))')
echo "=== the wheel under test"
$PY -c 'import pylibmc; print(pylibmc.build_info(), pylibmc.__file__)'
echo "--- pylibmc.libs:"; ls -l "$site.libs"
echo "--- pylibmc/sasl2:"; ls -l "$site/sasl2"
echo "--- NEEDED/RUNPATH of the plugins:"
for f in "$site"/sasl2/*.so; do
    echo "$(basename "$f"): $(readelf -d "$f" | grep -E 'NEEDED|RPATH|RUNPATH' | sed 's/.*\[\(.*\)\]/\1/' | tr '\n' ' ')"
done

status=0
echo
echo "=== a second libsasl2 in the same process keeps the system's plugins (#358)"
if ! $PY "$HERE/sasl-isolation-check.py"; then
    echo "ISOLATION CHECK FAILED"
    status=1
fi
# server-side mech_list name : plugin file the client must load
for pair in plain:libplain.so login:liblogin.so cram-md5:libcrammd5.so \
            digest-md5:libdigestmd5.so scram-sha-1:libscram.so; do
    mech=${pair%%:*}
    plugin=${pair##*:}
    echo
    echo "=== mechanism $mech (client must load $plugin from the wheel)"
    "$HERE/sasl-server.sh" start 11211 "$mech"
    if ! $PY "$HERE/sasl-login-check.py" "$plugin"; then
        echo "MECHANISM $mech FAILED"
        status=1
    fi
    "$HERE/sasl-server.sh" stop 11211
done
exit "$status"
