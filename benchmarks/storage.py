import abc
import csv
import os
import platform
import sys
from collections import defaultdict
from itertools import chain
from time import time


import convtools
from convtools import conversion as c
from convtools.contrib.tables import Table

from .timer import SimpleTimer
from typing import NamedTuple


class Environment(NamedTuple):
    system: str
    arch: str
    py_version: str
    py_version_exact: str
    py_implementation: str
    py_compiler: str
    convtools_version: str


class BenchmarkResult(NamedTuple):
    system: str
    arch: str
    py_version: str
    py_version_exact: str
    py_implementation: str
    py_compiler: str
    convtools_version: str
    name: str
    diff: float


ENVIRONMENT = Environment(
    system=platform.system(),
    arch=platform.machine(),
    py_version=".".join(map(str, sys.version_info[0:2])),
    py_version_exact=platform.python_version(),
    py_implementation=platform.python_implementation(),
    py_compiler=platform.python_compiler(),
    convtools_version=convtools.__version__,
)


class BaseBenchmark(abc.ABC):
    HAS_CODE_GEN_TEST = True
    HAS_EXECUTION_TEST = True

    def get_name(self):
        return f"{self.__class__.__name__}"

    def _measure(self, f, data):
        number_of_iterations, mean = SimpleTimer(
            "f(data)", "f = _f; data = _data", globals={"_f": f, "_data": data}
        ).auto_measure()
        return mean / number_of_iterations

    def compare_results(self, data1, data2) -> bool:
        return data1 == data2

    def get_execution_result(self) -> BenchmarkResult:
        name = self.get_name()
        print(f"TESTING: {name}")
        data = self.gen_data()

        convtools_converter = self.gen_converter()
        naive_implementations = list(self.gen_naive_implementations())

        # make sure the results are the same
        expected = convtools_converter(data)
        for naive_f in naive_implementations:
            result = naive_f(data)
            assert self.compare_results(result, expected)

        best_naive = min(
            self._measure(naive_f, data) for naive_f in naive_implementations
        )
        convtools_time = self._measure(convtools_converter, data)
        return BenchmarkResult(
            name=name,
            diff=best_naive / convtools_time,
            **ENVIRONMENT._asdict(),
        )

    @abc.abstractmethod
    def gen_converter(self):
        pass

    @abc.abstractmethod
    def gen_naive_implementations(self):
        pass

    @abc.abstractmethod
    def gen_data(self):
        pass


class BenchmarkResultsStorage:
    FILENAME = os.path.join(
        os.path.dirname(__file__), "benchmark_results_V1.csv"
    )

    def __init__(self):
        self.new_results = []

    def load_results(self):
        if os.path.exists(self.FILENAME):
            return list(
                map(
                    BenchmarkResult._make,
                    Table.from_csv(self.FILENAME, header=True)
                    .update(diff=c.col("diff").as_type(float))
                    .into_iter_rows(tuple),
                )
            )
        return []

    def add_item(self, result: BenchmarkResult):
        self.new_results.append(result)

    _key_fields = (
        "system",
        "arch",
        "py_version",
        "py_implementation",
        "py_compiler",
        "convtools_version",
        "name",
    )
    _sort_fields = ("py_version", "diff")

    def save(self):
        merged_results = (
            c.group_by(*(c.attr(key_) for key_ in self._key_fields))
            .aggregate(c.ReduceFuncs.Last(c.this))
            .iter(c.this.call_method("_asdict"))
            .execute(chain(self.load_results(), self.new_results))
        )
        resulting_rows = sorted(
            merged_results,
            key=c.tuple(
                *(c.item(key_) for key_ in self._sort_fields)
            ).gen_converter(),
        )
        new_filename = f"{self.FILENAME}_"
        Table.from_rows(resulting_rows).into_csv(new_filename)
        os.replace(new_filename, self.FILENAME)
