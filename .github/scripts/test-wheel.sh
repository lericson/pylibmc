#!/bin/bash
# Run the test suite against the INSTALLED pylibmc, with a throwaway memcached
# on 127.0.0.1:11211 (tests/test_autoconf.py assumes the default port).
#
# Usage: test-wheel.sh PYTEST_ARGS...
#
# Unlike bin/with-memcached this waits until memcached accepts connections
# before starting the tests, always stops it afterwards, and exits with
# pytest's status. It also fails if pylibmc is imported from anywhere other
# than site-packages (for example the source tree).
set -u

HOST=127.0.0.1
PORT=11211

port_open() {
    if command -v nc >/dev/null 2>&1; then
        nc -z "$HOST" "$PORT" >/dev/null 2>&1
    else
        (exec 3<>"/dev/tcp/$HOST/$PORT") >/dev/null 2>&1
    fi
}

if port_open; then
    echo "test-wheel.sh: something is already listening on $HOST:$PORT" >&2
    exit 1
fi

# memcached refuses to run as root unless told which user to switch to (we
# are root inside the manylinux containers).
user_args=()
if [ "$(id -u)" = 0 ]; then user_args=(-u root); fi

memcached -l "$HOST" -p "$PORT" ${user_args[@]+"${user_args[@]}"} &
pid=$!
cleanup() {
    kill "$pid" 2>/dev/null
    wait "$pid" 2>/dev/null
}
trap cleanup EXIT
trap 'exit 130' INT TERM

up=
for _ in $(seq 1 100); do
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "test-wheel.sh: memcached exited prematurely" >&2
        exit 1
    fi
    if port_open; then up=1; break; fi
    sleep 0.1
done
if [ -z "$up" ]; then
    echo "test-wheel.sh: memcached did not start listening on $HOST:$PORT" >&2
    exit 1
fi

python - <<'PY' || exit 1
import sys, pylibmc, _pylibmc
print("python", sys.version.split()[0], "| pylibmc", pylibmc.__version__,
      "| libmemcached", _pylibmc.libmemcached_runtime_version,
      "| from", pylibmc.__file__)
for mod in (pylibmc, _pylibmc):
    if "site-packages" not in mod.__file__:
        sys.exit("pylibmc must be tested from the installed wheel, but "
                 "%s was imported from %s" % (mod.__name__, mod.__file__))
PY

python -m pytest "$@"
status=$?
exit "$status"
