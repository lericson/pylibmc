/**
 * _pylibmc: hand-made libmemcached bindings for Python
 *
 * Copyright (c) 2008, Ludvig Ericson
 * All rights reserved.
 * 
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 * 
 *  - Redistributions of source code must retain the above copyright notice,
 *  this list of conditions and the following disclaimer.
 * 
 *  - Redistributions in binary form must reproduce the above copyright notice,
 *  this list of conditions and the following disclaimer in the documentation
 *  and/or other materials provided with the distribution.
 * 
 *  - Neither the name of the author nor the names of the contributors may be
 *  used to endorse or promote products derived from this software without
 *  specific prior written permission.
 * 
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 */

#ifndef __PYLIBMC_H__
#define __PYLIBMC_H__

/* This makes the "s#" format for PyArg_ParseTuple and such take a Py_ssize_t
 * instead of an int or whatever. */
#define PY_SSIZE_T_CLEAN

#include <Python.h>
#include <libmemcached/memcached.h>

#ifndef LIBMEMCACHED_VERSION_HEX
#  define LIBMEMCACHED_VERSION_HEX 0x0
#endif

#include "pylibmc-version.h"

/* Py_ssize_t appeared in Python 2.5. */
#ifndef PY_SSIZE_T_MAX
typedef ssize_t Py_ssize_t;
#endif

/* Server types. */
#define PYLIBMC_SERVER_TCP   (1 << 0)
#define PYLIBMC_SERVER_UDP   (1 << 1)
#define PYLIBMC_SERVER_UNIX  (1 << 2)

/* {{{ Key flags from python-memcached
 * Some flags (like the compression one, ZLIB) are combined with others.
 */
#define PYLIBMC_FLAG_NONE    0
#define PYLIBMC_FLAG_PICKLE  (1 << 0)
#define PYLIBMC_FLAG_INTEGER (1 << 1)
#define PYLIBMC_FLAG_LONG    (1 << 2)
/* Note: this is an addition! python-memcached doesn't handle bools. */
#define PYLIBMC_FLAG_BOOL    (1 << 4)
#define PYLIBMC_FLAG_TYPES   (PYLIBMC_FLAG_PICKLE | PYLIBMC_FLAG_INTEGER | \
                              PYLIBMC_FLAG_LONG | PYLIBMC_FLAG_BOOL)
/* Modifier flags */
#define PYLIBMC_FLAG_ZLIB    (1 << 3)
/* }}} */

typedef memcached_return (*_PylibMC_SetCommand)(memcached_st *, const char *,
        size_t, const char *, size_t, time_t, uint32_t);
typedef memcached_return (*_PylibMC_IncrCommand)(memcached_st *,
        const char *, size_t, unsigned int, uint64_t*);

static PyObject *_exc_by_rc(memcached_return);

typedef struct {
  char *key;
  Py_ssize_t key_len;
  char *value;
  Py_ssize_t value_len;
  time_t time;
  uint32_t flags;

  /* the objects that must be freed after the mset is executed */
  PyObject *key_obj;
  PyObject *prefixed_key_obj;
  PyObject *value_obj;

  /* the success of executing the mset afterwards */
  int success;

} pylibmc_mset;

typedef struct {
  char* key;
  Py_ssize_t key_len;
  _PylibMC_IncrCommand incr_func;
  unsigned int delta;
  uint64_t result;
} pylibmc_incr;

typedef struct {
    PyObject *self;
    PyObject *retval;
    memcached_server_st *servers;  /* DEPRECATED */
    memcached_stat_st *stats;
    int index;
} _PylibMC_StatsContext;

/* {{{ Exceptions */
static PyObject *PylibMCExc_MemcachedError;

/* Mapping of memcached_return value -> Python exception object. */
typedef struct {
    memcached_return rc;
    char *name;
    PyObject *exc;
} PylibMC_McErr;

static PylibMC_McErr PylibMCExc_mc_errs[] = {
    { MEMCACHED_FAILURE, "Failure", NULL },
    { MEMCACHED_HOST_LOOKUP_FAILURE, "HostLookupError", NULL },
    { MEMCACHED_CONNECTION_FAILURE, "ConnectionError", NULL },
    { MEMCACHED_CONNECTION_BIND_FAILURE, "ConnectionBindError", NULL },
    { MEMCACHED_WRITE_FAILURE, "WriteError", NULL },
    { MEMCACHED_READ_FAILURE, "ReadError", NULL },
    { MEMCACHED_UNKNOWN_READ_FAILURE, "UnknownReadFailure", NULL },
    { MEMCACHED_PROTOCOL_ERROR, "ProtocolError", NULL },
    { MEMCACHED_CLIENT_ERROR, "ClientError", NULL },
    { MEMCACHED_SERVER_ERROR, "ServerError", NULL },
    { MEMCACHED_CONNECTION_SOCKET_CREATE_FAILURE, "SocketCreateError", NULL },
    { MEMCACHED_DATA_EXISTS, "DataExists", NULL },
    { MEMCACHED_DATA_DOES_NOT_EXIST, "DataDoesNotExist", NULL },
    //{ MEMCACHED_NOTSTORED, "NotStored", NULL },
    //{ MEMCACHED_STORED, "Stored", NULL },
    { MEMCACHED_NOTFOUND, "NotFound", NULL },
    { MEMCACHED_MEMORY_ALLOCATION_FAILURE, "AllocationError", NULL },
    //{ MEMCACHED_PARTIAL_READ, "PartialRead", NULL },
    { MEMCACHED_SOME_ERRORS, "SomeErrors", NULL },
    { MEMCACHED_NO_SERVERS, "NoServers", NULL },
    //{ MEMCACHED_END, "", NULL },
    //{ MEMCACHED_DELETED, "", NULL },
    //{ MEMCACHED_VALUE, "", NULL },
    //{ MEMCACHED_STAT, "", NULL },
    //{ MEMCACHED_ITEM, "", NULL },
    //{ MEMCACHED_ERRNO, "", NULL },
    { MEMCACHED_FAIL_UNIX_SOCKET, "UnixSocketError", NULL },
    { MEMCACHED_NOT_SUPPORTED, "NotSupportedError", NULL },
    { MEMCACHED_FETCH_NOTFINISHED, "FetchNotFinished", NULL },
    //{ MEMCACHED_TIMEOUT, "TimeoutError", NULL },
    //{ MEMCACHED_BUFFERED, "Buffer, NULL },
    { MEMCACHED_BAD_KEY_PROVIDED, "BadKeyProvided", NULL },
    { MEMCACHED_INVALID_HOST_PROTOCOL, "InvalidHostProtocolError", NULL },
    { MEMCACHED_SERVER_MARKED_DEAD, "ServerDead", NULL },
#ifdef MEMCACHED_SERVER_TEMPORARILY_DISABLED
    { MEMCACHED_SERVER_TEMPORARILY_DISABLED, "ServerDown", NULL },
#endif
    { MEMCACHED_UNKNOWN_STAT_KEY, "UnknownStatKey", NULL },
    //{ MEMCACHED_E2BIG, "TooBigError", NULL },
    { 0, NULL, NULL }
};
/* }}} */

/* {{{ Behavior statics */
typedef struct {
    int flag;
    char *name;
} PylibMC_Behavior;

static PylibMC_Behavior PylibMC_behaviors[] = {
    { MEMCACHED_BEHAVIOR_NO_BLOCK, "no_block" },
    { MEMCACHED_BEHAVIOR_TCP_NODELAY, "tcp_nodelay" },
    { MEMCACHED_BEHAVIOR_HASH, "hash" },
    { MEMCACHED_BEHAVIOR_KETAMA_HASH, "ketama_hash" },
    { MEMCACHED_BEHAVIOR_KETAMA, "ketama" },
    { MEMCACHED_BEHAVIOR_KETAMA_WEIGHTED, "ketama_weighted" },
    { MEMCACHED_BEHAVIOR_DISTRIBUTION, "distribution" },
    { MEMCACHED_BEHAVIOR_SUPPORT_CAS, "cas" },
    { MEMCACHED_BEHAVIOR_BUFFER_REQUESTS, "buffer_requests" },
    { MEMCACHED_BEHAVIOR_VERIFY_KEY, "verify_keys" },
    { MEMCACHED_BEHAVIOR_CONNECT_TIMEOUT, "connect_timeout" },
    { MEMCACHED_BEHAVIOR_SND_TIMEOUT, "send_timeout" },
    { MEMCACHED_BEHAVIOR_RCV_TIMEOUT, "receive_timeout" },
    { MEMCACHED_BEHAVIOR_NUMBER_OF_REPLICAS, "num_replicas" },
    { MEMCACHED_BEHAVIOR_AUTO_EJECT_HOSTS, "auto_eject" },
    { MEMCACHED_BEHAVIOR_RETRY_TIMEOUT, "retry_timeout" },
#if LIBMEMCACHED_VERSION_HEX >= 0x00049000
    { MEMCACHED_BEHAVIOR_REMOVE_FAILED_SERVERS, "remove_failed" },
#endif
    /* make sure failure_limit is set after remove_failed
     * as the latter overwrites the former. */
    { MEMCACHED_BEHAVIOR_SERVER_FAILURE_LIMIT, "failure_limit" },

    { MEMCACHED_BEHAVIOR_IO_MSG_WATERMARK, "_io_msg_watermark" },
    { MEMCACHED_BEHAVIOR_IO_BYTES_WATERMARK, "_io_bytes_watermark" },
    { MEMCACHED_BEHAVIOR_IO_KEY_PREFETCH, "_io_key_prefetch" },
    { MEMCACHED_BEHAVIOR_HASH_WITH_PREFIX_KEY, "_hash_with_prefix_key" },
    { MEMCACHED_BEHAVIOR_NOREPLY, "_noreply" },
    { MEMCACHED_BEHAVIOR_SORT_HOSTS, "_sort_hosts" },
    { MEMCACHED_BEHAVIOR_POLL_TIMEOUT, "_poll_timeout" },
    { MEMCACHED_BEHAVIOR_SOCKET_SEND_SIZE, "_socket_send_size" },
    { MEMCACHED_BEHAVIOR_SOCKET_RECV_SIZE, "_socket_recv_size" },
    { 0, NULL }
};

static PylibMC_Behavior PylibMC_hashers[] = {
    { MEMCACHED_HASH_DEFAULT, "default" },
    { MEMCACHED_HASH_MD5, "md5" },
    { MEMCACHED_HASH_CRC, "crc" },
    { MEMCACHED_HASH_FNV1_64, "fnv1_64" },
    { MEMCACHED_HASH_FNV1A_64, "fnv1a_64" },
    { MEMCACHED_HASH_FNV1_32, "fnv1_32" },
    { MEMCACHED_HASH_FNV1A_32, "fnv1a_32" },
    { MEMCACHED_HASH_MURMUR, "murmur" },
#ifdef MEMCACHED_HASH_HSIEH
    { MEMCACHED_HASH_HSIEH, "hsieh" },
#endif
    { 0, NULL }
};

static PylibMC_Behavior PylibMC_distributions[] = {
    { MEMCACHED_DISTRIBUTION_MODULA, "modula" },
    { MEMCACHED_DISTRIBUTION_CONSISTENT, "consistent" },
    { MEMCACHED_DISTRIBUTION_CONSISTENT_KETAMA, "consistent_ketama" },
    { 0, NULL }
};
/* }}} */

/* {{{ _pylibmc.client */
typedef struct {
    PyObject_HEAD
    memcached_st *mc;
    uint8_t sasl_set;
} PylibMC_Client;

/* {{{ Prototypes */
static PylibMC_Client *PylibMC_ClientType_new(PyTypeObject *, PyObject *,
        PyObject *);
static void PylibMC_ClientType_dealloc(PylibMC_Client *);
static int PylibMC_Client_init(PylibMC_Client *, PyObject *, PyObject *);
static PyObject *PylibMC_Client_get(PylibMC_Client *, PyObject *arg);
static PyObject *PylibMC_Client_gets(PylibMC_Client *, PyObject *arg);
static PyObject *PylibMC_Client_set(PylibMC_Client *, PyObject *, PyObject *);
static PyObject *PylibMC_Client_replace(PylibMC_Client *, PyObject *, PyObject *);
static PyObject *PylibMC_Client_add(PylibMC_Client *, PyObject *, PyObject *);
static PyObject *PylibMC_Client_prepend(PylibMC_Client *, PyObject *, PyObject *);
static PyObject *PylibMC_Client_append(PylibMC_Client *, PyObject *, PyObject *);
static PyObject *PylibMC_Client_cas(PylibMC_Client *, PyObject *, PyObject *);
static PyObject *PylibMC_Client_delete(PylibMC_Client *, PyObject *);
static PyObject *PylibMC_Client_incr(PylibMC_Client *, PyObject *);
static PyObject *PylibMC_Client_decr(PylibMC_Client *, PyObject *);
static PyObject *PylibMC_Client_incr_multi(PylibMC_Client*, PyObject*, PyObject*);
static PyObject *PylibMC_Client_get_multi(PylibMC_Client *, PyObject *, PyObject *);
static PyObject *PylibMC_Client_set_multi(PylibMC_Client *, PyObject *, PyObject *);
static PyObject *PylibMC_Client_add_multi(PylibMC_Client *, PyObject *, PyObject *);
static PyObject *PylibMC_Client_delete_multi(PylibMC_Client *, PyObject *, PyObject *);
static PyObject *PylibMC_Client_get_behaviors(PylibMC_Client *);
static PyObject *PylibMC_Client_set_behaviors(PylibMC_Client *, PyObject *);
static PyObject *PylibMC_Client_get_stats(PylibMC_Client *, PyObject *);
static PyObject *PylibMC_Client_flush_all(PylibMC_Client *, PyObject *, PyObject *);
static PyObject *PylibMC_Client_disconnect_all(PylibMC_Client *);
static PyObject *PylibMC_Client_clone(PylibMC_Client *);
static PyObject *PylibMC_ErrFromMemcachedWithKey(PylibMC_Client *, const char *,
        memcached_return, const char *, Py_ssize_t);
static PyObject *PylibMC_ErrFromMemcached(PylibMC_Client *, const char *,
        memcached_return);
static PyObject *_PylibMC_Unpickle(const char *, size_t);
static PyObject *_PylibMC_Pickle(PyObject *);
static int _PylibMC_CheckKey(PyObject *);
static int _PylibMC_CheckKeyStringAndSize(char *, Py_ssize_t);
static int _PylibMC_SerializeValue(PyObject *key_obj,
                                   PyObject *key_prefix,
                                   PyObject *value_obj,
                                   time_t time,
                                   pylibmc_mset *serialized);
static void _PylibMC_FreeMset(pylibmc_mset*);
static PyObject *_PylibMC_RunSetCommandSingle(PylibMC_Client *self,
        _PylibMC_SetCommand f, char *fname, PyObject *args, PyObject *kwds);
static PyObject *_PylibMC_RunSetCommandMulti(PylibMC_Client *self,
        _PylibMC_SetCommand f, char *fname, PyObject *args, PyObject *kwds);
static bool _PylibMC_RunSetCommand(PylibMC_Client *self,
                                   _PylibMC_SetCommand f, char *fname,
                                   pylibmc_mset *msets, size_t nkeys,
                                   size_t min_compress);
static int _PylibMC_Deflate(char *value, size_t value_len,
                            char **result, size_t *result_len);
static bool _PylibMC_IncrDecr(PylibMC_Client *, pylibmc_incr *, size_t);

/* }}} */

/* {{{ Type's method table */
static PyMethodDef PylibMC_ClientType_methods[] = {
    {"get", (PyCFunction)PylibMC_Client_get, METH_O,
        "Retrieve a key from a memcached."},
    {"gets", (PyCFunction)PylibMC_Client_gets, METH_O,
        "Retrieve a key and cas_id from a memcached."},
    {"set", (PyCFunction)PylibMC_Client_set, METH_VARARGS|METH_KEYWORDS,
        "Set a key unconditionally."},
    {"replace", (PyCFunction)PylibMC_Client_replace, METH_VARARGS|METH_KEYWORDS,
        "Set a key only if it exists."},
    {"add", (PyCFunction)PylibMC_Client_add, METH_VARARGS|METH_KEYWORDS,
        "Set a key only if doesn't exist."},
    {"prepend", (PyCFunction)PylibMC_Client_prepend, METH_VARARGS|METH_KEYWORDS,
        "Prepend data to  a key."},
    {"append", (PyCFunction)PylibMC_Client_append, METH_VARARGS|METH_KEYWORDS,
        "Append data to a key."},
    {"cas", (PyCFunction)PylibMC_Client_cas, METH_VARARGS|METH_KEYWORDS,
        "Attempt to compare-and-store a key by CAS ID."},
    {"delete", (PyCFunction)PylibMC_Client_delete, METH_VARARGS,
        "Delete a key."},
    {"incr", (PyCFunction)PylibMC_Client_incr, METH_VARARGS,
        "Increment a key by a delta."},
    {"decr", (PyCFunction)PylibMC_Client_decr, METH_VARARGS,
        "Decrement a key by a delta."},
    {"incr_multi", (PyCFunction)PylibMC_Client_incr_multi, METH_VARARGS|METH_KEYWORDS,
        "Increment more than one key by a delta."},
    {"get_multi", (PyCFunction)PylibMC_Client_get_multi,
        METH_VARARGS|METH_KEYWORDS, "Get multiple keys at once."},
    {"set_multi", (PyCFunction)PylibMC_Client_set_multi,
        METH_VARARGS|METH_KEYWORDS, "Set multiple keys at once."},
    {"add_multi", (PyCFunction)PylibMC_Client_add_multi,
        METH_VARARGS|METH_KEYWORDS, "Add multiple keys at once."},
    {"delete_multi", (PyCFunction)PylibMC_Client_delete_multi,
        METH_VARARGS|METH_KEYWORDS, "Delete multiple keys at once."},
    {"get_behaviors", (PyCFunction)PylibMC_Client_get_behaviors, METH_NOARGS,
        "Get behaviors dict."},
    {"set_behaviors", (PyCFunction)PylibMC_Client_set_behaviors, METH_O,
        "Set behaviors dict."},
    {"get_stats", (PyCFunction)PylibMC_Client_get_stats,
        METH_VARARGS, "Retrieve statistics from all memcached servers."},
    {"flush_all", (PyCFunction)PylibMC_Client_flush_all,
        METH_VARARGS|METH_KEYWORDS, "Flush all data on all servers."},
    {"disconnect_all", (PyCFunction)PylibMC_Client_disconnect_all, METH_NOARGS,
        "Disconnect from all servers and reset own state."},
    {"clone", (PyCFunction)PylibMC_Client_clone, METH_NOARGS,
        "Clone this client entirely such that it is safe to access from "
        "another thread. This creates a new connection."},
    {NULL, NULL, 0, NULL}
};
/* }}} */

/* {{{ Type def */
static PyTypeObject PylibMC_ClientType = {
    PyObject_HEAD_INIT(NULL)
    0,
    "client",
    sizeof(PylibMC_Client),
    0,
    (destructor)PylibMC_ClientType_dealloc,

    0,
    0,
    0,
    0,
    0,

    0,
    0,
    0,

    0,
    0,
    0,
    0,
    0,
    0,
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    "memcached client type",
    0,
    0,
    0,
    0,
    0,
    0,
    PylibMC_ClientType_methods,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    (initproc)PylibMC_Client_init,
    0,
    (newfunc)PylibMC_ClientType_new, //PyType_GenericNew,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0
};

/* }}} */

#endif /* def __PYLIBMC_H__ */
