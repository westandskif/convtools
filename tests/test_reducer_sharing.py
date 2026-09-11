import ast
import sys
import time
from collections import deque

import pytest

from convtools import conversion as c
from convtools._base import BaseConversion
from convtools._reducer_sharing import (
    _analyze_template_block,
    _check_temp_order,
    _replace_by_key,
    _structural_keys,
)
from convtools._reducers import SumReducer

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
    converter = conv.gen_converter()
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

    eager, weights = _analyze_template_block(("pass",), 1)
    assert eager == [False]
    assert weights == [0]


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


def _assert_comp_iter_is_tmp_not_target(code_str, expected_target=None):
    found = False
    for line in code_str.splitlines():
        if " for " not in line or " in " not in line or "lambda" in line:
            continue
        if "{" not in line and "[" not in line:
            continue
        found = True
        after_for = line.split(" for ", 1)[1]
        target, rest = after_for.split(" in ", 1)
        if expected_target is None:
            assert "_tmp" not in target
        else:
            assert target.strip() == expected_target
        assert "_tmp" in rest
    assert found


def test_lambda_defaults_are_eager_and_rewritten():
    R = c.ReduceFuncs
    data = [{"a": {"b": 1}}, {"a": {"b": 2}}]
    spec = c.aggregate(
        {
            "s": R.Sum(
                c.inline_expr("(lambda y={0}: y)()").pass_args(
                    c.item("a", "b")
                )
            ),
            "m": R.Max(c.item("a", "b")),
        }
    )
    assert spec.execute(data) == {"s": 3, "m": 2}
    code_str = get_code_str(spec.gen_converter())
    assert (
        '_tmp0_ = row_["a"]["b"]' in code_str
        or "_tmp0_ = row_['a']['b']" in code_str
    )
    assert "lambda y=_tmp0_:" in code_str
    assert "_tmp1_" not in code_str

    spec = c.aggregate(
        {
            "s": R.Sum(
                c.inline_expr("(lambda *, y={0}: y)()").pass_args(
                    c.item("a", "b")
                )
            ),
            "m": R.Max(c.item("a", "b")),
        }
    )
    assert spec.execute(data) == {"s": 3, "m": 2}
    code_str = get_code_str(spec.gen_converter())
    assert "lambda *, y=_tmp0_:" in code_str
    assert "_tmp1_" not in code_str

    spec = c.aggregate(
        {
            "arr": R.Array(
                c.inline_expr("(lambda *, z, y={0}: y)").pass_args(
                    c.item("a", "b")
                )
            ),
            "m": R.Max(c.item("a", "b")),
        }
    )
    result = spec.execute(data)
    assert [fn(z=0) for fn in result["arr"]] == [1, 2]
    assert result["m"] == 2
    code_str = get_code_str(spec.gen_converter())
    assert "lambda *, z, y=_tmp0_:" in code_str
    assert "_tmp1_" not in code_str


def test_keyword_argument_calls_share():
    R = c.ReduceFuncs

    def f(x):
        return x

    spec = c.aggregate(
        {
            "s": R.Sum(c.call_func(f, x=c.item("a", "b"))),
            "m": R.Max(c.item("a", "b")),
        }
    )
    data = [{"a": {"b": 1}}, {"a": {"b": 2}}]
    assert spec.execute(data) == {"s": 3, "m": 2}
    code_str = get_code_str(spec.gen_converter())
    assert "_tmp0_" in code_str
    assert "x=_tmp0_" in code_str
    assert "_tmp1_" not in code_str


def test_comprehension_first_iterable_shares():
    R = c.ReduceFuncs
    data = [{"k": [("a", 1), ("b", 2)]}, {"k": [("c", 3)]}]
    spec = c.aggregate(
        {
            "arr": R.Array(
                c.inline_expr("{{k: v for k, v in {0}}}").pass_args(
                    c.item("k")
                )
            ),
            "m": R.Max(c.item("k")),
        }
    )
    assert spec.execute(data) == {
        "arr": [{"a": 1, "b": 2}, {"c": 3}],
        "m": [("c", 3)],
    }
    code_str = get_code_str(spec.gen_converter())
    _assert_comp_iter_is_tmp_not_target(code_str)
    assert "_tmp1_" not in code_str

    spec = c.aggregate(
        {
            "arr": R.Array(
                c.inline_expr("[k for k in {0}]").pass_args(c.item("k"))
            ),
            "m": R.Max(c.item("k")),
        }
    )
    assert spec.execute(data) == {
        "arr": [[("a", 1), ("b", 2)], [("c", 3)]],
        "m": [("c", 3)],
    }
    code_str = get_code_str(spec.gen_converter())
    _assert_comp_iter_is_tmp_not_target(code_str)
    assert "_tmp1_" not in code_str


@pytest.mark.skipif(sys.version_info < (3, 8), reason="walrus requires 3.8+")
def test_named_expr_in_reducer_value_does_not_crash():
    R = c.ReduceFuncs
    spec = c.aggregate(
        {
            "a": R.Array(
                c.item("x")
                + c.inline_expr("(_v := {0})").pass_args(c.item("x"))
            ),
            "s": R.Sum(c.item("x")),
        }
    )
    data = [{"x": 1}, {"x": 2}]
    assert spec.execute(data) == {"a": [2, 4], "s": 3}
    code_str = get_code_str(spec.gen_converter())
    assert "_tmp0_" in code_str


class _Idle(SumReducer):
    reduce_lines = ("pass",)


def test_unrecognized_template_stmt_contributes_zero():
    spec = c.group_by(c.item("g")).aggregate(
        {
            "g": c.item("g"),
            "v": _Idle(c.item("x")),
        }
    )
    assert spec.execute([{"g": 1, "x": 1}, {"g": 1, "x": 99}]) == [
        {"g": 1, "v": 1}
    ]


def test_shared_next_call_once_across_array_and_sum():
    next_it = c.call_func(next, c.input_arg("it"))
    spec = c.aggregate(
        {
            "a": c.ReduceFuncs.Array(next_it),
            "b": c.ReduceFuncs.Sum(next_it),
        }
    )
    assert spec.execute([None, None, None], it=iter(range(6))) == {
        "a": [0, 1, 2],
        "b": 3,
    }

    spec = c.group_by(c.item("g")).aggregate(
        {
            "g": c.item("g"),
            "a": c.ReduceFuncs.Array(next_it),
            "b": c.ReduceFuncs.Sum(next_it),
        }
    )
    data = [{"g": 1}, {"g": 1}, {"g": 1}]
    assert spec.execute(data, it=iter(range(6))) == [
        {"g": 1, "a": [0, 1, 2], "b": 3}
    ]


def test_shared_call_aliases_same_object():
    listed = c.call_func(list, c.this)
    result = c.aggregate(
        {
            "a": c.ReduceFuncs.First(listed),
            "b": c.ReduceFuncs.Array(listed),
        }
    ).execute([[1], [2]])
    assert result["a"] == [1]
    assert result["b"] == [[1], [2]]
    assert result["a"] is result["b"][0]


def test_unguarded_reducers_evaluated_before_guarded():
    with pytest.raises(KeyError, match="missing_a"):
        c.aggregate(
            {
                "a": c.ReduceFuncs.Sum(c.item("missing_a")),
                "b": c.ReduceFuncs.Sum(
                    c.item("missing_b"), where=c.item("x") > 0
                ),
            }
        ).execute([{"x": 1}])


def test_ternary_max_guard_is_parenthesized_or_hoisted():
    spec = c.aggregate(
        c.ReduceFuncs.Max(c.if_(c.item("ok"), c.item("x"), c.item("y")))
    )
    data = [
        {"ok": True, "x": 3, "y": 1},
        {"ok": False, "x": 0, "y": 9},
    ]
    converter = spec.gen_converter()
    assert converter(data) == 9
    code_str = get_code_str(converter)
    assert "else" not in code_str.split("is not None")[0].split("if ")[-1]
    assert "_tmp" in code_str or "(row_" in code_str


def test_piped_maxrow_minrow_share_row_expr():
    class CountingDict(dict):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.n = 0

        def __getitem__(self, key):
            self.n += 1
            return super().__getitem__(key)

    def rows():
        return [
            CountingDict({"a": CountingDict({"x": 1, "k": "first"})}),
            CountingDict({"a": CountingDict({"x": 3, "k": "second"})}),
            CountingDict({"a": CountingDict({"x": 2, "k": "mid"})}),
        ]

    max_spec = c.aggregate(c.item("a").pipe(c.ReduceFuncs.MaxRow(c.item("x"))))
    min_spec = c.aggregate(c.item("a").pipe(c.ReduceFuncs.MinRow(c.item("x"))))
    max_data = rows()
    min_data = rows()
    assert max_spec.execute(max_data)["k"] == "second"
    assert [row.n for row in max_data] == [1, 1, 1]
    assert min_spec.execute(min_data)["k"] == "first"
    assert [row.n for row in min_data] == [1, 1, 1]

    for spec in (max_spec, min_spec):
        code_str = get_code_str(spec.gen_converter())
        loop_bodies = code_str.split("for row_ in")[1:]
        assert loop_bodies
        for body in loop_bodies:
            assert body.count('row_["a"]') + body.count("row_['a']") == 1

    # %(row)s is not eager in MaxRow/MinRow reduce (only the comparison body).
    losing = [{"a": 1}, {}]
    assert (
        c.aggregate(
            (c.item("a") + c.item("a")).pipe(c.ReduceFuncs.MaxRow(1))
        ).execute(losing)
        == 2
    )
    assert (
        c.aggregate(
            (c.item("a") + c.item("a")).pipe(c.ReduceFuncs.MinRow(1))
        ).execute(losing)
        == 2
    )


def test_user_tmp_name_in_lambda_is_not_replaced():
    data = [{"x": 1, "y": 6}, {"x": 2, "y": 7}]
    spec = c.aggregate(
        {
            "s": c.ReduceFuncs.Sum(c.item("x")),
            "m": c.ReduceFuncs.Max(c.item("x")),
            "b": c.ReduceFuncs.Array(
                c.inline_expr("(lambda _tmp0_: _tmp0_ * 10)({v})").pass_args(
                    v=c.item("y")
                )
            ),
            "t": c.ReduceFuncs.Sum(c.item("y")),
        }
    )
    converter = spec.gen_converter()
    assert converter(data)["b"] == [60, 70]
    code_str = get_code_str(converter)
    assert "lambda _tmp0_:" in code_str
    assert "(lambda _tmp0_: _tmp0_ * 10)(_tmp1_)" in code_str


def test_user_tmp_name_in_comprehension_target_is_not_replaced():
    data = [{"x": 1, "y": [6, 7]}, {"x": 2, "y": [8]}]
    spec = c.aggregate(
        {
            "s": c.ReduceFuncs.Sum(c.item("x")),
            "m": c.ReduceFuncs.Max(c.item("x")),
            "b": c.ReduceFuncs.Array(
                c.inline_expr("[_tmp0_ * 10 for _tmp0_ in {v}]").pass_args(
                    v=c.item("y")
                )
            ),
            "t": c.ReduceFuncs.Sum(c.item("y")),
        }
    )
    converter = spec.gen_converter()
    assert converter(data)["b"] == [[60, 70], [80]]
    code_str = get_code_str(converter)
    _assert_comp_iter_is_tmp_not_target(code_str, expected_target="_tmp0_")
    assert "for _tmp0_ in _tmp1_" in code_str


def _marked_tmp_ref_tree(code):
    tree = ast.parse(code, mode="eval").body
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id.startswith("_tmp"):
            node._cse_temp = True
    return tree


def test_check_temp_order_forward_ref_raises():
    left = _marked_tmp_ref_tree("_tmp1_ + 1")
    right = _marked_tmp_ref_tree("_tmp0_ + 1")
    with pytest.raises(
        RuntimeError, match="reducer-sharing temp .* references a later temp"
    ):
        _check_temp_order([("_tmp0_", left), ("_tmp1_", right)])


def test_analyze_template_block_empty_lines():
    eager, weights = _analyze_template_block((), 2)
    assert eager == [False, False]
    assert weights == [0, 0]
    eager, weights, row_eager, row_weight = _analyze_template_block(
        (), 1, include_row=True
    )
    assert eager == [False]
    assert weights == [0]
    assert row_eager is False
    assert row_weight == 0


def test_replace_by_key_unmatched_comprehension_iter():
    tree = ast.parse("[x for x in y]", mode="eval").body
    keys = _structural_keys(tree, {})
    new_tree, changed = _replace_by_key(tree, {}, keys)
    assert changed is False
    assert new_tree is tree


def test_contributor_unchanged_replace_is_skipped(monkeypatch):
    import convtools._reducer_sharing as rs

    real = rs._replace_by_key
    calls = []

    def wrapped(node, key_to_name, keys):
        tree, changed = real(node, key_to_name, keys)
        if not calls:
            calls.append(True)
            return node, False
        return tree, changed

    monkeypatch.setattr(rs, "_replace_by_key", wrapped)
    spec = c.aggregate(
        {
            "s": c.ReduceFuncs.Sum(c.item("a") + 1),
            "m": c.ReduceFuncs.Max(c.item("a") + 1),
        }
    )
    assert spec.execute([{"a": 1}, {"a": 2}]) == {"s": 5, "m": 3}


def _shared_pairs_spec(n):
    reducers = {}
    for i in range(n):
        expr = c.item(i) + 1
        reducers["s{}".format(i)] = c.ReduceFuncs.Sum(expr)
        reducers["m{}".format(i)] = c.ReduceFuncs.Max(expr)
    return c.aggregate(reducers)


def test_sharing_plan_scales_roughly_linearly():
    def plan_seconds(n):
        spec = _shared_pairs_spec(n)
        started = time.perf_counter()
        spec.gen_converter()
        return time.perf_counter() - started

    t400 = plan_seconds(400)
    t800 = plan_seconds(800)
    print(
        "sharing plan 400 pairs: {:.4f}s; 800 pairs: {:.4f}s".format(
            t400, t800
        )
    )
    assert t800 < t400 * 3 + 0.5


def _spec_lambda_bind():
    return c.aggregate(
        {
            "s": c.ReduceFuncs.Sum(c.item("x")),
            "m": c.ReduceFuncs.Max(c.item("x")),
            "b": c.ReduceFuncs.Array(
                c.inline_expr("(lambda _tmp0_: _tmp0_ * 10)({v})").pass_args(
                    v=c.item("y")
                )
            ),
            "t": c.ReduceFuncs.Sum(c.item("y")),
        }
    )


def _spec_comprehension_bind():
    return c.aggregate(
        {
            "arr": c.ReduceFuncs.Array(
                c.inline_expr("[_tmp0_ for _tmp0_ in {0}]").pass_args(
                    c.item("k")
                )
            ),
            "m": c.ReduceFuncs.Max(c.item("k")),
        }
    )


def _spec_where_guards():
    return c.aggregate(
        {
            "all_": c.ReduceFuncs.Sum(c.item("x")),
            "ok": c.ReduceFuncs.Sum(c.item("x"), where=c.item("ok")),
        }
    )


def _spec_nested_aggregate():
    inner = c.item("xs").pipe(
        c.aggregate(
            {
                "s": c.ReduceFuncs.Sum(c.item("a")),
                "m": c.ReduceFuncs.Max(c.item("a")),
            }
        )
    )
    return c.aggregate(
        {
            "inner": c.ReduceFuncs.Array(inner),
            "n": c.ReduceFuncs.Count(),
        }
    )


def _spec_piped_deferred():
    return c.aggregate(
        (
            c.item("a").pipe(c.ReduceFuncs.MaxRow(c.item("x"))),
            c.item("a").pipe(c.ReduceFuncs.MinRow(c.item("x"))),
        )
    )


def _spec_group_by_signature():
    return c.group_by(c.item("g")).aggregate(
        {
            "g": c.item("g"),
            "s": c.ReduceFuncs.Sum(c.item("g")),
            "x": c.ReduceFuncs.Sum(c.item("x")),
            "m": c.ReduceFuncs.Max(c.item("x")),
        }
    )


@pytest.mark.parametrize(
    "make_spec, data",
    [
        (
            _spec_lambda_bind,
            [{"x": 1, "y": 6}, {"x": 2, "y": 7}],
        ),
        (
            _spec_comprehension_bind,
            [{"k": [("a", 1), ("b", 2)]}, {"k": [("c", 3)]}],
        ),
        (
            _spec_where_guards,
            [
                {"ok": True, "x": 1},
                {"ok": False, "x": 2},
                {"ok": True, "x": 3},
            ],
        ),
        (
            _spec_nested_aggregate,
            [{"xs": [{"a": 1}, {"a": 2}]}, {"xs": [{"a": 3}]}],
        ),
        (
            _spec_piped_deferred,
            [
                {"a": {"x": 1, "k": "first"}},
                {"a": {"x": 3, "k": "second"}},
                {"a": {"x": 2, "k": "mid"}},
            ],
        ),
        (
            _spec_group_by_signature,
            [{"g": 1, "x": 10}, {"g": 1, "x": 11}, {"g": 2, "x": 20}],
        ),
    ],
)
def test_sharing_on_off_same_output(monkeypatch, make_spec, data):
    with_sharing = make_spec().execute(data)
    monkeypatch.setattr(
        "convtools._aggregations.analyze_scope", lambda *a, **k: 0
    )
    without_sharing = make_spec().execute(data)
    assert with_sharing == without_sharing


def _deep_getitem_row(value, depth):
    obj = value
    for i in range(depth - 1, -1, -1):
        row = [0] * (i + 1)
        row[i] = obj
        obj = row
    return obj


def test_deep_shared_getitem_compiles():
    depth = 500
    chain = c.item(*range(depth))
    spec = c.aggregate(
        {
            "a": c.ReduceFuncs.Sum(chain),
            "b": c.ReduceFuncs.Max(chain),
        }
    )
    converter = spec.gen_converter()
    data = [_deep_getitem_row(1, depth), _deep_getitem_row(2, depth)]
    assert converter(data) == {"a": 3, "b": 2}


def test_analyze_scope_recursion_fallback(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RecursionError

    monkeypatch.setattr("convtools._aggregations.analyze_scope", boom)
    spec = c.aggregate(
        {"a": c.ReduceFuncs.Sum(c.this), "b": c.ReduceFuncs.Max(c.this)}
    )
    converter = spec.gen_converter()
    assert converter([1, 2, 3]) == {"a": 6, "b": 3}
    assert "_tmp" not in get_code_str(converter)
