#!/usr/bin/env python
# encoding: utf-8

"""Run benchmarks with build/lib.* in sys.path"""

import sys
import math
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


def ratio(a, b):
    if a > b:
        return (a / b, 1)
    elif a < b:
        return (1, b / a)
    else:
        return (1, 1)


class Stopwatch(object):
    "A stopwatch that never stops"

    def __init__(self):
        self.t0 = time.clock()
        self.laps = []

    def __unicode__(self):
        m = self.mean()
        d = self.stddev()
        fmt = u"%.3gs, σ=%.3g, n=%d, snr=%.3g:%.3g".__mod__
        return fmt((m, d, len(self.laps)) + ratio(m, d))

    def mean(self):
        return sum(self.laps) / len(self.laps)

    def stddev(self):
        mean = self.mean()
        return math.sqrt(sum((lap - mean)**2 for lap in self.laps) / len(self.laps))

    def total(self):
        return time.clock() - self.t0

    @contextmanager
    def timing(self):
        t0 = time.clock()
        try:
            yield
        finally:
            te = time.clock()
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
def bench_get_set_multi(mc, keys, pairs):
    fails = mc.set_multi(pairs)
    if fails:
        logger.warn('set_multi(%r) fail', fails)
    if len(mc.get_multi(keys)) != len(pairs):
        logger.warn('get_multi() incomplete')


def multi_pairs(n, *keys):
    d = dict(('%s%d' % (k, i), 'data%s%d' % (k, i))
             for i in xrange(n)
             for k in keys)
    return (d.keys(), d)


complex_data_type = ([], {}, __import__('fractions').Fraction(3, 4))

benchmarks = [
    bench_get_set('Small I/O', 'abc', 'all work no play jack is a dull boy'),
    bench_get_set_multi('Multi I/O', *multi_pairs(10, 'abc', 'def', 'ghi', 'kjl')),
    bench_get_set('4k uncompressed I/O', 'abc' * 8, 'defb' * 1000),
    bench_get_set('4k compressed I/O', 'abc' * 8, 'a' + 'defb' * 1000),
    bench_get_set('Complex data I/O', 'abc', complex_data_type),
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

    mcs     = [p.factory() for p in participants]
    means   = [[]          for p in participants]
    stddevs = [[]          for p in participants]

    # Have each lifter do one benchmark each
    for benchmark_name, f, args, kwargs in benchmarks:
        logger.info('%s', benchmark_name)

        for i, (participant, mc) in enumerate(zip(participants, mcs)):
            sw = Stopwatch()

            while sw.total() < bench_time:
                with sw.timing():
                    f(mc, *args, **kwargs)

            means[i].append(sw.mean())
            stddevs[i].append(sw.stddev())

            logger.info(u'%s: %s', participant.name, sw)

    return means, stddevs


def main(args=sys.argv[1:]):
    sys.path.insert(0, build_lib_dirname())
    from pylibmc import build_info
    logger.info('Loaded %s', build_info())

    ps = [p for p in participants if p.name in args]
    ps = ps if ps else participants

    bs = benchmarks[:]

    logger.info('%d participants in %d benchmarks', len(ps), len(bs))

    means, stddevs = bench(participants=ps, benchmarks=bs)

    print 'labels =',     [p.name for p in ps]
    print 'benchmarks =', [b.name for b in bs]
    print 'means =',      means
    print 'stddevs =',    stddevs


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
