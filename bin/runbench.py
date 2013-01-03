#!/usr/bin/env python
"""Run benchmarks with build/lib.* in sys.path"""

import sys
import time
import logging
from contextlib import contextmanager

logger = logging.getLogger('pylibmc.bench')

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
    def inner(name, *args, **kwds):
        return (name, (f, args, kwds))
    return inner

@benchmark_method
def bench_get_set(ctx, key, data):
    if not ctx.mc.set(key, data, min_compress_len=4001):
        ctx.logger.warn('set(%r, ...) fail', key)
    if ctx.mc.get(key) != data:
        ctx.logger.warn('get(%r) fail', key)

@benchmark_method
def bench_get_set_multi(ctx, keys, datagen='data%s'.__mod__):
    fails = ctx.mc.set_multi(dict((k, datagen(k)) for k in keys))
    if fails:
        ctx.logger.warn('set_multi(%r) fail', fails)
    if len(ctx.mc.get_multi(keys).keys()) != len(keys):
        ctx.logger.warn('get_multi() incomplete')

complex_data_type = ([], {}, __import__('fractions').Fraction(3, 4))

benchmarks = [
    bench_get_set('small i/o', 'abc', 'all work no play jack is a dull boy'),
    bench_get_set_multi('small multi i/o', ('abc', 'def', 'ghi', 'kjl')),
    bench_get_set('4k uncompressed i/o', 'abc' * 8, 'defb' * 1000),
    bench_get_set('4k compressed i/o', 'abc' * 8, 'a' + 'defb' * 1000),
    bench_get_set('complex i/o', 'abc', complex_data_type),
]

def bench(mc):
    behavior_sets = [
        {'name':        'default'},

        {'name':        'fast',
         'tcp_nodelay': True,
         'verify_keys': False,
         'hash':        'crc',
         'distribution': 'consistent',
         'no_block':    True}
    ]

    for behaviors in behavior_sets:
        logger.info('using behavior set %s', behaviors.pop('name'))
        ctx = type('Context', (object,), {
            'mc': mc(behaviors=behaviors),
            'logger': logger,
            'bench_time': 10.0
        })
        for (name, (f, a, k)) in benchmarks:
            logger.info('benchmarking %s', name)
            sw = Stopwatch()
            while sw.total() < ctx.bench_time:
                with sw.timing():
                    f(ctx, *a, **k)
            logger.info('%.2f benches per second average', 1.0 / sw.avg())

def main(args=sys.argv[1:]):
    from pylibmc import build_info
    from pylibmc.test import make_test_client
    logger.info('benching %s', build_info())
    bench(make_test_client)

if __name__ == "__main__":
    sys.path.insert(0, build_lib_dirname())
    logging.basicConfig(level=logging.DEBUG)
    main()
