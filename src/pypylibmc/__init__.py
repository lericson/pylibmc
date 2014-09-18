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

#define LIBMEMCACHED_VERSION_STRING ...
#define LIBMEMCACHED_VERSION_HEX ...

#define PYLIBMC_SASL_SUPPORT ...
#define PYLIBMC_COMPRESSION_SUPPORT ...

typedef struct {...;} memcached_st;

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
  MEMCACHED_SUCCESS,
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

memcached_st* memcached_create(memcached_st *ptr);
void memcached_quit(memcached_st *ptr);
void memcached_free(memcached_st *ptr);

memcached_return_t memcached_set_sasl_auth_data(memcached_st *ptr, const char *username, const char *password);

const char *memcached_last_error_message(memcached_st *);
""")

libmemcached = ffi.verify("""
#include <libmemcached/memcached.h>

#if LIBMEMCACHED_WITH_SASL_SUPPORT
    #define PYLIBMC_SASL_SUPPORT 1
#else
    #define PYLIBMC_SASL_SUPPORT 0
#endif

#ifdef USE_ZLIB
    #define PYLIBMC_COMPRESSION_SUPPORT 1
#else
    #define PYLIBMC_COMPRESSION_SUPPORT 0
#endif
""", ext_package='pypylibmc', libraries=["memcached"])


class Error(Exception):
    retcode = None

    def __init__(self, what, error_message, key=None):
        lead = 'error %d from %s' % (self.retcode, what)
        if key:
            lead += '(%s)' % key

        msg = '%s: %s' % (lead, error_message)
        super(Error, self).__init__(msg)


class Failure(Error):
    retcode = libmemcached.MEMCACHED_FAILURE


class HostLookupError(Error):
    retcode = libmemcached.MEMCACHED_HOST_LOOKUP_FAILURE


class ConnectionError(Error):
    retcode = libmemcached.MEMCACHED_CONNECTION_FAILURE


class ConnectionBindError(Error):
    retcode = libmemcached.MEMCACHED_CONNECTION_BIND_FAILURE


class WriteError(Error):
    retcode = libmemcached.MEMCACHED_WRITE_FAILURE


class ReadError(Error):
    retcode = libmemcached.MEMCACHED_READ_FAILURE


class UnknownReadFailure(Error):
    retcode = libmemcached.MEMCACHED_UNKNOWN_READ_FAILURE


class ProtocolError(Error):
    retcode = libmemcached.MEMCACHED_PROTOCOL_ERROR


class ClientError(Error):
    retcode = libmemcached.MEMCACHED_CLIENT_ERROR


class ServerError(Error):
    retcode = libmemcached.MEMCACHED_SERVER_ERROR


class SocketCreateError(Error):
    retcode = libmemcached.MEMCACHED_CONNECTION_SOCKET_CREATE_FAILURE


class DataExists(Error):
    retcode = libmemcached.MEMCACHED_DATA_EXISTS


class DataDoesNotExist(Error):
    retcode = libmemcached.MEMCACHED_DATA_DOES_NOT_EXIST


class NotFound(Error):
    retcode = libmemcached.MEMCACHED_NOTFOUND


class AllocationError(Error):
    retcode = libmemcached.MEMCACHED_MEMORY_ALLOCATION_FAILURE


class SomeErrors(Error):
    retcode = libmemcached.MEMCACHED_SOME_ERRORS


class NoServers(Error):
    retcode = libmemcached.MEMCACHED_NO_SERVERS


class UnixSocketError(Error):
    retcode = libmemcached.MEMCACHED_FAIL_UNIX_SOCKET


class NotSupportedError(Error):
    retcode = libmemcached.MEMCACHED_NOT_SUPPORTED


class FetchNotFinished(Error):
    retcode = libmemcached.MEMCACHED_FETCH_NOTFINISHED


class BadKeyProvided(Error):
    retcode = libmemcached.MEMCACHED_BAD_KEY_PROVIDED


class InvalidHostProtocolError(Error):
    retcode = libmemcached.MEMCACHED_INVALID_HOST_PROTOCOL


class ServerDead(Error):
    retcode = libmemcached.MEMCACHED_SERVER_MARKED_DEAD


class ServerDown(Error):
    retcode = libmemcached.MEMCACHED_SERVER_TEMPORARILY_DISABLED


class UnknownStatKey(Error):
    retcode = libmemcached.MEMCACHED_UNKNOWN_STAT_KEY


exceptions = [
    ('Error', Error),
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
    ('UnknownStatKey', UnknownStatKey)
]

all_behaviors = [
    'no_block',
    'tcp_nodelay',
    'tcp_keepalive',
    'hash',
    'ketama_hash',
    'ketama',
    'ketama_weighted',
    'distribution',
    'cas',
    'buffer_requests',
    'verify_keys',
    'connect_timeout',
    'send_timeout',
    'receive_timeout',
    'num_replicas',
    'auto_eject',
    'retry_timeout',
    'remove_failed',
    'failure_limit',
    '_io_msg_watermark',
    '_io_bytes_watermark',
    '_io_key_prefetch',
    '_hash_with_prefix_key',
    '_noreply',
    '_sort_hosts',
    '_poll_timeout',
    '_socket_send_size',
    '_socket_recv_size',
    'dead_timeout'
]

all_callbacks = [
    'namespace'
]

server_type_tcp = (1 << 0)
server_type_udp = (1 << 1)
server_type_unix = (1 << 2)

libmemcached_version = libmemcached.LIBMEMCACHED_VERSION_STRING
libmemcached_version_hex = libmemcached.LIBMEMCACHED_VERSION_HEX

support_sasl = bool(libmemcached.PYLIBMC_SASL_SUPPORT)
support_compression = bool(libmemcached.PYLIBMC_COMPRESSION_SUPPORT)
__version__ = "1.3.100-dev"


def get_exception_by_return_code(rc):
    for _, e in exceptions:
        if e.retcode == rc:
            return e

    raise ValueError("Invalid memcached return code")


def destructor(mc):
    libmemcached.memcached_free(mc)


class client(object):
    libmemcached = None

    def _create_memcached_handle(self):
        return ffi.gc(self.libmemcached.memcached_create(ffi.NULL), destructor)

    def __init__(self, servers=None, binary=None, username=None, password=None, behaviors=None):
        if not self.libmemcached:
            self.libmemcached = libmemcached

        self.mc = self._create_memcached_handle()

        if username is not None or password is not None:
            if self._support_sasl:
                if not username or not password:
                    raise TypeError("SASL requires both username and password")

                rc = self.libmemcached.memcached_set_sasl_auth_data(self.mc, username, password)

                if rc != self.libmemcached.MEMCACHED_SUCCESS:
                    exception_class = get_exception_by_return_code(rc)
                    raise exception_class('memcached_set_sasl_auth_data',
                                          self.libmemcached.memcached_last_error_message(self.mc))
            else:
                raise TypeError("libmemcached does not support SASL")

    def disconnect_all(self):
        self.libmemcached.memcached_quit(self.mc)

    @property
    def _support_sasl(self):
        return bool(self.libmemcached.PYLIBMC_SASL_SUPPORT)

    @property
    def _support_compression(self):
        return bool(self.libmemcached.PYLIBMC_COMPRESSION_SUPPORT)