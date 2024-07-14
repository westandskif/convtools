import os
import sys

from setuptools import Extension, find_packages, setup


ext_modules = []

if (
    sys.implementation.name == "cpython"
    and sys.version_info[:2] >= (3, 10)
    and os.environ.get("CONVTOOLS_CEXT_DISABLED", "") != "1"
):
    ext_modules.append(
        Extension(
            name="convtools._cext",  # as it would be imported
            sources=[
                "src/convtools/c_extensions/getters.c"
            ],  # all sources are compiled into a single binary file
            optional=True,
            py_limited_api=True,
            extra_compile_args=["-w"],
        )
    )

setup(
    ext_modules=ext_modules,
    packages=find_packages("src", exclude=["tests"]),
)
