import argparse
from time import time

from benchmarks.benchmarks import (
    Aggregate1,
    Aggregate2,
    GetItem1,
    GetItem2,
    GroupBy1,
    GroupBy2,
    IterOfGroupBy1,
    IterOfIter1,
    JoinInner1,
    JoinLeft1,
    JoinOuter1,
    JoinRight1,
    Pipe1,
    Pipe2,
    Table1,
    Table2,
    TableJoin1,
    FilterOfIter1,
    IterMut1,
    Or1,
    Table1CodeGen,
    Table2CodeGen,
    TableJoin1CodeGen,
)
from benchmarks.storage import BenchmarkResultsStorageV1


BENCHMARKS = [
    Aggregate1(),
    Aggregate2(),
    FilterOfIter1(),
    GetItem1(),
    GetItem2(),
    GroupBy1(GroupBy1.Modes.FEW_GROUPS),
    GroupBy1(GroupBy1.Modes.MANY_GROUPS),
    GroupBy2(GroupBy2.Modes.FEW_GROUPS),
    GroupBy2(GroupBy2.Modes.MANY_GROUPS),
    IterOfGroupBy1(),
    IterOfIter1(),
    JoinInner1(),
    JoinLeft1(),
    JoinOuter1(),
    JoinRight1(),
    Pipe1(),
    Pipe2(),
    Table1(),
    Table2(),
    TableJoin1(),
    IterMut1(),
    Or1(),
    Table1CodeGen(),
    Table2CodeGen(),
    TableJoin1CodeGen(),
]


def run():
    from convtools import __version__

    storage = BenchmarkResultsStorageV1(version=__version__)
    for benchmark in BENCHMARKS:
        # if benchmark.HAS_CODE_GEN_TEST:
        #     storage.add_item(benchmark.get_code_gen_result())
        if benchmark.HAS_EXECUTION_TEST:
            storage.add_item(benchmark.get_execution_result())
    storage.save()


if __name__ == "__main__":
    run()
