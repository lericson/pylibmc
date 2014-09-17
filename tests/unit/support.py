#!/usr/bin/env python
# coding: utf-8
from mock import Mock

from pylibmc import Client


class FakeClient(Client):
    libmemcached = Mock()

    def __init__(self, servers=None, **kwargs):
        if not servers:
            servers = []
        super(FakeClient, self).__init__(servers, **kwargs)


def fake_sasl_support(client, enabled):
    client.libmemcached.PYLIBMC_SASL_SUPPORT = enabled

    return client


def fake_compression_support(client, enabled):
    client.libmemcached.PYLIBMC_COMPRESSION_SUPPORT = enabled

    return client
