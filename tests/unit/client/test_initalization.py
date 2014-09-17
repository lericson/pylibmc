#!/usr/bin/env python
# coding: utf-8
from tests import PylibmcTestCase
from tests.unit.support import FakeClient, fake_sasl_support


class ClientInitializationTestCase(PylibmcTestCase):
    def test_verify_that_when_the_client_is_initialized_with_a_username_without_sasl_support_then_a_type_error_is_raised(self):
        Client = fake_sasl_support(FakeClient, False)
        with self.assertRaisesRegexp(TypeError, "libmemcached does not support SASL"):
            Client(username='fake')

    def test_verify_that_when_the_client_is_initialized_with_a_password_without_sasl_support_then_a_type_error_is_raised(self):
        Client = fake_sasl_support(FakeClient, False)

        with self.assertRaisesRegexp(TypeError, "libmemcached does not support SASL"):
            Client(password='fake')

    def test_verify_that_when_the_client_is_initialized_with_a_username_and_password_without_sasl_support_then_a_type_error_is_raised(self):
        Client = fake_sasl_support(FakeClient, False)
        with self.assertRaisesRegexp(TypeError, "libmemcached does not support SASL"):
            Client(username='fake', password='fake')

    def test_verify_that_when_the_client_is_initialized_with_a_username_but_without_a_password_and_sasl_is_supported_then_a_type_error_is_raised(self):
        Client = fake_sasl_support(FakeClient, True)
        with self.assertRaisesRegexp(TypeError, "SASL requires both username and password"):
            Client(username='fake')

    def test_verify_that_when_the_client_is_initialized_with_a_password_but_without_a_username_and_sasl_is_supported_then_a_type_error_is_raised(self):
        Client = fake_sasl_support(FakeClient, True)
        with self.assertRaisesRegexp(TypeError, "SASL requires both username and password"):
            Client(password='fake')