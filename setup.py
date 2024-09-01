import os
import sys
import sysconfig

from setuptools import Extension, find_packages, setup


ext_modules = []
setup_kwargs = {}
ext_kwargs = {}
is_free_threading = sysconfig.get_config_var("Py_GIL_DISABLED") == 1

if not is_free_threading:
    ext_kwargs["py_limited_api"] = True
    ext_kwargs["define_macros"] = [("Py_LIMITED_API", 0x03A00000)]
    opts = setup_kwargs.setdefault("options", {})
    opts["bdist_wheel"] = {"py_limited_api": "cp310"}

if (
    sys.implementation.name == "cpython"
    and sys.version_info[:2] >= (3, 10)
    and os.environ.get("CONVTOOLS_CEXT_DISABLED", "") != "1"
):
    ext_modules.append(
        Extension(
            name="convtools._cext",
            sources=["src/convtools/c_extensions/getters.c"],
            optional=True,
            extra_compile_args=["-w"],
            **ext_kwargs,
        )
    )


setup(
    ext_modules=ext_modules,
    packages=find_packages("src", exclude=["tests"]),
    **setup_kwargs,
)
