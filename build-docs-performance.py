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


def gen_md(results: List[BenchmarkResult], py_version: str, indent="    "):
    filtered_results = (
        c.filter(
            c.and_(
                c.attr("py_version") == py_version,
                c.attr("convtools_version") == convtools.__version__,
            )
        )
        .pipe(
            c.group_by(c.attr("name"))
            .aggregate(
                c.ReduceFuncs.MinRow(c.attr("diff")).call_method("_asdict")
            )
            .sort(key=lambda x: x["diff"])
        )
        .execute(results)
    )
    table_data = list(
        Table.from_rows(filtered_results)
        .update(
            speed_up=c.col("diff")
            .pipe((c.this - 1) * 100)
            .pipe("{:+.1f}%".format)
        )
        .take("name", "speed_up", "py_compiler", "arch")
        .into_iter_rows(tuple, include_header=True)
    )
    with open(
        ensure_dir(os.path.join(MD_DIR, f"perf-{py_version}.md")), "w"
    ) as f:
        table_str = tabulate(table_data, headers="firstrow", tablefmt="pipe")
        for line in table_str.splitlines(keepends=True):
            f.write(indent + line)


if __name__ == "__main__":
    benchmark_results = BenchmarkResultsStorage().load_results()
    gen_md(benchmark_results, "3.6")
    gen_md(benchmark_results, "3.7")
    gen_md(benchmark_results, "3.8")
    gen_md(benchmark_results, "3.9")
    gen_md(benchmark_results, "3.10")
    gen_md(benchmark_results, "3.11")
    gen_md(benchmark_results, "3.12")
    gen_md(benchmark_results, "3.13")
