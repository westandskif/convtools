from collections import defaultdict
from csv import DictReader
from datetime import date, datetime, timedelta
from random import choice, random, seed
from string import ascii_letters

from convtools import conversion as c
from convtools.contrib.tables import Table

from .storage import BaseBenchmark


seed(1)


class Aggregate1(BaseBenchmark):
    def gen_converter(self):
        return c.aggregate(
            {
                "a": c.ReduceFuncs.Sum(c.item("value_1")),
                "b": c.ReduceFuncs.Min(c.item("value_2")),
                "c": c.ReduceFuncs.Max(c.item("value_2")),
            }
        ).gen_converter()

    def gen_naive_implementations(self):
        def f(data):
            a = 0
            b = None
            c = None
            for i in data:
                a += i["value_1"] or 0
                if i["value_2"] is not None and (
                    b is None or b > i["value_2"]
                ):
                    b = i["value_2"]

                if i["value_2"] is not None and (
                    c is None or c < i["value_2"]
                ):
                    c = i["value_2"]
            return {
                "a": a,
                "b": b,
                "c": c,
            }

        yield f

    def gen_data(self):
        return [
            {"value_1": random(), "value_2": random()} for i in range(10000)
        ]


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
                    "avg": c.ReduceFuncs.Average(c.item("value")),
                    "min": c.ReduceFuncs.Min(c.item("value")),
                    "max": c.ReduceFuncs.Max(c.item("value")),
                }
            )
            .gen_converter()
        )

    def gen_naive_implementations(self):
        def f(data):
            agg = defaultdict(
                lambda: {"count": 0, "sum": 0, "min": None, "max": None}
            )
            for i in data:
                v = agg[i["name"]]
                v["count"] += 1
                v["sum"] += i["value"] or 0
                if v["min"] is None or v["min"] > i["value"]:
                    v["min"] = i["value"]
                if v["max"] is None or v["max"] < i["value"]:
                    v["max"] = i["value"]
            return [
                {
                    "name": name,
                    "avg": (
                        value["sum"] / value["count"] if value["count"] else 0
                    ),
                    "min": value["min"],
                    "max": value["max"],
                }
                for name, value in agg.items()
            ]

        yield f

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


class IterOfIter1(BaseBenchmark):
    def gen_converter(self):
        return (
            c.list_comp(c.this() + 1)
            .iter(c.this() + 2)
            .iter(c.this() + 3)
            .as_type(list)
            .gen_converter()
        )

    def gen_naive_implementations(self):
        def f1(data):
            for i in data:
                yield i + 1

        def f2(data):
            for i in data:
                yield i + 2

        def f3(data):
            for i in data:
                yield i + 3

        def f(data):
            return list(f3(f2(f1(data))))

        yield f

    def gen_data(self):
        return list(range(10000))


class TableDictReader(BaseBenchmark):
    def gen_converter(self):
        def f(data):
            return list(Table.from_csv(data, header=True).into_iter_rows(dict))

        return f

    def gen_naive_implementations(self):
        def f(data):
            it = iter(data)
            header = next(it).split(",")
            reader = DictReader(it, fieldnames=header)
            return list(reader)

        yield f

    def gen_data(self):
        row = "a,b,c,d,e,f"
        return [row for i in range(10000)]


class DatetimeFormat(BaseBenchmark):
    FMT: str

    def gen_converter(self):
        return c.iter(c.format_dt(self.FMT)).as_type(list).gen_converter()

    def gen_naive_implementations(self):
        def f(data):
            return [dt.strftime(self.FMT) for dt in data]

        yield f

    def gen_data(self):
        dt = datetime(2020, 1, 1)
        return [dt + timedelta(days=i) for i in range(1000)]


class DateFormat(BaseBenchmark):
    FMT: str

    def gen_converter(self):
        return c.iter(c.format_dt(self.FMT)).as_type(list).gen_converter()

    def gen_naive_implementations(self):
        def f(data):
            return [dt.strftime(self.FMT) for dt in data]

        yield f

    def gen_data(self):
        dt = date(2020, 1, 1)
        return [dt + timedelta(days=i) for i in range(1000)]


class DatetimeParse(BaseBenchmark):
    FMT: str

    def gen_converter(self):
        return c.iter(c.datetime_parse(self.FMT)).as_type(list).gen_converter()

    def gen_naive_implementations(self):
        def f(data):
            return [datetime.strptime(dt_str, self.FMT) for dt_str in data]

        yield f

    def gen_data(self):
        dt = datetime(2020, 1, 1)
        return [
            (dt + timedelta(days=i)).strftime(self.FMT) for i in range(1000)
        ]


class DateParse(BaseBenchmark):
    FMT: str

    def gen_converter(self):
        return c.iter(c.date_parse(self.FMT)).as_type(list).gen_converter()

    def gen_naive_implementations(self):
        def f(data):
            return [
                datetime.strptime(dt_str, self.FMT).date() for dt_str in data
            ]

        yield f

    def gen_data(self):
        dt = datetime(2020, 1, 1)
        return [
            (dt + timedelta(days=i)).strftime(self.FMT) for i in range(1000)
        ]


class GetDefault(BaseBenchmark):
    POSITIVE = True

    def gen_converter(self):
        return c.item(0, default=-1).gen_converter()

    def gen_naive_implementations(self):
        def f(data):
            try:
                return data[0]
            except (TypeError, KeyError, IndexError):
                return -1

        yield c.call_func(f, c.this).gen_converter()

    def gen_data(self):
        if self.POSITIVE:
            return {0: 1}
        else:
            return {10: 1}
