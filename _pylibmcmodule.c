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


/* {{{ _pylibmc.client implementation */
/* {{{ Type methods */
static PylibMC_Client *PylibMC_ClientType_new(PyTypeObject *type,
        PyObject *args, PyObject *kwds) {
    PylibMC_Client *self;

    self = (PylibMC_Client *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->mc = memcached_create(NULL);
    } else {
        args = kwds = NULL;
    }

    return self;
}

static void PylibMC_ClientType_dealloc(PylibMC_Client *self) {
    memcached_free(self->mc);
}
/* }}} */

static int PylibMC_Client_init(PylibMC_Client *self, PyObject *args,
        PyObject *kwds) {
    PyObject *srv_list, *srv_list_it;

    if (!PyArg_ParseTuple(args, "O", &srv_list)) {
        return -1;
    } else {
        kwds = NULL;
    }

    if ((srv_list_it = PyObject_GetIter(srv_list)) != NULL) {
        PyObject *c_srv;

        while ((c_srv = PyIter_Next(srv_list_it)) != NULL
                && !PyErr_Occurred()) {
            unsigned char stype;
            char *hostname;
            unsigned short int port;

            port = 0;
            if (PyString_Check(c_srv)) {
                memcached_server_st *list;

                list = memcached_servers_parse(PyString_AS_STRING(c_srv));
                if (list != NULL) {
                    memcached_return rc;

                    rc = memcached_server_push(self->mc, list);
                    if (rc != MEMCACHED_SUCCESS) {
                        PylibMC_ErrFromMemcached(self,
                                "memcached_server_push", rc);
                    }
                    free(list);
                } else {
                    PyErr_SetString(PylibMCExc_MemcachedError,
                            "memcached_servers_parse returned NULL");
                }
            } else if (PyArg_ParseTuple(c_srv, "Bs|H",
                        &stype, &hostname, &port)) {
                switch (stype) {
                    case PYLIBMC_SERVER_TCP:
                        memcached_server_add(self->mc, hostname, port);
                        break;
                    case PYLIBMC_SERVER_UDP:
                        memcached_server_add_udp(self->mc, hostname, port);
                        break;
                    case PYLIBMC_SERVER_UNIX:
                        if (port) {
                            PyErr_SetString(PyExc_ValueError,
                                    "can't set port on unix sockets");
                        } else {
                            memcached_server_add_unix_socket(
                                    self->mc, hostname);
                        }
                        break;
                    default:
                        PyErr_Format(PyExc_ValueError,
                                "bad server type: %u", stype);
                }
            }
            Py_DECREF(c_srv);
        }
        Py_DECREF(srv_list_it);
    }

    return PyErr_Occurred() ? -1 : 0;
}

static PyObject *_PylibMC_parse_memcached_value(char *value, size_t size,
        uint32_t flags) {
    PyObject *retval, *tmp;

    retval = NULL;
    switch (flags) {
        case PYLIBMC_FLAG_PICKLE:
            retval = _PylibMC_Unpickle(value, size);
            break;
        case PYLIBMC_FLAG_INTEGER:
        case PYLIBMC_FLAG_LONG:
            retval = PyInt_FromString(value, NULL, 10);
            break;
        case PYLIBMC_FLAG_BOOL:
            if ((tmp = PyInt_FromString(value, NULL, 10)) == NULL) {
                return NULL;
            }
            retval = PyBool_FromLong(PyInt_AS_LONG(tmp));
            Py_DECREF(tmp);
            break;
        case PYLIBMC_FLAG_NONE:
            retval = PyString_FromStringAndSize(value, (Py_ssize_t)size);
            break;
        default:
            PyErr_Format(PylibMCExc_MemcachedError,
                    "unknown memcached key flags %u", flags);
    }

    return retval;
}

static PyObject *PylibMC_Client_get(PylibMC_Client *self, PyObject *arg) {
    char *mc_val;
    size_t val_size;
    uint32_t flags;
    memcached_return error;

    if (!_PylibMC_CheckKey(arg)) {
        return NULL;
    } else if (!PySequence_Length(arg) ) {
        /* Others do this, so... */
        Py_RETURN_NONE;
    }

    mc_val = memcached_get(self->mc,
            PyString_AS_STRING(arg), PyString_GET_SIZE(arg),
            &val_size, &flags, &error);
    if (mc_val != NULL) {
        PyObject *r = _PylibMC_parse_memcached_value(mc_val, val_size, flags);
        free(mc_val);
        return r;
    }

    if (error == MEMCACHED_NOTFOUND) {
        /* Since python-memcache returns None when the key doesn't exist,
         * so shall we. */
        Py_RETURN_NONE;
    }

    return PylibMC_ErrFromMemcached(self, "memcached_get", error);
}

/* {{{ Set commands (set, replace, add, prepend, append) */
static PyObject *_PylibMC_RunSetCommand(PylibMC_Client *self,
        _PylibMC_SetCommand f, char *fname, PyObject *args,
        PyObject *kwds) {
    char *key;
    Py_ssize_t key_sz;
    memcached_return rc;
    PyObject *val, *tmp;
    PyObject *retval = NULL;
    PyObject *store_val = NULL;
    unsigned int time = 0;
    uint32_t store_flags = 0;

    static char *kws[] = { "key", "val", "time", NULL };

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "s#O|I", kws,
                &key, &key_sz, &val, &time)) {
        return NULL;
    }
    if (!_PylibMC_CheckKeyStringAndSize(key, key_sz)) {
        return NULL;
    }

    /* Adapt val to a str. */
    if (PyString_Check(val)) {
        store_val = val;
        Py_INCREF(store_val);
    } else if (PyBool_Check(val)) {
        store_flags |= PYLIBMC_FLAG_BOOL;
        tmp = PyNumber_Int(val);
        store_val = PyObject_Str(tmp);
        Py_DECREF(tmp);
    } else if (PyInt_Check(val)) {
        store_flags |= PYLIBMC_FLAG_INTEGER;
        tmp = PyNumber_Int(val);
        store_val = PyObject_Str(tmp);
        Py_DECREF(tmp);
    } else if (PyLong_Check(val)) {
        store_flags |= PYLIBMC_FLAG_LONG;
        tmp = PyNumber_Long(val);
        store_val = PyObject_Str(tmp);
        Py_DECREF(tmp);
    } else {
        Py_INCREF(val);
        store_flags |= PYLIBMC_FLAG_PICKLE;
        store_val = _PylibMC_Pickle(val);
        Py_DECREF(val);
    }
    if (store_val == NULL) {
        return NULL;
    }

    rc = f(self->mc, key, key_sz,
           PyString_AS_STRING(store_val), PyString_GET_SIZE(store_val),
           time, store_flags);
    Py_DECREF(store_val);

    switch (rc) {
        case MEMCACHED_SUCCESS:
            retval = Py_True;
            break;
        case MEMCACHED_FAILURE:
        case MEMCACHED_NO_KEY_PROVIDED:
        case MEMCACHED_BAD_KEY_PROVIDED:
        case MEMCACHED_MEMORY_ALLOCATION_FAILURE:
        case MEMCACHED_NOTSTORED:
            retval = Py_False;
            break;
        default:
            PylibMC_ErrFromMemcached(self, fname, rc);
    }

    Py_XINCREF(retval);
    return retval;
}

/* These all just call _PylibMC_RunSetCommand with the appropriate arguments. 
 * In other words: bulk. */
static PyObject *PylibMC_Client_set(PylibMC_Client *self, PyObject *args,
        PyObject *kwds) {
    return _PylibMC_RunSetCommand(
            self, memcached_set, "memcached_set", args, kwds);
}

static PyObject *PylibMC_Client_replace(PylibMC_Client *self, PyObject *args,
        PyObject *kwds) {
    return _PylibMC_RunSetCommand(
            self, memcached_replace, "memcached_replace", args, kwds);
}

static PyObject *PylibMC_Client_add(PylibMC_Client *self, PyObject *args,
        PyObject *kwds) {
    return _PylibMC_RunSetCommand(
            self, memcached_add, "memcached_add", args, kwds);
}

static PyObject *PylibMC_Client_prepend(PylibMC_Client *self, PyObject *args,
        PyObject *kwds) {
    return _PylibMC_RunSetCommand(
            self, memcached_prepend, "memcached_prepend", args, kwds);
}

static PyObject *PylibMC_Client_append(PylibMC_Client *self, PyObject *args,
        PyObject *kwds) {
    return _PylibMC_RunSetCommand(
            self, memcached_append, "memcached_append", args, kwds);
}
/* }}} */

static PyObject *PylibMC_Client_delete(PylibMC_Client *self, PyObject *args) {
    PyObject *retval;
    char *key;
    Py_ssize_t key_sz;
    unsigned int time;
    memcached_return rc;

    retval = NULL;
    time = 0;
    if (PyArg_ParseTuple(args, "s#|I", &key, &key_sz, &time)
            && _PylibMC_CheckKeyStringAndSize(key, key_sz)) {
        switch (rc = memcached_delete(self->mc, key, key_sz, time)) {
            case MEMCACHED_SUCCESS:
                Py_RETURN_TRUE;
                break;
            case MEMCACHED_FAILURE:
            case MEMCACHED_NOTFOUND:
            case MEMCACHED_NO_KEY_PROVIDED:
            case MEMCACHED_BAD_KEY_PROVIDED:
                Py_RETURN_FALSE;
                break;
            default:
                return PylibMC_ErrFromMemcached(self, "memcached_delete", rc);
        }
    }

    return NULL;
}

/* {{{ Increment & decrement */
static PyObject *_PylibMC_IncDec(PylibMC_Client *self, uint8_t dir, 
        PyObject *args) {
    PyObject *retval;
    char *key;
    Py_ssize_t key_sz;
    unsigned int delta;
    uint64_t result;

    retval = NULL;
    delta = 1;
    if (PyArg_ParseTuple(args, "s#|I", &key, &key_sz, &delta)
            && _PylibMC_CheckKeyStringAndSize(key, key_sz)) {
        memcached_return (*incdec)(memcached_st *, const char *, size_t,
                unsigned int, uint64_t *);
        incdec = (dir == PYLIBMC_INC) ? memcached_increment
                                      : memcached_decrement;
        incdec(self->mc, key, key_sz, delta, &result);
        retval = PyLong_FromUnsignedLong((unsigned long)result);
    }

    return retval;
}

static PyObject *PylibMC_Client_incr(PylibMC_Client *self, PyObject *args) {
    return _PylibMC_IncDec(self, PYLIBMC_INC, args);
}

static PyObject *PylibMC_Client_decr(PylibMC_Client *self, PyObject *args) {
    return _PylibMC_IncDec(self, PYLIBMC_DEC, args);
}
/* }}} */

static PyObject *PylibMC_Client_get_multi(PylibMC_Client *self, PyObject *args,
        PyObject *kwds) {
    PyObject *key_seq, **key_objs, *retval = NULL;
    char **keys, *prefix = NULL;
    Py_ssize_t prefix_len = 0;
    Py_ssize_t i;
    PyObject *key_it, *ckey;
    size_t *key_lens;
    size_t nkeys;
    memcached_return rc;

    char curr_key[MEMCACHED_MAX_KEY];
    size_t curr_key_len, curr_val_len;
    uint32_t curr_flags;
    char *curr_val;

    static char *kws[] = { "keys", "key_prefix", NULL };

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|s#", kws,
            &key_seq, &prefix, &prefix_len)) {
        return NULL;
    }

    if ((nkeys = (size_t)PySequence_Length(key_seq)) == -1) {
        return NULL;
    }

    /* Populate keys and key_lens. */
    keys = PyMem_New(char *, nkeys);
    key_lens = PyMem_New(size_t, nkeys);
    key_objs = PyMem_New(PyObject *, nkeys);
    if (keys == NULL || key_lens == NULL || key_objs == NULL) {
        PyMem_Free(keys);
        PyMem_Free(key_lens);
        PyMem_Free(key_objs);
        return PyErr_NoMemory();
    }

    /* Clear potential previous exception, because we explicitly check for
     * exceptions as a loop predicate. */
    PyErr_Clear();

    /* Iterate through all keys and set lengths etc. */
    i = 0;
    key_it = PyObject_GetIter(key_seq);
    while (!PyErr_Occurred()
            && i < nkeys
            && (ckey = PyIter_Next(key_it)) != NULL) {
        PyObject *rkey;

        if (!_PylibMC_CheckKey(ckey)) {
            break;
        } else {
            key_lens[i] = (size_t)(PyString_GET_SIZE(ckey) + prefix_len);
            if (prefix != NULL) {
                rkey = PyString_FromFormat("%s%s",
                        prefix, PyString_AS_STRING(ckey));
                Py_DECREF(ckey);
            } else {
                rkey = ckey;
            }
            keys[i] = PyString_AS_STRING(rkey);
            key_objs[i++] = rkey;
        }
    }
    Py_XDECREF(key_it);

    if (i == 0) {
        /* No usable keys to fetch. */
        nkeys = 0;
        goto cleanup;
    } else if (PyErr_Occurred()) {
        nkeys--;
        goto cleanup;
    }

    /* TODO Make an iterator interface for getting each key separately.
     *
     * This would help large retrievals, as a single dictionary containing all
     * the data at once isn't needed. (Should probably look into if it's even
     * worth it.)
     */
    retval = PyDict_New();

    if ((rc = memcached_mget(self->mc, keys, key_lens, nkeys))
            != MEMCACHED_SUCCESS) {
        PylibMC_ErrFromMemcached(self, "memcached_mget", rc);
        goto cleanup;
    }

    while ((curr_val = memcached_fetch(
                    self->mc, curr_key, &curr_key_len, &curr_val_len,
                    &curr_flags, &rc)) != NULL
            && !PyErr_Occurred()) {
        if (curr_val == NULL && rc == MEMCACHED_END) {
            break;
        } else if (rc == MEMCACHED_BAD_KEY_PROVIDED
                || rc == MEMCACHED_NO_KEY_PROVIDED) {
            /* Do nothing at all. :-) */
        } else if (rc != MEMCACHED_SUCCESS) {
            PylibMC_ErrFromMemcached(self, "memcached_fetch", rc);
            memcached_quit(self->mc);
            goto cleanup;
        } else {
            PyObject *val;

            /* This is safe because libmemcached's max key length
             * includes space for a NUL-byte. */
            curr_key[curr_key_len] = 0;
            val = _PylibMC_parse_memcached_value(
                    curr_val, curr_val_len, curr_flags);
            if (val == NULL) {
                memcached_quit(self->mc);
                goto cleanup;
            }
            PyDict_SetItemString(retval, curr_key + prefix_len, val);
            Py_DECREF(val);
        }
        /* Although Python prohibits you from using the libc memory allocation
         * interface, we have to since libmemcached goes around doing
         * malloc()... */
        free(curr_val);
    }

    PyMem_Free(key_lens);
    PyMem_Free(keys);
    for (i = 0; i < nkeys; i++) {
        Py_DECREF(key_objs[i]);
    }
    PyMem_Free(key_objs);

    /* Not INCREFing because the only two outcomes are NULL and a new dict.
     * We're the owner of that dict already, so. */
    return retval;
cleanup:
    Py_XDECREF(retval);
    PyMem_Free(key_lens);
    PyMem_Free(keys);
    for (i = 0; i < nkeys; i++)
        Py_DECREF(key_objs[i]);
    PyMem_Free(key_objs);
    return NULL;
}

/**
 * Run func over every item in value, building arguments of:
 *     *(item + extra_args)
 */
static PyObject *_PylibMC_DoMulti(PyObject *values, PyObject *func,
        PyObject *prefix, PyObject *extra_args) {
    PyObject *retval = PyList_New(0);
    PyObject *iter = NULL;
    PyObject *item = NULL;
    int is_mapping = PyMapping_Check(values);

    if (retval == NULL)
        goto error;

    if ((iter = PyObject_GetIter(values)) == NULL)
        goto error;

    while ((item = PyIter_Next(iter)) != NULL) {
        PyObject *args_f = NULL;
        PyObject *args = NULL;
        PyObject *key = NULL;
        PyObject *ro = NULL;

        /* Calculate key. */
        if (prefix == NULL || prefix == Py_None) {
            /* We now have two owned references to item. */
            key = item;
            Py_INCREF(key);
        } else {
            key = PySequence_Concat(prefix, item);
        }
        if (key == NULL || !_PylibMC_CheckKey(key))
            goto iter_error;

        /* Calculate args. */
        if (is_mapping) {
            PyObject *value;
            char *key_str = PyString_AS_STRING(item);

            if ((value = PyMapping_GetItemString(values, key_str)) == NULL)
                goto iter_error;

            args = PyTuple_Pack(2, key, value);
        } else {
            args = PyTuple_Pack(1, key);
        }
        if (args == NULL)
            goto iter_error;

        /* Calculate full argument tuple. */
        if (extra_args == NULL) {
            Py_INCREF(args);
            args_f = args;
        } else {
            if ((args_f = PySequence_Concat(args, extra_args)) == NULL)
                goto iter_error;
        }

        /* Call stuff. */
        ro = PyObject_CallObject(func, args_f);
        /* This is actually safe even if True got deleted because we're
         * only comparing addresses. */
        Py_XDECREF(ro);
        if (ro == NULL) {
            goto iter_error;
        } else if (ro != Py_True) {
            if (PyList_Append(retval, item) != 0)
                goto iter_error;
        }
        Py_DECREF(args_f);
        Py_DECREF(args);
        Py_DECREF(key);
        Py_DECREF(item);
        continue;
iter_error:
        Py_XDECREF(args_f);
        Py_XDECREF(args);
        Py_XDECREF(key);
        Py_DECREF(item);
        goto error;
    }
    Py_DECREF(iter);

    return retval;
error:
    Py_XDECREF(retval);
    Py_XDECREF(iter);
    return NULL;
}

static PyObject *PylibMC_Client_set_multi(PylibMC_Client *self, PyObject *args,
        PyObject *kwds) {
    PyObject *prefix = NULL;
    PyObject *time = NULL;
    PyObject *set = NULL;
    PyObject *map;
    PyObject *call_args;
    PyObject *retval;

    static char *kws[] = { "mapping", "time", "key_prefix", NULL };

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|O!S", kws,
                &map, &PyInt_Type, &time, &prefix))
        return NULL;

    if ((set = PyObject_GetAttrString((PyObject *)self, "set")) == NULL)
        return NULL;

    if (time == NULL) {
        retval = _PylibMC_DoMulti(map, set, prefix, NULL);
    } else {
        if ((call_args = PyTuple_Pack(1, time)) == NULL)
            goto error;
        retval = _PylibMC_DoMulti(map, set, prefix, call_args);
        Py_DECREF(call_args);
    }
    Py_DECREF(set);

    return retval;
error:
    Py_XDECREF(set);
    return NULL;
}

static PyObject *PylibMC_Client_delete_multi(PylibMC_Client *self,
        PyObject *args, PyObject *kwds) {
    PyObject *prefix = NULL;
    PyObject *time = NULL;
    PyObject *delete;
    PyObject *keys;
    PyObject *call_args;
    PyObject *retval;

    static char *kws[] = { "keys", "time", "key_prefix", NULL };

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|O!S", kws,
                &keys, &PyInt_Type, &time, &prefix))
        return NULL;

    if ((delete = PyObject_GetAttrString((PyObject *)self, "delete")) == NULL)
        return NULL;

    if (time == NULL) {
        retval = _PylibMC_DoMulti(keys, delete, prefix, NULL);
    } else {
        if ((call_args = PyTuple_Pack(1, time)) == NULL)
            goto error;
        retval = _PylibMC_DoMulti(keys, delete, prefix, call_args);
        Py_DECREF(call_args);
    }
    Py_DECREF(delete);

    return retval;
error:
    Py_XDECREF(delete);
    return NULL;
}

static PyObject *PylibMC_Client_get_behaviors(PylibMC_Client *self) {
    PyObject *retval = PyDict_New();
    PylibMC_Behavior *b;

    for (b = PylibMC_behaviors; b->name != NULL; b++) {
        uint64_t bval;
        PyObject *x;

        bval = memcached_behavior_get(self->mc, b->flag);
        x = PyInt_FromLong((long)bval);
        if (x == NULL || PyDict_SetItemString(retval, b->name, x) == -1) {
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

    for (b = PylibMC_behaviors; b->name != NULL; b++) {
        PyObject *v;
        memcached_return r;

        if (!PyMapping_HasKeyString(behaviors, b->name)) {
            continue;
        }

        v = PyMapping_GetItemString(behaviors, b->name);

        if (v == NULL) {
            goto error;
        } else if (!PyInt_Check(v)) {
            PyErr_Format(PyExc_TypeError, "behavior %s must be int",
                         b->name);
            goto error;
        }

        r = memcached_behavior_set(self->mc, b->flag, (uint64_t)PyInt_AS_LONG(v));
        Py_DECREF(v);
        if (r != MEMCACHED_SUCCESS) {
            PyErr_Format(PylibMCExc_MemcachedError,
                         "memcached_behavior_set returned %d", r);
            goto error;
        }
    }

    Py_RETURN_NONE;
error:
    return NULL;
}

static PyObject *PylibMC_Client_flush_all(PylibMC_Client *self,
        PyObject *args, PyObject *kwds) {
    memcached_return rc;
    time_t expire = 0;
    PyObject *time = NULL;

    static char *kws[] = { "time", NULL };

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "|O!", kws,
                                     &PyInt_Type, &time))
        return NULL;

    if (time != NULL)
        expire = PyInt_AS_LONG(time);

    expire = (expire > 0) ? expire : 0;

    rc = memcached_flush(self->mc, expire);
    if (rc != MEMCACHED_SUCCESS)
        return PylibMC_ErrFromMemcached(self, "delete_multi", rc);

    Py_RETURN_TRUE;
}

static PyObject *PylibMC_Client_disconnect_all(PylibMC_Client *self) {
    memcached_quit(self->mc);
    Py_RETURN_NONE;
}
/* }}} */

static PyObject *PylibMC_ErrFromMemcached(PylibMC_Client *self, const char *what,
        memcached_return error) {
    if (error == MEMCACHED_ERRNO) {
        PyErr_Format(PylibMCExc_MemcachedError,
                "system error %d from %s: %s", errno, what, strerror(errno));
    /* The key exists, but it has no value */
    } else if (error == MEMCACHED_SUCCESS) {
        PyErr_Format(PyExc_RuntimeError, "error == 0? %s:%d",
                     __FILE__, __LINE__);
    } else { 
        PyErr_Format(PylibMCExc_MemcachedError, "error %d from %s: %s",
                error, what, memcached_strerror(self->mc, error));
    }
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

static PyObject *_PylibMC_Unpickle(const char *buff, size_t size) {
    PyObject *pickle_load;
    PyObject *retval = NULL;
    
    retval = NULL;
    pickle_load = _PylibMC_GetPickles("loads");
    if (pickle_load != NULL) {
        retval = PyObject_CallFunction(pickle_load, "s#", buff, size);
        Py_DECREF(pickle_load);
    }

    return retval;
}

static PyObject *_PylibMC_Pickle(PyObject *val) {
    PyObject *pickle_dump;
    PyObject *retval = NULL;

    retval = NULL;
    pickle_dump = _PylibMC_GetPickles("dumps");
    if (pickle_dump != NULL) {
        retval = PyObject_CallFunction(pickle_dump, "Oi", val, -1);
        Py_DECREF(pickle_dump);
    }

    return retval;
}
/* }}} */

static int _PylibMC_CheckKey(PyObject *key) {
    if (key == NULL) {
        PyErr_SetString(PyExc_ValueError, "key must be given");
        return 0;
    } else if (!PyString_Check(key)) {
        PyErr_SetString(PyExc_TypeError, "key must be an instance of str");
        return 0;
    }

    return _PylibMC_CheckKeyStringAndSize(
            PyString_AS_STRING(key), PyString_GET_SIZE(key));
}

static int _PylibMC_CheckKeyStringAndSize(char *key, Py_ssize_t size) {
    if (size > MEMCACHED_MAX_KEY) {
        PyErr_Format(PyExc_ValueError, "key too long, max is %d",
                MEMCACHED_MAX_KEY);
        return 0;
    }
    /* TODO Check key contents here. */

    return key != NULL;
}

static PyMethodDef PylibMC_functions[] = {
    {NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC init_pylibmc(void) {
    PyObject *module;
    PylibMC_Behavior *b;
    char name[128];

    if (PyType_Ready(&PylibMC_ClientType) < 0) {
        return;
    }

    module = Py_InitModule3("_pylibmc", PylibMC_functions,
            "Hand-made wrapper for libmemcached.\n\
\n\
You ought to look at python-memcached's documentation for now, seeing\n\
as this module is more or less a drop-in replacement, the difference\n\
being in how you connect. Therefore that's documented here::\n\
\n\
    c = _pylibmc.client([(_pylibmc.server_type_tcp, 'localhost', 11211)])\n\
\n\
As you see, a list of three-tuples of (type, host, port) is used. If \n\
type is `server_type_unix`, no port should be given. A simpler form \n\
can be used as well::\n\
\n\
   c = _pylibmc.client('localhost')\n\
\n\
See libmemcached's memcached_servers_parse for more info on that. I'm told \n\
you can use UNIX domain sockets by specifying paths, and multiple servers \n\
by using comma-separation. Good luck with that.\n\
\n\
Oh, and: plankton.\n");
    if (module == NULL) {
        return;
    }

    PylibMCExc_MemcachedError = PyErr_NewException(
            "_pylibmc.MemcachedError", NULL, NULL);

    PyModule_AddStringConstant(module, "__version__", PYLIBMC_VERSION);

    Py_INCREF(&PylibMC_ClientType);
    PyModule_AddObject(module, "client", (PyObject *)&PylibMC_ClientType);

    PyModule_AddIntConstant(module, "server_type_tcp", PYLIBMC_SERVER_TCP);
    PyModule_AddIntConstant(module, "server_type_udp", PYLIBMC_SERVER_UDP);
    PyModule_AddIntConstant(module, "server_type_unix", PYLIBMC_SERVER_UNIX);

    /* Add hasher and distribution constants. */
    for (b = PylibMC_hashers; b->name != NULL; b++) {
        sprintf(name, "hash_%s", b->name);
        PyModule_AddIntConstant(module, name, b->flag);
    }
    for (b = PylibMC_distributions; b->name != NULL; b++) {
        sprintf(name, "distribution_%s", b->name);
        PyModule_AddIntConstant(module, name, b->flag);
    }

    PyModule_AddStringConstant(module,
            "libmemcached_version", LIBMEMCACHED_VERSION_STRING);
}
