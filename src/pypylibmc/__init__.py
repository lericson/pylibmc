#!/usr/bin/env python
# coding: utf-8

from cffi import FFI

ffi = FFI()

ffi.verify("""
#include <libmemcached/memcached.h>
""", ext_package='pypylibmc')