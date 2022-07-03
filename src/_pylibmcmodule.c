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

#include "_pylibmcmodule.h"
#ifdef USE_ZLIB
#  include <zlib.h>
#  define ZLIB_BUFSZ (1 << 14)
/* only release the GIL during inflate if the size of the data
   is greater than this (deflate always releases at present) */
#  define ZLIB_GIL_RELEASE ZLIB_BUFSZ
#endif

#define PyBool_TEST(t) ((t) ? Py_True : Py_False)

#define PyModule_ADD_REF(mod, nam, obj) \
    { Py_INCREF(obj); \
      PyModule_AddObject(mod, nam, obj); }


/* Some Python 3 porting stuff */
#ifndef Py_TYPE
#define Py_TYPE(ob) (((PyObject*)(ob))->ob_type)
#endif
#ifndef PyInt_Check
#define PyInt_Check PyLong_Check
#endif

#define MOD_ERROR_VAL NULL
#define MOD_SUCCESS_VAL(val) val
#define MOD_INIT(name) PyMODINIT_FUNC PyInit_##name(void)
#define MOD_DEF(ob, name, doc, methods)                     \
    static struct PyModuleDef moduledef = {                 \
        PyModuleDef_HEAD_INIT, name, doc, -1, methods, };   \
    ob = PyModule_Create(&moduledef);

/* Cache the values of {cP,p}ickle.{load,dump}s */
static PyObject *_PylibMC_pickle_loads = NULL;
static PyObject *_PylibMC_pickle_dumps = NULL;

/* {{{ Type methods */
static PylibMC_Client *PylibMC_ClientType_new(PyTypeObject *type,
        PyObject *args, PyObject *kwds) {
    PylibMC_Client *self;

    /* GenericNew calls GenericAlloc (via the indirection type->tp_alloc) which
     * adds GC tracking if flagged for, and also calls PyObject_Init. */
    self = (PylibMC_Client *)PyType_GenericNew(type, args, kwds);

    if (self != NULL) {
        self->mc = memcached_create(NULL);
        self->sasl_set = false;
    }

    return self;
}

/* Helper: detect whether the serialize and deserialize methods were overridden. */
static int _PylibMC_method_is_overridden(PylibMC_Client *self, const char *method) {
    /* `self.__class__.serialize is _pylibmc.client.serialize`, in C */
    PyObject *base_method = NULL, *current_class = NULL, *current_method = NULL;

    base_method = PyObject_GetAttrString((PyObject *) &PylibMC_ClientType, method);
    current_class = PyObject_GetAttrString((PyObject *) self, "__class__");
    if (current_class != NULL) {
        current_method = PyObject_GetAttrString(current_class, method);
    }

    Py_XDECREF(base_method);
    Py_XDECREF(current_class);
    Py_XDECREF(current_method);

    if (base_method && current_class && current_method) {
        return base_method == current_method;
    } else {
        return -1;
    }
}

static void PylibMC_ClientType_dealloc(PylibMC_Client *self) {
    if (self->mc != NULL) {
#if LIBMEMCACHED_WITH_SASL_SUPPORT
        if (self->sasl_set) {
            memcached_destroy_sasl_auth_data(self->mc);
        }
#endif
        memcached_free(self->mc);
    }

    Py_TYPE(self)->tp_free(self);
}
/* }}} */

static int PylibMC_Client_init(PylibMC_Client *self, PyObject *args,
        PyObject *kwds) {
    PyObject *srvs, *srvs_it, *c_srv;
    unsigned char set_stype = 0, bin = 0, got_server = 0;
    const char *user = NULL, *pass = NULL;
    PyObject *behaviors = NULL;
    memcached_return rc;

    self->pickle_protocol = -1;

    static char *kws[] = { "servers", "binary", "username", "password",
                           "behaviors", NULL };

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|bzzO", kws,
                                     &srvs, &bin, &user, &pass,
                                     &behaviors)) {
        return -1;
    }

    if ((srvs_it = PyObject_GetIter(srvs)) == NULL) {
        return -1;
    }

    /* setup sasl */
    if (user != NULL || pass != NULL) {

#if LIBMEMCACHED_WITH_SASL_SUPPORT
        if (user == NULL || pass == NULL) {
            PyErr_SetString(PyExc_TypeError, "SASL requires both username and password");
            goto error;
        }

        if (!bin) {
            PyErr_SetString(PyExc_TypeError, "SASL requires the memcached binary protocol");
            goto error;
        }

        rc = memcached_set_sasl_auth_data(self->mc, user, pass);
        if (rc != MEMCACHED_SUCCESS) {
            PylibMC_ErrFromMemcached(self, "memcached_set_sasl_auth_data", rc);
            goto error;
        }

        /* Can't just look at the memcached_st->sasl data, because then it
         * breaks in libmemcached 0.43 and potentially earlier. */
        self->sasl_set = true;

#else
        PyErr_SetString(PyExc_TypeError, "libmemcached does not support SASL");
        goto error;

#endif
    }

    rc = memcached_behavior_set(self->mc, MEMCACHED_BEHAVIOR_BINARY_PROTOCOL, bin);
    if (rc != MEMCACHED_SUCCESS) {
        PyErr_SetString(PyExc_RuntimeError, "binary protocol behavior set failed");
        goto error;
    }

    if (behaviors != NULL) {
        if (PylibMC_Client_set_behaviors(self, behaviors) == NULL) {
            goto error;
        }
    }

    /* Detect whether we should dispatch to user-modified Python
     * serialization implementations. */
    int native_serialization, native_deserialization;
    if ((native_serialization = _PylibMC_method_is_overridden(self, "serialize")) == -1) {
        goto error;
    }
    self->native_serialization = (uint8_t) native_serialization;
    if ((native_deserialization = _PylibMC_method_is_overridden(self, "deserialize")) == -1) {
        goto error;
    }
    self->native_deserialization = (uint8_t) native_deserialization;

    while ((c_srv = PyIter_Next(srvs_it)) != NULL) {
        unsigned char stype;
        char *hostname;
        unsigned short int port;
        unsigned short int weight;

        got_server |= 1;
        port = 0;
        weight = 1;
        if (PyBytes_Check(c_srv)) {
            memcached_server_st *list;

            list = memcached_servers_parse(PyBytes_AS_STRING(c_srv));
            if (list == NULL) {
                PyErr_SetString(PylibMCExc_Error,
                        "memcached_servers_parse returned NULL");
                goto it_error;
            }

            rc = memcached_server_push(self->mc, list);
            memcached_server_list_free(list);
            if (rc != MEMCACHED_SUCCESS) {
                PylibMC_ErrFromMemcached(self, "memcached_server_push", rc);
                goto it_error;
            }
        } else if (PyArg_ParseTuple(c_srv, "Bs|HH", &stype, &hostname, &port, &weight)) {
            if (set_stype && set_stype != stype) {
                PyErr_SetString(PyExc_ValueError, "can't mix transport types");
                goto it_error;
            } else {
                set_stype = stype;
                if (stype == PYLIBMC_SERVER_UDP) {
                    rc = memcached_behavior_set(self->mc, MEMCACHED_BEHAVIOR_USE_UDP, 1);
                    if (rc != MEMCACHED_SUCCESS) {
                        PyErr_SetString(PyExc_RuntimeError, "udp behavior set failed");
                        goto it_error;
                    }
                }
            }

            switch (stype) {
                case PYLIBMC_SERVER_UDP:
#if LIBMEMCACHED_VERSION_HEX <= 0x00053000
                    rc = memcached_server_add_udp_with_weight(self->mc, hostname, port, weight);
                    break;
#endif
                case PYLIBMC_SERVER_TCP:
                    rc = memcached_server_add_with_weight(self->mc, hostname, port, weight);
                    break;
                case PYLIBMC_SERVER_UNIX:
                    if (port) {
                        PyErr_SetString(PyExc_ValueError,
                                "can't set port on unix sockets");
                        goto it_error;
                    }
                    rc = memcached_server_add_unix_socket_with_weight(self->mc, hostname, weight);
                    break;
                default:
                    PyErr_Format(PyExc_ValueError, "bad type: %u", stype);
                    goto it_error;
            }
            if (rc != MEMCACHED_SUCCESS) {
                PylibMC_ErrFromMemcached(self, "memcached_server_add_*", rc);
                goto it_error;
            }
        }
        Py_DECREF(c_srv);
        continue;

it_error:
        Py_DECREF(c_srv);
        goto error;
    }

    if (!got_server) {
        PyErr_SetString(PylibMCExc_Error, "empty server list");
        goto error;
    }

    Py_DECREF(srvs_it);
    return 0;
error:
    Py_DECREF(srvs_it);
    return -1;
}

/* {{{ Compression helpers */
#ifdef USE_ZLIB
static int _PylibMC_Deflate(char *value, Py_ssize_t value_len,
                    char **result, Py_ssize_t *result_len,
                    int compress_level) {
    /* FIXME Failures are entirely silent. */
    int rc;

    /* n.b.: this is called while *not* holding the GIL, and must not
       contain Python-API code */

    ssize_t out_sz;
    z_stream strm;
    *result = NULL;
    *result_len = 0;

    /* Don't ask me about this one. Got it from zlibmodule.c in Python 2.6. */
    out_sz = value_len + value_len / 1000 + 12 + 1;

    if ((*result = malloc(out_sz)) == NULL) {
      goto error;
    }

    /* TODO Should break up next_in into blocks of max 0xffffffff in length. */
    assert(value_len < 0xffffffffU);
    assert(out_sz < 0xffffffffU);

    strm.avail_in = (uInt)value_len;
    strm.avail_out = (uInt)out_sz;
    strm.next_in = (Bytef *)value;
    strm.next_out = (Bytef *)*result;

    /* we just pre-allocated all of it up front */
    strm.zalloc = (alloc_func)NULL;
    strm.zfree = (free_func)Z_NULL;

    if (deflateInit((z_streamp)&strm, compress_level) != Z_OK) {
        goto error;
    }

    rc = deflate((z_streamp)&strm, Z_FINISH);

    if (rc != Z_STREAM_END) {
        goto error;
    }

    if (deflateEnd((z_streamp)&strm) != Z_OK) {
        goto error;
    }

    if ((Py_ssize_t)strm.total_out >= value_len) {
      /* if no data was saved, don't use compression */
      goto error;
    }

    /* *result should already be populated since that's the address we
       passed into the z_stream */
    *result_len = strm.total_out;

    return 1;
error:
    /* if any error occurred, we'll just use the original value
       instead of trying to compress it */
    if(*result != NULL) {
      free(*result);
      *result = NULL;
    }
    return 0;
}

static int _PylibMC_Inflate(char *value, Py_ssize_t size,
                            char** result, Py_ssize_t* result_size,
                            char** failure_reason) {

    /*
       can be called while not holding the GIL. returns the zlib return value,
       returns the size of the inflated data in *result_size and the data itself
       in *result, and the failed call in failure_reason if appropriate

       while deflate can silently ignore errors, we can't
    */

    int rc;
    char* out = NULL;
    char* tryrealloc = NULL;
    z_stream strm;

    /* Output buffer */
    size_t rvalsz = ZLIB_BUFSZ;
    out = malloc(ZLIB_BUFSZ);

    if(out == NULL) {
        return Z_MEM_ERROR;
    }

    /* TODO 64-bit fix size/rvalsz */
    assert(size < 0xffffffffU);
    assert(rvalsz < 0xffffffffU);

    /* Set up zlib stream. */
    strm.avail_in = (uInt)size;
    strm.avail_out = (uInt)rvalsz;
    strm.next_in = (Byte*)value;
    strm.next_out = (Byte*)out;

    strm.zalloc = (alloc_func)NULL;
    strm.zfree = (free_func)Z_NULL;
    strm.opaque = (voidpf)NULL;

    /* TODO Add controlling of windowBits with inflateInit2? */
    if ((rc = inflateInit((z_streamp)&strm)) != Z_OK) {
        *failure_reason = "inflateInit";
        goto error;
    }

    do {
        *failure_reason = "inflate";
        rc = inflate((z_streamp)&strm, Z_FINISH);

        switch (rc) {
        case Z_STREAM_END:
            break;
        /* When a Z_BUF_ERROR occurs, we should be out of memory.
         * This is also true for Z_OK, hence the fall-through. */
        case Z_BUF_ERROR:
            if (strm.avail_out) {
                goto zerror;
            }
        /* Fall-through */
        case Z_OK:
            if ((tryrealloc = realloc(out, rvalsz << 1)) == NULL) {
                *failure_reason = "realloc";
                rc = Z_MEM_ERROR;
                goto zerror;
            }
            out = tryrealloc;

            /* Wind forward */
            strm.next_out = (unsigned char*)(out + rvalsz);
            strm.avail_out = rvalsz;
            rvalsz = rvalsz << 1;
            break;
        default:
            goto zerror;
        }

    } while (rc != Z_STREAM_END);

    if ((rc = inflateEnd(&strm)) != Z_OK) {
        *failure_reason = "inflateEnd";
        goto error;
    }

    if ((tryrealloc = realloc(out, strm.total_out)) == NULL) {
        *failure_reason = "realloc";
        rc = Z_MEM_ERROR;
        goto error;
    }
    out = tryrealloc;

    *result = out;
    *result_size = strm.total_out;

    return Z_OK;

zerror:
    inflateEnd(&strm);

error:
    if (out != NULL) {
        free(out);
    }
    *result = NULL;
    return rc;
}
#endif
/* }}} */

/* Helper for multiset / multiget:
   1. Take the iterable `keys` and build a map of UTF-8 encoded bytestrings
      to Unicode keys.
   2. If `key_array` and `nkeys` are not NULL, additionally copy *new*
      references to everything in the iterable into `key_array`. Store
      the actual number of items in `nkeys`.
*/
static PyObject *_PylibMC_map_str_keys(PyObject *keys, PyObject **key_array, Py_ssize_t *nkeys) {
    PyObject *key_str_map = NULL;
    PyObject *iter = NULL;
    PyObject *key = NULL;
    PyObject *key_bytes = NULL;
    Py_ssize_t i = 0;

    key_str_map = PyDict_New();
    if (key_str_map == NULL)
        goto cleanup;

    if ((iter = PyObject_GetIter(keys)) == NULL)
        goto cleanup;

    while ((key = PyIter_Next(iter)) != NULL) {
        if (PyUnicode_Check(key)) {
            key_bytes = PyUnicode_AsUTF8String(key);
            if (key_bytes == NULL)
                goto cleanup;
            PyDict_SetItem(key_str_map, key_bytes, key);
            Py_DECREF(key_bytes);
        }
        /* stash our owned reference to `key` in this array: */
        if (key_array != NULL && i < *nkeys) {
            key_array[i++] = key;
        } else {
            Py_DECREF(key);
        }
    }
    if (nkeys != NULL) {
        *nkeys = i;
    }

    Py_DECREF(iter);
    return key_str_map;

cleanup:
    if (key_array != NULL) {
        for (Py_ssize_t j = 0; j < i; j++) {
            Py_DECREF(key_array[j]);
        }
    }
    Py_XDECREF(key);
    Py_XDECREF(iter);
    Py_XDECREF(key_str_map);
    return NULL;
}

/* }}} */

static PyObject *_PylibMC_parse_memcached_value(PylibMC_Client *self,
        char *value, Py_ssize_t size, uint32_t flags) {
    PyObject *retval = NULL;

#if USE_ZLIB
    PyObject *inflated = NULL;

    /* Decompress value if necessary. */
    if (flags & PYLIBMC_FLAG_ZLIB) {
        int rc;
        char* inflated_buf = NULL;
        Py_ssize_t inflated_size = 0;
        char* failure_reason = NULL;

        if(size >= ZLIB_GIL_RELEASE) {
            Py_BEGIN_ALLOW_THREADS;
            rc = _PylibMC_Inflate(value, size,
                                  &inflated_buf, &inflated_size,
                                  &failure_reason);
            Py_END_ALLOW_THREADS;
        } else {
            rc = _PylibMC_Inflate(value, size,
                                  &inflated_buf, &inflated_size,
                                  &failure_reason);
        }

        if(rc != Z_OK) {
            /* set up the exception */
            if(failure_reason == NULL) {
                PyErr_Format(PylibMCExc_Error,
                             "Failed to decompress value: %d", rc);
            } else {
                PyErr_Format(PylibMCExc_Error,
                             "Failed to decompress value: %s", failure_reason);
            }
            return NULL;
        }

        inflated = PyBytes_FromStringAndSize(inflated_buf, inflated_size);

        free(inflated_buf);

        if(inflated == NULL) {
            return NULL;
        }

        value = PyBytes_AS_STRING(inflated);
        size = PyBytes_GET_SIZE(inflated);
    }

#else
    if (flags & PYLIBMC_FLAG_ZLIB) {
        PyErr_SetString(PylibMCExc_Error,
            "key is compressed but pylibmc is compiled without zlib support");
        return NULL;
    }
#endif

    if (self->native_deserialization) {
        retval = _PylibMC_deserialize_native(self, NULL, value, size, flags);
    } else {
        retval = PyObject_CallMethod((PyObject *)self, "deserialize", "y#I", value, size, (unsigned int) flags);
    }

#if USE_ZLIB
    Py_XDECREF(inflated);
#endif


    return retval;
}

/** Helper because PyLong_FromString requires a null-terminated string. */
static PyObject *_PyLong_FromStringAndSize(char *value, Py_ssize_t size, char **pend, int base) {
    PyObject *retval;
    char *tmp;
    if ((tmp = malloc(size+1)) == NULL) {
        return PyErr_NoMemory();
    }
    strncpy(tmp, value, size);
    tmp[size] = '\0';
    retval = PyLong_FromString(tmp, pend, base);
    free(tmp);
    return retval;
}

/** C implementation of deserialization.

  This either takes a Python bytestring as `value`, or else `value` is NULL and
  the value to be deserialized is a byte array `value_str` of length
  `value_size`.
  */
static PyObject *_PylibMC_deserialize_native(PylibMC_Client *self, PyObject *value, char *value_str, Py_ssize_t value_size, uint32_t flags) {
    assert(value || value_str);
    PyObject *retval = NULL;

    uint32_t dtype = flags & PYLIBMC_FLAG_TYPES;

    switch (dtype) {
        case PYLIBMC_FLAG_PICKLE:
            retval = value ? _PylibMC_Unpickle_Bytes(self, value) : _PylibMC_Unpickle(self, value_str, value_size);
            break;
        case PYLIBMC_FLAG_INTEGER:
        case PYLIBMC_FLAG_LONG:
            if (value) {
                retval = PyLong_FromString(PyBytes_AS_STRING(value), NULL, 10);
            } else {
                retval = _PyLong_FromStringAndSize(value_str, value_size, NULL, 10);;
            }
            break;
        case PYLIBMC_FLAG_TEXT:
            if (value) {
                retval = PyUnicode_FromEncodedObject(value, "utf-8", "strict");
            } else {
                retval = PyUnicode_FromStringAndSize(value_str, value_size);
            }
            break;
        case PYLIBMC_FLAG_NONE:
            if (value) {
                /* acquire an additional reference for parity */
                Py_INCREF(value);
                retval = value;
            } else {
                retval = PyBytes_FromStringAndSize(value_str, value_size);
            }
            break;
        default:
            PyErr_Format(PylibMCExc_Error,
                    "unknown memcached key flags %u", dtype);
    }

    return retval;
}

static PyObject *PylibMC_Client_deserialize(PylibMC_Client *self, PyObject *args) {
    PyObject *value;
    unsigned int flags;
    if (!PyArg_ParseTuple(args, "OI", &value, &flags)) {
        return NULL;
    }
    return _PylibMC_deserialize_native(self, value, NULL, 0, flags);
}

static PyObject *_PylibMC_parse_memcached_result(PylibMC_Client *self, memcached_result_st *res) {
        return _PylibMC_parse_memcached_value(
                                              self,
                                              (char *)memcached_result_value(res),
                                              memcached_result_length(res),
                                              memcached_result_flags(res));
}

/* Helper to call after _PylibMC_parse_memcached_value;
   determines whether the deserialized value should be ignored
   and treated as a miss.
*/
static int _PylibMC_cache_miss_simulated(PyObject *r) {
    if (r == NULL && PyErr_Occurred() && PyErr_ExceptionMatches(PylibMCExc_CacheMiss)) {
        PyErr_Clear();
        return 1;
    }
    return 0;
}

static PyObject *PylibMC_Client_get(PylibMC_Client *self, PyObject *args) {
    char *mc_val;
    size_t val_size;
    uint32_t flags;
    memcached_return error;
    PyObject *key;
    /* if a default argument was in fact passed, it's still a borrowed reference
       at this point, so borrow a reference to Py_None as well for parity. */
    PyObject *default_value = Py_None;

    if (!PyArg_UnpackTuple(args, "get", 1, 2, &key, &default_value)) {
        return NULL;
    }

    if (!_key_normalized_obj(&key)) {
        return NULL;
    } else if (!PySequence_Length(key)) {
        Py_INCREF(default_value);
        return default_value;
    }

    Py_BEGIN_ALLOW_THREADS;
    mc_val = memcached_get(self->mc,
            PyBytes_AS_STRING(key), PyBytes_GET_SIZE(key),
            &val_size, &flags, &error);
    Py_END_ALLOW_THREADS;

    Py_DECREF(key);

    if (error == MEMCACHED_SUCCESS) {
        /* note that mc_val can and is NULL for zero-length values. */
        PyObject *r = _PylibMC_parse_memcached_value(self, mc_val, val_size, flags);

        if (mc_val != NULL) {
            free(mc_val);
        }

        if (_PylibMC_cache_miss_simulated(r)) {
            Py_INCREF(default_value);
            return default_value;
        }

        return r;
    }

    if (error == MEMCACHED_NOTFOUND) {
        Py_INCREF(default_value);
        return default_value;
    }

    return PylibMC_ErrFromMemcachedWithKey(self, "memcached_get", error,
                                           PyBytes_AS_STRING(key),
                                           PyBytes_GET_SIZE(key));
}

static PyObject *PylibMC_Client_gets(PylibMC_Client *self, PyObject *arg) {
    const char* keys[2];
    size_t keylengths[2];
    memcached_result_st *res = NULL;
    memcached_return rc;
    PyObject* ret = NULL;

    if (!_key_normalized_obj(&arg)) {
        return NULL;
    } else if (!PySequence_Length(arg)) {
        return Py_BuildValue("(OO)", Py_None, Py_None);
    } else if (!memcached_behavior_get(self->mc, MEMCACHED_BEHAVIOR_SUPPORT_CAS)) {
        PyErr_SetString(PyExc_ValueError, "gets without cas behavior");
        return NULL;
    }

    /* Use an mget to fetch the key.
     * mget is the only function that returns a memcached_result_st,
     * which is the only way to get at the returned cas value. */
    *keys = PyBytes_AS_STRING(arg);
    *keylengths = (size_t)PyBytes_GET_SIZE(arg);

    Py_DECREF(arg);

    Py_BEGIN_ALLOW_THREADS;

    rc = memcached_mget(self->mc, keys, keylengths, 1);
    if (rc == MEMCACHED_SUCCESS)
        res = memcached_fetch_result(self->mc, res, &rc);

    Py_END_ALLOW_THREADS;

    int miss = 0;
    int fail = 0;
    if (rc == MEMCACHED_SUCCESS && res != NULL) {
        PyObject *val = _PylibMC_parse_memcached_result(self, res);
        if (_PylibMC_cache_miss_simulated(val)) {
            miss = 1;
        } else {
            ret = Py_BuildValue("(NL)",
                                val,
                                memcached_result_cas(res));
        }

        /* we have to fetch the last result from the mget cursor */
        if (NULL != memcached_fetch_result(self->mc, NULL, &rc)) {
            memcached_quit(self->mc);
            Py_DECREF(ret);
            ret = NULL;
            fail = 1;
            PyErr_SetString(PyExc_RuntimeError, "fetch not done");
        }
    } else if (rc == MEMCACHED_END || rc == MEMCACHED_NOTFOUND) {
        miss = 1;
    } else {
        ret = PylibMC_ErrFromMemcached(self, "memcached_gets", rc);
    }

    if (miss && !fail) {
        /* Key not found => (None, None) */
        ret = Py_BuildValue("(OO)", Py_None, Py_None);
    }

    if (res != NULL) {
        memcached_result_free(res);
    }

    return ret;
}

static PyObject *PylibMC_Client_hash(PylibMC_Client *self, PyObject *args, PyObject *kwds) {
    char *key;
    Py_ssize_t key_len = 0;
    uint32_t h;

    if (!PyArg_ParseTuple(args, "s#:hash", &key, &key_len)) {
        return NULL;
    }

    h = memcached_generate_hash(self->mc, key, (Py_ssize_t)key_len);

    return PyLong_FromLong((long)h);
}

/* {{{ Set commands (set, replace, add, prepend, append) */
static PyObject *_PylibMC_RunSetCommandSingle(PylibMC_Client *self,
        _PylibMC_SetCommand f, char *fname, PyObject *args,
        PyObject *kwds) {
    /* function called by the set/add/etc commands */
    static char *kws[] = { "key", "val", "time",
                           "min_compress_len", "compress_level",
                           NULL };
    const char *key_raw;
    PyObject *key;
    Py_ssize_t keylen;
    PyObject *value;
    pylibmc_mset serialized = { NULL };
    unsigned int time = 0; /* this will be turned into a time_t */
    unsigned int min_compress = 0;
    int compress_level = -1;

    bool success = false;

    /*
     * "s#" specifies that (Unicode) text objects will be encoded
     * to UTF-8 byte strings for use as keys, and this seems to be
     * the only sensible thing to do when the user attempts this
     */
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "s#O|IIi", kws,
                                     &key_raw, &keylen, &value,
                                     &time, &min_compress, &compress_level)) {
      return NULL;
    }

#ifdef USE_ZLIB
    if (compress_level == -1) {
        compress_level = Z_DEFAULT_COMPRESSION;
    } else if (compress_level < 0 || compress_level > 9) {
        PyErr_SetString(PyExc_ValueError, "compress_level must be between 0 and 9 inclusive");
        return NULL;
    }
#else
    if (min_compress) {
      PyErr_SetString(PyExc_TypeError, "min_compress_len without zlib");
      return NULL;
    }
#endif



    /*
    Kind of clumsy to convert to a char* and then to a Python
    bytes object, but using "s#" for argument parsing seems to
    be the cleanest way to accept both byte strings and text
    strings as keys.
     */
    key = PyBytes_FromStringAndSize(key_raw, keylen);

    success = _PylibMC_SerializeValue(self, key, NULL, value, time, &serialized);

    if (!success)
        goto cleanup;

    success = _PylibMC_RunSetCommand(self, f, fname,
                                     &serialized, 1,
                                     min_compress, compress_level);

cleanup:
    _PylibMC_FreeMset(&serialized);
    Py_DECREF(key);

    if(PyErr_Occurred() != NULL) {
        return NULL;
    } else if(success) {
        Py_RETURN_TRUE;
    } else {
        Py_RETURN_FALSE;
    }
}

static PyObject *_PylibMC_RunSetCommandMulti(PylibMC_Client *self,
        _PylibMC_SetCommand f, char *fname, PyObject *args,
        PyObject *kwds) {
    /* function called by the set/add/incr/etc commands */
    PyObject *keys = NULL;
    const char *key_prefix_raw = NULL;
    Py_ssize_t key_prefix_len = 0;
    PyObject *key_prefix = NULL;
    unsigned int time = 0;
    unsigned int min_compress = 0;
    int compress_level = -1;
    PyObject *failed = NULL;
    Py_ssize_t idx = 0;
    PyObject *curr_key, *curr_value;
    PyObject *key_str_map = NULL;
    Py_ssize_t i;
    Py_ssize_t nkeys;
    pylibmc_mset* serialized = NULL;
    bool allsuccess;

    static char *kws[] = { "keys", "time", "key_prefix",
                           "min_compress_len", "compress_level",
                           NULL };

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O!|Is#Ii", kws,
                                     &PyDict_Type, &keys,
                                     &time, &key_prefix_raw, &key_prefix_len,
                                     &min_compress, &compress_level)) {
        return NULL;
    }

#ifdef USE_ZLIB
    if (compress_level == -1) {
        compress_level = Z_DEFAULT_COMPRESSION;
    } else if (compress_level < 0 || compress_level > 9) {
        PyErr_SetString(PyExc_ValueError, "compress_level must be between 0 and 9 inclusive");
        return NULL;
    }
#else
    if (min_compress) {
      PyErr_SetString(PyExc_TypeError, "min_compress_len without zlib");
      return NULL;
    }
#endif

    nkeys = (Py_ssize_t)PyDict_Size(keys);

    key_str_map = _PylibMC_map_str_keys(keys, NULL, NULL);
    if (key_str_map == NULL) {
        goto cleanup;
    }

    serialized = PyMem_New(pylibmc_mset, nkeys);
    if (serialized == NULL) {
        goto cleanup;
    }

    if (key_prefix_raw != NULL) {
        key_prefix = PyBytes_FromStringAndSize(key_prefix_raw, key_prefix_len);
    }

    for (i = 0, idx = 0; PyDict_Next(keys, &i, &curr_key, &curr_value); idx++) {
        int success = _PylibMC_SerializeValue(self, curr_key, key_prefix,
                                              curr_value, time,
                                              &serialized[idx]);

        if (!success || PyErr_Occurred() != NULL) {
            nkeys = idx + 1;
            goto cleanup;
        }
    }

    allsuccess = _PylibMC_RunSetCommand(self, f, fname,
                                        serialized, nkeys,
                                        min_compress, compress_level);

    if (PyErr_Occurred() != NULL) {
        goto cleanup;
    }

    if ((failed = PyList_New(0)) == NULL)
        return PyErr_NoMemory();

    for (idx = 0; !allsuccess && idx < nkeys; idx++) {
        PyObject *key_obj;

        if (serialized[idx].success)
            continue;

        key_obj = serialized[idx].key_obj;
        if (PyDict_Contains(key_str_map, key_obj)) {
            key_obj = PyDict_GetItem(key_str_map, key_obj);
        }
        if (PyList_Append(failed, key_obj) != 0) {
            Py_DECREF(failed);
            failed = PyErr_NoMemory();
            goto cleanup;
        }
    }

cleanup:
    if (serialized != NULL) {
        for (i = 0; i < nkeys; i++) {
            _PylibMC_FreeMset(&serialized[i]);
        }
        PyMem_Free(serialized);
    }
    Py_XDECREF(key_prefix);
    Py_XDECREF(key_str_map);

    return failed;
}

static PyObject *_PylibMC_RunCasCommand(PylibMC_Client *self,
        PyObject *args, PyObject *kwds) {
    /* function called by the set/add/etc commands */
    static char *kws[] = { "key", "val", "cas", "time", NULL };
    PyObject *ret = NULL;
    const char *key_raw;
    Py_ssize_t key_len;
    PyObject *key;
    PyObject *value;
    uint64_t cas = 0;
    unsigned int time = 0; /* this will be turned into a time_t */
    bool success = false;
    memcached_return rc;
    pylibmc_mset mset = { NULL };

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "s#OL|I", kws,
                                     &key_raw, &key_len, &value, &cas,
                                     &time)) {
      return NULL;
    }

    if (!memcached_behavior_get(self->mc, MEMCACHED_BEHAVIOR_SUPPORT_CAS)) {
      PyErr_SetString(PyExc_ValueError, "cas without cas behavior");
      return NULL;
    }

    key = PyBytes_FromStringAndSize(key_raw, key_len);

    /* TODO: because it's RunSetCommand that does the zlib
       compression, cas can't currently use compressed values. */
    success = _PylibMC_SerializeValue(self, key, NULL, value, time, &mset);

    if (!success || PyErr_Occurred() != NULL) {
        goto cleanup;
    }

    Py_BEGIN_ALLOW_THREADS;
    rc = memcached_cas(self->mc,
                       mset.key, mset.key_len,
                       mset.value, mset.value_len,
                       mset.time, mset.flags, cas);
    Py_END_ALLOW_THREADS;

    switch(rc) {
        case MEMCACHED_SUCCESS:
            Py_INCREF(Py_True);
            ret = Py_True;
            break;
        case MEMCACHED_DATA_EXISTS:
            Py_INCREF(Py_False);
            ret = Py_False;
            break;
        default:
            PylibMC_ErrFromMemcachedWithKey(self, "memcached_cas", rc,
                                            mset.key, mset.key_len);
    }

cleanup:
    _PylibMC_FreeMset(&mset);
    Py_DECREF(key);

    return ret;
}

static void _PylibMC_FreeMset(pylibmc_mset *mset) {
    Py_XDECREF(mset->key_obj);
    mset->key_obj = NULL;

    Py_XDECREF(mset->prefixed_key_obj);
    mset->prefixed_key_obj = NULL;

    /* Either a ref we own, or a ref passed to us which we borrowed. */
    Py_XDECREF(mset->value_obj);
    mset->value_obj = NULL;
}

static int _PylibMC_SerializeValue(PylibMC_Client *self,
                                   PyObject* key_obj,
                                   PyObject* key_prefix,
                                   PyObject* value_obj,
                                   time_t time,
                                   pylibmc_mset* serialized) {

    /* first zero the whole structure out */
    memset((void *)serialized, 0x0, sizeof(pylibmc_mset));

    serialized->time = time;
    serialized->success = false;
    serialized->value_obj = NULL;

    if (!_key_normalized_obj(&key_obj)) {
        return false;
    }

    serialized->key_obj = key_obj;

    if (PyBytes_AsStringAndSize(key_obj,
                                &serialized->key,
                                &serialized->key_len) == -1) {
        Py_DECREF(key_obj);
        return false;
    }

    /* Check the key_prefix */
    if (key_prefix != NULL) {
        if (!_key_normalized_obj(&key_prefix)) {
            return false;
        }

        /* Ignore empty prefixes */
        if (!PyBytes_Size(key_prefix)) {
            Py_DECREF(key_prefix);
            key_prefix = NULL;
        }
    }

    /* Make the prefixed key if appropriate */
    if (key_prefix != NULL) {
        PyObject* prefixed_key_obj = NULL; /* freed by _PylibMC_FreeMset */

        prefixed_key_obj = PyBytes_FromFormat("%s%s",
                PyBytes_AS_STRING(key_prefix),
                PyBytes_AS_STRING(key_obj));

        Py_DECREF(key_prefix);
        key_prefix = NULL;

        if (prefixed_key_obj == NULL) {
            return false;
        }

        /* check the key and overwrite the C string */
        if(!_key_normalized_obj(&prefixed_key_obj)
           || PyBytes_AsStringAndSize(prefixed_key_obj,
                                       &serialized->key,
                                       &serialized->key_len) == -1) {
            return false;
        }

        serialized->prefixed_key_obj = prefixed_key_obj;
    }

    int success;
    /* Build serialized->value_obj, a Python str/bytes object. */
    if (self->native_serialization) {
        success = _PylibMC_serialize_native(self, value_obj, &(serialized->value_obj), &(serialized->flags));
    } else {
        success = _PylibMC_serialize_user(self, value_obj, &(serialized->value_obj), &(serialized->flags));
    }

    if (!success) {
        return false;
    }

    if (PyBytes_AsStringAndSize(serialized->value_obj, &serialized->value,
                                &serialized->value_len) == -1) {
        return false;
    }

    return true;
}

static int _PylibMC_serialize_user(PylibMC_Client *self, PyObject *value_obj, PyObject **dest, uint32_t *flags) {
    PyObject *serval_and_flags = PyObject_CallMethod((PyObject *)self, "serialize", "(O)", value_obj);
    if (serval_and_flags == NULL) {
        return false;
    }

    if (PyTuple_Check(serval_and_flags)) {
        PyObject *flags_obj = PyTuple_GetItem(serval_and_flags, 1);
        if (flags_obj != NULL) {
            if (PyLong_Check(flags_obj)) {
                *flags = (uint32_t) PyLong_AsLong(flags_obj);
                *dest = PyTuple_GetItem(serval_and_flags, 0);
            }
        }
    }

    if (*dest == NULL) {
        /* PyErr_SetObject(PyExc_ValueError, serval_and_flags); */
        PyErr_SetString(PyExc_ValueError, "serialize() must return (bytes, flags)");
        Py_DECREF(serval_and_flags);
        return false;
    } else {
        /* We're getting rid of serval_and_flags, which owns the only new
           reference to value_obj. However, we can't deallocate value_obj
           until we're done with value and value_len (after the set
           operation). Therefore, take possession of a new reference to it
           before cleaning up the tuple: */
        Py_INCREF(*dest);
        Py_DECREF(serval_and_flags);
    }

    return true;
}

/** C implementation of serialization.

    This either returns true and stores the serialized bytestring in *dest
    and the flags in *flags, or it returns false with an exception set.
*/
static int _PylibMC_serialize_native(PylibMC_Client *self, PyObject *value_obj, PyObject **dest, uint32_t *flags) {
    PyObject *store_val = NULL;
    uint32_t store_flags = PYLIBMC_FLAG_NONE;

    if (PyBytes_Check(value_obj)) {
        store_flags = PYLIBMC_FLAG_NONE;
        /* Make store_val an owned reference */
        store_val = value_obj;
        Py_INCREF(store_val);
    } else if (PyUnicode_Check(value_obj)) {
        store_flags = PYLIBMC_FLAG_TEXT;
        store_val = PyUnicode_AsUTF8String(value_obj);
    } else if (PyBool_Check(value_obj)) {
        store_flags |= PYLIBMC_FLAG_INTEGER;
        store_val = PyBytes_FromStringAndSize(&"01"[value_obj == Py_True], 1);
    } else if (PyLong_Check(value_obj)) {
        store_flags |= PYLIBMC_FLAG_LONG;
        PyObject *tmp = PyObject_Str(value_obj);
        store_val = PyUnicode_AsEncodedString(tmp, "ascii", "strict");
        Py_DECREF(tmp);
    } else if (value_obj != NULL) {
        /* we have no idea what it is, so we'll store it pickled */
        Py_INCREF(value_obj);
        store_flags |= PYLIBMC_FLAG_PICKLE;
        store_val = _PylibMC_Pickle(self, value_obj);
        Py_DECREF(value_obj);
    }

    if (store_val == NULL) {
        return false;
    }

    *dest = store_val;
    *flags = store_flags;
    return true;
}

static PyObject *PylibMC_Client_serialize(PylibMC_Client *self, PyObject *value_obj) {
    PyObject *serialized_val;
    uint32_t flags;
    if (!_PylibMC_serialize_native(self, value_obj, &serialized_val, &flags)) {
        return NULL;
    }
    /* we own a reference to serialized_val. "give" it to the tuple return value: */
    return Py_BuildValue("(NI)", serialized_val, flags);
}

/* {{{ Set commands (set, replace, add, prepend, append) */
static bool _PylibMC_RunSetCommand(PylibMC_Client* self,
                                   _PylibMC_SetCommand f, char *fname,
                                   pylibmc_mset* msets, Py_ssize_t nkeys,
                                   Py_ssize_t min_compress,
                                   int compress_level) {
    memcached_st *mc = self->mc;
    memcached_return rc = MEMCACHED_SUCCESS;
    bool softerrors = false,
         harderrors = false;
    int i;

    Py_BEGIN_ALLOW_THREADS;

    for (i = 0; i < nkeys && !harderrors; i++) {
        pylibmc_mset *mset = &msets[i];

        char *value = mset->value;
        Py_ssize_t value_len = (Py_ssize_t)mset->value_len;
        uint32_t flags = mset->flags;

#ifdef USE_ZLIB
        char *compressed_value = NULL;
        Py_ssize_t compressed_len = 0;

        if (compress_level && min_compress && value_len >= min_compress) {
            _PylibMC_Deflate(value, value_len,
                             &compressed_value, &compressed_len,
                             compress_level);
        }

        if (compressed_value != NULL) {
            /* Will want to change this if this function
             * needs to get back at the old *value at some point */
            value = compressed_value;
            value_len = compressed_len;
            flags |= PYLIBMC_FLAG_ZLIB;
        }
#endif

        if (mset->key_len == 0) {
            rc = MEMCACHED_NOTSTORED;
        } else {
            rc = f(mc, mset->key, mset->key_len,
                   value, value_len, mset->time, flags);
        }

#ifdef USE_ZLIB
        if (compressed_value != NULL) {
            free(compressed_value);
        }
#endif

        switch (rc) {

            /* Successful case */
            case MEMCACHED_SUCCESS:
                mset->success = true;
                break;

            case MEMCACHED_FAILURE:
            case MEMCACHED_NO_KEY_PROVIDED:
            case MEMCACHED_BAD_KEY_PROVIDED:
            case MEMCACHED_MEMORY_ALLOCATION_FAILURE:
            case MEMCACHED_DATA_EXISTS:
            case MEMCACHED_NOTSTORED:
                mset->success = false;
                softerrors = true;
                break;

            default:
                mset->success = false;
                softerrors = true;
                harderrors = true;
                break;
        }
    }

    Py_END_ALLOW_THREADS;

    if (harderrors) {
        PylibMC_ErrFromMemcached(self, fname, rc);
    }

    return !softerrors;
}

/* These all just call _PylibMC_RunSetCommand with the appropriate
 * arguments.  In other words: bulk. */
static PyObject *PylibMC_Client_set(PylibMC_Client *self, PyObject *args,
        PyObject *kwds) {
    PyObject* retval = _PylibMC_RunSetCommandSingle(
            self, memcached_set, "memcached_set", args, kwds);
    return retval;
}

static PyObject *PylibMC_Client_replace(PylibMC_Client *self, PyObject *args,
        PyObject *kwds) {
    return _PylibMC_RunSetCommandSingle(
            self, memcached_replace, "memcached_replace", args, kwds);
}

static PyObject *PylibMC_Client_add(PylibMC_Client *self, PyObject *args,
        PyObject *kwds) {
    return _PylibMC_RunSetCommandSingle(
            self, memcached_add, "memcached_add", args, kwds);
}

static PyObject *PylibMC_Client_prepend(PylibMC_Client *self, PyObject *args,
        PyObject *kwds) {
    return _PylibMC_RunSetCommandSingle(
            self, memcached_prepend, "memcached_prepend", args, kwds);
}

static PyObject *PylibMC_Client_append(PylibMC_Client *self, PyObject *args,
        PyObject *kwds) {
    return _PylibMC_RunSetCommandSingle(
            self, memcached_append, "memcached_append", args, kwds);
}
/* }}} */

static PyObject *PylibMC_Client_cas(PylibMC_Client *self, PyObject *args,
        PyObject *kwds) {
  return _PylibMC_RunCasCommand(self, args, kwds);
}

static PyObject *PylibMC_Client_delete(PylibMC_Client *self, PyObject *args) {
    char *key;
    Py_ssize_t key_len = 0;
    memcached_return rc;

    if (PyArg_ParseTuple(args, "s#:delete", &key, &key_len)
            && _key_normalized_str(&key, &key_len)) {
        Py_BEGIN_ALLOW_THREADS;
        rc = memcached_delete(self->mc, key, key_len, 0);
        Py_END_ALLOW_THREADS;
        switch (rc) {
            case MEMCACHED_SUCCESS:
                Py_RETURN_TRUE;
            case MEMCACHED_FAILURE:
            case MEMCACHED_NOTFOUND:
            case MEMCACHED_NO_KEY_PROVIDED:
            case MEMCACHED_BAD_KEY_PROVIDED:
                Py_RETURN_FALSE;
            default:
                return PylibMC_ErrFromMemcachedWithKey(self, "memcached_delete",
                                                       rc, key, key_len);
        }
    }

    return NULL;
}

static PyObject *PylibMC_Client_touch(PylibMC_Client *self, PyObject *args) {
#if LIBMEMCACHED_VERSION_HEX >= 0x01000002
    char *key;
    long seconds;
    Py_ssize_t key_len;
    memcached_return rc;

    if(PyArg_ParseTuple(args, "s#k", &key, &key_len, &seconds)
            && _key_normalized_str(&key, &key_len)) {
        Py_BEGIN_ALLOW_THREADS;
        rc = memcached_touch(self->mc, key, key_len, seconds);
        Py_END_ALLOW_THREADS;
        switch (rc){
            case MEMCACHED_SUCCESS:
            case MEMCACHED_STORED:
                Py_RETURN_TRUE;
            case MEMCACHED_FAILURE:
            case MEMCACHED_NOTFOUND:
            case MEMCACHED_NO_KEY_PROVIDED:
            case MEMCACHED_BAD_KEY_PROVIDED:
                Py_RETURN_FALSE;
            default:
                return PylibMC_ErrFromMemcachedWithKey(self, "memcached_touch",
                                                       rc, key, key_len);
        }
    }

    return NULL;
#else
    PyErr_Format(PylibMCExc_Error,
                 "memcached_touch isn't available; upgrade libmemcached to >= 1.0.2");
    return NULL;
#endif
}



/* {{{ Increment & decrement */
static PyObject *_PylibMC_IncrSingle(PylibMC_Client *self,
                                     _PylibMC_IncrCommand incr_func,
                                     PyObject *args) {
    char *key;
    Py_ssize_t key_len = 0;
    int delta = 1;
    pylibmc_incr incr;

    if (!PyArg_ParseTuple(args, "s#|i", &key, &key_len, &delta)) {
        return NULL;
    } else if (!_key_normalized_str(&key, &key_len)) {
        return NULL;
    }

    if (delta < 0L) {
        PyErr_SetString(PyExc_ValueError, "delta must be positive");
        return NULL;
    }

    incr.key = key;
    incr.key_len = key_len;
    incr.incr_func = incr_func;
    incr.delta = delta;
    incr.result = 0;

    _PylibMC_IncrDecr(self, &incr, 1);

    if(PyErr_Occurred() != NULL) {
      /* exception already on the stack */
      return NULL;
    }

    /* might be NULL, but if that's true then it's the right return value */
    return PyLong_FromUnsignedLong((unsigned long)incr.result);
}

static PyObject *_PylibMC_IncrMulti(PylibMC_Client *self,
                                    _PylibMC_IncrCommand incr_func,
                                    PyObject *args, PyObject *kwds) {
    PyObject *key = NULL;
    PyObject *keys = NULL;
    PyObject *keys_tmp = NULL;
    const char *key_prefix_raw = NULL;
    Py_ssize_t key_prefix_len = 0;
    PyObject *key_prefix = NULL;
    PyObject *retval = NULL;
    PyObject *iterator = NULL;
    unsigned int delta = 1;
    Py_ssize_t nkeys = 0, i = 0;
    pylibmc_incr *incrs;

    static char *kws[] = { "keys", "key_prefix", "delta", NULL };

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|s#I", kws,
                                     &keys, &key_prefix_raw,
                                     &key_prefix_len, &delta))
        return NULL;

    nkeys = (Py_ssize_t)PySequence_Size(keys);
    if (nkeys == -1)
        return NULL;

    if (key_prefix_raw != NULL) {
        key_prefix = PyBytes_FromStringAndSize(key_prefix_raw, key_prefix_len);

        if (key_prefix != NULL && PyBytes_Size(key_prefix) == 0)
            key_prefix = NULL;
    }

    keys_tmp = PyList_New(nkeys);
    if (keys_tmp == NULL)
        return NULL;

    incrs = PyMem_New(pylibmc_incr, nkeys);
    if (incrs == NULL)
        goto cleanup;

    iterator = PyObject_GetIter(keys);
    if (iterator == NULL)
        goto cleanup;

    /* Build pylibmc_incr structs, prefixed as appropriate. */
    for (i = 0; (key = PyIter_Next(iterator)) != NULL; i++) {
        pylibmc_incr *incr = incrs + i;

        if (!_key_normalized_obj(&key))
            goto loopcleanup;

        /* prefix `key` with `key_prefix` */
        if (key_prefix != NULL) {
            PyObject* newkey = PyBytes_FromFormat("%s%s",
                                                   PyBytes_AS_STRING(key_prefix),
                                                   PyBytes_AS_STRING(key));
            Py_DECREF(key);
            key = newkey;
        }

        Py_INCREF(key);
        if (PyList_SetItem(keys_tmp, i, key) == -1)
            goto loopcleanup;

        /* Populate pylibmc_incr */
        if (PyBytes_AsStringAndSize(key, &incr->key, &incr->key_len) == -1)
            goto loopcleanup;
        incr->delta = delta;
        incr->incr_func = incr_func;
        /* After incring we have no way of knowing whether the real result is 0
         * or if the incr wasn't successful (or if noreply is set), but since
         * we're not actually returning the result that's okay for now */
        incr->result = 0;

loopcleanup:
        Py_DECREF(key);
        if (PyErr_Occurred())
            goto cleanup;
    } /* end each key */

    _PylibMC_IncrDecr(self, incrs, nkeys);

    if (!PyErr_Occurred()) {
        retval = Py_None;
        Py_INCREF(retval);
    } else {
        Py_XDECREF(retval);
        retval = NULL;
    }

cleanup:
    if (incrs != NULL)
        PyMem_Free(incrs);
    Py_XDECREF(key_prefix);
    Py_DECREF(keys_tmp);
    Py_XDECREF(iterator);

    return retval;
}

static PyObject *PylibMC_Client_incr(PylibMC_Client *self, PyObject *args) {
    return _PylibMC_IncrSingle(self, memcached_increment, args);
}

static PyObject *PylibMC_Client_decr(PylibMC_Client *self, PyObject *args) {
    return _PylibMC_IncrSingle(self, memcached_decrement, args);
}

static PyObject *PylibMC_Client_incr_multi(PylibMC_Client *self, PyObject *args,
                                           PyObject *kwds) {
    return _PylibMC_IncrMulti(self, memcached_increment, args, kwds);
}

static bool _PylibMC_IncrDecr(PylibMC_Client *self,
                              pylibmc_incr *incrs, Py_ssize_t nkeys) {
    memcached_return rc = MEMCACHED_SUCCESS;
    _PylibMC_IncrCommand f = NULL;
    Py_ssize_t i, notfound = 0, errors = 0;

    Py_BEGIN_ALLOW_THREADS;
    for (i = 0; i < nkeys; i++) {
        pylibmc_incr *incr = &incrs[i];
        uint64_t result = 0;

        f = incr->incr_func;
        rc = f(self->mc, incr->key, incr->key_len, incr->delta, &result);
        /* TODO Signal errors through `incr` */
        if (rc == MEMCACHED_SUCCESS) {
            incr->result = result;
        } else if (rc == MEMCACHED_NOTFOUND) {
            notfound++;
        } else {
            errors++;
        }
    }
    Py_END_ALLOW_THREADS;

    if (errors + notfound) {
        PyObject *exc = PylibMCExc_Error;

        if (errors == 0)
            exc = _exc_by_rc(MEMCACHED_NOTFOUND);
        else if (errors == 1)
            exc = _exc_by_rc(rc);

        PyErr_Format(exc, "%d keys %s",
                     (int)(notfound + errors),
                     errors ? "failed" : "not found");
    }

    return 0 == (errors + notfound);
}
/* }}} */

static pylibmc_mget_res _fetch_multi(memcached_st *mc,
                                     pylibmc_mget_req req) {
    /* Completely GIL-free multi getter */
    pylibmc_mget_res res = { 0 };

    res.rc = memcached_mget(mc, (const char **)req.keys, req.key_lens, req.nkeys);

    if (res.rc != MEMCACHED_SUCCESS) {
        res.err_func = "memcached_mget";
        return res;
    }

    /* Allocate the results array, with room for libmemcached's sentinel. */
    res.results = PyMem_RawNew(memcached_result_st, req.nkeys + 1);

    /* Note that nresults will not be off by one with this because the loops
     * runs a half pass after the last key has been fetched, thus bumping the
     * count once. */
    for (res.nresults = 0; ; res.nresults++) {
        memcached_result_st *result = memcached_result_create(mc, &res.results[res.nresults]);

        assert(res.nresults <= req.nkeys);

        result = memcached_fetch_result(mc, result, &res.rc);

        if (result == NULL || res.rc == MEMCACHED_END) {
            /* This is how libmecached signals EOF. */
            break;
        } else if (res.rc == MEMCACHED_BAD_KEY_PROVIDED
                || res.rc == MEMCACHED_NO_KEY_PROVIDED) {
            continue;
        } else if (res.rc != MEMCACHED_SUCCESS) {
            memcached_quit(mc);  /* Reset fetch state */
            res.err_func = "memcached_fetch";
            _free_multi_result(res);
        }
    }

    res.rc = MEMCACHED_SUCCESS;
    return res;
}

static void _free_multi_result(pylibmc_mget_res res) {
    if (res.results == NULL)
        return;
    for (Py_ssize_t i = 0; i < res.nresults; i++) {
        memcached_result_free(&res.results[i]);
    }
    PyMem_RawDel(res.results);
}

static PyObject *PylibMC_Client_get_multi(
        PylibMC_Client *self, PyObject *args, PyObject *kwds) {
    PyObject *key_seq, **key_objs, **orig_key_objs, *retval = NULL;
    char **keys, *prefix = NULL;
    Py_ssize_t prefix_len = 0;
    Py_ssize_t i;
    PyObject *key_str_map = NULL;
    PyObject *temp_key_obj;
    size_t *key_lens;
    Py_ssize_t nkeys = 0, orig_nkeys = 0;
    pylibmc_mget_req req;
    pylibmc_mget_res res = { 0 };

    static char *kws[] = { "keys", "key_prefix", NULL };

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|s#:get_multi", kws,
            &key_seq, &prefix, &prefix_len))
        return NULL;

    if ((orig_nkeys = PySequence_Length(key_seq)) == -1)
        return NULL;

    /* Populate keys and key_lens. */
    keys = PyMem_New(char *, orig_nkeys);
    key_lens = PyMem_New(size_t, (size_t) orig_nkeys);
    key_objs = PyMem_New(PyObject *, (Py_ssize_t) orig_nkeys);
    orig_key_objs = PyMem_New(PyObject *, (Py_ssize_t) orig_nkeys);
    if (!keys || !key_lens || !key_objs || !orig_key_objs) {
        PyErr_NoMemory();
        goto memory_cleanup;
    }

    /* Clear potential previous exception, because we explicitly check for
     * exceptions as a loop predicate. */
    PyErr_Clear();

    key_str_map = _PylibMC_map_str_keys(key_seq, orig_key_objs, &orig_nkeys);
    if (key_str_map == NULL) {
        goto memory_cleanup;
    }

    /* Iterate through all keys and set lengths etc. */
    Py_ssize_t key_idx = 0;
    for (i = 0; i < orig_nkeys; i++) {
        PyObject *ckey = orig_key_objs[i];
        char *key;
        Py_ssize_t key_len;
        Py_ssize_t final_key_len;
        PyObject *rkey;

        if (PyErr_Occurred() || !_key_normalized_obj(&ckey)) {
            nkeys = key_idx;
            goto earlybird;
        }

        /* Normalization created an owned reference to ckey */

        PyBytes_AsStringAndSize(ckey, &key, &key_len);

        final_key_len = (Py_ssize_t)(key_len + prefix_len);

        /* Skip empty keys */
        if (!final_key_len) {
            Py_DECREF(ckey);
            continue;
        }

        /* Determine rkey, the prefixed ckey */
        if (prefix != NULL) {
            rkey = PyBytes_FromStringAndSize(prefix, prefix_len);
            PyBytes_Concat(&rkey, ckey);
            if (rkey == NULL)
                goto earlybird;
            Py_DECREF(rkey);
            rkey = PyBytes_FromFormat("%s%s",
                    prefix, PyBytes_AS_STRING(ckey));
        } else {
            Py_INCREF(ckey);
            rkey = ckey;
        }
        Py_DECREF(ckey);

        keys[key_idx] = PyBytes_AS_STRING(rkey);
        key_objs[key_idx] = rkey;
        key_lens[key_idx] = final_key_len;
        key_idx++;
        /* we've added a total of 1 ref, to rkey */
    }
    nkeys = key_idx;

    if (nkeys == 0) {
        retval = PyDict_New();
        goto earlybird;
    } else if (PyErr_Occurred()) {
        nkeys--;
        goto earlybird;
    }

    req.keys = keys;
    req.nkeys = (ssize_t) nkeys;
    req.key_lens = key_lens;

    Py_BEGIN_ALLOW_THREADS;
    res = _fetch_multi(self->mc, req);
    Py_END_ALLOW_THREADS;

    if (res.rc != MEMCACHED_SUCCESS) {
        PylibMC_ErrFromMemcached(self, res.err_func, res.rc);
        goto earlybird;
    }

    retval = PyDict_New();

    for (i = 0; i < res.nresults; i++) {
        PyObject *val, *key_obj;
        memcached_result_st *result = &(res.results[i]);
        int rc;

        /* Long-winded, but this way we can handle NUL-bytes in keys. */
        key_obj = PyBytes_FromStringAndSize(memcached_result_key_value(result) + prefix_len,
                                             memcached_result_key_length(result) - prefix_len);
        if (key_obj == NULL)
            goto loopcleanup;

        if (PyDict_Contains(key_str_map, key_obj)) {
            temp_key_obj = key_obj;
            key_obj = PyDict_GetItem(key_str_map, temp_key_obj);
            /* PyDict_GetItem borrows a reference; own it for consistency */
            Py_INCREF(key_obj);
            Py_DECREF(temp_key_obj);
        }

        /* Parse out value */
        val = _PylibMC_parse_memcached_result(self, result);
        if (_PylibMC_cache_miss_simulated(val)) {
            Py_DECREF(key_obj);
            continue;
        }
        else if (val == NULL)
            goto loopcleanup;

        rc = PyDict_SetItem(retval, key_obj, val);
        /* clean up our local owned references (now that rc has its own) */
        Py_DECREF(key_obj);
        Py_DECREF(val);

        if (rc != 0)
            goto loopcleanup;

        continue;

loopcleanup:
        Py_DECREF(retval);
        retval = NULL;
        break;
    }

earlybird:
    for (i = 0; i < orig_nkeys; i++)
        Py_DECREF(orig_key_objs[i]);
    for (i = 0; i < nkeys; i++)
        Py_DECREF(key_objs[i]);
    Py_XDECREF(key_str_map);

memory_cleanup:
    PyMem_Free(key_objs);
    PyMem_Free(key_lens);
    PyMem_Free(keys);
    PyMem_Free(orig_key_objs);
    _free_multi_result(res);

    return retval;
}

/**
 * Run func over every item in value, building arguments of:
 *     *(item + extra_args)
 */
static PyObject *_PylibMC_DoMulti(PyObject *values, PyObject *func,
        PyObject *prefix, PyObject *extra_args) {
    /* TODO: acquire/release the GIL only once per DoMulti rather than
       once per action; fortunately this is only used for
       delete_multi, which isn't used very often */

    PyObject *retval = PyList_New(0);
    PyObject *iter = NULL;
    PyObject *item = NULL;
    PyObject *orig_item = NULL;
    int is_mapping = PyDict_Check(values);

    if (retval == NULL)
        goto cleanup;

    if ((iter = PyObject_GetIter(values)) == NULL)
        goto cleanup;

    while ((orig_item = item = PyIter_Next(iter)) != NULL) {
        PyObject *args_f = NULL;
        PyObject *args = NULL;
        PyObject *key = NULL;
        PyObject *ro = NULL;

        /**
         * Calculate key.
         *
         * prefix is already converted to a byte string, so ensure that
         * the key is of the same type before trying to append.
         */
        if (!_key_normalized_obj(&item))
            goto loopcleanup;
        if (prefix == NULL || prefix == Py_None) {
            key = item;
            Py_INCREF(key);
        } else {
            PyObject *concat_key = key = PySequence_Concat(prefix, item);
            /**
             * Another call to _key_normalized_obj is still a good idea since
             * we might have created a key that's too long
             */
            if (key == NULL || !_key_normalized_obj(&key))
                goto loopcleanup;
            /* Normalization created a new ref to key; clean up the temporary ref. */
            Py_DECREF(concat_key);
        }

        /* Calculate args. */
        if (is_mapping) {
            PyObject *value;
            char *key_str = PyBytes_AS_STRING(item);

            if ((value = PyMapping_GetItemString(values, key_str)) == NULL)
                goto loopcleanup;

            args = PyTuple_Pack(2, key, value);
            Py_DECREF(value);
        } else {
            args = PyTuple_Pack(1, key);
        }
        if (args == NULL)
            goto loopcleanup;

        /* Calculate full argument tuple. */
        if (extra_args == NULL) {
            Py_INCREF(args);
            args_f = args;
        } else {
            if ((args_f = PySequence_Concat(args, extra_args)) == NULL)
                goto loopcleanup;
        }

        /* Call stuff. */
        ro = PyObject_CallObject(func, args_f);
        /* This is actually safe even if True got deleted because we're
         * only comparing addresses. */
        Py_XDECREF(ro);
        if (ro == NULL) {
            goto loopcleanup;
        } else if (ro != Py_True) {
            if (PyList_Append(retval, item) != 0)
                goto loopcleanup;
        }
        Py_DECREF(args_f);
        Py_DECREF(args);
        Py_DECREF(key);
        Py_DECREF(item);
        Py_DECREF(orig_item);
        continue;
loopcleanup:
        Py_XDECREF(args_f);
        Py_XDECREF(args);
        Py_XDECREF(key);
        Py_DECREF(item);
        goto cleanup;
    }
    Py_DECREF(iter);

    return retval;
cleanup:
    Py_XDECREF(retval);
    Py_XDECREF(iter);
    return NULL;
}

static PyObject *PylibMC_Client_set_multi(PylibMC_Client *self, PyObject *args,
        PyObject *kwds) {
  return _PylibMC_RunSetCommandMulti(self, memcached_set, "memcached_set_multi",
                                     args, kwds);
}

static PyObject *PylibMC_Client_add_multi(PylibMC_Client *self, PyObject *args,
        PyObject *kwds) {
  return _PylibMC_RunSetCommandMulti(self, memcached_add, "memcached_add_multi",
                                     args, kwds);
}

static PyObject *PylibMC_Client_delete_multi(PylibMC_Client *self,
        PyObject *args, PyObject *kwds) {
    const char *prefix_raw = NULL;
    Py_ssize_t prefix_len;
    PyObject *prefix = NULL;
    PyObject *delete;
    PyObject *keys;
    PyObject *retval;

    static char *kws[] = { "keys", "key_prefix", NULL };

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|s#:delete_multi", kws,
                                     &keys, &prefix_raw, &prefix_len))
        return NULL;

    /**
     * Prohibit use of mappings, otherwise DoMulti interprets the values of
     * such mappings as the 2nd argument to the delete function, e.g.
     * DoMulti({"a": 1, "b": 2}) calls delete("a", 1) and delete("b", 2), which
     * is nonsense.
     */
    if (PyDict_Check(keys)) {
        PyErr_SetString(PyExc_TypeError,
            "keys must be a sequence, not a mapping");
        return NULL;
    }

    if (prefix_raw != NULL)
        prefix = PyBytes_FromStringAndSize(prefix_raw, prefix_len);

    if ((delete = PyObject_GetAttrString((PyObject *)self, "delete")) == NULL)
        return NULL;

    retval = _PylibMC_DoMulti(keys, delete, prefix, NULL);

    Py_DECREF(delete);
    Py_XDECREF(prefix);

    if (retval == NULL)
        return NULL;

    if (PyList_Size(retval) == 0) {
        Py_DECREF(retval);
        retval = Py_True;
    } else {
        Py_DECREF(retval);
        retval = Py_False;
    }

    Py_INCREF(retval);
    return retval;
}

static PyObject *PylibMC_Client_get_behaviors(PylibMC_Client *self) {
    PyObject *retval = PyDict_New();
    PylibMC_Behavior *b;

    if (retval == NULL)
        return NULL;

    for (b = PylibMC_behaviors; b->name != NULL; b++) {
        uint64_t bval;
        PyObject *x;

        switch (b->flag) {
        case PYLIBMC_BEHAVIOR_PICKLE_PROTOCOL:
            bval = self->pickle_protocol;
            break;
        default:
            bval = memcached_behavior_get(self->mc, b->flag);
        }

        x = PyLong_FromLong((long)bval);
        if (x == NULL || PyDict_SetItemString(retval, b->name, x) == -1) {
            Py_XDECREF(x);
            goto error;
        }
        Py_DECREF(x);

    }

    return retval;
error:
    Py_XDECREF(retval);
    return NULL;
}

static PyObject *PylibMC_Client_set_behaviors(PylibMC_Client *self,
        PyObject *behaviors) {
    PylibMC_Behavior *b;
    PyObject *py_v;
    long v;
    memcached_return r;
    char *key;

    for (b = PylibMC_behaviors; b->name != NULL; b++) {
        if (!PyMapping_HasKeyString(behaviors, b->name)) {
            continue;
        } else if ((py_v = PyMapping_GetItemString(behaviors, b->name)) == NULL) {
            goto error;
        } else if (!(PyInt_Check(py_v) || PyLong_Check(py_v) || PyBool_Check(py_v))) {
            PyErr_Format(PyExc_TypeError, "behavior %.32s must be int, not %s",
                b->name, Py_TYPE(py_v)->tp_name);
            goto error;
        }

        v = PyLong_AsLong(py_v);
        Py_DECREF(py_v);

        switch (b->flag) {
        case PYLIBMC_BEHAVIOR_PICKLE_PROTOCOL:
            self->pickle_protocol = v;
            break;
        default:
            r = memcached_behavior_set(self->mc, b->flag, (uint64_t)v);
            if (r != MEMCACHED_SUCCESS) {
                PyErr_Format(PylibMCExc_Error,
                             "memcached_behavior_set returned %d for "
                             "behavior '%.32s' = %ld", r, b->name, v);
                goto error;
            }
        }

    }

    for (b = PylibMC_callbacks; b->name != NULL; b++) {
        if (!PyMapping_HasKeyString(behaviors, b->name)) {
            continue;
        } else if ((py_v = PyMapping_GetItemString(behaviors, b->name)) == NULL) {
            goto error;
        }

        key = PyBytes_AS_STRING(py_v);

        r = memcached_callback_set(self->mc, b->flag, key);

        if (r == MEMCACHED_BAD_KEY_PROVIDED) {
            PyErr_Format(PyExc_ValueError, "bad key provided: %s", key);
            goto error;
        } else if (r != MEMCACHED_SUCCESS) {
            PyErr_Format(PylibMCExc_Error,
                         "memcached_callback_set returned %d for "
                         "callback '%.32s' = %.32s", r, b->name, key);
            goto error;
        }
    }

    Py_RETURN_NONE;
error:
    return NULL;
}

static memcached_return
_PylibMC_AddServerCallback(memcached_st *mc,
#if LIBMEMCACHED_VERSION_HEX >= 0x01000017
                           memcached_instance_st* instance,
#elif LIBMEMCACHED_VERSION_HEX >= 0x00039000
                           memcached_server_instance_st instance,
#else
                           memcached_server_st *server,
#endif
                           void *user) {
    _PylibMC_StatsContext *context = (_PylibMC_StatsContext *)user;
    PylibMC_Client *self = (PylibMC_Client *)context->self;
    memcached_stat_st *stat;
    memcached_return rc;
    PyObject *desc, *val;
    char **stat_keys = NULL;
    char **curr_key;

    stat = context->stats + context->index;

    if ((val = PyDict_New()) == NULL)
        return MEMCACHED_FAILURE;

    stat_keys = memcached_stat_get_keys(mc, stat, &rc);
    if (rc != MEMCACHED_SUCCESS)
        return rc;

    for (curr_key = stat_keys; *curr_key; curr_key++) {
        PyObject *curr_value;
        char *mc_val;
        int fail;

        mc_val = memcached_stat_get_value(mc, stat, *curr_key, &rc);
        if (rc != MEMCACHED_SUCCESS) {
            PylibMC_ErrFromMemcached(self, "get_stats val", rc);
            goto error;
        }

        curr_value = PyBytes_FromString(mc_val);
        free(mc_val);
        if (curr_value == NULL)
            goto error;

        fail = PyDict_SetItemString(val, *curr_key, curr_value);
        Py_DECREF(curr_value);
        if (fail)
            goto error;
    }

    free(stat_keys);

    desc = PyBytes_FromFormat("%s:%d (%u)",
#if LIBMEMCACHED_VERSION_HEX >= 0x00039000
            memcached_server_name(instance), memcached_server_port(instance),
#else /* ver < libmemcached 0.39 */
            server->hostname, server->port,
#endif
            (unsigned int)context->index);

    PyList_SET_ITEM(context->retval, context->index++,
                    Py_BuildValue("NN", desc, val));

    return MEMCACHED_SUCCESS;

error:
    free(stat_keys);
    Py_DECREF(val);
    return MEMCACHED_FAILURE;
}

static PyObject *PylibMC_Client_get_stats(PylibMC_Client *self, PyObject *args) {
    memcached_stat_st *stats;
    memcached_return rc;
    char *mc_args;
    Py_ssize_t nservers;
    _PylibMC_StatsContext context;
#if LIBMEMCACHED_VERSION_HEX >= 0x00038000
    memcached_server_function callbacks[] = {
        (memcached_server_function)_PylibMC_AddServerCallback
    };
#endif

    mc_args = NULL;
    if (!PyArg_ParseTuple(args, "|s:get_stats", &mc_args))
        return NULL;

    Py_BEGIN_ALLOW_THREADS;
    stats = memcached_stat(self->mc, mc_args, &rc);
    Py_END_ALLOW_THREADS;
    if (rc != MEMCACHED_SUCCESS)
        return PylibMC_ErrFromMemcached(self, "get_stats", rc);

    /** retval contents:
     * [('<addr, 127.0.0.1:11211> (<num, 1>)', {stat: stat, stat: stat}),
     *  (str, dict),
     *  (str, dict)]
     */
    nservers = (Py_ssize_t)memcached_server_count(self->mc);

    /* Setup stats callback context */
    context.self = (PyObject *)self;
    context.retval = PyList_New(nservers);
    context.stats = stats;
    context.servers = NULL;  /* DEPRECATED */
    context.index = 0;

#if LIBMEMCACHED_VERSION_HEX >= 0x00038000
    rc = memcached_server_cursor(self->mc, callbacks, (void *)&context, 1);
#else /* ver < libmemcached 0.38 */
    context.servers = memcached_server_list(self->mc);

    for (; context.index < nservers; context.index++) {
        memcached_server_st *server = context.servers + context.index;
        memcached_return rc;

        rc = _PylibMC_AddServerCallback(self->mc, server, (void *)&context);
        if (rc != MEMCACHED_SUCCESS)
            break;
    }
#endif

    if (rc != MEMCACHED_SUCCESS) {
        if (!PyErr_Occurred())
            PyErr_SetString(PyExc_RuntimeError, "unknown error occured");
        Py_DECREF(context.retval);
        context.retval = NULL;
    }

    free(context.stats);

    return context.retval;
}

static PyObject *PylibMC_Client_flush_all(PylibMC_Client *self,
        PyObject *args, PyObject *kwds) {
    memcached_return rc;
    time_t expire = 0;
    PyObject *time = NULL;

    static char *kws[] = { "time", NULL };

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "|O!:flush_all", kws,
                                     &PyLong_Type, &time))
        return NULL;

    if (time != NULL)
        expire = PyLong_AS_LONG(time);

    expire = (expire > 0) ? expire : 0;

    Py_BEGIN_ALLOW_THREADS;
    rc = memcached_flush(self->mc, expire);
    Py_END_ALLOW_THREADS;
    if (rc != MEMCACHED_SUCCESS)
        return PylibMC_ErrFromMemcached(self, "flush_all", rc);

    Py_RETURN_TRUE;
}

static PyObject *PylibMC_Client_disconnect_all(PylibMC_Client *self) {
    Py_BEGIN_ALLOW_THREADS;
    memcached_quit(self->mc);
    Py_END_ALLOW_THREADS;
    Py_RETURN_NONE;
}

static PyObject *PylibMC_Client_clone(PylibMC_Client *self) {
    /* Essentially this is a reimplementation of the allocator, only it uses a
     * cloned memcached_st for mc. */
    PylibMC_Client *clone;

    clone = (PylibMC_Client *)PyType_GenericNew(Py_TYPE(self), NULL, NULL);
    if (clone == NULL) {
        return NULL;
    }

    Py_BEGIN_ALLOW_THREADS;
    clone->mc = memcached_clone(NULL, self->mc);
    Py_END_ALLOW_THREADS;
    clone->native_serialization = self->native_serialization;
    clone->native_deserialization = self->native_deserialization;
    clone->pickle_protocol = self->pickle_protocol;
    return (PyObject *)clone;
}
/* }}} */

static PyObject *_exc_by_rc(memcached_return rc) {
    PylibMC_McErr *err;
    for (err = PylibMCExc_mc_errs; err->name != NULL; err++)
        if (err->rc == rc)
            return err->exc;
    return (PyObject *)PylibMCExc_Error;
}

static char *_get_lead(memcached_st *mc, char *buf, int n, const char *what,
        memcached_return error, const char *key, Py_ssize_t len) {
    int sz = snprintf(buf, n, "error %d from %.32s", error, what);

    if (key != NULL && len) {
        sz += snprintf(buf+sz, n-sz, "(%.32s)", key);
    }

    return buf;
}

static void _set_error(memcached_st *mc, memcached_return error, char *lead) {
    if (error == MEMCACHED_ERRNO) {
        PyErr_Format(PylibMCExc_Error, "%s: %s",
                     lead, strerror(errno));
    } else if (error == MEMCACHED_SUCCESS) {
        PyErr_Format(PyExc_RuntimeError, "error == MEMCACHED_SUCCESS");
#if LIBMEMCACHED_VERSION_HEX >= 0x01000002
    } else if (error == MEMCACHED_E2BIG) {
        PyErr_SetNone(_exc_by_rc(error));
#endif
    } else {
        PyObject *exc = _exc_by_rc(error);
#if LIBMEMCACHED_VERSION_HEX >= 0x00049000
        if (memcached_last_error(mc) != MEMCACHED_SUCCESS) {
            PyErr_Format(exc, "%s: %.200s", lead, memcached_last_error_message(mc));
        } else {
            PyErr_SetString(exc, lead);
        }
#else
        PyErr_Format(exc, "%s: %.200s", lead, memcached_strerror(mc, error));
#endif
    }
}

static PyObject *PylibMC_ErrFromMemcachedWithKey(PylibMC_Client *self,
        const char *what, memcached_return error, const char *key, Py_ssize_t len) {
    char lead[128];

    _get_lead(self->mc, lead, sizeof(lead), what, error, key, len);
    _set_error(self->mc, error, lead);

    return NULL;
}

static PyObject *PylibMC_ErrFromMemcached(PylibMC_Client *self,
        const char *what, memcached_return error) {
    char lead[128];

    _get_lead(self->mc, lead, sizeof(lead), what, error, NULL, 0);
    _set_error(self->mc, error, lead);

    return NULL;
}

/* {{{ Pickling */
static PyObject *_PylibMC_GetPickles(const char *attname) {
    PyObject *pickle, *pickle_attr;

    pickle_attr = NULL;
    /* Import cPickle or pickle. */
    pickle = PyImport_ImportModule("cPickle");
    if (pickle == NULL) {
        PyErr_Clear();
        pickle = PyImport_ImportModule("pickle");
    }

    /* Find attribute and return it. */
    if (pickle != NULL) {
        pickle_attr = PyObject_GetAttrString(pickle, attname);
        Py_DECREF(pickle);
    }

    return pickle_attr;
}

static PyObject *_PylibMC_Unpickle(PylibMC_Client *self, const char *buff, Py_ssize_t size) {
        return PyObject_CallFunction(_PylibMC_pickle_loads, "y#", buff, size);
}

static PyObject *_PylibMC_Unpickle_Bytes(PylibMC_Client *self, PyObject *val) {
    return PyObject_CallFunctionObjArgs(_PylibMC_pickle_loads, val, NULL);
}

static PyObject *_PylibMC_Pickle(PylibMC_Client *self, PyObject *val) {
    return PyObject_CallFunction(_PylibMC_pickle_dumps, "Oi", val, self->pickle_protocol);
}
/* }}} */

/**
 * Normalize a key. Takes in a PyObject **.
 *
 * Returns a status code; on success (code != 0), *key will contain a new
 * reference to a normalized key (possibly the original object itself).
 * On error (code == 0), no references are created.
 */
static int _key_normalized_obj(PyObject **key) {
    int rc;
    char *key_str;
    Py_ssize_t key_sz;
    PyObject *orig_key = *key;
    PyObject *retval = orig_key;
    PyObject *encoded_key = NULL;

    if (*key == NULL) {
        PyErr_SetString(PyExc_ValueError, "key must be given");
        return 0;
    }

    /* The key object may be borrowed; hold a ref to it for now. */
    Py_INCREF(orig_key);

    if (PyUnicode_Check(retval)) {
        encoded_key = PyUnicode_AsUTF8String(retval);
        retval = encoded_key;
        if (retval == NULL) {
            rc = 0;
            goto END;
        }
    }

    if (!PyBytes_Check(retval)) {
        PyErr_SetString(PyExc_TypeError, "key must be bytes");
        rc = 0;
        retval = NULL;
        goto END;
    }

    key_str = PyBytes_AS_STRING(retval);
    key_sz = PyBytes_GET_SIZE(retval);
    rc = _key_normalized_str(&key_str, &key_sz);
    if (rc == 2) {
        retval = PyBytes_FromStringAndSize(key_str, key_sz);
        if (retval != NULL) {
            rc = 1;
        } else {
            rc = 0;
        }
    }

END:
    if (retval != orig_key) {
        /* If retval is new, release the temporary reference on the original. */
        Py_DECREF(orig_key);
    }
    if (retval != encoded_key) {
        /* Same deal for the UTF-8 encoded key, if we made one. */
        Py_XDECREF(encoded_key);
    }
    if (retval != NULL) {
        *key = retval;
    }
    return rc;
}

/**
 * Normalize memcached key.
 *
 * Returns 0 if invalid, 1 if already normalized, and 2 if mutated.
 */
static int _key_normalized_str(char **str, Py_ssize_t *size) {
    /* libmemcached pads max_key_size with one byte for null termination */
    if (*size >= MEMCACHED_MAX_KEY) {
        PyErr_Format(PyExc_ValueError, "key length %zd too long, max is %d",
                                       *size, MEMCACHED_MAX_KEY - 1);
        return 0;
    }

    if (*str == NULL) {
        return 0;
    }

    return 1;
}

static int _init_sasl(void) {
#if LIBMEMCACHED_WITH_SASL_SUPPORT
    int rc;

    /* sasl_client_init needs to be called once before using SASL, and
     * sasl_done after all SASL usage is done (so basically, once per process
     * lifetime). */
    rc = sasl_client_init(NULL);
    if (rc == SASL_NOMEM) {
        PyErr_NoMemory();
    } else if (rc == SASL_BADVERS) {
        PyErr_Format(PyExc_RuntimeError, "SASL: Mechanism version mismatch");
    } else if (rc == SASL_BADPARAM) {
        PyErr_Format(PyExc_RuntimeError, "SASL: Error in config file");
    } else if (rc == SASL_NOMECH) {
        PyErr_Format(PyExc_RuntimeError, "SASL: No mechanisms available");
    } else if (rc != SASL_OK) {
        PyErr_Format(PyExc_RuntimeError, "SASL: Unknown error (rc=%d)", rc);
    }

    if (rc != SASL_OK) {
        return false;
    }

    /* Terrible, terrible hack. Need to call sasl_done, but the Python/C API
     * doesn't provide a hook for when the module is unloaded, so register an
     * atexit handler. This is particularly problematic because
     * "At most 32 cleanup functions can be registered". */
    if (Py_AtExit(sasl_done)) {
        PyErr_Format(PyExc_RuntimeError, "Failed to register atexit handler");
        return false;
    }
#endif

    return true;
}

static int _check_libmemcached_version(void) {
    uint8_t maj, min;
    char *ver, *dot, *tmp;

    ver = dot = strdup(LIBMEMCACHED_VERSION_STRING);
    while ((tmp = strrchr(ver, '.')) != NULL) {
        dot = tmp;
        *dot = 0;
    }

    maj = atoi(ver);
    min = atoi(dot + 1);

    if (maj == 0 && min < 32) {
        PyErr_Format(PyExc_RuntimeError,
            "pylibmc requires >= libmemcached 0.32, was compiled with %s",
            LIBMEMCACHED_VERSION_STRING);
        return false;
    } else {
        return true;
    }
}

static void _make_excs(PyObject *module) {
    PyObject *exc_objs;
    PylibMC_McErr *err;

    PylibMCExc_Error = PyErr_NewException(
            "pylibmc.Error", NULL, NULL);

    PylibMCExc_CacheMiss = PyErr_NewException(
            "pylibmc.CacheMiss", PylibMCExc_Error, NULL);

    exc_objs = PyList_New(0);
    PyList_Append(exc_objs,
                  Py_BuildValue("sO", "Error", (PyObject *)PylibMCExc_Error));
    PyList_Append(exc_objs,
                  Py_BuildValue("sO", "CacheMiss", (PyObject *)PylibMCExc_CacheMiss));

    for (err = PylibMCExc_mc_errs; err->name != NULL; err++) {
        char excnam[64];
        snprintf(excnam, 64, "pylibmc.%s", err->name);
        err->exc = PyErr_NewException(excnam, PylibMCExc_Error, NULL);
        PyObject_SetAttrString(err->exc, "retcode", PyLong_FromLong(err->rc));
        PyModule_AddObject(module, err->name, (PyObject *)err->exc);
        PyList_Append(exc_objs,
                      Py_BuildValue("sO", err->name, (PyObject *)err->exc));
    }

    PyModule_AddObject(module, "Error",
                       (PyObject *)PylibMCExc_Error);

    PyModule_AddObject(module, "CacheMiss",
                       (PyObject *)PylibMCExc_CacheMiss);

    /* Backwards compatible name for <= pylibmc 1.2.3
     *
     * Need to increase the refcount since we're adding another
     * reference to the exception class. Otherwise, debug builds
     * of Python dump core with
     * Modules/gcmodule.c:379: visit_decref: Assertion `((gc)->gc.gc_refs >> (1)) != 0' failed.
     */
    Py_INCREF(PylibMCExc_Error);
    PyModule_AddObject(module, "MemcachedError",
                       (PyObject *)PylibMCExc_Error);

    PyModule_AddObject(module, "exceptions", exc_objs);
}

static void _make_behavior_consts(PyObject *mod) {
    PyObject *names;
    PylibMC_Behavior *b;
    char name[128];

    /* Add hasher and distribution constants. */
    for (b = PylibMC_hashers; b->name != NULL; b++) {
        sprintf(name, "hash_%s", b->name);
        PyModule_AddIntConstant(mod, name, b->flag);
    }

    for (b = PylibMC_distributions; b->name != NULL; b++) {
        sprintf(name, "distribution_%s", b->name);
        PyModule_AddIntConstant(mod, name, b->flag);
    }

    names = PyList_New(0);

    for (b = PylibMC_callbacks; b->name != NULL; b++) {
        sprintf(name, "callback_%s", b->name);
        PyModule_AddIntConstant(mod, name, b->flag);
        PyList_Append(names, PyUnicode_FromString(b->name));
    }

    PyModule_AddObject(mod, "all_callbacks", names);

    names = PyList_New(0);

    for (b = PylibMC_behaviors; b->name != NULL; b++) {
        PyList_Append(names, PyUnicode_FromString(b->name));
    }

    PyModule_AddObject(mod, "all_behaviors", names);
}

static PyMethodDef PylibMC_functions[] = {
    {NULL, NULL, 0, NULL}
};

MOD_INIT(_pylibmc) {
    PyObject *module;

    MOD_DEF(module, "_pylibmc", "Hand-made wrapper for libmemcached.\n\
\n\
You should really use the Python wrapper around this library.\n\
\n\
    c = _pylibmc.client([(_pylibmc.server_type_tcp, 'localhost', 11211)])\n\
\n\
Three-tuples of (type, host, port) are used. If type is `server_type_unix`,\n\
no port should be given. libmemcached can parse strings as well::\n\
\n\
   c = _pylibmc.client('localhost')\n\
\n\
See libmemcached's memcached_servers_parse for more info on that. I'm told \n\
you can use UNIX domain sockets by specifying paths, and multiple servers \n\
by using comma-separation. Good luck with that.\n", PylibMC_functions);

    if (!_check_libmemcached_version())
        return MOD_ERROR_VAL;

    if (!_init_sasl())
        return MOD_ERROR_VAL;

    if (PyType_Ready(&PylibMC_ClientType) < 0) {
        return MOD_ERROR_VAL;
    }

    if (module == NULL) {
        return MOD_ERROR_VAL;
    }

    _make_excs(module);

    if (!(_PylibMC_pickle_loads = _PylibMC_GetPickles("loads"))) {
        return MOD_ERROR_VAL;
    }

    if (!(_PylibMC_pickle_dumps = _PylibMC_GetPickles("dumps"))) {
        return MOD_ERROR_VAL;
    }

    PyModule_AddStringConstant(module, "__version__", PYLIBMC_VERSION);
    PyModule_ADD_REF(module, "client", (PyObject *)&PylibMC_ClientType);
    PyModule_AddStringConstant(module,
            "libmemcached_version", LIBMEMCACHED_VERSION_STRING);
    PyModule_AddIntConstant(module,
            "libmemcached_version_hex", LIBMEMCACHED_VERSION_HEX);

#if LIBMEMCACHED_WITH_SASL_SUPPORT
    PyModule_ADD_REF(module, "support_sasl", Py_True);
#else
    PyModule_ADD_REF(module, "support_sasl", Py_False);
#endif

#ifdef USE_ZLIB
    PyModule_ADD_REF(module, "support_compression", Py_True);
#else
    PyModule_ADD_REF(module, "support_compression", Py_False);
#endif

    PyModule_AddIntConstant(module, "server_type_tcp", PYLIBMC_SERVER_TCP);
    PyModule_AddIntConstant(module, "server_type_udp", PYLIBMC_SERVER_UDP);
    PyModule_AddIntConstant(module, "server_type_unix", PYLIBMC_SERVER_UNIX);

    _make_behavior_consts(module);
    return MOD_SUCCESS_VAL(module);
}
