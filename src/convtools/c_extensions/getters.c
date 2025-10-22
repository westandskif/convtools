#define PY_SSIZE_T_CLEAN /* Make "s#" use Py_ssize_t rather than int. */
#include <Python.h>

static PyObject *get_item_deep_default_simple(PyObject *self, PyObject *args[],
                                              Py_ssize_t nargs) {
    if (nargs < 3) {
        PyErr_SetString(PyExc_ValueError, "at least 3 arguments are expected");
        return NULL;
    }

    Py_ssize_t i;
    Py_ssize_t default_index = nargs - 1;

    PyObject *a;
    PyObject *item = args[0];
    Py_INCREF(item);

    for (i = 1; i < default_index; i++) {
        if (item == Py_None) {
            Py_DECREF(item);
            goto return_default;
        }
        a = PyObject_GetItem(item, args[i]);
        Py_DECREF(item);
        if (a == NULL) {
            if (PyErr_ExceptionMatches(PyExc_KeyError) ||
                PyErr_ExceptionMatches(PyExc_IndexError) ||
                PyErr_ExceptionMatches(PyExc_TypeError)) {
                PyErr_Clear();
                goto return_default;
            } else {
                return NULL;
            }
        }
        item = a;
    }

    return item;

return_default:
    Py_INCREF(args[default_index]);
    return args[default_index];
}

static PyObject *get_item_deep_default_callable(PyObject *self,
                                                PyObject *args[],
                                                Py_ssize_t nargs) {
    if (nargs < 3) {
        PyErr_SetString(PyExc_ValueError, "at least 3 arguments are expected");
        return NULL;
    }

    Py_ssize_t i;
    Py_ssize_t default_index = nargs - 1;

    PyObject *a;
    PyObject *item = args[0];
    Py_INCREF(item);

    for (i = 1; i < default_index; i++) {
        if (item == Py_None) {
            Py_DECREF(item);
            goto return_default;
        }
        a = PyObject_GetItem(item, args[i]);
        Py_DECREF(item);
        if (a == NULL) {
            if (PyErr_ExceptionMatches(PyExc_KeyError) ||
                PyErr_ExceptionMatches(PyExc_IndexError) ||
                PyErr_ExceptionMatches(PyExc_TypeError)) {
                PyErr_Clear();
                goto return_default;
            } else {
                return NULL;
            }
        }
        item = a;
    }

    return item;

return_default:
    a = PyObject_CallNoArgs(args[default_index]);
    if (a == NULL) {
        return NULL;
    }
    return a;
}

static PyObject *get_attr_deep_default_simple(PyObject *self, PyObject *args[],
                                              Py_ssize_t nargs) {
    if (nargs < 3) {
        PyErr_SetString(PyExc_ValueError, "at least 3 arguments are expected");
        return NULL;
    }

    Py_ssize_t i;
    Py_ssize_t default_index = nargs - 1;

    PyObject *a;
    PyObject *item = args[0];
    Py_INCREF(item);

    for (i = 1; i < default_index; i++) {
        if (item == Py_None) {
            Py_DECREF(item);
            goto return_default;
        }

        a = PyObject_GetAttr(item, args[i]);
        Py_DECREF(item);
        if (a == NULL) {
            if (PyErr_ExceptionMatches(PyExc_AttributeError)) {
                PyErr_Clear();
                goto return_default;
            } else {
                return NULL;
            }
        }
        item = a;
    }

    return item;

return_default:
    Py_INCREF(args[default_index]);
    return args[default_index];
}

static PyObject *get_attr_deep_default_callable(PyObject *self,
                                                PyObject *args[],
                                                Py_ssize_t nargs) {
    if (nargs < 3) {
        PyErr_SetString(PyExc_ValueError, "at least 3 arguments are expected");
        return NULL;
    }
    Py_ssize_t i;
    Py_ssize_t default_index = nargs - 1;

    PyObject *a;
    PyObject *item = args[0];
    Py_INCREF(item);

    for (i = 1; i < default_index; i++) {
        if (item == Py_None) {
            Py_DECREF(item);
            goto return_default;
        }

        a = PyObject_GetAttr(item, args[i]);
        Py_DECREF(item);
        if (a == NULL) {
            if (PyErr_ExceptionMatches(PyExc_AttributeError)) {
                PyErr_Clear();
                goto return_default;
            } else {
                return NULL;
            }
        }
        item = a;
    }

    return item;

return_default:
    a = PyObject_CallNoArgs(args[default_index]);
    if (a == NULL) {
        return NULL;
    }
    return a;
}

static PyMethodDef cext_methods[] = {
    {"get_item_deep_default_simple", (PyCFunction)get_item_deep_default_simple,
     METH_FASTCALL, "c-level fail-safe __getitem__ with default"},
    {"get_item_deep_default_callable",
     (PyCFunction)get_item_deep_default_callable, METH_FASTCALL,
     "c-level fail-safe __getattr__ with default callable"},
    {"get_attr_deep_default_simple", (PyCFunction)get_attr_deep_default_simple,
     METH_FASTCALL, "tst method doc."},
    {"get_attr_deep_default_callable",
     (PyCFunction)get_attr_deep_default_callable, METH_FASTCALL,
     "c-level fail-safe __getattr__ with default callable"},

    {NULL, NULL, 0, NULL} /* Sentinel */
};
static struct PyModuleDef cext_module = {
    PyModuleDef_HEAD_INIT,
    "_cext", /* name of module */
    NULL,    /* module documentation, may be NULL */
    -1,      /* size of per-interpreter state of the module,
                or -1 if the module keeps state in global variables. */
    cext_methods,
};

PyMODINIT_FUNC PyInit__cext(void) {
    PyObject *module = PyModule_Create(&cext_module);
    if (module == NULL) {
        return NULL;
    }
#ifdef Py_GIL_DISABLED
    PyUnstable_Module_SetGIL(module, Py_MOD_GIL_NOT_USED);
#endif
    return module;
};
// PySys_WriteStdout(PyUnicode_AsUTF8AndSize(PyObject_Repr(config), NULL));
