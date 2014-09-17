#!/usr/bin/env python
# coding: utf-8

from cffi import FFI

ffi = FFI()

ffi.cdef("""
#define MEMCACHED_DEFAULT_PORT ...
#define MEMCACHED_MAX_KEY ...
#define MEMCACHED_MAX_BUFFER ...
#define MEMCACHED_MAX_HOST_SORT_LENGTH ...
#define MEMCACHED_POINTS_PER_SERVER ...
#define MEMCACHED_POINTS_PER_SERVER_KETAMA ...
#define MEMCACHED_CONTINUUM_SIZE ...
#define MEMCACHED_STRIDE ...
#define MEMCACHED_DEFAULT_TIMEOUT ...
#define MEMCACHED_DEFAULT_CONNECT_TIMEOUT ...
#define MEMCACHED_CONTINUUM_ADDITION ...
#define MEMCACHED_PREFIX_KEY_MAX_SIZE ...
#define MEMCACHED_EXPIRATION_NOT_ADD ...
#define MEMCACHED_VERSION_STRING_LENGTH ...


typedef enum {
  MEMCACHED_FAILURE,
  MEMCACHED_HOST_LOOKUP_FAILURE,
  MEMCACHED_CONNECTION_FAILURE,
  MEMCACHED_CONNECTION_BIND_FAILURE,
  MEMCACHED_WRITE_FAILURE,
  MEMCACHED_READ_FAILURE,
  MEMCACHED_UNKNOWN_READ_FAILURE,
  MEMCACHED_PROTOCOL_ERROR,
  MEMCACHED_CLIENT_ERROR,
  MEMCACHED_SERVER_ERROR,
  MEMCACHED_CONNECTION_SOCKET_CREATE_FAILURE,
  MEMCACHED_DATA_EXISTS,
  MEMCACHED_DATA_DOES_NOT_EXIST,
  MEMCACHED_NOTFOUND,
  MEMCACHED_MEMORY_ALLOCATION_FAILURE,
  MEMCACHED_SOME_ERRORS,
  MEMCACHED_NO_SERVERS,
  MEMCACHED_FAIL_UNIX_SOCKET,
  MEMCACHED_NOT_SUPPORTED,
  MEMCACHED_FETCH_NOTFINISHED,
  MEMCACHED_BAD_KEY_PROVIDED,
  MEMCACHED_INVALID_HOST_PROTOCOL,
  MEMCACHED_SERVER_MARKED_DEAD,
  MEMCACHED_SERVER_TEMPORARILY_DISABLED,
  MEMCACHED_UNKNOWN_STAT_KEY,
  ...
} memcached_return_t;


typedef enum {
  ...
} memcached_server_distribution_t;

typedef enum {
  ...
} memcached_behavior_t;

typedef enum {
  ...
} memcached_callback_t;

typedef enum {
  ...
} memcached_hash_t;

typedef enum {
  ...
} memcached_connection_t;
""")

libmemcached = ffi.verify("""
#include <libmemcached/memcached.h>
""", ext_package='pypylibmc')


class MemcachedError(Exception):
    retcode = None


class Failure(MemcachedError):
    retcode = libmemcached.MEMCACHED_FAILURE


class HostLookupError(MemcachedError):
    retcode = libmemcached.MEMCACHED_HOST_LOOKUP_FAILURE


class ConnectionError(MemcachedError):
    retcode = libmemcached.MEMCACHED_CONNECTION_FAILURE


class ConnectionBindError(MemcachedError):
    retcode = libmemcached.MEMCACHED_CONNECTION_BIND_FAILURE


class WriteError(MemcachedError):
    retcode = libmemcached.MEMCACHED_WRITE_FAILURE


class ReadError(MemcachedError):
    retcode = libmemcached.MEMCACHED_READ_FAILURE


class UnknownReadFailure(MemcachedError):
    retcode = libmemcached.MEMCACHED_UNKNOWN_READ_FAILURE


class ProtocolError(MemcachedError):
    retcode = libmemcached.MEMCACHED_PROTOCOL_ERROR


class ClientError(MemcachedError):
    retcode = libmemcached.MEMCACHED_CLIENT_ERROR


class ServerError(MemcachedError):
    retcode = libmemcached.MEMCACHED_SERVER_ERROR


class SocketCreateError(MemcachedError):
    retcode = libmemcached.MEMCACHED_CONNECTION_SOCKET_CREATE_FAILURE


class DataExists(MemcachedError):
    retcode = libmemcached.MEMCACHED_DATA_EXISTS


class DataDoesNotExist(MemcachedError):
    retcode = libmemcached.MEMCACHED_DATA_DOES_NOT_EXIST


class NotFound(MemcachedError):
    retcode = libmemcached.MEMCACHED_NOTFOUND


class AllocationError(MemcachedError):
    retcode = libmemcached.MEMCACHED_MEMORY_ALLOCATION_FAILURE


class SomeErrors(MemcachedError):
    retcode = libmemcached.MEMCACHED_SOME_ERRORS


class NoServers(MemcachedError):
    retcode = libmemcached.MEMCACHED_NO_SERVERS


class UnixSocketError(MemcachedError):
    retcode = libmemcached.MEMCACHED_FAIL_UNIX_SOCKET


class NotSupportedError(MemcachedError):
    retcode = libmemcached.MEMCACHED_NOT_SUPPORTED


class FetchNotFinished(MemcachedError):
    retcode = libmemcached.MEMCACHED_FETCH_NOTFINISHED


class BadKeyProvided(MemcachedError):
    retcode = libmemcached.MEMCACHED_BAD_KEY_PROVIDED


class InvalidHostProtocolError(MemcachedError):
    retcode = libmemcached.MEMCACHED_INVALID_HOST_PROTOCOL


class ServerDead(MemcachedError):
    retcode = libmemcached.MEMCACHED_SERVER_MARKED_DEAD


class ServerDown(MemcachedError):
    retcode = libmemcached.MEMCACHED_SERVER_TEMPORARILY_DISABLED


class UnknownStatKey(MemcachedError):
    retcode = libmemcached.MEMCACHED_UNKNOWN_STAT_KEY


exceptions = [('Error', MemcachedError),
              ('Failure', Failure),
              ('HostLookupError', HostLookupError),
              ('ConnectionError', ConnectionError),
              ('ConnectionBindError', ConnectionBindError),
              ('WriteError', WriteError),
              ('ReadError', ReadError),
              ('UnknownReadFailure', UnknownReadFailure),
              ('ProtocolError', ProtocolError),
              ('ClientError', ClientError),
              ('ServerError', ServerError),
              ('SocketCreateError', SocketCreateError),
              ('DataExists', DataExists),
              ('DataDoesNotExist', DataDoesNotExist),
              ('NotFound', NotFound),
              ('AllocationError', AllocationError),
              ('SomeErrors', SomeErrors),
              ('NoServers', NoServers),
              ('UnixSocketError', UnixSocketError),
              ('NotSupportedError', NotSupportedError),
              ('FetchNotFinished', FetchNotFinished),
              ('BadKeyProvided', BadKeyProvided),
              ('InvalidHostProtocolError', InvalidHostProtocolError),
              ('ServerDead', ServerDead),
              ('ServerDown', ServerDown),
              ('UnknownStatKey', UnknownStatKey)]