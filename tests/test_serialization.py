import datetime
import json
import pickle
import uuid

import pylibmc
import _pylibmc
from pylibmc.test import make_test_client
from tests import PylibmcTestCase
from tests import get_refcounts


f_none = 0
f_pickle, f_int, f_long, f_zlib, f_text = (1 << i for i in range(5))
f_bool = 1 << 31


class SerializationMethodTests(PylibmcTestCase):
    """Coverage tests for serialize and deserialize."""

    def test_integers(self):
        c = make_test_client(binary=True)
        assert c.serialize(1) == (b'1', f_long)
        assert c.serialize(2**64) == (b'18446744073709551616', f_long)
        assert c.deserialize(b'18446744073709551616', f_long) == 2**64
        assert c.deserialize(b'1', f_long) == 1

    def test_bools_stored_by_older_versions_read_as_ints(self):
        # Before 1.8.0 a bool was stored as the integer 1 or 0, without the flag.
        c = make_test_client(binary=True)
        for stored, value in ((b'1', 1), (b'0', 0)):
            got = c.deserialize(stored, f_int)
            assert got == value and type(got) is int

    def test_nonintegers(self):
        # tuples (python_value, (expected_bytestring, expected_flags))
        SERIALIZATION_TEST_VALUES = [
            # booleans are ints with an extra flag
            (True, (b'1', f_int | f_bool)),
            (False, (b'0', f_int | f_bool)),
            # bytestrings
            (b'asdf', (b'asdf', f_none)),
            (b'\xb5\xb1\xbf\xed\xa9\xc2{8', (b'\xb5\xb1\xbf\xed\xa9\xc2{8', f_none)),
            (b'', (b'', f_none)),
            # unicode objects
            ('åäö', ('åäö'.encode(), f_text)),
            ('', (b'', f_text)),
            # objects
            (datetime.date(2015, 12, 28), (pickle.dumps(datetime.date(2015, 12, 28),
                                                        protocol=-1), f_pickle)),
        ]

        c = make_test_client(binary=True)
        for value, serialized_value in SERIALIZATION_TEST_VALUES:
            assert c.serialize(value) == serialized_value
            assert c.deserialize(*serialized_value) == value


class SerializationTests(PylibmcTestCase):
    """Test coverage for overriding serialization behavior in subclasses."""

    def test_override_deserialize(self):
        class MyClient(pylibmc.Client):
            ignored = []

            def deserialize(self, bytes_, flags):
                try:
                    return super().deserialize(bytes_, flags)
                except Exception as error:
                    self.ignored.append(error)
                    raise pylibmc.CacheMiss

        global MyObject # Needed by the pickling system.
        class MyObject:
            def __getstate__(self):
                return dict(a=1)
            def __eq__(self, other):
                return type(other) is type(self)
            def __setstate__(self, d):
                assert d['a'] == 1

        c = make_test_client(MyClient, behaviors={'cas': True})
        assert c.get('notathing') is None

        refcountables = ['foo', 'myobj', 'noneobj', 'myobj2', 'cachemiss']
        initial_refcounts = get_refcounts(refcountables)

        c['foo'] = 'foo'
        c['myobj'] = MyObject()
        c['noneobj'] = None
        c['myobj2'] = MyObject()

        # Show that everything is initially regular.
        assert c.get('myobj') == MyObject()
        assert get_refcounts(refcountables) == initial_refcounts
        assert (c.get_multi(['foo', 'myobj', 'noneobj', 'cachemiss']) ==
                dict(foo='foo', myobj=MyObject(), noneobj=None))
        assert get_refcounts(refcountables) == initial_refcounts
        assert c.gets('myobj2')[0] == MyObject()
        assert get_refcounts(refcountables) == initial_refcounts

        # Show that the subclass can transform unpickling issues into a cache miss.
        del MyObject # Break unpickling

        assert c.get('myobj') is None
        assert get_refcounts(refcountables) == initial_refcounts
        assert (c.get_multi(['foo', 'myobj', 'noneobj', 'cachemiss']) ==
                dict(foo='foo', noneobj=None))
        assert get_refcounts(refcountables) == initial_refcounts
        assert c.gets('myobj2') == (None, None)
        assert get_refcounts(refcountables) == initial_refcounts

        # The ignored errors are "AttributeError: test.test_client has no MyObject"
        assert len(MyClient.ignored) == 3
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

        refcountables = [1, SENTINEL, DUMMY, KEY, VALUE]
        c = make_test_client(MyClient)
        initial_refcounts = get_refcounts(refcountables)

        c.set(KEY, VALUE)
        assert get_refcounts(refcountables) == initial_refcounts
        assert c.get(KEY) is SENTINEL
        assert get_refcounts(refcountables) == initial_refcounts
        assert c.get_multi([KEY]) == {KEY: SENTINEL}
        assert get_refcounts(refcountables) == initial_refcounts
        c.set_multi({KEY: True})
        assert get_refcounts(refcountables) == initial_refcounts

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
        assert c['foo'] == [1, 2, 3, 4]

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
        DUMMY = uuid.uuid4().hex.encode()
        BAD_FLAGS = object()
        KEY = uuid.uuid4().hex
        VALUE = object()
        refcountables = [KEY, DUMMY, VALUE, BAD_FLAGS]

        class MyClient(pylibmc.Client):
            def serialize(self, value):
                return DUMMY, BAD_FLAGS

        c = make_test_client(MyClient)
        initial_refcounts = get_refcounts(refcountables)
        self._assert_set_raises(c, KEY, VALUE)
        assert get_refcounts(refcountables) == initial_refcounts

    def test_invalid_flags_returned_2(self):
        # Fresh objects, not literals: interned strings and cached constants
        # are referenced from all over the interpreter and the test runner,
        # so their reference counts can change for reasons unrelated to
        # pylibmc (this test once failed on "key" going from 233 to 232).
        DUMMY = uuid.uuid4().hex
        KEY = uuid.uuid4().hex
        VALUE = int(uuid.uuid4().int % 10**9) + 1000
        refcountables = [DUMMY, KEY, VALUE]

        class MyClient(pylibmc.Client):
            def serialize(self, value):
                return DUMMY

        c = make_test_client(MyClient)
        initial_refcounts = get_refcounts(refcountables)

        self._assert_set_raises(c, KEY, VALUE)
        assert get_refcounts(refcountables) == initial_refcounts

        try:
            c.set_multi({KEY: DUMMY})
        except ValueError:
            raised = True
        assert raised
        assert get_refcounts(refcountables) == initial_refcounts

    def test_invalid_flags_returned_does_not_drift(self):
        # A single before/after comparison cannot tell a leak from noise in
        # the count. Repeating the failing calls makes a per-call leak or
        # over-decref grow with the number of calls.
        DUMMY = uuid.uuid4().hex
        KEY = uuid.uuid4().hex
        VALUE = int(uuid.uuid4().int % 10**9) + 1000
        refcountables = [DUMMY, KEY, VALUE]

        class MyClient(pylibmc.Client):
            def serialize(self, value):
                return DUMMY

        c = make_test_client(MyClient)
        initial_refcounts = get_refcounts(refcountables)
        for _ in range(1000):
            self._assert_set_raises(c, KEY, VALUE)
            with self.assertRaises(ValueError):
                c.set_multi({KEY: DUMMY})
        assert get_refcounts(refcountables) == initial_refcounts


class DeserializeArgumentTests(PylibmcTestCase):
    """deserialize() is public API and must reject what it cannot decode."""

    def test_integer_requires_bytes(self):
        c = make_test_client()
        for flags in (f_int, f_long):
            self.assertEqual(c.deserialize(b'12', flags), 12)
            for bad in (None, 12, '12', [b'12']):
                with self.assertRaises(TypeError):
                    c.deserialize(bad, flags)

    def test_other_flags_do_not_crash(self):
        c = make_test_client()
        # The plain flag hands the object back untouched.
        self.assertIsNone(c.deserialize(None, f_none))
        # Which exception these raise is up to pickle and str decoding (PyPy's
        # pickle raises EOFError where CPython's raises TypeError). All that
        # matters here is that they fail cleanly instead of crashing.
        for flags in (f_pickle, f_text):
            with self.assertRaises(Exception):
                c.deserialize(None, flags)
