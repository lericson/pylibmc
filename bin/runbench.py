#!/usr/bin/env python
# encoding: utf-8
"""Run benchmarks with build/lib.* in sys.path"""

from __future__ import print_function, unicode_literals

import sys
import math
import time
import logging
from functools import wraps
from collections import namedtuple
from contextlib import contextmanager

try:
    xrange          # Python 2
except NameError:
    xrange = range  # Python 3


logger = logging.getLogger('pylibmc.bench')

Benchmark = namedtuple('Benchmark', 'name f args kwargs')
Participant = namedtuple('Participant', 'name connect')


def build_lib_dirname():
    from distutils.dist import Distribution
    from distutils.command.build import build
    build_cmd = build(Distribution({"ext_modules": True}))
    build_cmd.finalize_options()
    return build_cmd.build_lib


class Stopwatch(object):
    "A stopwatch that never stops"

    def __init__(self):
        self.t0 = time.clock()
        self.laps = []

    def __unicode__(self):
        mean, diff = self.interval()
        return u"%.3g ± %.3g secs" % (mean, diff)

    def mean(self):
        return sum(self.laps) / len(self.laps)

    def stddev(self, mean=None):
        mean = self.mean() if mean is None else mean
        sqsum = sum((lap - mean)**2 for lap in self.laps)
        return math.sqrt(sqsum / len(self.laps))

    def interval(self, alpha=0.05):
        "Confidence interval of 1 - alpha probability"
        from scipy.stats import norm
        mean = self.mean()
        sigma = self.stddev(mean=mean)
        diff = norm(0, sigma).ppf(1 - alpha/2)
        return mean, diff

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


@benchmark_method
def bench_incr_decr(mc, key):
    mc.set(key, 0)
    mc.incr(key)
    mc.incr(key, 2)
    mc.decr(key, 10)
    if mc.get(key) != 0:
        logger.warn('key not zero')


def multi_pairs(n, *keys):
    d = dict((b'%s%d' % (k, i), b'data%s%d' % (k, i))
             for i in xrange(n)
             for k in keys)
    return (d.keys(), d)


complex_data_type = ([], {}, __import__('fractions').Fraction(3, 4))

benchmarks = [
    bench_get_set('Small I/O', b'abc', b'all work no play jack is a dull boy'),
    bench_get_set_multi('Multi I/O', *multi_pairs(10, b'abc', b'def', b'ghi', b'kjl')),
    bench_get_set('4k uncompressed I/O', b'abc' * 8, b'defb' * 1000),
    bench_get_set('4k compressed I/O', b'abc' * 8, b'a' + 'defb' * 1000),
    bench_get_set('Complex data I/O', b'abc', complex_data_type),
    bench_incr_decr('Incr/decr I/O', b'abc'),
]

participants = [

    Participant(name='pylibmc',
               connect=lambda: __import__('pylibmc.test').test.make_test_client()),

    Participant(name='nonblock',
               connect=lambda: __import__('pylibmc.test').test.make_test_client(
        behaviors={'tcp_nodelay':  True,
                   'verify_keys':  False,
                   'hash':         'crc',
                   'no_block':     True})),

    Participant(name='binary',
               connect=lambda: __import__('pylibmc.test').test.make_test_client(
        binary=True,
        behaviors={'tcp_nodelay': True,
                   'hash':        'crc'})),

    Participant(name='python-memcache',
               connect=lambda: __import__('memcache').Client(['127.0.0.1:11211'])),

]


class Workout(object):
    """Do you even lift?"""

    # Confidence level in plot
    plot_alpha = 0.1

    def __init__(self, timings=None,
                 participants=participants, benchmarks=benchmarks,
                 bench_time=10.0):
        self.timings = timings
        self.participants = participants
        self.benchmarks = benchmarks
        self.bench_time = bench_time

    def bench(self):
        self.mcs = [p.connect() for p in self.participants]
        self.timings = [list(self._time(*b)) for b in self.benchmarks]

    def _time(self, name, f, args, kwargs):
        "Perform a benchmark for all participants and time it"
        logger.info('Benchmark %s', name)
        for participant, mc in zip(self.participants, self.mcs):
            sw = Stopwatch()
            while sw.total() < self.bench_time:
                with sw.timing():
                    f(mc, *args, **kwargs)
            logger.info(u'%s: %s', participant.name, sw)
            yield sw

    def print_stats(self, file=sys.stdout):
        for i, timings in enumerate(self.timings):
            print(self.benchmarks[i].name, file=file)
            for participant, timing in zip(self.participants, timings):
                print(' - {}: {}'.format(participant.name, timing), file=file)

    def plot(self, filename):
        from matplotlib import pyplot as plt

        # Find how many rows and columns the benchmark plots can be laid out on
        # while still "filling the rectangle" by the greatest divisor of the
        # number of benchmarks.
        n = len(self.benchmarks)
        rows = next(i for i in range(n - 1, 0, -1) if i*(n/i) == n)
        cols = n/rows
        assert cols*rows == n

        plt.figure(figsize=(6*cols, 2.5*rows))

        for i, (name, f, args, kwargs) in enumerate(self.benchmarks):
            plt.subplot(rows, cols, 1+i)
            plt.title(name)
            plt.boxplot([timing.laps for timing in self.timings[i]],
                        labels=[p.name for p in self.participants])

        plt.tight_layout()
        plt.savefig(filename)


def main(args=sys.argv[1:]):
    sys.path.insert(0, build_lib_dirname())
    from pylibmc import build_info
    logger.info('Loaded %s', build_info())

    ps = participants
    bs = benchmarks

    logger.info('%d participants in %d benchmarks', len(ps), len(bs))

    import pickle

    # usages:
    #   runbench.py bench -- run benchmark once
    #   runbench.py dump [stats] -- run benchmark and write stats to file
    #   runbench.py plot [stats] [plot] -- load stats and write a plot to file

    def bench():
        workout = Workout(participants=ps, benchmarks=bs)
        workout.bench()
        workout.print_stats()
        return workout

    def dump(fn='tmp/timings.pickle'):
        workout = bench()
        with open(fn, 'wb') as f:
            pickle.dump(workout.timings, f)

    def plot(fn='tmp/timings.pickle', out='tmp/timing_plot.svg'):
        with open(fn, 'rb') as f:
            workout = Workout(timings=pickle.load(f))
        workout.print_stats()
        workout.plot(filename=out)

    if args:
        fs = (bench, dump, plot)
        f = dict((f.__name__, f) for f in fs)[args[0]]
        f(*args[1:])
    else:
        bench()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
