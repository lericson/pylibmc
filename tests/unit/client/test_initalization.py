#!/usr/bin/env python
# coding: utf-8
from pypylibmc import libmemcached
from pylibmc.compat import _pylibmc
from tests import PylibmcTestCase
from tests.unit.support import FakeClient, fake_sasl_support


class ClientInitializationTestCase(PylibmcTestCase):
    def tearDown(self):
        FakeClient.libmemcached.reset_mock()

    def test_verify_that_when_the_client_is_initialized_with_a_username_without_sasl_support_then_a_type_error_is_raised(
            self):
        Client = fake_sasl_support(FakeClient, False)
        with self.assertRaisesRegexp(TypeError, "libmemcached does not support SASL"):
            Client(username='fake')

    def test_verify_that_when_the_client_is_initialized_with_a_password_without_sasl_support_then_a_type_error_is_raised(
            self):
        Client = fake_sasl_support(FakeClient, False)

        with self.assertRaisesRegexp(TypeError, "libmemcached does not support SASL"):
            Client(password='fake')

    def test_verify_that_when_the_client_is_initialized_with_a_username_and_password_without_sasl_support_then_a_type_error_is_raised(
            self):
        Client = fake_sasl_support(FakeClient, False)
        with self.assertRaisesRegexp(TypeError, "libmemcached does not support SASL"):
            Client(username='fake', password='fake')

    def test_verify_that_when_the_client_is_initialized_with_a_username_but_without_a_password_and_sasl_is_supported_then_a_type_error_is_raised(
            self):
        Client = fake_sasl_support(FakeClient, True)
        with self.assertRaisesRegexp(TypeError, "SASL requires both username and password"):
            Client(username='fake')

    def test_verify_that_when_the_client_is_initialized_with_a_password_but_without_a_username_and_sasl_is_supported_then_a_type_error_is_raised(
            self):
        Client = fake_sasl_support(FakeClient, True)
        with self.assertRaisesRegexp(TypeError, "SASL requires both username and password"):
            Client(password='fake')

    def test_verify_that_when_the_client_is_initialized_with_a_username_and_password_and_sasl_is_supported_then_the_client_authenticates_with_the_provided_credentials(
            self):
        Client = fake_sasl_support(FakeClient, True)

        Client.libmemcached.MEMCACHED_SUCCESS = libmemcached.MEMCACHED_SUCCESS
        Client.libmemcached.memcached_set_sasl_auth_data.return_value = libmemcached.MEMCACHED_SUCCESS

        c = Client(username='fake', password='fake')

        c.libmemcached.memcached_set_sasl_auth_data.assert_called_once_with(c.mc, 'fake', 'fake')

    def test_verify_that_when_the_client_is_initialized_with_a_username_and_password_and_sasl_is_supported_but_an_error_occured_then_an_exception_is_raised(self):
        Client = fake_sasl_support(FakeClient, True)

        Client.libmemcached.MEMCACHED_SUCCESS = libmemcached.MEMCACHED_SUCCESS
        Client.libmemcached.memcached_set_sasl_auth_data.return_value = libmemcached.MEMCACHED_NOT_SUPPORTED

        with self.assertRaises(_pylibmc.NotSupportedError):
            Client(username='fake', password='fake')

