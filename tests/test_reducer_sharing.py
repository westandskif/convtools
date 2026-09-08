from collections import deque

from convtools import conversion as c
from convtools._aggregations import SumReducer, _analyze_template_block
from convtools._base import BaseConversion

from .utils import get_code_str


def test_call_sharing_aggregate_and_group_by():
    calls = []

    def f(x):
        calls.append(x)
        return x

    data = [{"x": i} for i in range(10)]
    spec = c.aggregate(
        {
            "s": c.ReduceFuncs.Sum(c.call_func(f, c.item("x"))),
            "m": c.ReduceFuncs.Max(c.call_func(f, c.item("x"))),
        }
    )
    assert spec.execute(data) == {"s": 45, "m": 9}
    assert calls == [row["x"] for row in data]

    calls.clear()
    spec = c.group_by(c.item("g")).aggregate(
        {
            "g": c.item("g"),
            "s": c.ReduceFuncs.Sum(c.call_func(f, c.item("x"))),
            "m": c.ReduceFuncs.Max(c.call_func(f, c.item("x"))),
        }
    )
    grouped = [{"g": i % 2, "x": i} for i in range(10)]
    spec.execute(grouped)
    assert calls == [row["x"] for row in grouped]


def test_guard_laziness_and_shared_unguarded():
    def boom(x):
        if x is None:
            raise ValueError("excluded row")
        return x

    data = [None, 1, 2, None, 3]
    assert (
        c.aggregate(
            c.ReduceFuncs.Sum(
                c.call_func(boom, c.this), where=c.this.is_not(None)
            )
        ).execute(data)
        == 6
    )

    counts = []

    def counted(x):
        counts.append(x)
        return x

    data = [{"ok": True, "x": 1}, {"ok": False, "x": 2}, {"ok": True, "x": 3}]
    result = c.aggregate(
        {
            "all_": c.ReduceFuncs.Sum(c.call_func(counted, c.item("x"))),
            "ok": c.ReduceFuncs.Sum(
                c.call_func(counted, c.item("x")), where=c.item("ok")
            ),
        }
    ).execute(data)
    assert result == {"all_": 6, "ok": 4}
    assert counts == [1, 2, 3]


def test_init_only_laziness():
    calls = []

    def f(x):
        calls.append(x)
        return x

    data = [
        {"g": 1, "k": "a", "x": 10},
        {"g": 1, "k": "a", "x": 11},
        {"g": 1, "k": "b", "x": 12},
        {"g": 2, "k": "a", "x": 20},
        {"g": 2, "k": "a", "x": 21},
    ]
    result = (
        c.group_by(c.item("g"))
        .aggregate(
            {
                "g": c.item("g"),
                "first": c.ReduceFuncs.First(c.call_func(f, c.item("x"))),
                "sum": c.ReduceFuncs.Sum(c.item("x")),
            }
        )
        .execute(data)
    )
    assert result == [
        {"g": 1, "first": 10, "sum": 33},
        {"g": 2, "first": 20, "sum": 41},
    ]
    assert calls == [10, 20]

    calls.clear()
    result = (
        c.group_by(c.item("g"))
        .aggregate(
            {
                "g": c.item("g"),
                "d": c.ReduceFuncs.DictFirst(
                    c.item("k"), c.call_func(f, c.item("x"))
                ),
            }
        )
        .execute(data)
    )
    assert result == [
        {"g": 1, "d": {"a": 10, "b": 12}},
        {"g": 2, "d": {"a": 20}},
    ]
    assert calls == [10, 12, 20]


def test_prefix_sharing_getitem_and_temps():
    class Counting(list):
        def __init__(self, inner):
            super().__init__(inner)
            self.n = 0

        def __getitem__(self, key):
            self.n += 1
            value = list.__getitem__(self, key)
            if isinstance(value, list) and not isinstance(value, Counting):
                value = Counting(value)
                self[key] = value
            return value

    nested = Counting([[None, [None, None, [None, None, None, 1]]]])
    result = c.aggregate(
        {
            "deep": c.ReduceFuncs.Sum(c.item(0, 1, 2, 3)),
            "prefix": c.ReduceFuncs.Max(c.item(0, 1, 2)),
        }
    ).execute([nested])
    assert result == {"deep": 1, "prefix": [None, None, None, 1]}
    assert nested.n == 1

    c_obj_1 = c.item(*range(50))
    c_obj_2 = c.item(*range(100))
    conv = c.aggregate(
        (c.ReduceFuncs.Sum(c_obj_1),)
        + tuple(c.ReduceFuncs.Sum(c_obj_2.item(key)) for key in "abcdefghijk"),
    )
    code_str = get_code_str(conv.gen_converter(debug=False))
    assert (
        "_tmp0_ = row_[0][1][2][3][4][5][6][7][8][9][10][11][12][13][14][15][16][17][18][19][20][21][22][23][24][25][26][27][28][29][30][31][32][33][34][35][36][37][38][39][40][41][42][43][44][45][46][47][48][49]"
        in code_str
        and "_tmp1_ = _tmp0_[50][51][52][53][54][55][56][57][58][59][60][61][62][63][64][65][66][67][68][69][70][71][72][73][74][75][76][77][78][79][80][81][82][83][84][85][86][87][88][89][90][91][92][93][94][95][96][97][98][99]"
        in code_str
        and "_tmp2_" not in code_str
    )


def test_where_value_and_signature_sharing():
    class CountingDict(dict):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.n = 0

        def __getitem__(self, key):
            self.n += 1
            return super().__getitem__(key)

    data = [CountingDict({"a": 1, "x": 10}), CountingDict({"a": 1, "x": 20})]
    result = (
        c.group_by(c.item("a"))
        .aggregate(
            {
                "a": c.item("a"),
                "s": c.ReduceFuncs.Sum(c.item("a")),
            }
        )
        .execute(data)
    )
    assert result == [{"a": 1, "s": 2}]
    assert data[0].n == 1
    assert data[1].n == 1

    counts = []

    def counted(x):
        counts.append(x)
        return x > 0

    result = c.aggregate(
        {
            "n": c.ReduceFuncs.Count(),
            "s": c.ReduceFuncs.Sum(
                c.call_func(counted, c.this),
                where=c.call_func(counted, c.this),
            ),
        }
    ).execute([1, -1, 2])
    assert result == {"n": 3, "s": 2}
    assert counts == [1, -1, 2]


def test_custom_reduce_shares_with_sum():
    calls = []

    def f(x):
        calls.append(x)
        return x

    def add(acc, value):
        return acc + value

    result = c.aggregate(
        {
            "s": c.ReduceFuncs.Sum(c.call_func(f, c.this)),
            "r": c.reduce(add, c.call_func(f, c.this), initial=0),
        }
    ).execute([1, 2, 3])
    assert result == {"s": 6, "r": 6}
    assert calls == [1, 2, 3]


def test_aggregate_two_loop_skips_init_only_values():
    first_calls = []
    sum_calls = []

    def first_f(x):
        first_calls.append(x)
        return x

    def sum_f(x):
        sum_calls.append(x)
        return x

    data = list(range(5))
    result = c.aggregate(
        {
            "first": c.ReduceFuncs.First(c.call_func(first_f, c.this)),
            "s": c.ReduceFuncs.Sum(c.call_func(sum_f, c.this)),
            "m": c.ReduceFuncs.Max(c.this, where=c.this > 2),
        }
    ).execute(data)
    assert result == {"first": 0, "s": 10, "m": 4}
    assert first_calls == [0]
    assert sum_calls == [0, 1, 2, 3, 4]


def test_single_use_has_no_temporary():
    code_str = get_code_str(
        c.aggregate(c.ReduceFuncs.Sum(c.item("a"))).gen_converter()
    )
    assert "_tmp" not in code_str

    code_str = get_code_str(
        c.aggregate(
            c.ReduceFuncs.DictCountDistinct(
                c.this,
                c.item("v").add_hint(BaseConversion.OutputHints.NOT_NONE),
            )
        ).gen_converter()
    )
    assert "_tmp" not in code_str

    code_str = get_code_str(
        c.aggregate(
            c.ReduceFuncs.DictCountDistinct(c.this, c.item("v"))
        ).gen_converter()
    )
    assert "_tmp0_" in code_str

    code_str = get_code_str(
        c.aggregate(
            c.ReduceFuncs.DictCountDistinct(c.item("k"), c.item("v"))
        ).gen_converter()
    )
    assert "_tmp" in code_str


def test_lambda_with_rebinding_param_is_not_rewritten():
    R = c.ReduceFuncs
    key = c.inline_expr("(lambda row_: row_['a'])({})")
    conv = c.aggregate(
        {
            "s": R.Sum(key.pass_args(c.this)),
            "t": R.Sum(c.item("a")),
            "m": R.Max(c.item("a")),
        }
    )
    converter = conv.gen_converter(debug=True)
    assert converter([{"a": 1}, {"a": 2}]) == {"s": 3, "t": 3, "m": 2}
    code_str = get_code_str(converter)
    assert (
        "lambda row_: row_['a']" in code_str
        or 'lambda row_: row_["a"]' in code_str
    )
    for line in code_str.splitlines():
        if "lambda" in line:
            assert "_tmp" not in line.split("lambda", 1)[1]


def test_piped_maxrow_does_not_share_row_slots():
    R = c.ReduceFuncs
    data = [{"a": 10, "b": 20}]
    spec = c.aggregate(
        (
            c.item("a").pipe(R.MaxRow(1)),
            c.item("b").pipe(R.MaxRow(1)),
        )
    )
    assert spec.execute(data) == (10, 20)
    code_str = get_code_str(spec.gen_converter())
    assert "agg_data__v0" in code_str
    assert "agg_data__v1" in code_str

    same = c.aggregate(
        {
            "a": R.MaxRow(c.item("x")),
            "b": R.MaxRow(c.item("x")),
        }
    )
    rows = [{"x": 1, "k": "first"}, {"x": 2, "k": "second"}]
    result = same.execute(rows)
    assert result["a"] is result["b"]
    assert result["a"]["k"] == "second"
    same_code = get_code_str(same.gen_converter())
    assert "agg_data__v0" in same_code
    assert "agg_data__v1" not in same_code


def test_if_else_eagerness_is_intersection():
    eager, _ = _analyze_template_block(
        (
            "if %(result)s < 0:",
            "    %(result)s = %(value0)s",
            "else:",
            "    %(result)s = 0",
        ),
        1,
    )
    assert eager == [False]

    eager, _ = _analyze_template_block(
        (
            "if %(value0)s in %(result)s:",
            "    %(result)s[%(value0)s] += 1",
            "else:",
            "    %(result)s[%(value0)s] = %(value1)s",
        ),
        2,
    )
    assert eager == [True, False]

    eager, _ = _analyze_template_block(
        (
            "if %(value0)s not in %(result)s:",
            "    %(result)s[%(value0)s] = { %(value1)s }",
            "else:",
            "    %(result)s[%(value0)s].add(%(value1)s)",
        ),
        2,
    )
    assert eager == [True, True]

    eager, _ = _analyze_template_block(
        (
            "if %(result)s < 0:",
            "    %(result)s = %(value0)s",
            "elif %(result)s > 10:",
            "    %(result)s = %(value1)s",
            "else:",
            "    %(result)s = %(value2)s",
        ),
        3,
    )
    assert eager == [False, False, False]

    eager, _ = _analyze_template_block(
        (
            "if %(result)s < 0:",
            "    %(result)s = %(value0)s",
            "elif %(result)s > 10:",
            "    %(result)s = %(value0)s",
            "else:",
            "    %(result)s = %(value0)s",
        ),
        1,
    )
    assert eager == [True]


class _OneBranchValue(SumReducer):
    reduce_lines = (
        "if %(result)s < 0:",
        "    %(result)s = %(value0)s",
        "else:",
        "    %(result)s = 0",
    )


def test_one_branch_value_is_not_hoisted():
    spec = c.group_by(c.item("g")).aggregate(
        {
            "g": c.item("g"),
            "v": _OneBranchValue(c.item("x") + c.item("x")),
        }
    )
    assert spec.execute([{"g": 1, "x": 1}, {"g": 1}]) == [{"g": 1, "v": 0}]
