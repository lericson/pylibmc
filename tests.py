"""Tests. They want YOU!!


Basic functionality.
>>> _pylibmc.__version__ == pylibmc.__version__
True
>>> c = _pylibmc.client([test_server])
>>> c.get("hello")
>>> c.set("test_key", 123)
True
>>> c.get("test_key")
123
>>> c.get("test_key_2")
>>> c.delete("test_key")
True
>>> c.get("test_key")
>>>

We should handle empty values just nicely.
>>> c.set("foo", "")
True
>>> c.get("foo")
''

Now this section is because most other implementations ignore zero-keys.
>>> c.get("")
>>> c.set("", "hi")
False
>>> c.delete("")
False
>>>

Multi functionality.
>>> c.set_multi({"a": 1, "b": 2, "c": 3})
[]
>>> c.get_multi("abc").keys() == ["a", "c", "b"]
True
>>> c.delete_multi("abc")
True
>>> c.get_multi("abc").keys() == []
True
>>> c.set_multi(dict(zip("abc", "def")), key_prefix="test_")
[]
>>> list(sorted(c.get_multi("abc", key_prefix="test_").iteritems()))
[('a', 'd'), ('b', 'e'), ('c', 'f')]
>>> c.get("test_a")
'd'
>>> c.delete_multi("abc", key_prefix="test_")
True
>>> bool(c.get_multi("abc", key_prefix="test_"))
False

Zero-key-test-time!
>>> c.get_multi([""])
{}
>>> c.delete_multi([""])
False
>>> c.set_multi({"": "hi"})
['']
>>> c.delete_multi({"a": "b"})
Traceback (most recent call last):
  ...
TypeError: keys must be a sequence, not a mapping

Timed stuff. The reason we, at UNIX times, set it two seconds in the future and
then sleep for >3 is that memcached might round the time up and down and left
and yeah, so you know...
>>> from time import sleep, time
>>> c.set("hi", "steven", 1)
True
>>> c.get("hi")
'steven'
>>> sleep(2.1)
>>> c.get("hi")
>>> c.set("hi", "loretta", int(time()) + 2)
True
>>> c.get("hi")
'loretta'
>>> sleep(3.1)
>>> c.get("hi")
>>>

Now for keys with funny types.
>>> c.set(1, "hi")
Traceback (most recent call last):
  ...
TypeError: argument 1 must be string or read-only buffer, not int
>>> c.get(1)
Traceback (most recent call last):
  ...
TypeError: key must be an instance of str
>>> c.set_multi({1: True})
Traceback (most recent call last):
  ...
TypeError: key must be an instance of str
>>> c.get_multi([1, 2])
Traceback (most recent call last):
  ...
TypeError: key must be an instance of str

This didn't use to work, but now it does.
>>> c.get_multi([])
{}

Getting stats is fun!
>>> for (svr, stats) in c.get_stats():
...     print svr
...     ks = stats.keys()
...     while ks:
...         cks, ks = ks[:6], ks[6:]
...         print ", ".join(cks)
localhost:11211 (0)
pid, total_items, uptime, version, limit_maxbytes, rusage_user
bytes_read, rusage_system, cmd_get, curr_connections, threads, total_connections
cmd_set, curr_items, get_misses, evictions, bytes, connection_structures
bytes_written, time, pointer_size, get_hits

Also test some flush all.
>>> c.set("hi", "guys")
True
>>> c.get("hi")
'guys'
>>> c.flush_all()
True
>>> c.get("hi")
>>>

Get and set booleans.
>>> c.set("greta", True)
True
>>> c.get("greta")
True
>>> c.set("greta", False)
True
>>> c.get("greta")
False
>>> c.delete("greta")
True

Complex data types!
>>> bla = Foo()
>>> bla.bar = "Hello!"
>>> c.set("tengil", bla)
True
>>> c.get("tengil").bar == bla.bar
True

Cloning (ethically, I don't know about it.)
>>> c is not c.clone()
True
>>> c2 = c.clone()
>>> c.set("test", "hello")
True
>>> c2.get("test")
'hello'
>>> c2.delete("test")
True
>>> del c2

Per-error exceptions
>>> c.incr("test")
Traceback (most recent call last):
  ...
NotFound: error 16 from memcached_increment: NOT FOUND
>>> c.incr(chr(0))
Traceback (most recent call last):
  ...
ProtocolError: error 8 from memcached_increment: PROTOCOL ERROR

Behaviors.
>>> c.set_behaviors({"tcp_nodelay": True, "hash": 6})
>>> list(sorted((k, v) for (k, v) in c.get_behaviors().items()
...             if k in ("tcp_nodelay", "hash")))
[('hash', 6), ('tcp_nodelay', 1)]

Binary protocol!
>>> c = _pylibmc.client([test_server], binary=True)
>>> c.set("hello", "world")
True
>>> c.get("hello")
'world'
>>> c.delete("hello")
True

Empty server lists are bad for your health.
>>> c = _pylibmc.client([])
Traceback (most recent call last):
  ...
MemcachedError: empty server list

Python-wrapped behaviors dict
>>> pc = pylibmc.Client(["%s:%d" % test_server[1:]])
>>> (pc.behaviors["hash"], pc.behaviors["distribution"])
('default', 'modula')
>>> pc.behaviors.update({"hash": "fnv1a_32", "distribution": "consistent"})
>>> (pc.behaviors["hash"], pc.behaviors["distribution"])
('fnv1a_32', 'consistent')
"""

# Used to test pickling.
class Foo(object): pass

# Fix up sys.path so as to include the correct build/lib.*/ directory.
import sys
from distutils.dist import Distribution
from distutils.command.build import build

build_cmd = build(Distribution({"ext_modules": True}))
build_cmd.finalize_options()
lib_dirn = build_cmd.build_lib
sys.path.insert(0, lib_dirn)

import pylibmc, _pylibmc
import socket

__doc__ = pylibmc.__doc__ + "\n\n" + __doc__

# {{{ Ported cmemcache tests
import unittest

class TestCmemcached(unittest.TestCase):
    def setUp(self):
        self.mc = pylibmc.Client(["%s:%d" % (test_server[1:])])

    def testSetAndGet(self):
        self.mc.set("num12345", 12345)
        self.assertEqual(self.mc.get("num12345"), 12345)
        self.mc.set("str12345", "12345")
        self.assertEqual(self.mc.get("str12345"), "12345")

    def testDelete(self):
        self.mc.set("str12345", "12345")
        #delete return True on success, otherwise False
        ret = self.mc.delete("str12345")
        self.assertEqual(self.mc.get("str12345"), None)
        self.assertEqual(ret, True)

        # This test only works with old memcacheds. This has become a "client
        # error" in memcached.
        try:
            ret = self.mc.delete("hello world")
        except pylibmc.ClientError:
            pass
        else:
            self.assertEqual(ret, False)

    def testGetMulti(self):
        self.mc.set("a", "valueA")
        self.mc.set("b", "valueB")
        self.mc.set("c", "valueC")
        result = self.mc.get_multi(["a", "b", "c", "", "hello world"])
        self.assertEqual(result, {'a':'valueA', 'b':'valueB', 'c':'valueC'})

    def testBigGetMulti(self):
        count = 10
        keys = ['key%d' % i for i in xrange(count)]
        pairs = zip(keys, ['value%d' % i for i in xrange(count)])
        for key, value in pairs:
            self.mc.set(key, value)
        result = self.mc.get_multi(keys)
        assert result == dict(pairs)

    def testFunnyDelete(self):
        result= self.mc.delete("")
        self.assertEqual(result, False)

    def testAppend(self):
        self.mc.delete("a")
        self.mc.set("a", "I ")
        ret = self.mc.append("a", "Do")
        result = self.mc.get("a")
        self.assertEqual(result, "I Do")

    def testPrepend(self):
        self.mc.delete("a")
        self.mc.set("a", "Do")
        ret = self.mc.prepend("a", "I ")
        result = self.mc.get("a")
        self.assertEqual(result, "I Do")
# }}}

test_server = (_pylibmc.server_type_tcp, "localhost", 11211)

def get_version(addr):
    (type_, host, port) = addr
    if (type_ != _pylibmc.server_type_tcp):
        raise NotImplementedError("test server can only be on tcp for now")
    else:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        s.send("version\r\n")
        version = s.recv(4096)
        s.close()
        if not version.startswith("VERSION ") or not version.endswith("\r\n"):
            raise ValueError("unexpected version return: %r" % (version,))
        else:
            version = version[8:-2]
        return version

def is_alive(addr):
    try:
        return bool(get_version(addr))
    except (ValueError, socket.error):
        return False

def make_full_suite():
    from doctest import DocTestFinder, DocTestSuite
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    finder = DocTestFinder()
    for modname in (__name__, "pylibmc", "_pylibmc"):
        ss = (DocTestSuite(sys.modules[modname], test_finder=finder),
              loader.loadTestsFromName(modname))
        for subsuite in ss:
            map(suite.addTest, subsuite._tests)
    return suite

class _TextTestResult(unittest._TextTestResult):
    def startTest(self, test):
        # Treat doctests a little specially because we want each example to
        # count as a test.
        if hasattr(test, "_dt_test"):
            self.testsRun += len(test._dt_test.examples) - 1
        elif hasattr(test, "countTestCases"):
            self.testsRun += test.countTestCases() - 1
        return unittest._TextTestResult.startTest(self, test)

class TextTestRunner(unittest.TextTestRunner):
    def _makeResult(self):
        return _TextTestResult(self.stream, self.descriptions, self.verbosity)

class TestProgram(unittest.TestProgram):
    defaultTest = "make_full_suite"
    testRunner = TextTestRunner

    def __init__(self, module="__main__", argv=None,
                 testLoader=unittest.defaultTestLoader):
        super(TestProgram, self).__init__(
            module=module, argv=argv, testLoader=testLoader,
            defaultTest=self.defaultTest, testRunner=self.testRunner)

    def runTests(self):
        pass

    def makeRunner(self):
        return self.testRunner(verbosity=self.verbosity)

    def run(self):
        runner = self.makeRunner()
        return runner.run(self.test)

if __name__ == "__main__":
    if hasattr(_pylibmc, "__file__"):
        print "Starting tests with _pylibmc at", _pylibmc.__file__
    else:
        print "Starting tests with static _pylibmc:", _pylibmc
    print "Reported libmemcached version:", _pylibmc.libmemcached_version
    print "Reported pylibmc version:", _pylibmc.__version__
    print "Support compression:", _pylibmc.support_compression

    if not is_alive(test_server):
        raise SystemExit("Test server (%r) not alive." % (test_server,))

    res = TestProgram().run()
    if not res.wasSuccessful():
        sys.exit(1)
