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

#include <Python.h>
#include <libmemcached/memcached.h>

/* Server types. */
#define PYLIBMC_SERVER_TCP   (1 << 0)
#define PYLIBMC_SERVER_UDP   (1 << 1)
#define PYLIBMC_SERVER_UNIX  (1 << 2)

/* Key flags from python-memcache. */
#define PYLIBMC_FLAG_NONE    0
#define PYLIBMC_FLAG_PICKLE  (1 << 0)
#define PYLIBMC_FLAG_INTEGER (1 << 1)
#define PYLIBMC_FLAG_LONG    (1 << 2)

#define PYLIBMC_INC  (1 << 0)
#define PYLIBMC_DEC  (1 << 1)

typedef memcached_return (*_PylibMC_SetCommand)(memcached_st *, const char *,
        size_t, const char *, size_t, time_t, uint32_t);

/* {{{ Exceptions */
static PyObject *PylibMCExc_MemcachedError;
/* }}} */

/* {{{ Behavior statics */
typedef struct {
    int flag;
    char *name;
} PylibMC_Behavior;

static PylibMC_Behavior PylibMC_behaviors[] = {
    { MEMCACHED_BEHAVIOR_NO_BLOCK, "no block" },
    { MEMCACHED_BEHAVIOR_TCP_NODELAY, "tcp_nodelay" },
    { MEMCACHED_BEHAVIOR_HASH, "hash" },
    { MEMCACHED_BEHAVIOR_KETAMA, "ketama" },
    { MEMCACHED_BEHAVIOR_DISTRIBUTION, "distribution" },
    { MEMCACHED_BEHAVIOR_SOCKET_SEND_SIZE, "socket send size" },
    { MEMCACHED_BEHAVIOR_SOCKET_RECV_SIZE, "socket recv size" },
    { MEMCACHED_BEHAVIOR_CACHE_LOOKUPS, "cache_lookups" },
    { MEMCACHED_BEHAVIOR_SUPPORT_CAS, "support_cas" },
    { MEMCACHED_BEHAVIOR_POLL_TIMEOUT, "poll_timeout" },
    { MEMCACHED_BEHAVIOR_BUFFER_REQUESTS, "buffer_requests" },
    { MEMCACHED_BEHAVIOR_SORT_HOSTS, "sort_hosts" },
    { MEMCACHED_BEHAVIOR_VERIFY_KEY, "verify_key" },
    { MEMCACHED_BEHAVIOR_CONNECT_TIMEOUT, "connect_timeout" },
    { MEMCACHED_BEHAVIOR_RETRY_TIMEOUT, "retry_timeout" },
    { MEMCACHED_BEHAVIOR_KETAMA_WEIGHTED, "ketama_weighted" },
    { MEMCACHED_BEHAVIOR_KETAMA_HASH, "ketama_hash" },
    { MEMCACHED_BEHAVIOR_BINARY_PROTOCOL, "binary_protocol" },
    { MEMCACHED_BEHAVIOR_SND_TIMEOUT, "snd_timeout" },
    { MEMCACHED_BEHAVIOR_RCV_TIMEOUT, "rcv_timeout" },
    { MEMCACHED_BEHAVIOR_SERVER_FAILURE_LIMIT, "server_failure_limit" },
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
    { MEMCACHED_HASH_HSIEH, "hsieh" },
    { MEMCACHED_HASH_MURMUR, "murmur" },
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
} PylibMC_Client;

/* {{{ Prototypes */
static PylibMC_Client *PylibMC_ClientType_new(PyTypeObject *, PyObject *,
        PyObject *);
static void PylibMC_ClientType_dealloc(PylibMC_Client *);
static int PylibMC_Client_init(PylibMC_Client *, PyObject *, PyObject *);
static PyObject *PylibMC_Client_get(PylibMC_Client *, PyObject *arg);
static PyObject *PylibMC_Client_set(PylibMC_Client *, PyObject *, PyObject *);
static PyObject *PylibMC_Client_replace(PylibMC_Client *, PyObject *, PyObject *);
static PyObject *PylibMC_Client_add(PylibMC_Client *, PyObject *, PyObject *);
static PyObject *PylibMC_Client_prepend(PylibMC_Client *, PyObject *, PyObject *);
static PyObject *PylibMC_Client_append(PylibMC_Client *, PyObject *, PyObject *);
static PyObject *PylibMC_Client_delete(PylibMC_Client *, PyObject *);
static PyObject *PylibMC_Client_incr(PylibMC_Client *, PyObject *);
static PyObject *PylibMC_Client_decr(PylibMC_Client *, PyObject *);
static PyObject *PylibMC_Client_get_multi(PylibMC_Client *, PyObject *, PyObject *);
static PyObject *PylibMC_Client_set_multi(PylibMC_Client *, PyObject *, PyObject *);
static PyObject *PylibMC_Client_delete_multi(PylibMC_Client *, PyObject *, PyObject *);
static PyObject *PylibMC_Client_get_behaviors(PylibMC_Client *);
static PyObject *PylibMC_Client_set_behaviors(PylibMC_Client *, PyObject *);
static PyObject *PylibMC_Client_flush_all(PylibMC_Client *, PyObject *, PyObject *);
static PyObject *PylibMC_Client_disconnect_all(PylibMC_Client *);
static PyObject *PylibMC_ErrFromMemcached(PylibMC_Client *, const char *,
        memcached_return);
static PyObject *_PylibMC_Unpickle(const char *, size_t);
static PyObject *_PylibMC_Pickle(PyObject *);
static int _PylibMC_CheckKey(PyObject *);
static int _PylibMC_CheckKeyStringAndSize(char *, int);
/* }}} */

/* {{{ Type's method table */
static PyMethodDef PylibMC_ClientType_methods[] = {
    {"get", (PyCFunction)PylibMC_Client_get, METH_O,
        "Retrieve a key from a memcached."},
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
    {"delete", (PyCFunction)PylibMC_Client_delete, METH_VARARGS,
        "Delete a key."},
    {"incr", (PyCFunction)PylibMC_Client_incr, METH_VARARGS,
        "Increment a key by a delta."},
    {"decr", (PyCFunction)PylibMC_Client_decr, METH_VARARGS,
        "Decrement a key by a delta."},
    {"get_multi", (PyCFunction)PylibMC_Client_get_multi,
        METH_VARARGS|METH_KEYWORDS, "Get multiple keys at once."},
    {"set_multi", (PyCFunction)PylibMC_Client_set_multi,
        METH_VARARGS|METH_KEYWORDS, "Set multiple keys at once."},
    {"delete_multi", (PyCFunction)PylibMC_Client_delete_multi,
        METH_VARARGS|METH_KEYWORDS, "Delete multiple keys at once."},
    {"get_behaviors", (PyCFunction)PylibMC_Client_get_behaviors, METH_NOARGS,
        "Get behaviors dict."},
    {"set_behaviors", (PyCFunction)PylibMC_Client_set_behaviors, METH_O,
        "Set behaviors dict."},
    {"flush_all", (PyCFunction)PylibMC_Client_flush_all,
        METH_VARARGS|METH_KEYWORDS, "Flush all data on all servers."},
    {"disconnect_all", (PyCFunction)PylibMC_Client_disconnect_all, METH_NOARGS,
        "Disconnect from all servers and reset own state."},
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
    (newfunc)PylibMC_ClientType_new,              
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
