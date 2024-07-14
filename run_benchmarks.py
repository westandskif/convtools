import argparse
from time import time

from benchmarks.benchmarks import (
    Aggregate1,
    DateFormat,
    DateParse,
    DatetimeFormat,
    DatetimeParse,
    GetDefault,
    GroupBy1,
    IterOfIter1,
    TableDictReader,
)
from benchmarks.storage import BenchmarkResultsStorage


BENCHMARKS = [
    # fmt: off
    type("GetDefaultPositive", (GetDefault,), {"POSITIVE": True})(),
    type("GetDefaultNegative", (GetDefault,), {"POSITIVE": False})(),
    Aggregate1(),
    GroupBy1(GroupBy1.Modes.FEW_GROUPS),
    GroupBy1(GroupBy1.Modes.MANY_GROUPS),
    IterOfIter1(),
    TableDictReader(),
    type("DateParse1", (DateParse,), {"FMT": "%m/%d/%Y"})(),
    type("DateParse2", (DateParse,), {"FMT": "%Y-%m-%d"})(),
    type("DatetimeParse1", (DatetimeParse,), {"FMT": "%m/%d/%Y %I:%M %p"})(),
    type("DatetimeParse2", (DatetimeParse,), {"FMT": "%Y-%m-%dt%H:%M:%S.%f"})(),
    type("DateFormat1", (DateFormat,), {"FMT": "%Y-%m-%d"})(),
    type("DateFormat2", (DateFormat,), {"FMT": "%m/%d/%Y"})(),
    type("DatetimeFormat1", (DatetimeFormat,), {"FMT": "%m/%d/%Y %I:%M %p"})(),
    type("DatetimeFormat2", (DatetimeFormat,), {"FMT": "%Y-%m-%dT%H:%M:%S.%f"})(),
    # fmt: on
]


def run():
    storage = BenchmarkResultsStorage()
    for benchmark in BENCHMARKS:
        storage.add_item(benchmark.get_execution_result())
    storage.save()


if __name__ == "__main__":
    run()
