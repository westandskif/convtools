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
        .sort(
            key=(
                c.item("py_version").pipe(c_version_to_tuple).desc(),
                c.item("convtools_version").pipe(c_version_to_tuple).desc(),
                c.item("diff"),
            )
        )
        .iter_unique(c.this, by_=(c.item("name"), c.item("py_version")))
        .as_type(list)
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
            values={"speed_up": c.ReduceFuncs.Min(c.col("speed_up"))},
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
    return filtered_results


if __name__ == "__main__":
    storage = BenchmarkResultsStorage()
    benchmark_results = storage.load_results()
    rendered_results = gen_md(benchmark_results)
    # Replace the stored history with exactly the rows used in the docs.
    # storage.save() merges old results back in, so it cannot prune them.
    rendered_results.sort(key=lambda row: (row["py_version"], row["diff"]))
    new_filename = f"{storage.FILENAME}_"
    Table.from_rows(rendered_results).into_csv(new_filename)
    os.replace(new_filename, storage.FILENAME)
