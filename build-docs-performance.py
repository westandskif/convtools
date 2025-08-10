import os
import subprocess
from glob import glob
from hashlib import sha256

from convtools import conversion as c
from convtools.contrib.tables import Table


DOCS_ROOT = "./docs"
MD_DIR = os.path.join(DOCS_ROOT, "performance-md")
_ensured_dirs = set()


def ensure_dir(file_path):
    dir_to_ensure = os.path.dirname(file_path)
    if dir_to_ensure in _ensured_dirs:
        return file_path
    _ensured_dirs.add(dir_to_ensure)
    os.makedirs(dir_to_ensure, exist_ok=True)
    return file_path


from typing import List

from benchmarks.storage import BenchmarkResult, BenchmarkResultsStorage
from tabulate import tabulate

import convtools


def gen_md(results: List[BenchmarkResult], indent="    "):
    c_version_to_tuple = (
        c.this.call_method("split", ".")
        .iter(c.this.as_type(int))
        .as_type(tuple)
    )
    filtered_results = (
        c.iter(
            c.this.call_method("_asdict"),
        )
        .iter_mut(
            c.Mut.set_item(
                "convtools_version",
                c.item("convtools_version").pipe(c_version_to_tuple),
            ),
            c.Mut.set_item(
                "py_version_tup",
                c.item("py_version").pipe(c_version_to_tuple),
            ),
        )
        .sort(
            key=(
                c.item("py_version_tup").desc(),
                c.item("diff"),
            )
        )
        .iter_unique(c.this, by_=(c.item("name"), c.item("py_version")))
        .execute(results)
    )
    table_data = list(
        Table.from_rows(filtered_results)
        .update(
            speed_up=c.col("diff")
            .pipe((c.this - 1) * 100)
            .pipe("{:+.1f}%".format)
        )
        .take("name", "speed_up", "py_version")
        .pivot(
            rows=["name"],
            columns=["py_version"],
            values={"speed_up": c.ReduceFuncs.Min(c.item("speed_up"))},
            prepare_column_names=lambda l: l[0],
        )
        .into_iter_rows(tuple, include_header=True)
    )
    with open(
        ensure_dir(os.path.join(MD_DIR, f"perf-benchmarks.md")), "w"
    ) as f:
        table_str = tabulate(table_data, headers="firstrow", tablefmt="pipe")
        for line in table_str.splitlines(keepends=True):
            f.write(indent + line)


if __name__ == "__main__":
    benchmark_results = BenchmarkResultsStorage().load_results()
    gen_md(benchmark_results)
