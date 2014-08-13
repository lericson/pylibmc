#!/usr/bin/env python
# encoding: utf-8

"""Run benchmarks with build/lib.* in sys.path"""

import sys
import time
import logging
from functools import wraps
from collections import namedtuple
from contextlib import contextmanager


logger = logging.getLogger('pylibmc.bench')

Benchmark = namedtuple('Benchmark', 'name f args kwargs')
Participant = namedtuple('Participant', 'name factory')


def build_lib_dirname():
    from distutils.dist import Distribution
    from distutils.command.build import build
    build_cmd = build(Distribution({"ext_modules": True}))
    build_cmd.finalize_options()
    return build_cmd.build_lib


class Stopwatch(object):
    "A stopwatch that never stops"

    def __init__(self):
        self.t0 = time.time()
        self.laps = []

    def avg(self):
        return sum(self.laps) / len(self.laps)

    def error(self):
        return (max(self.laps) - min(self.laps)) / 2.0

    def total(self):
        return time.time() - self.t0

    @contextmanager
    def timing(self):
        t0 = time.time()
        try:
            yield
        finally:
            te = time.time()
            self.laps.append(te - t0)


def benchmark_method(f):
    "decorator to turn f into a factory of benchmarks"
    @wraps(f)
    def inner(name, *args, **kwargs):
        return Benchmark(name, f, args, kwargs)
    return inner


@benchmark_method
def bench_get_set(mc, key, data):
    if not mc.set(key, data, min_compress_len=4001):
        logger.warn('set(%r, ...) fail', key)
    if mc.get(key) != data:
        logger.warn('get(%r) fail', key)


@benchmark_method
def bench_get_set_multi(mc, keys, datagen='data%s'.__mod__):
    fails = mc.set_multi(dict((k, datagen(k)) for k in keys))
    if fails:
        logger.warn('set_multi(%r) fail', fails)
    if len(mc.get_multi(keys).keys()) != len(keys):
        logger.warn('get_multi() incomplete')


complex_data_type = ([], {}, __import__('fractions').Fraction(3, 4))

benchmarks = [
    bench_get_set('small i/o', 'abc', 'all work no play jack is a dull boy'),
    bench_get_set_multi('small multi i/o', ('abc', 'def', 'ghi', 'kjl')),
    bench_get_set('4k uncompressed i/o', 'abc' * 8, 'defb' * 1000),
    bench_get_set('4k compressed i/o', 'abc' * 8, 'a' + 'defb' * 1000),
    bench_get_set('complex i/o', 'abc', complex_data_type),
]

participants = [

    Participant(name='pylibmc',
               factory=lambda: __import__('pylibmc.test').test.make_test_client()),

    Participant(name='pylibmc nonblock',
               factory=lambda: __import__('pylibmc.test').test.make_test_client(
        behaviors={'tcp_nodelay':  True,
                   'verify_keys':  False,
                   'hash':         'crc',
                   'no_block':     True})),

    Participant(name='pylibmc binary',
               factory=lambda: __import__('pylibmc.test').test.make_test_client(
        binary=True,
        behaviors={'tcp_nodelay': True,
                   'hash':        'crc'})),

    Participant(name='python-memcache',
               factory=lambda: __import__('memcache').Client(['127.0.0.1:11211'])),

]


def bench(participants=participants, benchmarks=benchmarks, bench_time=10.0):
    """Do you even lift?"""

    mcs = [p.factory() for p in participants]

    data = []

    # Have each lifter do one benchmark each
    for benchmark_name, f, args, kwargs in benchmarks:
        logger.info('Benchmark %s', benchmark_name)

        results = []
        errors = []
        data.append((results, errors))

        for participant, mc in zip(participants, mcs):
            sw = Stopwatch()

            while sw.total() < bench_time:
                with sw.timing():
                    f(mc, *args, **kwargs)

            results.append(1.0 / sw.avg())
            errors.append(1.0 / sw.error())

            logger.info(u'%s: %.3g±%.3g benches/sec', participant.name,
                        1.0 / sw.avg(), 1.0 / sw.error())

    print 'labels =', [p.name for p in participants]
    print 'benchmarks =', [b.name for b in benchmarks]
    print 'data =', data


def main(args=sys.argv[1:]):
    sys.path.insert(0, build_lib_dirname())
    from pylibmc import build_info
    logger.info('Loaded %s', build_info())

    ps = [p for p in participants if p.name in args] if args else participants

    logger.info('Benchmarking %d participants in %d benchmarks',
                len(ps), len(benchmarks))

    bench(participants=ps)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
