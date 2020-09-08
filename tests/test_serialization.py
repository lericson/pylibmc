# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from __future__ import print_function

import datetime
import json
import sys

import pylibmc
import _pylibmc
from pylibmc.test import make_test_client
from tests import PylibmcTestCase
from tests import get_refcounts

try:
    import cPickle as pickle
except ImportError:
    import pickle

def long_(val):
    try:
        return long(val)
    except NameError:
        # this happens under Python 3
        return val

f_none = 0
f_pickle, f_int, f_long, f_zlib, f_text = (1 << i for i in range(5))

class SerializationMethodTests(PylibmcTestCase):
    """Coverage tests for serialize and deserialize."""

    def test_integers(self):
        c = make_test_client(binary=True)
        if sys.version_info[0] == 3:
            self.assertEqual(c.serialize(1), (b'1', f_long))
            self.assertEqual(c.serialize(2**64), (b'18446744073709551616', f_long))
        else:
            self.assertEqual(c.serialize(1), (b'1', f_int))
            self.assertEqual(c.serialize(2**64), (b'18446744073709551616', f_long))

            self.assertEqual(c.deserialize(b'1', f_int), 1)

        self.assertEqual(c.deserialize(b'18446744073709551616', f_long), 2**64)
        self.assertEqual(c.deserialize(b'1', f_long), long_(1))

    def test_nonintegers(self):
        # tuples (python_value, (expected_bytestring, expected_flags))
        SERIALIZATION_TEST_VALUES = [
            # booleans are just ints
            (True, (b'1', f_int)),
            (False, (b'0', f_int)),
            # bytestrings
            (b'asdf', (b'asdf', f_none)),
            (b'\xb5\xb1\xbf\xed\xa9\xc2{8', (b'\xb5\xb1\xbf\xed\xa9\xc2{8', f_none)),
            (b'', (b'', f_none)),
            # unicode objects
            (u'åäö', (u'åäö'.encode('utf-8'), f_text)),
            (u'', (b'', f_text)),
            # objects
            (datetime.date(2015, 12, 28), (pickle.dumps(datetime.date(2015, 12, 28),
                                                        protocol=-1), f_pickle)),
        ]

        c = make_test_client(binary=True)
        for value, serialized_value in SERIALIZATION_TEST_VALUES:
            self.assertEqual(c.serialize(value), serialized_value)
            self.assertEqual(c.deserialize(*serialized_value), value)


class SerializationTests(PylibmcTestCase):
    """Test coverage for overriding serialization behavior in subclasses."""

    def test_override_deserialize(self):
        class MyClient(pylibmc.Client):
            ignored = []

            def deserialize(self, bytes_, flags):
                try:
                    return super(MyClient, self).deserialize(bytes_, flags)
                except Exception as error:
                    self.ignored.append(error)
                    raise pylibmc.CacheMiss

        global MyObject # Needed by the pickling system.
        class MyObject(object):
            def __getstate__(self):
                return dict(a=1)
            def __eq__(self, other):
                return type(other) is type(self)
            def __setstate__(self, d):
                assert d['a'] == 1

        c = make_test_client(MyClient, behaviors={'cas': True})
        self.assertEqual(c.get('notathing'), None)

        refcountables = ['foo', 'myobj', 'noneobj', 'myobj2', 'cachemiss']
        initial_refcounts = get_refcounts(refcountables)

        c['foo'] = 'foo'
        c['myobj'] = MyObject()
        c['noneobj'] = None
        c['myobj2'] = MyObject()

        # Show that everything is initially regular.
        self.assertEqual(c.get('myobj'), MyObject())
        self.assertEqual(get_refcounts(refcountables), initial_refcounts)
        self.assertEqual(c.get_multi(['foo', 'myobj', 'noneobj', 'cachemiss']),
                dict(foo='foo', myobj=MyObject(), noneobj=None))
        self.assertEqual(get_refcounts(refcountables), initial_refcounts)
        self.assertEqual(c.gets('myobj2')[0], MyObject())
        self.assertEqual(get_refcounts(refcountables), initial_refcounts)

        # Show that the subclass can transform unpickling issues into a cache miss.
        del MyObject # Break unpickling

        self.assertEqual(c.get('myobj'), None)
        self.assertEqual(get_refcounts(refcountables), initial_refcounts)
        self.assertEqual(c.get_multi(['foo', 'myobj', 'noneobj', 'cachemiss']),
                dict(foo='foo', noneobj=None))
        self.assertEqual(get_refcounts(refcountables), initial_refcounts)
        self.assertEqual(c.gets('myobj2'), (None, None))
        self.assertEqual(get_refcounts(refcountables), initial_refcounts)

        # The ignored errors are "AttributeError: test.test_client has no MyObject"
        self.assertEqual(len(MyClient.ignored), 3)
        assert all(isinstance(error, AttributeError) for error in MyClient.ignored)

    def test_refcounts(self):
        SENTINEL = object()
        DUMMY = b"dummy"
        KEY = b"fwLiDZKV7IlVByM5bVDNkg"
        VALUE = "PVILgNVNkCfMkQup5vkGSQ"

        class MyClient(_pylibmc.client):
            """Always serialize and deserialize to the same constants."""

            def serialize(self, value):
                return DUMMY, 1

            def deserialize(self, bytes_, flags):
                return SENTINEL

        refcountables = [1, long_(1), SENTINEL, DUMMY, KEY, VALUE]
        c = make_test_client(MyClient)
        initial_refcounts = get_refcounts(refcountables)

        c.set(KEY, VALUE)
        self.assertEqual(get_refcounts(refcountables), initial_refcounts)
        assert c.get(KEY) is SENTINEL
        self.assertEqual(get_refcounts(refcountables), initial_refcounts)
        self.assertEqual(c.get_multi([KEY]), {KEY: SENTINEL})
        self.assertEqual(get_refcounts(refcountables), initial_refcounts)
        c.set_multi({KEY: True})
        self.assertEqual(get_refcounts(refcountables), initial_refcounts)

    def test_override_serialize(self):
        class MyClient(pylibmc.Client):
            def serialize(self, value):
                return json.dumps(value).encode('utf-8'), 0

            def deserialize(self, bytes_, flags):
                assert flags == 0
                return json.loads(bytes_.decode('utf-8'))

        c = make_test_client(MyClient)
        c['foo'] = (1, 2, 3, 4)
        # json turns tuples into lists:
        self.assertEqual(c['foo'], [1, 2, 3, 4])

        raised = False
        try:
            c['bar'] = object()
        except TypeError:
            raised = True
        assert raised

    def _assert_set_raises(self, client, key, value):
        """Assert that set operations raise a ValueError when appropriate.

        This is in a separate method to avoid confusing the reference counts.
        """
        raised = False
        try:
            client[key] = value
        except ValueError:
            raised = True
        assert raised

    def test_invalid_flags_returned(self):
        # test that nothing bad (memory leaks, segfaults) happens
        # when subclasses implement `deserialize` incorrectly
        DUMMY = b"dummy"
        BAD_FLAGS = object()
        KEY = 'foo'
        VALUE = object()
        refcountables = [KEY, DUMMY, VALUE, BAD_FLAGS]

        class MyClient(pylibmc.Client):
            def serialize(self, value):
                return DUMMY, BAD_FLAGS

        c = make_test_client(MyClient)
        initial_refcounts = get_refcounts(refcountables)
        self._assert_set_raises(c, KEY, VALUE)
        self.assertEqual(get_refcounts(refcountables), initial_refcounts)

    def test_invalid_flags_returned_2(self):
        DUMMY = "ab"
        KEY = "key"
        VALUE = 123456
        refcountables = [DUMMY, KEY, VALUE]

        class MyClient(pylibmc.Client):
            def serialize(self, value):
                return DUMMY

        c = make_test_client(MyClient)
        initial_refcounts = get_refcounts(refcountables)

        self._assert_set_raises(c, KEY, VALUE)
        self.assertEqual(get_refcounts(refcountables), initial_refcounts)

        try:
            c.set_multi({KEY: DUMMY})
        except ValueError:
            raised = True
        assert raised
        self.assertEqual(get_refcounts(refcountables), initial_refcounts)
