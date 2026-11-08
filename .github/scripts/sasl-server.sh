#!/bin/bash
# Start or stop a memcached that requires SASL (binary protocol, one mechanism,
# users in a sasldb). One recipe, shared by ci.yml (source builds) and
# test-sasl-wheel.sh (release wheels).
#
# Usage: sasl-server.sh start PORT MECH   (waits until the port accepts)
#        sasl-server.sh stop  PORT
#
# The user is "testuser" with the password "secretpw". Needs memcached,
# sasl2-bin (saslpasswd2), libsasl2-modules, netcat and, unless root, sudo (the
# memcached application config lives in /etc/sasl2). State is in
# ${SASL_SERVER_DIR:-/tmp/pylibmc-sasl-server}.
set -eu
DIR=${SASL_SERVER_DIR:-/tmp/pylibmc-sasl-server}
cmd=${1:?start or stop}
port=${2:?port}
SUDO=
if [ "$(id -u)" != 0 ]; then SUDO=sudo; fi

case "$cmd" in
start)
    mech=${3:?mechanism}
    mkdir -p "$DIR"
    rm -f "$DIR/sasldb2"
    echo secretpw | saslpasswd2 -a memcached -c -p -f "$DIR/sasldb2" testuser
    chmod 644 "$DIR/sasldb2"
    $SUDO mkdir -p /etc/sasl2
    printf 'mech_list: %s\nlog_level: 5\nsasldb_path: %s/sasldb2\n' "$mech" "$DIR" |
        $SUDO tee /etc/sasl2/memcached.conf >/dev/null
    user_args=()
    if [ "$(id -u)" = 0 ]; then user_args=(-u root); fi
    memcached -S -B binary -l 127.0.0.1 -p "$port" ${user_args[@]+"${user_args[@]}"} \
        >"$DIR/memcached-$port.log" 2>&1 &
    echo $! >"$DIR/memcached-$port.pid"
    for _ in $(seq 1 40); do nc -z 127.0.0.1 "$port" && exit 0; sleep 0.25; done
    echo "memcached did not come up on port $port:" >&2
    cat "$DIR/memcached-$port.log" >&2
    exit 1
    ;;
stop)
    if [ -f "$DIR/memcached-$port.pid" ]; then
        pid=$(cat "$DIR/memcached-$port.pid")
        kill "$pid" 2>/dev/null || true
        for _ in $(seq 1 20); do kill -0 "$pid" 2>/dev/null || break; sleep 0.25; done
        rm -f "$DIR/memcached-$port.pid"
    fi
    ;;
*)
    echo "usage: $0 start PORT MECH | stop PORT" >&2
    exit 2
    ;;
esac
