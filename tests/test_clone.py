"""What a clone carries over from the client it was made from."""

import uuid

import pylibmc
from tests import PylibmcTestCase


class Overriding(pylibmc.Client):
    def serialize(self, value):
        return b"serialized", 0

    def deserialize(self, bytes_, flags):
        return "deserialized:" + bytes_.decode()


class CloneTests(PylibmcTestCase):
    def test_behaviors_and_pickle_protocol(self):
        mc = pylibmc.Client(["127.0.0.1:11211"], binary=True,
                            behaviors={"tcp_nodelay": True, "ketama": True,
                                       "pickle_protocol": 2})
        clone = mc.clone()
        a, b = mc.get_behaviors(), clone.get_behaviors()
        assert a == b
        assert a["tcp_nodelay"] and a["ketama"]
        assert b["pickle_protocol"] == 2

    def test_serialization_overrides(self):
        mc = Overriding(["127.0.0.1:11211"])
        clone = mc.clone()
        assert type(clone) is Overriding
        key = uuid.uuid4().hex
        try:
            assert clone.set(key, object())
            assert clone.get(key) == "deserialized:serialized"
        finally:
            clone.delete(key)
