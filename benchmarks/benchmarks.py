import abc
from random import choice, random, seed
from string import ascii_letters

from convtools import conversion as c
from convtools.contrib.tables import Table

from .storage import BenchmarkResult
from .timer import SimpleTimer


seed(1)


def measure(*args, **kwargs):
    return dict(
        zip(
            ("number", "time_taken"),
            SimpleTimer(*args, **kwargs).auto_measure(),
        )
    )


class BaseBenchmark(abc.ABC):
    HAS_CODE_GEN_TEST = True
    HAS_EXECUTION_TEST = True

    def get_name(self):
        return f"{self.__class__.__name__}"

    def get_code_gen_result(self):
        name = f"[GEN] {self.get_name()}"
        print(f"TESTING: {name}")
        return BenchmarkResult(name, **measure(self.gen_converter))

    def get_execution_result(self):
        name = f"[EXE] {self.get_name()}"
        print(f"TESTING: {name}")
        return BenchmarkResult(
            name,
            **measure(
                "converter(data)",
                "converter = _converter; data = _data",
                globals={
                    "_converter": self.gen_converter(),
                    "_data": self.gen_data(),
                },
            ),
        )

    @abc.abstractmethod
    def gen_converter(self):
        pass

    @abc.abstractmethod
    def gen_data(self):
        pass


class GroupBy1(BaseBenchmark):
    class Modes:
        FEW_GROUPS = "FEW_GROUPS"
        MANY_GROUPS = "MANY_GROUPS"

    def __init__(self, mode):
        self.mode = mode

    def get_name(self):
        return f"{super().get_name()} - {self.mode}"

    def gen_converter(self):
        return (
            c.group_by(c.item("name"))
            .aggregate(
                {
                    "name": c.item("name"),
                    "sum": c.ReduceFuncs.Sum(c.item("value") * 1),
                }
            )
            .gen_converter()
        )

    def gen_data(self):
        if self.mode == self.Modes.FEW_GROUPS:
            name_length = 1
            symbols = ascii_letters[:3]
        else:
            name_length = 6
            symbols = ascii_letters
        return [
            {
                "name": "".join(choice(symbols) for i in range(name_length)),
                "value": random(),
            }
            for i in range(10000)
        ]


class GroupBy2(GroupBy1):
    def gen_converter(self):
        return (
            c.group_by(c.item("name"))
            .aggregate(
                {
                    "name": c.item("name"),
                    "category_with_min": c.ReduceFuncs.MinRow(
                        c.item("value")
                    ).item("category"),
                    "categories_first_n_last": (
                        c.ReduceFuncs.First(c.item("value")),
                        c.ReduceFuncs.Last(c.item("value")),
                    ),
                    "count": c.ReduceFuncs.Count(),
                    "sum": c.ReduceFuncs.Sum(c.item("value")),
                    "avg": c.ReduceFuncs.Average(c.item("value")),
                }
            )
            .gen_converter()
        )

    def gen_data(self):
        categories = ("CatA", "CatB", "CatC")
        if self.mode == self.Modes.FEW_GROUPS:
            name_length = 1
            symbols = ascii_letters[:3]
        else:
            name_length = 6
            symbols = ascii_letters
        return [
            {
                "name": "".join(choice(symbols) for i in range(name_length)),
                "category": choice(categories),
                "value": random(),
            }
            for i in range(10000)
        ]


class Aggregate1(BaseBenchmark):
    def gen_converter(self):
        return c.aggregate(c.ReduceFuncs.Sum(c.item("value"))).gen_converter()

    def gen_data(self):
        return [{"value": random()} for i in range(10000)]


class Aggregate2(BaseBenchmark):
    def gen_converter(self):
        return c.aggregate(
            (
                c.ReduceFuncs.Sum(c.this()),
                c.ReduceFuncs.Sum(c.this(), where=c.this() > 0.3),
                c.ReduceFuncs.Sum(c.this(), where=c.this() > 0.6),
                c.ReduceFuncs.CountDistinct(c.this()),
                c.ReduceFuncs.CountDistinct(c.this(), where=c.this() > 0.3),
                c.ReduceFuncs.DictCount(
                    c.this().pipe(round), c.this(), where=c.this() > 0.3
                ),
                c.ReduceFuncs.DictCount(c.this().pipe(round), c.this()),
            )
        ).gen_converter()

    def gen_data(self):
        return [random() for i in range(10000)]


class IterOfIter1(BaseBenchmark):
    def gen_converter(self):
        return (
            c.list_comp(c.this() + 1)
            .iter(c.this() + 2)
            .iter(c.this() + 3)
            .as_type(list)
            .gen_converter()
        )

    def gen_data(self):
        return list(range(10000))


class FilterOfIter1(BaseBenchmark):
    def gen_converter(self):
        return (
            c.list_comp(c.this())
            .filter(c.this() < 1000)
            .iter(c.this() + 1)
            .as_type(list)
            .gen_converter()
        )

    def gen_data(self):
        return list(range(10000))


class IterMut1(BaseBenchmark):
    def gen_converter(self):
        return (
            c.list_comp(c.this())
            .iter_mut(c.Mut.set_item("i", c.item("i") + 1))
            .as_type(list)
            .gen_converter()
        )

    def gen_data(self):
        return [{"i": i} for i in range(10000)]


class Or1(BaseBenchmark):
    def gen_converter(self):
        return (
            c.iter(c.item(0).or_(c.item(1)).or_(c.item(2)))
            .as_type(list)
            .gen_converter()
        )

    def gen_data(self):
        return [(None, 0, 1) for i in range(10000)]


class IterOfGroupBy1(BaseBenchmark):
    def gen_converter(self):
        return (
            c.group_by(c.item("name"))
            .aggregate(c.ReduceFuncs.Sum(c.item("value")))
            .iter(c.this() + 1)
            .iter(c.this() + 2)
            .iter(c.this() + 3)
            .as_type(list)
            .gen_converter()
        )

    def gen_data(self):
        name_length = 6
        symbols = ascii_letters
        return [
            {
                "name": "".join(choice(symbols) for i in range(name_length)),
                "value": random(),
            }
            for i in range(10000)
        ]


class JoinInner1(BaseBenchmark):
    HOW = "inner"

    def gen_converter(self):
        return (
            c.join(
                c.item(0),
                c.item(1),
                c.LEFT.item(0) == c.RIGHT.item(0),
                self.HOW,
            )
            .as_type(list)
            .gen_converter()
        )

    def gen_data(self):
        return (
            [(i,) for i in range(100000)],
            [(i,) for i in range(10000, 0, -1)],
        )


class JoinLeft1(JoinInner1):
    HOW = "left"


class JoinRight1(JoinInner1):
    HOW = "right"

    def gen_data(self):
        return (
            [(i,) for i in range(10000, 0, -1)],
            [(i,) for i in range(100000)],
        )


class JoinOuter1(JoinInner1):
    HOW = "outer"


class GetItem1(BaseBenchmark):
    def gen_converter(self):
        return c.iter(c.item(0)).as_type(list).gen_converter()

    def gen_data(self):
        return [(i,) for i in range(10000)]


class GetItem2(BaseBenchmark):
    def gen_converter(self):
        return c.iter(c.item(1, default=-1)).as_type(list).gen_converter()

    def gen_data(self):
        return list(range(10000))


class Pipe1(BaseBenchmark):
    def gen_converter(self):
        return (
            c.iter(
                (c.this() + 1)
                .pipe(c.this() + 2)
                .pipe(c.this() + 3)
                .pipe(round)
            )
            .as_type(list)
            .gen_converter()
        )

    def gen_data(self):
        return list(range(10000))


class Pipe2(BaseBenchmark):
    def gen_converter(self):
        return (
            c.iter(
                (c.this() + 1)
                .pipe(c.this() + c.this())
                .pipe(c.this() + 3)
                .pipe(round)
            )
            .as_type(list)
            .gen_converter()
        )

    def gen_data(self):
        return list(range(10000))


class TableJoin1(BaseBenchmark):
    HAS_CODE_GEN_TEST = False

    def gen_converter(self):
        def f(data):
            return len(
                list(
                    Table.from_rows(data[0], header=["a"])
                    .join(
                        Table.from_rows(data[1], header=["a"]),
                        on="a",
                        how="inner",
                    )
                    .into_iter_rows(dict)
                )
            )

        return f

    def gen_data(self):
        return (
            [(i,) for i in range(100000)],
            [(i,) for i in range(10000, 0, -1)],
        )


class Table1(BaseBenchmark):
    def gen_converter(self):
        def f(data):
            return len(
                list(Table.from_rows(data, header=["a"]).into_iter_rows(dict))
            )

        return f

    def gen_data(self):
        return [(i,) for i in range(100000)]


class Table2(BaseBenchmark):
    def gen_converter(self):
        def f(data):
            return len(
                list(
                    Table.from_rows(data, header=["a"])
                    .update(
                        b=c.col("a") + 1,
                    )
                    .update(
                        c=c.col("a") + 2,
                    )
                    .update(d=c.col("b") + c.col("c"))
                    .into_iter_rows(dict)
                )
            )

        return f

    def gen_data(self):
        return [(i,) for i in range(100000)]


class TableJoin1CodeGen(TableJoin1):
    def gen_data(self):
        return (
            [(i,) for i in range(1)],
            [(i,) for i in range(1)],
        )


class Table1CodeGen(Table1):
    def gen_data(self):
        return [(i,) for i in range(1)]


class Table2CodeGen(Table2):
    def gen_data(self):
        return [(i,) for i in range(100000)]
