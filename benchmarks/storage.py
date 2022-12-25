import csv
import os
import sys
from collections import defaultdict
from time import time

from .timer import SimpleTimer

PY_VERSION = tuple(sys.version_info[0:3])


class BenchmarkResult:
    def __init__(self, name, time_taken, number):
        self.name = name
        self.time_taken = time_taken
        self.number = number
        self.ts = time()


class BenchmarkStorageItemV1:
    def __init__(
        self, py_version, version, ts, name, number, ticks_taken, rel_speed
    ):
        self.py_version = (
            py_version
            if isinstance(py_version, tuple)
            else tuple(map(int, py_version.split(".")))
        )
        self.version = version
        self.ts = ts
        self.name = name
        self.number = int(number)
        self.ticks_taken = int(ticks_taken)
        self.rel_speed = float(rel_speed)

    def get_key(self):
        return (self.py_version[0:2], self.version, self.name)

    def get_key_to_compare_speed(self):
        return (self.py_version[0:2], self.name)

    @staticmethod
    def get_field_names():
        return (
            "py_version",
            "version",
            "ts",
            "name",
            "number",
            "ticks_taken",
            "rel_speed",
        )

    def as_tuple(self):
        return (
            ".".join(map(str, self.py_version)),
            self.version,
            self.ts,
            self.name,
            self.number,
            self.ticks_taken,
            self.rel_speed,
        )


class BenchmarkResultsStorageV1:
    FILENAME = os.path.join(
        os.path.dirname(__file__), "benchmark_results_V1.csv"
    )

    def __init__(self, version):
        items = []
        if os.path.exists(self.FILENAME):
            with open(self.FILENAME, "r") as f:
                rows = iter(csv.reader(f))
                header = tuple(next(rows))
                if header != BenchmarkStorageItemV1.get_field_names():
                    raise AssertionError

                for row in rows:
                    items.append(
                        BenchmarkStorageItemV1(**dict(zip(header, row)))
                    )

        self.key_to_item = {item.get_key(): item for item in items}
        self.new_results = []
        self.version = version

    def add_item(self, result: BenchmarkResult):
        self.new_results.append(result)

    def get_base_time(self):
        number, time_taken = SimpleTimer("'abc'").auto_measure(
            rel_precision=0.001
        )
        return time_taken / number

    def save(self):
        if not self.new_results:
            print("NOTHING TO SAVE")
            return

        base_time = self.get_base_time()
        print(f"BASE_TIME: {base_time}")

        for result in self.new_results:
            item = BenchmarkStorageItemV1(
                py_version=PY_VERSION,
                version=self.version,
                ts=result.ts,
                name=result.name,
                number=result.number,
                ticks_taken=int(result.time_taken / result.number / base_time),
                rel_speed=0,
            )
            self.key_to_item[item.get_key()] = item

        key_to_items = defaultdict(list)
        for item in self.key_to_item.values():
            key_to_items[item.get_key_to_compare_speed()].append(item)

        for items in key_to_items.values():
            max_ticks = max(item.ticks_taken for item in items)
            for item in items:
                item.rel_speed = round(max_ticks * 100.0 / item.ticks_taken, 1)

        new_filename = f"{self.FILENAME}_"
        with open(new_filename, "w") as f:
            writer = csv.writer(f)
            writer.writerow(BenchmarkStorageItemV1.get_field_names())
            for items in key_to_items.values():
                for item in items:
                    writer.writerow(item.as_tuple())

        os.replace(new_filename, self.FILENAME)
