from unittest.mock import MagicMock

import pytest

from convtools import conversion as c
from convtools._columns import ColumnDef, MetaColumns
from convtools.contrib.tables import CloseFileIterator, Table


def test_table_base_init():
    list(
        Table.from_rows([(1, -2), (2, -3)], ["a", "b"])
        .update(c=c.col("a") + c.col("b"))  # adding new column: "c"
        .update(c=c.call_func(abs, c.col("c")))  # updating new column: "c"
        .into_iter_rows(dict)
    )
    result = list(
        Table.from_rows(
            [(1, 2, 3), (2, 3, 4)], ["a", "b", "c"]
        ).into_iter_rows(include_header=True)
    )
    assert result == [
        ("a", "b", "c"),
        (1, 2, 3),
        (2, 3, 4),
    ]
    result = list(
        Table.from_rows(
            [(1, 2, 3), (2, 3, 4)], {"a": 2, "b": 1, "c": 0}
        ).into_iter_rows(dict)
    )
    assert result == [
        {"a": 3, "b": 2, "c": 1},
        {"a": 4, "b": 3, "c": 2},
    ]

    input_data = [("a", "a", "b"), (1, 2, 3)]
    with pytest.raises(ValueError):
        Table.from_rows(input_data, True)
    with pytest.raises(ValueError):
        Table.from_rows(input_data, True, duplicate_columns="raise")

    result = list(
        Table.from_rows(
            input_data, True, duplicate_columns="keep"
        ).into_iter_rows(include_header=True)
    )
    assert result == input_data

    result = list(
        Table.from_rows(
            input_data, True, duplicate_columns="drop"
        ).into_iter_rows(include_header=True)
    )
    assert result == [("a", "b"), (1, 3)]

    result = list(
        Table.from_rows(
            input_data, True, duplicate_columns="mangle"
        ).into_iter_rows(include_header=True)
    )
    assert result == [("a", "a_1", "b"), (1, 2, 3)]

    result = list(
        Table.from_rows(input_data, None).into_iter_rows(include_header=True)
    )
    assert result == [
        ("COLUMN_0", "COLUMN_1", "COLUMN_2"),
        ("a", "a", "b"),
        (1, 2, 3),
    ]

    result = list(
        Table.from_rows(input_data, {"a": 0, "b": 1, "c": 2}).into_iter_rows(
            include_header=True
        )
    )
    assert result == [("a", "b", "c"), ("a", "a", "b"), (1, 2, 3)]

    result = list(
        Table.from_rows(
            input_data, {"a": 1, "b": 0, "c": 2}, skip_rows=1
        ).into_iter_rows(dict)
    )
    assert result == [{"a": 2, "b": 1, "c": 3}]

    result = list(
        Table.from_rows([{"a": 1, "b": 2, "c": 3}]).into_iter_rows(dict)
    )
    assert result == [{"a": 1, "b": 2, "c": 3}]

    result = list(
        Table.from_rows(
            [{"a": 1, "b": 2, "c": 3}], header=False
        ).into_iter_rows(dict)
    )
    assert result == [{"COLUMN_0": 1, "COLUMN_1": 2, "COLUMN_2": 3}]

    assert list(
        Table.from_rows([1, (1,), (2,)], header=True)
        .update(**{"abc": c.col("1").item(0)})
        .take("abc")
        .into_iter_rows(dict)
    ) == [
        {"abc": 1},
        {"abc": 2},
    ]

    Table.from_rows(range(3), header=False).update(a=c.col("COLUMN_0"))

    assert list(
        Table.from_rows(["name", "cde"], header=True).into_iter_rows(dict)
    ) == [{"name": "cde"}]
    assert list(
        Table.from_rows(["name", "cde"], header=False).into_iter_rows(dict)
    ) == [{"COLUMN_0": "name"}, {"COLUMN_0": "cde"}]

    assert list(Table.from_rows([0, 1, 2]).into_iter_rows(dict)) == [
        {"COLUMN_0": 0},
        {"COLUMN_0": 1},
        {"COLUMN_0": 2},
    ]
    assert list(
        Table.from_rows([0, 1, 2], header=["a"]).into_iter_rows(dict)
    ) == [
        {"a": 0},
        {"a": 1},
        {"a": 2},
    ]
    table = Table.from_rows((), header=("a", "b"))
    assert list(table.into_iter_rows(dict)) == [] and table.columns == [
        "a",
        "b",
    ]
    table = Table.from_rows((), header={"a": 1, "b": 2})
    assert list(table.into_iter_rows(dict)) == [] and table.columns == [
        "a",
        "b",
    ]

    with pytest.raises(ValueError):
        Table.from_rows([0, 1, 2], header=["a", "b"]).into_iter_rows(dict)
    with pytest.raises(ValueError):
        Table.from_rows([0, 1, 2], header={"a": 1}).into_iter_rows(dict)

    with pytest.raises(ValueError):
        Table.from_rows((), header=True)


def test_table_take():
    result = list(
        Table.from_rows(
            [(1, 2, 3), (2, 3, 4)], ["a", "b", "c"], duplicate_columns="keep"
        )
        .take("c", "a", "a")
        .into_iter_rows(include_header=True)
    )
    assert result == [
        ("c", "a", "a"),
        (3, 1, 1),
        (4, 2, 2),
    ]

    result = list(
        Table.from_rows([[1, 2, 3, 4]], header=["a", "b", "c", "d"])
        .take("b", "d", ...)
        .into_iter_rows(tuple, include_header=True)
    )
    assert result == [
        ("b", "d", "a", "c"),
        (2, 4, 1, 3),
    ]

    result = list(
        Table.from_rows([[1, 2, 3, 4]], header=["a", "b", "c", "d"])
        .take(..., "c", "a")
        .into_iter_rows(tuple, include_header=True)
    )
    assert result == [
        ("b", "d", "c", "a"),
        (2, 4, 3, 1),
    ]

    result = list(
        Table.from_rows([[1, 2, 3, 4]], header=["a", "b", "c", "d"])
        .take("b", ..., "a")
        .into_iter_rows(tuple, include_header=True)
    )
    assert result == [
        ("b", "c", "d", "a"),
        (2, 3, 4, 1),
    ]


def test_table_drop():
    result = list(
        Table.from_rows([(1, 2, 3), (2, 3, 4)], ["a", "b", "c"])
        .drop("a", "c")
        .into_iter_rows(include_header=True)
    )
    assert result == [
        ("b",),
        (2,),
        (3,),
    ]


def test_table_update():
    result = list(
        Table.from_rows([(1,), (2,)], ["a"])
        .update(b=c.col("a") + 1)
        .into_iter_rows(include_header=True)
    )
    assert result == [
        ("a", "b"),
        (1, 2),
        (2, 3),
    ]
    result = list(
        Table.from_rows(result, True)
        .update(c=c.col("a") + c.col("b") + 1)
        .update(d=c.col("c") * -1)
        .take("a", "c", "d")
        .into_iter_rows(dict)
    )
    assert result == [
        {"a": 1, "c": 4, "d": -4},
        {"a": 2, "c": 6, "d": -6},
    ]


def test_table_rename():
    result = list(
        Table.from_rows([(1, 2), (3, 4)], ["a", "b"])
        .rename(["A", "B"])
        .into_iter_rows(dict)
    )
    assert result == [{"A": 1, "B": 2}, {"A": 3, "B": 4}]

    result = list(
        Table.from_rows([(1, 2), (3, 4)], ["a", "b"])
        .rename({"b": "B"})
        .into_iter_rows(tuple, include_header=True)
    )
    assert result == [("a", "B"), (1, 2), (3, 4)]

    result = list(
        Table.from_rows([{"a": 1}]).rename({"a": "A"}).into_iter_rows(dict)
    )
    assert result == [{"A": 1}]


# BEFORE
def process_table(rows):
    return (
        Table.from_rows(rows, ["a", "b"])
        .filter(c.col("a") > 0)
        .into_iter_rows(dict)
    )


def test_table_filter():
    result = list(
        Table.from_rows([(-1, 0), (1, 2), (3, 4)], ["a", "b"])
        .filter(c.col("a") > 0)
        .into_iter_rows(dict)
    )
    assert result == [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
    result = list(
        Table.from_rows([(-1, 0), (1, 2), (3, 4)], ["a", "b"])
        .update(c=c.col("a") * 100)
        .filter(c.col("c") > 0)
        .drop("c")
        .into_iter_rows(dict)
    )
    assert result == [{"a": 1, "b": 2}, {"a": 3, "b": 4}]


def test_table_columns():
    ref_columns = ["a", "b"]
    table = Table.from_rows([(1, 2), (3, 4)], ref_columns)
    columns = table.get_columns()
    columns2 = table.columns
    assert columns == ref_columns and columns2 == ref_columns


def test_table_inner_join():
    result = list(
        Table.from_rows([(1, 2), (2, 3)], ["a", "b"])
        .join(
            Table.from_rows([{"aa": 1, "cc": 3}, {"aa": 2, "cc": 4}]).rename(
                {"cc": "c", "aa": "a"}
            ),
            how="inner",
            on=["a"],
        )
        .into_iter_rows(dict)
    )
    assert result == [
        {"a": 1, "b": 2, "c": 3},
        {"a": 2, "b": 3, "c": 4},
    ]

    result = list(
        Table.from_rows([(1, 2), (2, 3)], ["a", "b"])
        .join(
            Table.from_rows([], ["a", "c"]),
            how="inner",
            on=["a"],
        )
        .into_iter_rows(dict)
    )
    assert result == []

    result = list(
        Table.from_rows([(1, 2), (2, 3)], ["a", "b"])
        .embed_conversions()
        .update()
        .drop()
        .join(
            Table.from_rows([(1, 3), (2, 4)], ["a", "c"]),
            how="inner",
            on=["a"],
        )
        .into_iter_rows(include_header=True)
    )
    assert result == [("a", "b", "c"), (1, 2, 3), (2, 3, 4)]

    with c.OptionsCtx() as o:
        o.debug = False
        result = list(
            Table.from_rows([(1, 2), (2, 3)], ["a", "b"])
            .join(
                Table.from_rows([(0, -1), (3, 4)], ["a", "c"]),
                how="inner",
                on=c.LEFT.col("a") < c.RIGHT.col("a"),
            )
            .into_iter_rows(include_header=True)
        )
    assert result == [
        ("a_LEFT", "b", "a_RIGHT", "c"),
        (1, 2, 3, 4),
        (2, 3, 3, 4),
    ]

    result = list(
        Table.from_rows(
            [
                {"aa": 1, "b": 2},
                {"aa": 2, "b": 3},
            ]
        )
        .rename({"aa": "a"})
        .join(
            Table.from_rows(
                [
                    (1, 10),
                    (2, 20),
                ],
                header=["a", "c"],
            ),
            on="a",
            how="inner",
        )
        .into_iter_rows(dict)
    )
    assert result == [
        {"a": 1, "b": 2, "c": 10},
        {"a": 2, "b": 3, "c": 20},
    ]


def test_table_left_simple():
    result = list(
        Table.from_rows([(1, 2), (2, 3)], ["a", "b"])
        .join(
            Table.from_rows([(1, 3), (2, 4)], ["a", "c"]),
            how="left",
            on=["a"],
        )
        .into_iter_rows(include_header=True)
    )
    assert result == [
        ("a", "b", "c"),
        (1, 2, 3),
        (2, 3, 4),
    ]

    result = list(
        Table.from_rows([(1, 2), (2, 3)], ["a", "b"])
        .join(
            Table.from_rows([], ["a", "c"]),
            how="left",
            on=["a"],
        )
        .into_iter_rows(include_header=True)
    )
    assert result == [
        ("a", "b", "c"),
        (1, 2, None),
        (2, 3, None),
    ]


def test_table_left_join():
    with c.OptionsCtx() as options:
        options.debug = False
        result = list(
            Table.from_rows([(1, 2), (2, 3)], ["a", "b"])
            .join(
                Table.from_rows([(1, 3), (2, 4)], ["a", "c"]),
                how="left",
                on=["a"],
            )
            .join(
                Table.from_rows(
                    [
                        (2, 4, 7),
                    ],
                    ["a", "c", "d"],
                ),
                how="left",
                on=["a", "c"],
            )
            .into_iter_rows(include_header=True)
        )
    assert result == [
        ("a", "b", "c", "d"),
        (1, 2, 3, None),
        (2, 3, 4, 7),
    ]


def test_table_right_join():
    result = list(
        Table.from_rows([(1, 2), (2, 3)], ["a", "b"])
        .join(
            Table.from_rows([(4, 3), (2, 4)], ["a", "c"]),
            how="right",
            on=["a"],
        )
        .into_iter_rows(include_header=True)
    )
    assert result == [
        ("a", "b", "c"),
        (4, None, 3),
        (2, 3, 4),
    ]
    result = list(
        Table.from_rows([(1, 2), (2, 3)], ["a", "b"])
        .join(
            Table.from_rows([], ["a", "c"]),
            how="right",
            on=["a"],
        )
        .into_iter_rows(include_header=True)
    )
    assert result == [("a", "b", "c")]


def test_table_outer_join():
    result = list(
        Table.from_rows([(1, 2, 10), (2, 3, 11)], ["a", "b", "d"])
        .join(
            Table.from_rows([(4, 3, 20), (2, 4, 21)], ["a", "c", "d"]),
            how="full",
            on=["a"],
        )
        .into_iter_rows(include_header=True)
    )
    assert result == [
        ("a", "b", "d_LEFT", "c", "d_RIGHT"),
        (1, 2, 10, None, None),
        (2, 3, 11, 4, 21),
        (4, None, None, 3, 20),
    ]

    result = list(
        Table.from_rows([(1, 2, 10), (2, 3, 11)], ["a", "b", "d"])
        .join(
            Table.from_rows([], ["a", "c", "d"]),
            how="full",
            on=["a"],
        )
        .into_iter_rows(include_header=True)
    )
    assert result == [
        ("a", "b", "d_LEFT", "c", "d_RIGHT"),
        (1, 2, 10, None, None),
        (2, 3, 11, None, None),
    ]


def test_table_csv():
    Table.from_csv("tests/csvs/ab.csv", True).into_csv("tests/csvs/out.csv")
    result = list(Table.from_csv("tests/csvs/out.csv", True).into_iter_rows())
    assert result == [("1", "2"), ("2", "3")]

    result = list(
        Table.from_csv("tests/csvs/ab.csv", True)
        .update_all(int)
        .join(
            Table.from_csv(
                "tests/csvs/ac.csv",
                True,
                dialect=Table.csv_dialect(delimiter="\t"),
            ).update_all(int),
            on=["a"],
            how="inner",
        )
        .into_iter_rows(include_header=True)
    )
    assert result == [
        ("a", "b", "c"),
        (1, 2, 3),
        (2, 3, 4),
    ]

    with open("tests/csvs/ab.csv", "r") as f_in, open(
        "tests/csvs/out.csv", "w"
    ) as f_out:
        result = Table.from_csv(
            f_in, header=["A", "B"], skip_rows=True
        ).into_csv(f_out)
    result = list(Table.from_csv("tests/csvs/out.csv").into_iter_rows())
    assert result == [("A", "B"), ("1", "2"), ("2", "3")]

    Table.from_rows([{"a": 1}]).into_csv("tests/csvs/out.csv")
    result = list(Table.from_csv("tests/csvs/out.csv").into_iter_rows())
    assert result == [("a",), ("1",)]

    Table.from_rows([{"a": 1}]).into_csv(
        "tests/csvs/out.csv", include_header=False
    )
    result = list(Table.from_csv("tests/csvs/out.csv").into_iter_rows())
    assert result == [("1",)]

    with open("tests/csvs/out.csv", "w") as f_out:
        Table.from_rows([{"a": 1}]).into_csv(f_out, include_header=False)
    result = list(Table.from_csv("tests/csvs/out.csv").into_iter_rows())
    assert result == [("1",)]


def test_table_exceptions():
    with pytest.raises(c.ConversionException):
        c.col("tst").gen_converter()
    with pytest.raises(ValueError):
        c.col(1)
    with pytest.raises(ValueError):
        ColumnDef("abc", None, None)
    with pytest.raises(ValueError):
        ColumnDef("abc", 0, c.this)
    with pytest.raises(ValueError):
        MetaColumns(duplicate_columns="abc")
    with pytest.raises(ValueError):
        Table.from_rows([("a",), (1,)], True).take("b")
    with pytest.raises(ValueError):
        Table.from_rows([("a",), (1,)], True).drop("b")

    with pytest.raises(ValueError):
        it = (
            Table.from_rows([(1, 2), (2, 3)], ["a", "b"])
            .join(
                Table.from_rows([(0, -1), (3, 4)], ["a", "c"]),
                how="inner",
                on=c.LEFT.col("a") < c.col("d"),
            )
            .into_iter_rows(include_header=True)
        )
    table = Table.from_rows([(1, 2), (2, 3)], ["a", "b"])
    with pytest.raises(TypeError):
        table.into_iter_rows(object)
    with pytest.raises(ValueError):
        table.rename(["A"])
    with pytest.raises(TypeError):
        table.rename({"A"})

    for header in [("a",), ["a"], {"a": "a"}]:
        with pytest.raises(ValueError):
            table.from_rows([[1, 2], [2, 3]], header=header)


def test_table_edge_cases():
    mock = MagicMock()
    item = CloseFileIterator(mock)
    list(item)
    item.__del__()
    mock.close.assert_called_once()

    mock = MagicMock()
    item = CloseFileIterator(mock)
    item.__del__()
    mock.close.assert_called_once()


def test_table_integration():
    input_data = [["a", "b"], [1, 2], [3, 4]]
    conversion = c.this.pipe(
        lambda it: Table.from_rows(it, header=True).into_iter_rows(dict)
    ).as_type(list)
    conversion.execute(input_data)


def test_table_chain():
    with c.OptionsCtx() as o:
        o.debug = True
        result = list(
            Table.from_rows([["a", "b"], [1, 2]], header=True)
            .chain(Table.from_rows([["b", "a", "c"], [4, 3, 5]], header=True))
            .into_iter_rows(tuple, include_header=True)
        )
    assert result == [
        ("a", "b", "c"),
        (1, 2, None),
        (3, 4, 5),
    ]

    result = list(
        Table.from_rows([["a", "b"], [1, 2], [5, 6]], header=True)
        .chain(Table.from_rows([["c", "a"], [4, 3]], header=True))
        .into_iter_rows(tuple, include_header=True)
    )
    assert result == [
        ("a", "b", "c"),
        (1, 2, None),
        (5, 6, None),
        (3, None, 4),
    ]

    result = list(
        Table.from_rows([["a"], ["1"]], header=True)
        .update(a=c.col("a").as_type(int) + 10)
        .chain(
            Table.from_rows([["b"], ["2"]], header=True).update_all(int),
            fill_value=False,
        )
        .into_iter_rows(tuple, include_header=True)
    )
    assert result == [
        ("a", "b"),
        (11, False),
        (False, 2),
    ]

    result = list(
        Table.from_rows([["a"], ["1"]], header=True)
        .chain(Table.from_rows([["a"], ["2"]], header=True))
        .into_iter_rows(include_header=True)
    )
    assert result == [
        ("a",),
        ("1",),
        ("2",),
    ]

    result = list(
        Table.from_rows([["a"], ["1"]], header=True)
        .update(a=c.col("a").as_type(int))
        .chain(Table.from_rows([["a"], ["2"]], header=True))
        .into_iter_rows()
    )
    assert result == [(1,), ("2",)]

    result = list(
        Table.from_rows([["a"], ["1"]], header=True)
        .chain(
            Table.from_rows([["a"], ["2"]], header=True).update(
                a=c.col("a").as_type(int)
            )
        )
        .into_iter_rows()
    )
    assert result == [("1",), (2,)]

    result = list(
        Table.from_rows([["a"], ["1"]], header=True)
        .update(a=c.col("a").as_type(int))
        .embed_conversions()
        .chain(Table.from_rows([["a"], ["2"]], header=True))
        .into_iter_rows()
    )
    assert result == [(1,), ("2",)]


def test_table_zip():
    result = list(
        Table.from_rows([["a", "b"], [1, 2]], header=True)
        .zip(
            Table.from_rows([["b", "a"], [4, 3], [6, 5]], header=True),
            fill_value=False,
        )
        .into_iter_rows(tuple, include_header=True)
    )
    assert result == [
        ("a", "b", "b", "a"),
        (1, 2, 4, 3),
        (False, False, 6, 5),
    ]

    result = list(
        Table.from_rows([["a"], ["1"], ["2"], ["3"]], header=True)
        .update_all(int, int)
        .zip(
            Table.from_rows([["a"], ["4"]], header=True).update(
                a=c.col("a").as_type(int)
            )
        )
        .into_iter_rows(tuple, include_header=True)
    )
    assert result == [
        ("a", "a"),
        (1, 4),
        (2, None),
        (3, None),
    ]


def test_table_explode():
    result = list(
        Table.from_rows(
            [["a", "b", "c"], [1, [2, 3], 10], [4, [5, 6], 20]], header=True
        )
        .explode("b")
        .into_iter_rows(dict)
    )
    assert result == [
        {"a": 1, "b": 2, "c": 10},
        {"a": 1, "b": 3, "c": 10},
        {"a": 4, "b": 5, "c": 20},
        {"a": 4, "b": 6, "c": 20},
    ]
    with pytest.raises(ValueError):
        (
            Table.from_rows([["a", "b"]], header=True)
            .explode("c")
            .into_iter_rows(dict)
        )


def test_table_wide_to_long():
    result = list(
        Table.from_rows([("a", "b", "c"), (1, 2, 3), (4, 5, 6)], header=True)
        .wide_to_long(
            col_for_names="metric",
            col_for_values="value",
            keep_cols=["a"],
        )
        .into_iter_rows(dict)
    )
    assert result == [
        {"a": 1, "metric": "b", "value": 2},
        {"a": 1, "metric": "c", "value": 3},
        {"a": 4, "metric": "b", "value": 5},
        {"a": 4, "metric": "c", "value": 6},
    ]

    result = list(
        Table.from_rows([("a", "b", "c"), (1, 2, 3), (4, 5, 6)], header=True)
        .wide_to_long(
            col_for_names="metric",
            col_for_values="value",
            prepare_name=lambda name: f"n_{name}",
            prepare_value=c("v_{}").call_method("format", c.this),
        )
        .into_iter_rows(dict)
    )
    assert result == [
        {"metric": "n_a", "value": "v_1"},
        {"metric": "n_b", "value": "v_2"},
        {"metric": "n_c", "value": "v_3"},
        {"metric": "n_a", "value": "v_4"},
        {"metric": "n_b", "value": "v_5"},
        {"metric": "n_c", "value": "v_6"},
    ]

    assert list(
        Table.from_rows(
            [
                {"name": "John", "height": 200, "age": 30},
            ]
        )
        .wide_to_long(
            col_for_names="metric", col_for_values="value", keep_cols=("name",)
        )
        .into_iter_rows(dict)
    ) == [
        {"name": "John", "metric": "height", "value": 200},
        {"name": "John", "metric": "age", "value": 30},
    ]


def test_table_pivot():
    data = [
        ("a", 1, "temp", 20),
        ("a", 1, "vel", 2.0),
        ("a", 1, "vel", 10.0),
        ("b", 1, "vel", 3.0),
        ("c", 1, "height", 7.0),
    ]
    result = list(
        Table.from_rows(data, header=("dim", "dim2", "param", "value"))
        .update(dim2=c.col("dim2") + 1)
        .pivot(
            rows=["dim", "dim2"],
            columns=["param"],
            values={
                "sum": c.ReduceFuncs.Sum(c.col("value")),
                "median": c.ReduceFuncs.Median(c.col("value")),
            },
            prepare_column_names="_".join,
        )
        .into_iter_rows(dict)
    )
    assert result == [
        {
            "dim": "a",
            "dim2": 2,
            "height_median": None,
            "height_sum": None,
            "temp_median": 20,
            "temp_sum": 20,
            "vel_median": 6.0,
            "vel_sum": 12.0,
        },
        {
            "dim": "b",
            "dim2": 2,
            "height_median": None,
            "height_sum": None,
            "temp_median": None,
            "temp_sum": None,
            "vel_median": 3.0,
            "vel_sum": 3.0,
        },
        {
            "dim": "c",
            "dim2": 2,
            "height_median": 7.0,
            "height_sum": 7.0,
            "temp_median": None,
            "temp_sum": None,
            "vel_median": None,
            "vel_sum": None,
        },
    ]
    result = list(
        Table.from_rows(
            [
                {"dept": 1, "year": 2023, "currency": "USD", "revenue": 100},
                {"dept": 1, "year": 2024, "currency": "USD", "revenue": 300},
                {"dept": 1, "year": 2024, "currency": "CNY", "revenue": 200},
                {"dept": 1, "year": 2024, "currency": "CNY", "revenue": 111},
            ]
        )
        .pivot(
            rows=["year", "dept"],
            columns=["currency"],
            values={
                "sum": c.ReduceFuncs.Sum(c.col("revenue")),
                "min": c.ReduceFuncs.Min(c.col("revenue")),
            },
        )
        .into_iter_rows(dict)
    )
    assert result == [
        {
            "CNY - min": None,
            "CNY - sum": None,
            "USD - min": 100,
            "USD - sum": 100,
            "dept": 1,
            "year": 2023,
        },
        {
            "CNY - min": 111,
            "CNY - sum": 311,
            "USD - min": 300,
            "USD - sum": 300,
            "dept": 1,
            "year": 2024,
        },
    ]

    result = list(
        Table.from_rows(
            [
                {"a": 1, "b": [1, 2], "c": 0},
                {"a": 2, "b": [1, 2], "c": 1},
                {"a": 3, "b": [1, 3], "c": 0},
                {"a": 4, "b": [1, 4], "c": 1},
            ]
        )
        .update(b=c.col("b").as_type(tuple))
        .explode("b")
        .update(d=c.col("b"))
        .drop("b")
        .pivot(
            rows=["c"],
            columns=["d"],
            values={
                "x": c.ReduceFuncs.Count(),
            },
        )
        .into_iter_rows(tuple, include_header=True)
    )
    assert result == [
        ("c", "1 - x", "2 - x", "3 - x", "4 - x"),
        (0, 2, 1, 1, None),
        (1, 2, 1, None, 1),
    ]
