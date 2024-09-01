#define PY_SSIZE_T_CLEAN /* Make "s#" use Py_ssize_t rather than int. */
#include <Python.h>

static PyObject *get_item_deep_default_simple(PyObject *self, PyObject *args[],
                                              Py_ssize_t nargs) {
    if (nargs < 3) {
        PyErr_SetString(PyExc_ValueError, "at least 3 arguments are expected");
        return NULL;
    }
    int i;
    int default_index = nargs - 1;
    PyObject *item = args[0];

    for (i = 1; i < default_index; i++) {
        if (item == Py_None) {
            break;
        }

        PyObject *a = PyObject_GetItem(item, args[i]);
        if (!a) {
            PyErr_Clear();
            break;
        }
        item = a;
    }
    if (i == default_index) {
        Py_INCREF(item);
        return item;
    } else {
        PyObject *a;
        a = args[default_index];
        Py_INCREF(a);
        return a;
    }
}
static PyObject *get_item_deep_default_callable(PyObject *self,
                                                PyObject *args[],
                                                Py_ssize_t nargs) {
    if (nargs < 3) {
        PyErr_SetString(PyExc_ValueError, "at least 3 arguments are expected");
        return NULL;
    }
    int i;
    int default_index = nargs - 1;
    PyObject *item = args[0];

    for (i = 1; i < default_index; i++) {
        if (item == Py_None) {
            break;
        }

        PyObject *a = PyObject_GetItem(item, args[i]);
        if (!a) {
            PyErr_Clear();
            break;
        }
        item = a;
    }
    if (i == default_index) {
        Py_INCREF(item);
        return item;
    } else {
        PyObject *a;
        a = PyObject_CallNoArgs(args[default_index]);
        if (!a) {
            return NULL;
        }
        Py_INCREF(a);
        return a;
    }
}

static PyObject *get_attr_deep_default_simple(PyObject *self, PyObject *args[],
                                              Py_ssize_t nargs) {
    if (nargs < 3) {
        PyErr_SetString(PyExc_ValueError, "at least 3 arguments are expected");
        return NULL;
    }
    int i;
    int default_index = nargs - 1;
    PyObject *item = args[0];

    for (i = 1; i < default_index; i++) {
        if (item == Py_None) {
            break;
        }

        PyObject *a = PyObject_GetAttr(item, args[i]);
        if (!a) {
            PyErr_Clear();
            break;
        }
        item = a;
    }
    if (i == default_index) {
        Py_INCREF(item);
        return item;
    } else {
        PyObject *a;
        a = args[default_index];
        Py_INCREF(a);
        return a;
    }
}
static PyObject *get_attr_deep_default_callable(PyObject *self,
                                                PyObject *args[],
                                                Py_ssize_t nargs) {
    if (nargs < 3) {
        PyErr_SetString(PyExc_ValueError, "at least 3 arguments are expected");
        return NULL;
    }
    int i;
    int default_index = nargs - 1;
    PyObject *item = args[0];

    for (i = 1; i < default_index; i++) {
        if (item == Py_None) {
            break;
        }

        PyObject *a = PyObject_GetAttr(item, args[i]);
        if (!a) {
            PyErr_Clear();
            break;
        }
        item = a;
    }
    if (i == default_index) {
        Py_INCREF(item);
        return item;
    } else {
        PyObject *a;
        a = PyObject_CallNoArgs(args[default_index]);
        if (!a) {
            return NULL;
        }
        Py_INCREF(a);
        return a;
    }
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
// PySys_WriteStdout("DBG2 ref count: %i\n", (int)context->tuple->ob_refcnt);
