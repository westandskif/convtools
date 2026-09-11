import math
from collections import deque, namedtuple
from datetime import date
from decimal import Decimal
from types import GeneratorType, SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

from convtools import conversion as c
from convtools._base import (
    GetAttr,
    GetItem,
    LazyEscapedString,
    NaiveConversion,
    Namespace,
)
from convtools._utils import Code

from .utils import get_code_str


def test_docs():
    print(1 < c.naive(2))


def test_naive_conversion():
    d = {1: 2}
    assert c.naive(d).gen_converter(debug=True)(1) == d
    assert c.naive("abc").gen_converter()(1) == "abc"
    assert c.naive(1).gen_converter()(10) == 1
    assert c.naive(True).gen_converter()(10) is True
    assert c.naive(False).gen_converter()(10) is False
    assert c.naive(None).gen_converter()(10) is None
    assert c.naive("1").as_type(int).gen_converter()(10) == 1
    assert c.naive(1).gen_converter(method=True)(None, 10) == 1

    assert "%abc" not in get_code_str(c.naive("%abc").gen_converter())
    assert "{abc" not in get_code_str(c.naive("{abc").gen_converter())
    assert "abc" in get_code_str(c.naive("abc").gen_converter())

    assert c.naive({1: 2}).item(c.this).execute(1) == 2

    def f1(x):
        return x + 1

    assert "f1" in get_code_str(c.naive(f1).call(1).gen_converter())
    code_str = get_code_str(
        c.naive(f1, name_prefix="prefix").call(1).gen_converter()
    )
    assert "f1" not in code_str and "prefix" in code_str

    def none__(x):
        return x

    # warm-up naming would otherwise produce "__none__", clashing with the
    # fixed ctx name of the same spelling
    assert (
        c.naive(none__)
        .call(c.this)
        .pipe(c.aggregate(c.ReduceFuncs.Count()))
        .execute([1, 2])
        == 2
    )


def test_naive_int_literals_are_parenthesized():
    """Bare ints break ** precedence, attr/method access, and inline_expr."""
    assert (c.naive(-2) ** 2).execute(None) == 4
    assert c.naive(5).call_method("bit_length").execute(None) == 3
    assert c.naive(-5).call_method("bit_length").execute(None) == 3
    assert c.naive(5).attr("real").execute(None) == 5
    assert c.inline_expr("{0}.bit_length()").pass_args(5).execute(None) == 3
    assert "True" in get_code_str(c.naive(True).gen_converter())
    assert "(True)" not in get_code_str(c.naive(True).gen_converter())
    assert "None" in get_code_str(c.naive(None).gen_converter())
    assert "(None)" not in get_code_str(c.naive(None).gen_converter())


def test_naive_equal_but_distinct_values_keep_identity():
    r = c.tuple(c.naive(1.0), c.naive(Decimal("1"))).execute(None)
    assert type(r[0]) is float and type(r[1]) is Decimal
    assert r[0] == 1.0 and r[1] == Decimal("1")

    r = c.tuple(c.naive((1, 2)), c.naive((True, 2))).execute(None)
    assert type(r[0][0]) is int and type(r[1][0]) is bool
    assert r[0] == (1, 2) and r[1] == (True, 2)

    r = c.tuple(c.naive(-0.0), c.naive(0.0)).execute(None)
    assert math.copysign(1, r[0]) == -1.0 and math.copysign(1, r[1]) == 1.0

    r = c.tuple(c.item("k", default=1.0), c.naive(Decimal("1"))).execute({})
    assert type(r[0]) is float and type(r[1]) is Decimal


def test_gen_converter():
    class A:
        x = 10

        def __init__(self):
            self.x = 20

        conv1 = (c.this() + c.input_arg("self").attr("x")).gen_converter(
            method=True
        )

        conv3 = (c.this + c.input_arg("cls").attr("x")).gen_converter(
            class_method=True
        )

        conv5 = (
            c.this + c.input_arg("self").attr("x") + c.input_arg("n")
        ).gen_converter(signature="self, n=1000, data_=15")

        conv6 = staticmethod(
            (
                (c.this + c.call_func(sum, c.input_arg("args")))
                * c.input_arg("kwargs").call_method("get", "multiplicator", 1)
            ).gen_converter(signature="data_, *args, **kwargs")
        )

    with pytest.raises(ValueError):
        (
            Namespace(
                c.call_func(list).pipe(
                    c.if_(
                        LazyEscapedString("abc"),
                        c.this()
                        * LazyEscapedString("abc")
                        * c.input_arg("abc"),
                        c.this,
                    )
                ),
                {"abc": "(0 + 1)"},
            )
        ).execute(1, abc=10)

    assert A().conv1(100) == 120
    assert A.conv3(100) == 110

    with pytest.raises(c.ConversionException):
        c.input_arg("self").gen_converter()
    with pytest.raises(c.ConversionException):
        c.input_arg("cls").gen_converter()
    with pytest.raises(c.ConversionException):
        (c.this + c.input_arg("cls").attr("x")).gen_converter(method=True)
    with pytest.raises(c.ConversionException):
        (c.this + c.input_arg("self").attr("x")).gen_converter(
            class_method=True
        )
    with pytest.raises(c.ConversionException):
        c.input_arg("self").gen_converter(signature="data_='self'")
    with pytest.raises(c.ConversionException):
        c.input_arg("cls").gen_converter(signature="data_='cls'")
    with pytest.raises(SyntaxError):
        c.input_arg("self").gen_converter(signature="self data_")

    assert A().conv5() == 1035
    assert A().conv5(data_=7) == 1027
    assert A().conv5(n=100) == 135

    assert A.conv6(20) == 20
    assert A.conv6(20, 1, 2, 3) == 26
    assert A.conv6(20, 1, 2, 3, multiplicator=10) == 260

    assert (
        c.call_func(sum, c.this).gen_converter(signature="*data_")(1, 2, 3)
        == 6
    )
    assert (
        c.call_func(
            sum, c.iter(c.this + c.call_func(lambda: 10))
        ).gen_converter(signature="*data_")(1, 2, 3)
        == 36
    )
    assert (
        c.call_func(
            sum, c.iter(c.this + c.call_func(lambda: 10))
        ).gen_converter()((1, 2, 3))
        == 36
    )
    assert (
        c.call_func(
            lambda i: globals().__setitem__("A", 1) or sum(i), c.this
        ).gen_converter(signature="*data_")(1, 2, 3)
        == 6
    )
    assert c(
        {
            c.naive("-").call_method(
                "join", c.this.call_method("keys")
            ): c.call_func(sum, c.this.call_method("values"))
        }
    ).gen_converter(signature="**data_")(a=1, b=2, c=3) == {"a-b-c": 6}
    with pytest.raises(c.ConversionException):
        c.call_func(sum, c.input_arg("x")).gen_converter(signature="*data_")(
            1, 2, 3
        )
    with pytest.raises(c.ConversionException):
        c.this.gen_converter(method=True, class_method=True)

    class A:
        value = 10

        def __init__(self):
            self.value = 100

        @classmethod
        def patch(cls):
            cls.method = (
                c.this + c.escaped_string("cls").attr("value")
            ).gen_converter(class_method=True)
            cls.method_2 = (
                c.this + c.escaped_string("self").attr("value")
            ).gen_converter(method=True)

    A.patch()
    assert A.method(1) == 11
    assert A().method(1) == 11

    assert A().method_2(1) == 101
    with pytest.raises(TypeError):
        A.method_2(1)


def test_custom_converter_generation():
    class CustomConversion(c.BaseConversion):
        def gen_code_and_update_ctx(self, code_input, ctx):
            function_ctx = self.as_function_ctx(ctx)
            with function_ctx:
                function_ctx.add_arg("data_", c.this)
                function_ctx.add_kwarg("kwarg1", 10)
                function_ctx.add_kwarg("kwarg2", 100, left=True)

                code_args = function_ctx.get_def_all_args_code()
                assert code_args.find("kwarg1") > code_args.find("kwarg2")

                converter_name = self.gen_random_name("test_func", ctx)
                code = Code()
                code.add_line(f"def {converter_name}({code_args}):", 1)
                code.add_line("return data_ + kwarg1 + kwarg2", 0)
                conversion = function_ctx.gen_conversion(
                    converter_name, code.to_string(0)
                )
            return function_ctx.call_with_all_args(
                conversion
            ).gen_code_and_update_ctx(code_input, ctx)

    assert CustomConversion().execute(7, debug=True) == 117


def test_tmp():
    d = {1: 2, 10: {"test": 15, 2: 777}, 100: {"test2": 200}}
    assert (
        c.item(10)
        .item("testt", default=c.call_func(lambda x: x, 0))
        .gen_converter(debug=True)(d)
        == 0
    )


def test_naive_conversion_item():
    d = {1: 2, 10: {"test": 15, 2: 777}, 100: {"test2": 200}}
    assert c.naive(d).item(1).execute(100) == 2
    assert c.item().execute(3) == 3
    assert c.item(1).gen_converter()(d) == 2
    assert c.item(10, "test").gen_converter()(d) == 15

    assert c.item(11, "test", default=77).gen_converter()(d) == 77
    assert (
        c.item(11, "test", default=c.call_func(lambda: 77)).gen_converter()(d)
        == 77
    )
    assert (
        c.item(
            10, c.input_arg("arg1"), default=c.input_arg("arg2")
        ).gen_converter()(d, arg1="test", arg2=77)
        == 15
    )
    assert (
        c.item(
            10, c.input_arg("arg1"), default=c.input_arg("arg2")
        ).gen_converter()(d, arg1="tst", arg2=77)
        == 77
    )
    assert (
        c.item(11, "test", default=77).gen_converter(method=True)(None, d)
        == 77
    )
    assert c.item(10, "testt", default=77).gen_converter()(d) == 77
    assert c.item(10).item("testt", default=77).gen_converter()(d) == 77

    assert c.item(10, "testt", default=c.this).gen_converter()(d) == d
    assert (
        c.item(10, "testt", default=c.call_func(int)).gen_converter()(d) == 0
    )
    assert (
        c.item(
            10, "testt", default=c.call_func(lambda x: x, 0)
        ).gen_converter()(d)
        == 0
    )
    assert (
        c.item(10)
        .item("testt", default=c.call_func(lambda x: x, 0))
        .gen_converter(debug=True)(d)
        == 0
    )
    assert (
        c.item(10, "testt", default=c.input_arg("a")).gen_converter()(d, a=-1)
        == -1
    )

    assert c.item(10, c.item(1)).gen_converter()(d) == 777
    assert c.item(10).item(2).gen_converter()(d) == 777

    assert (
        c.item("k", default=c.input_arg("fb").item("k") + 1).execute(
            {"k": 1}, fb={}
        )
        == 1
    )
    assert (
        c.item("k", default=c.input_arg("fb").item("k") + 1).execute(
            {}, fb={"k": 1}
        )
        == 2
    )
    assert (
        c.item("k", default=c.list(c.naive({}).item("x"))).execute({"k": 1})
        == 1
    )
    assert c.item(c.input_arg("d").item("k"), default=0).execute({}, d={}) == 0
    assert (
        c.item("k", default=c.input_arg("fb").item("k")).execute(
            {}, fb={"k": 7}
        )
        == 7
    )

    assert c.item("a", default=c.label("prev")).execute({"a": 1}) == 1
    labeled_item = c.this.pipe(
        c.item("a", default=c.label("prev")), label_input="prev"
    )
    assert labeled_item.execute({"a": 1}) == 1
    assert labeled_item.execute({"b": 2}) == {"b": 2}

    assert c.item("a", default=c.label("prev")).hardcoded_version is None
    const_item = c.item("a", default=1)
    assert isinstance(const_item.default, NaiveConversion)

    converter = c.item(0, 0, 0, default=1).gen_converter()
    assert converter([[[2]]]) == 2
    assert converter([[[]]]) == 1

    with pytest.raises(KeyError):
        c.naive(d).item(11).gen_converter()(100)
    with pytest.raises(IndexError):
        c.naive([]).item(11).gen_converter()(100)
    with pytest.raises(TypeError):
        c.naive(None).item(11).gen_converter()(100)
    with pytest.raises(TypeError):
        iter(c.naive(None))

    assert (
        c.naive(d).item(100).item("test2").gen_converter(debug=False)(100)
        == 200
    )
    assert (
        c.naive(d).item(c.this, "test2").gen_converter(debug=False)(100) == 200
    )
    assert (
        c.naive(d)
        .item(100, default=30)
        .item("test2", default=30)
        .gen_converter(debug=False)(100)
        == 200
    )

    # testing defaults
    assert (
        c.naive(d)
        .item(100, default=30)
        .item("test", default=30)
        .gen_converter()(100)
        == 30
    )
    assert (
        c.naive(d).item(10).item("test2", default=30).gen_converter()(100)
        == 30
    )
    assert c.naive(True).is_(True).execute(100) is True
    assert c.naive(True).is_not(True).execute(100) is False
    assert c.naive(1).in_({1, 2}).execute(100) is True
    assert c.naive(1).in_({3, 2}).execute(100) is False
    assert c.naive(1).in_(c.naive({1, 2})).execute(100) is True
    assert c.naive(1).in_({1: 2}).execute(100) is True
    assert c.naive(1).not_in({3, 2}).execute(100) is True
    assert c.naive(1).not_in(c.naive({3, 2})).execute(100) is True
    assert c.naive(1).not_in({3: 2}).execute(100) is True
    assert c.naive(1).eq(1).execute(100) is True
    assert (c.naive(1) == 1).execute(100) is True
    assert c.naive(1).not_eq(1).execute(100) is False
    assert (c.naive(1) != 1).execute(100) is False
    assert c.naive(1).gte(1).execute(100) is True
    assert (c.naive(1) >= 1).execute(100) is True
    assert c.naive(2).gte(1).execute(100) is True
    assert (c.naive(2) >= 1).execute(100) is True
    assert c.naive(10).gt(1).execute(100) is True
    assert (c.naive(10) > 1).execute(100) is True
    assert c.naive(1).lte(1).execute(100) is True
    assert (c.naive(1) <= 1).execute(100) is True
    assert c.naive(0).lte(1).execute(100) is True
    assert (c.naive(0) <= 1).execute(100) is True
    assert c.naive(0).lt(1).execute(100) is True
    assert (c.naive(0) < 1).execute(100) is True

    assert c.this.neg().execute(2) == -2
    assert (-c.this).execute(2) == -2
    assert (c.this + c.this).execute(2) == c.this.add(c.this).execute(2) == 4
    assert (c.this * c.this).execute(3) == c.this.mul(c.this).execute(3) == 9
    assert (
        (c.this ** (c.this + 1)).execute(2)
        == c.this.pow(c.this + 1).execute(2)
        == 8
    )
    assert (c.this - c.this).execute(2) == c.this.sub(c.this).execute(2) == 0
    assert (
        (c.naive(5) / c.this).execute(2) == c(5).div(c.this).execute(2) == 2.5
    )
    assert (
        (c.naive(5) // c.this).execute(2)
        == c(5).floor_div(c.this).execute(2)
        == 2
    )
    assert (c.naive(5) % c.this).execute(2) == c(5).mod(c.this).execute(2) == 1

    assert c.this.eq(1).eq(1).execute(1) == (c.this == 1).execute(1)
    assert c.this.eq(c.this == 2).execute(2) is False
    assert c.eq(c.this, c.this * 1, 7).execute(7) is True

    method = MagicMock(return_value=-1)

    converter = c.item(0, default=c.call_func(method)).gen_converter()
    assert converter([10]) == 10
    assert method.call_count == 0
    assert converter([]) == -1
    assert method.call_count == 1

    class A:
        def __getitem__(self, index):
            raise NotImplementedError

    with pytest.raises(NotImplementedError):
        c.item(0, default=-1).execute(A())

    class A:
        def __getattr__(self, index):
            raise NotImplementedError

    with pytest.raises(NotImplementedError):
        c.attr("a", default=-1).execute(A())


def test_getitem_const_default_uses_c_getter():
    if GetItem.getter_default_simple is None:
        pytest.skip("C getters not available")
    const_item = c.item("a", default=1)
    assert const_item.hardcoded_version is not None


def test_item_label_default_python_fallback(monkeypatch):
    monkeypatch.setattr(GetItem, "getter_default_simple", None)
    monkeypatch.setattr(GetItem, "getter_default_callable", None)
    monkeypatch.setattr(GetAttr, "getter_default_simple", None)
    monkeypatch.setattr(GetAttr, "getter_default_callable", None)
    assert c.item("a", default=c.label("prev")).execute({"a": 1}) == 1
    labeled_item = c.this.pipe(
        c.item("a", default=c.label("prev")), label_input="prev"
    )
    assert labeled_item.execute({"a": 1}) == 1
    assert labeled_item.execute({"b": 2}) == {"b": 2}
    assert c.item("a", default=c.label("prev")).hardcoded_version is None
    assert c.attr("a", default=c.label("prev")).hardcoded_version is None
    assert c.this.pipe(
        c.attr("a", default=c.label("prev")), label_input="prev"
    ).execute(SimpleNamespace(b=2)) == SimpleNamespace(b=2)


def test_item_attr_input_arg_escaped_string_default_fast_path():
    item_input_arg = c.item("a", default=c.input_arg("d"))
    item_escaped = c.item("a", default=c.escaped_string("123"))
    attr_input_arg = c.attr("a", default=c.input_arg("d"))
    if GetItem.getter_default_simple is not None:
        for conv, getter_name in (
            (item_input_arg, "get_item_deep_default_simple"),
            (item_escaped, "get_item_deep_default_simple"),
            (attr_input_arg, "get_attr_deep_default_simple"),
        ):
            code = get_code_str(conv)
            assert getter_name in code
            assert "item_or_default" not in code
            assert "attr_or_default" not in code
        assert item_input_arg.hardcoded_version is not None
        assert item_escaped.hardcoded_version is not None
        assert attr_input_arg.hardcoded_version is not None

    converter = item_input_arg.gen_converter()
    assert converter({"a": 1}, d=99) == 1
    assert converter({}, d=99) == 99
    assert converter(None, d=99) == 99

    converter = item_escaped.gen_converter()
    assert converter({"a": 1}) == 1
    assert converter({}) == 123
    assert converter(None) == 123

    converter = attr_input_arg.gen_converter()
    assert converter(SimpleNamespace(a=1), d=99) == 1
    assert converter(SimpleNamespace(), d=99) == 99
    assert converter(object(), d=99) == 99

    assert c.iter(c.item("a", default=c.input_arg("d"))).as_type(list).execute(
        [{"a": 1}, {}], d=99
    ) == [1, 99]
    assert c.aggregate(
        c.ReduceFuncs.Array(c.item("a", default=c.input_arg("d")))
    ).execute([{"a": 1}, {}], d=99) == [1, 99]

    label_code = get_code_str(c.item("a", default=c.label("x")))
    assert "item_or_default" in label_code
    assert "get_item_deep_default_simple" not in label_code


def test_item_attr_zero_indexes_with_default():
    assert c.item("a").item(default=1).execute({"a": 5}) == 5
    assert c.attr("a").attr(default=1).execute(SimpleNamespace(a=5)) == 5
    with pytest.raises(KeyError):
        c.item("a").item(default=1).execute({"b": 5})
    obj = object()
    assert c.this.item(default=1).execute(obj) is obj
    converter = (
        c.input_arg("x").item(default=1).gen_converter(signature="data_, x")
    )
    assert converter(None, 7) == 7


def test_item():
    assert c.item("key1").as_type(int).execute({"key1": "15"}) == 15


def test_in_semantics():
    assert c.this.in_([1]).execute(1) is True
    assert c.this.in_([1]).execute(2) is False
    assert c.this.in_({1}).execute(1) is True
    assert c.this.in_({1}).execute(2) is False
    assert c.this.in_((1,)).execute(1) is True
    assert c.this.in_(c.naive((1,))).execute(1) is True
    assert c.this.in_((1,)).execute(2) is False
    assert c.this.in_(c.list(1)).execute(1) is True
    assert c.this.in_(c.list(1)).execute(2) is False
    assert c.this.not_in([1]).execute(1) is False
    assert c.this.not_in([1]).execute(2) is True
    assert c.this.not_in(c.naive([1])).execute(2) is True

    class W:
        def __eq__(self, o):
            return "weird"

        __hash__ = object.__hash__

    assert c.this.in_({1}).execute(W()) is False
    assert c.this.in_([1]).execute(W()) is True
    with pytest.raises(TypeError):
        c.this.in_({1}).execute([1])
    assert c.this.not_in({1}).execute(W()) is True
    assert c.this.not_in([1]).execute(W()) is False
    with pytest.raises(TypeError):
        c.this.not_in({1}).execute([1])

    nan = float("nan")
    assert c.this.in_([nan]).execute(nan) is True
    assert (nan in [nan]) is True

    code_str = get_code_str(c.this.in_([1]))
    assert " in " in code_str
    code_str = get_code_str(c.this.in_(c.list(1)))
    assert " in " in code_str
    code_str = get_code_str(c.this.in_(c.set(1)))
    assert " in " in code_str
    code_str = get_code_str(c.this.in_(c.tuple(1)))
    assert " in " in code_str
    code_str = get_code_str(c.this.in_({1}))
    assert " in " in code_str
    code_str = get_code_str(c.this.in_((1,)))
    assert " in " in code_str
    code_str = get_code_str(c.this.in_(frozenset({1})))
    assert " in " in code_str
    code_str = get_code_str(c.this.not_in([1]))
    assert " not in " in code_str
    code_str = get_code_str(c.this.not_in(c.list(1)))
    assert " not in " in code_str
    code_str = get_code_str(c.this.in_([1, 2]))
    assert " in " in code_str
    code_str = get_code_str(c.this.not_in([1, 2]))
    assert " not in " in code_str
    code_str = get_code_str(c.this.in_([]))
    assert " in " in code_str


def test_in_not_in_nan_single_element():
    nan = float("nan")
    # naive containers
    assert c.this.in_([nan]).execute(nan) is True
    assert c.this.in_((nan,)).execute(nan) is True
    assert c.this.in_({nan}).execute(nan) is True
    assert c.this.in_(frozenset({nan})).execute(nan) is True
    assert c.this.not_in([nan]).execute(nan) is False
    assert c.this.not_in({nan}).execute(nan) is False
    assert c.this.not_in(frozenset({nan})).execute(nan) is False
    # literal container conversions
    assert c.this.in_(c.list(c.naive(nan))).execute(nan) is True
    assert c.this.not_in(c.list(c.naive(nan))).execute(nan) is False
    # dynamic single element
    assert c.item(0).in_([c.item(1)]).execute([nan, nan]) is True
    assert c.item(0).not_in([c.item(1)]).execute([nan, nan]) is False


def test_input_arg():
    assert c.input_arg("x").as_type(int).execute(None, x="10") == 10
    assert (
        c.inline_expr(""""{{}}_{{}}".format(type({x}).__name__, {x})""")
        .pass_args(x=c.item("value"))
        .gen_converter()
    )({"value": 123}) == "int_123"


@pytest.mark.parametrize(
    "name",
    [
        "data_",
        "_none",
        "_labels",
        "_naive",
        "__none__",
        "__exceptions_to_dump_sources",
        "__convtools__code_storage",
        "a b",
        "class",
        "1x",
    ],
)
def test_input_arg_rejects_invalid_and_reserved_names(name):
    with pytest.raises(ValueError) as exc_info:
        c.input_arg(name)
    assert name in str(exc_info.value)


def test_input_arg_builtin_and_helper_name_collisions():
    assert (c.this.len() + c.input_arg("len")).execute([1], len=1) == 2
    assert c.tuple_comp(c.this + c.input_arg("tuple")).execute(
        [1], tuple=1
    ) == (2,)

    assert (
        c.this.pipe(c.this + c.input_arg("len"), label_output="x").execute(
            1, len=2
        )
        == 3
    )
    assert (
        c.aggregate(c.ReduceFuncs.Sum(c.this + c.input_arg("len"))).execute(
            [1, 2], len=10
        )
        == 23
    )
    assert c.list_comp(c.this + c.input_arg("len")).execute(
        [1, 2], len=10
    ) == [11, 12]
    assert c.group_by(c.item(0)).aggregate(
        {
            "k": c.item(0),
            "s": c.ReduceFuncs.Sum(c.item(1) + c.input_arg("len")),
        }
    ).execute([(1, 2), (1, 3)], len=10) == [{"k": 1, "s": 25}]

    conv_with_data = (c.this.len() + c.input_arg("len")).gen_converter(
        signature="data_, len"
    )
    assert conv_with_data([1, 2], 3) == 5
    conv_no_data = c.input_arg("len").gen_converter(signature="len")
    assert conv_no_data(4) == 4

    class A:
        def __init__(self):
            self.offset = 10

        conv = (
            c.this.len()
            + c.input_arg("self").attr("offset")
            + c.input_arg("len")
        ).gen_converter(method=True)

    assert A().conv([1, 2], len=1) == 13

    assert c.group_by(c.item(0)).aggregate(
        {
            "k": c.item(0),
            "s": c.ReduceFuncs.Sum(c.item(1) + c.input_arg("defaultdict")),
        }
    ).execute([(1, 2), (1, 3)], defaultdict=10) == [{"k": 1, "s": 25}]
    assert (
        c.aggregate(
            c.ReduceFuncs.Sum(c.this + c.input_arg("aggregate_"))
        ).execute([1, 2], aggregate_=10)
        == 23
    )

    assert (
        c.aggregate(c.ReduceFuncs.Sum(c.this + c.input_arg("none"))).execute(
            [1, 2], none=10
        )
        == 23
    )
    assert (
        c.this.pipe(
            c.aggregate(c.ReduceFuncs.Sum(c.this + c.input_arg("labels"))),
            label_input="unused",
        ).execute([1, 2], labels=10)
        == 23
    )
    assert (
        c.aggregate(
            c.ReduceFuncs.Sum(c.item(*range(50))) + c.input_arg("tmp0_")
        ).execute([], tmp0_=7)
        == 7
    )

    assert c.group_by(c.item(0)).aggregate(
        {"k": c.item(0), "s": c.input_arg("signature")}
    ).execute([(1,)], signature=7) == [{"k": 1, "s": 7}]
    assert Namespace(c.input_arg("x"), {"x": "123"}).execute(None, x=5) == 5


def test_naive_conversion_attr():
    TestType = namedtuple("TestType", ["field_a", "field_b"])
    obj = TestType(1, 2)

    assert c.naive(obj).attr("field_b").gen_converter()(100) == 2
    assert (
        c.naive(obj)
        .attr("field_b", default=c.call_func(int))
        .gen_converter()(100)
        == 2
    )
    assert (
        c.naive(obj)
        .attr("field_a", "field_b", default=c.call_func(int))
        .gen_converter()(100)
        == 0
    )
    assert c.naive(obj).attr("field_b", "real").gen_converter()(100) == 2
    with pytest.raises(AttributeError):
        c.naive(obj).attr("field_c").gen_converter()(100)

    assert c.attr(c.naive(["field_a"]).item(0)).gen_converter()(obj) == 1


def test_attr_and_call_keyword_and_non_identifier_names():
    assert c.attr("class").execute(SimpleNamespace(**{"class": 1})) == 1
    assert (
        c.attr("a", "class").execute(
            SimpleNamespace(a=SimpleNamespace(**{"class": 3}))
        )
        == 3
    )
    assert c.this.call(**{"class": 1}).execute(lambda **kw: kw) == {"class": 1}
    assert c.call_func(lambda **kw: kw, **{"from": 1}).execute(None) == {
        "from": 1
    }
    assert c.this.call_method("m", **{"class": 1}).execute(
        SimpleNamespace(m=lambda **kw: kw)
    ) == {"class": 1}
    assert c.call_func(lambda **kw: kw, **{"a-b": 1}).execute(None) == {
        "a-b": 1
    }

    def f(x=0):
        return x

    assert ".a" in get_code_str(c.attr("a"))
    assert "x=" in get_code_str(c.call_func(f, x=1))

    obj = SimpleNamespace()
    setattr(obj, "ﬁ", "ligature")
    setattr(obj, "fi", "ascii")
    assert c.attr("ﬁ").execute(obj) == "ligature"
    assert c.attr("fi").execute(obj) == "ascii"
    assert c.call_func(lambda **kw: kw, **{"ﬁ": 1}).execute(None) == {"ﬁ": 1}
    assert c.call_func(lambda **kw: kw, **{"a\n": 1}).execute(None) == {
        "a\n": 1
    }


def test_item_attr_caching():
    result = c(
        {
            "item": c.item(0).pipe(c.item(0, default=None)),
            "item2": c.item(0).pipe(c.item(0, 1, default=None)),
            "item3": c.item(0, default=-1).item(0, default=-2),
            "item4": c.item(2, default=-1).item(0, default=-2),
            "attr": c.item(1).pipe(c.attr("year", default=None)),
            "attr2": c.item(1).pipe(c.attr("year", "month", default=None)),
            "attr3": c.item(1, default=-1).attr("year", default=-2),
            "attr4": c.item(2, default=-1).attr("year", default=-2),
        }
    ).execute([[1], date(1970, 1, 1)])
    assert result == {
        "item": 1,
        "item2": None,
        "item3": 1,
        "item4": -2,
        "attr": 1970,
        "attr2": None,
        "attr3": 1970,
        "attr4": -2,
    }

    converter = (
        c.this.or_(None)
        .item(c.item("key"), default=c.item("default"))
        .gen_converter()
    )
    assert converter({"key": "abc", "abc": 1, "default": -1}) == 1
    assert converter({"key": "abc", "default": -1}) == -1

    assert c(
        [
            c.item(1, default=c.call_func(int)),
            c.item(2, default=c.call_func(int)),
        ]
    ).execute([-1]) == [0, 0]

    data = {1: {2: {3: {4: 7}}}}
    for default in (
        c.input_arg("arg"),
        c.call_func(lambda: 10),
        c.call_func(lambda x: x + 10, 0),
        c.naive(10),
    ):
        converter = (
            c.item(1, 2, 3, 4, default=default)
            .or_(c.input_arg("arg"))
            .gen_converter()
        )
        assert converter(data, arg=10) == 7
        assert converter(None, arg=10) == 10


def test_naive_conversion_call():
    assert c.naive("TEST").attr("lower").call().gen_converter()(100) == "test"
    assert c.call_func(str.lower, c.this).gen_converter()("TEST") == "test"
    assert (
        c.naive("TE ST").attr("replace").call(" ", "").gen_converter()(100)
        == "TEST"
    )

    f = MagicMock(return_value=1)
    c.naive(f).call(1, 2, test1=True, test2="test3").gen_converter()(100)
    f.assert_called_with(1, 2, test1=True, test2="test3")
    c.call(10, test="abc").gen_converter()(f)
    f.assert_called_with(10, test="abc")


def test_naive_conversion_apply():
    f = MagicMock(return_value=1)
    c.naive(f).apply((1, 2), dict(test1=True, test2="test3")).gen_converter()(
        100
    )
    f.assert_called_with(1, 2, test1=True, test2="test3")
    c.apply((10,), dict(test="abc")).gen_converter()(f)
    f.assert_called_with(10, test="abc")

    c.apply((), {}).execute(f)
    f.assert_called_with()

    c.apply((1,), {}).execute(f)
    f.assert_called_with(1)


def test_naive_conversion_callmethod():
    mock = Mock()
    c.naive(mock).call_method("test_method", 1, abc=2).gen_converter()(100)
    mock.test_method.assert_called_with(1, abc=2)


def test_naive_conversion_applymethod():
    mock = Mock()
    c.naive(mock).apply_method(
        "test_method", (1,), dict(abc=2)
    ).gen_converter()(100)
    mock.test_method.assert_called_with(1, abc=2)


def test_naive_conversion_or_and():
    assert c.naive(False).or_(c.naive(False)).gen_converter()(100) is False
    assert (c.naive(False) | c.naive(False)).gen_converter()(100) is False
    assert c.naive(0).or_(c.naive(10)).gen_converter()(100) == 10
    assert c.naive(10).and_(c.naive(0)).gen_converter()(100) == 0
    assert (c.naive(10) & c.naive(0)).gen_converter()(100) == 0

    assert (
        c.this.and_(1).and_(2).execute(1)
        == c.and_(c.this, 1, 2).execute(1)
        == 2
    )
    assert (
        c.this.or_(1).or_(2).execute(1) == c.or_(c.this, 1, 2).execute(1) == 1
    )

    assert (
        c.this.and_(1).and_(2).or_(3).execute(1)
        == c.and_(c.this, 1, 2).or_(3).execute(1)
        == 2
    )

    assert c.this.or_(c.or_(c.this, 3)).execute(0) == 3
    assert (c.this | (c.this | 3)).execute(0) == 3

    assert c.this.and_(c.and_(c.this, 3)).execute(1) == 3
    assert (c.this & (c.this & 3)).execute(1) == 3

    assert c.this.or_(c.or_(default=True)).execute(0) is True
    assert c.this.and_(c.and_(default=False)).execute(1) is False
    assert c.this.or_(c.or_(default=False)).execute(0) is False


def test_escaped_string_conversion():
    assert c.escaped_string("1 == 1").gen_converter()(1) is True
    assert c.escaped_string("'1 == 1'").gen_converter()(1) == "1 == 1"


def test_or_and_not():
    assert c.or_(None, 0).gen_converter()(100) == 0
    assert c.and_(None, 0).gen_converter()(100) is None
    assert c.not_(True).gen_converter()(100) is False
    assert (~c.this).gen_converter()(True) is False
    assert c.naive(None).not_().execute(100) is True

    with pytest.raises(ValueError):
        c.or_()


def test_debug_true():
    with c.OptionsCtx() as options:
        options.debug = True
        assert c.this.gen_converter(debug=True)(1) == 1

    with pytest.raises(TypeError):
        assert c.item(0).gen_converter(debug=True)(1) == 1


def test_if():
    conv1 = c.if_(True, c.this * 2, c.this - 1000).gen_converter(debug=False)
    assert conv1(0) == -1000
    assert conv1(10) == 20

    conv2 = c.list_comp(
        c.if_(c.this % 2 == 0, c.this * 10, c.this * 100)
    ).gen_converter(debug=False)
    conv3 = c.list_comp(
        c.if_(
            c.this % 2 == 0,
            c.this * 10,
            c.this * 100,
            no_input_caching=True,
        )
    ).gen_converter(debug=False)
    assert conv2([1, 2, 3, 4]) == [100, 20, 300, 40]
    assert conv3([1, 2, 3, 4]) == [100, 20, 300, 40]

    conv4 = c.list_comp(
        (c.this - 5).pipe(c.if_(c.this % 2 == 0, c.this * 10, c.this * 100))
    ).gen_converter(debug=False)
    assert conv4([1, 2, 3, 4]) == [-40, -300, -20, -100]

    conv5 = c.if_().gen_converter(debug=False)
    assert conv5(0) == 0 and conv5(1) == 1

    conv6 = c.list_comp(
        c.if_(c.this, None, c.this, no_input_caching=True)
    ).gen_converter(debug=False)
    assert conv6([1, False, 2, None, 3, 0]) == [
        None,
        False,
        None,
        None,
        None,
        0,
    ]


def test_if_multiple():
    assert c.if_multiple((1, 2), (3, 4), else_=5).execute(None) == 2
    assert (
        c.if_multiple((c.this.is_(None), 2), (3, 4), else_=5).execute(None)
        == 2
    )
    assert c.list_comp(
        (
            c.if_multiple(
                (c.this < 0, c.this * 10), (c.this == 0, None), else_=5
            ),
            c.if_multiple(
                (c.this < 0, c.this * -100), (c.this == 0, None), else_=7
            ),
        )
    ).execute([-3, -2, 0, 1, 2]) == [
        (-30, 300),
        (-20, 200),
        (None, None),
        (5, 7),
        (5, 7),
    ]

    converter = c.if_multiple(
        (
            c.this.pipe(len) > 3,
            c.aggregate(c.ReduceFuncs.Sum(c.this + c.input_arg("base"))),
        ),
        (c.this.pipe(len) == 2, c.this),
        else_=None,
    ).gen_converter()
    assert converter([0, 1, 2, 3], base=10) == 46
    assert converter([0, 1], base=10) == [0, 1]
    assert converter([1], base=10) is None
    converter = c.if_multiple(
        (c.this < 10, c.this / 2), (c.this == 10, None), else_=c.this * 1.5
    ).gen_converter()
    assert (
        converter(4) == 2 and converter(10) is None and converter(100) == 150
    )


def test_callfunc():
    def func(i, abc=None):
        assert i == 1 and abc == 2

    c.call_func(func, 1, abc=2).gen_converter()(100)
    assert c.this.len().execute([1, 2]) == 2


def test_list():
    assert c.list(c.item(1), c.item(0), 3).gen_converter()([2, 1]) == [1, 2, 3]
    assert c([[c.item(1), c.item(0), 3]]).gen_converter()([2, 1]) == [
        [1, 2, 3]
    ]


def test_tuple():
    assert c.tuple().execute(None) == ()
    assert c.tuple(c.item(1), c.item(0), 3).gen_converter()([2, 1]) == (
        1,
        2,
        3,
    )
    assert c.tuple((c.item(1), c.item(0), 3)).gen_converter()([2, 1]) == (
        (1, 2, 3),
    )
    assert c(()).execute(None) == ()


def test_set():
    assert c({c.item(1), c.item(0), 3}).gen_converter()([2, 1]) == {1, 2, 3}
    assert c.set((c.item(1), c.item(0), 3)).gen_converter()([2, 1]) == {
        (1, 2, 3)
    }
    assert c.set((c.item(1), c.item(0), 3)).gen_converter()([2, 1]) == {
        (1, 2, 3)
    }


def test_dict():
    assert c.dict((1, c.escaped_string("1+1")), (2, 3)).gen_converter()(
        100
    ) == {1: 2, 2: 3}
    assert c({1: c.escaped_string("1+1"), 2: 3}).gen_converter()(100) == {
        1: 2,
        2: 3,
    }


def test_spread():
    # Basic spread
    conv = c.dict((1, 2), c.spread(c.item("a")), (3, 4)).gen_converter()
    assert conv({"a": {"x": 10}}) == {1: 2, "x": 10, 3: 4}

    # Multiple spreads
    conv = c.dict(c.spread(c.item("a")), c.spread(c.item("b"))).gen_converter()
    assert conv({"a": {"x": 1}, "b": {"y": 2}}) == {"x": 1, "y": 2}

    # Override order (later wins)
    conv = c.dict(("x", 1), c.spread(c.item("a"))).gen_converter()
    assert conv({"a": {"x": 999}}) == {"x": 999}

    # Empty spread
    conv = c.dict((1, 2), c.spread(c.item("a"))).gen_converter()
    assert conv({"a": {}}) == {1: 2}

    # Spread outside dict raises
    with pytest.raises(AssertionError):
        c.spread(c.this).gen_converter()

    # Spread combined with optional items (triggers generator code path)
    conv = c.dict(
        ("a", 1),
        c.spread(c.item("extra")),
        (c.optional(c.item("key"), skip_value=None), c.item("val")),
    ).gen_converter()
    assert conv({"extra": {"x": 10}, "key": "b", "val": 2}) == {
        "a": 1,
        "x": 10,
        "b": 2,
    }
    assert conv({"extra": {"x": 10}, "key": None, "val": 2}) == {
        "a": 1,
        "x": 10,
    }


def test_list_comprehension():
    assert c.list_comp(1).gen_converter()(range(5)) == [1] * 5
    data = [{"name": "John"}, {"name": "Bill"}, {"name": "Nick"}]
    assert c.list_comp(c.item("name")).sort(key=lambda n: n).gen_converter()(
        data
    ) == ["Bill", "John", "Nick"]
    assert c.list_comp(c.item("name")).sort().gen_converter()(data) == [
        "Bill",
        "John",
        "Nick",
    ]
    assert tuple(c.generator_comp(c.item("name")).gen_converter()(data)) == (
        "John",
        "Bill",
        "Nick",
    )
    assert c.list_comp(c.item("name")).sort(
        key=lambda n: n, reverse=True
    ).gen_converter()(data) == ["Nick", "John", "Bill"]
    assert c.list_comp(
        {(c.item("name"),)},
    ).execute(data) == [
        {("John",)},
        {("Bill",)},
        {("Nick",)},
    ]

    class CustomException(Exception):
        pass

    def f():
        yield 1
        raise CustomException

    wrapped_generator = c.generator_comp(c.this).execute(f())
    with pytest.raises(CustomException):
        list(wrapped_generator)

    it = iter(range(10))
    result = c.list_comp(c.this, where=False).execute(it)
    assert next(it, -1) == -1 and result == []

    assert c.iter(c.this + 1, where=c.this > 3).iter(c.this + 2).as_type(
        list
    ).execute(range(6)) == [7, 8]
    assert c.iter(c.this + 1, where=c.this > 3).iter(
        c.this + 2, where=c.this > 5
    ).as_type(list).execute(range(6)) == [8]

    assert c.list_comp(c.this + 1, where=None).execute(range(3)) == [1, 2, 3]


def test_tuple_comprehension():
    assert c.tuple_comp(1).gen_converter()(range(5)) == (1,) * 5
    data = [{"name": "John"}, {"name": "Bill"}, {"name": "Nick"}]
    assert c.tuple_comp(c.item("name")).sort(key=lambda n: n).gen_converter()(
        data
    ) == ("Bill", "John", "Nick")
    assert c.tuple_comp(c.item("name")).sort().gen_converter()(data) == (
        "Bill",
        "John",
        "Nick",
    )
    assert c.tuple_comp(c.item("name")).sort(
        key=lambda n: n, reverse=True
    ).gen_converter()(data) == ("Nick", "John", "Bill")

    it = iter(range(10))
    result = c.tuple_comp(c.this, where=False).execute(it)
    assert next(it, -1) == -1 and result == ()
    assert c.tuple_comp(c.this + 1, where=None).execute(range(3)) == (1, 2, 3)


def test_set_comprehension():
    assert c.set_comp(1).gen_converter()(range(5)) == {1}
    data = [
        {"name": "John"},
        {"name": "Bill"},
        {"name": "Bill"},
    ]
    assert c.set_comp(c.item("name")).gen_converter()(data) == {"John", "Bill"}

    assert (
        c.set_comp(c.item("name")).sort(key=lambda x: x).execute(data)
    ) == [
        "Bill",
        "John",
    ]
    it = iter(range(10))
    result = c.set_comp(c.this, where=False).execute(it)
    assert next(it, -1) == -1 and result == set()

    assert c.set_comp(c.this % 3).iter(c.this + 1).as_type(tuple).execute(
        range(10)
    ) == (1, 2, 3)
    assert c.set_comp(c.this + 1, where=None).execute(range(3)) == {1, 2, 3}


def test_dict_comprehension():
    data = [
        {"name": "John", "id": 1},
        {"name": "Bill", "id": 2},
    ]
    assert c.dict_comp(c.item("id"), c.item("name")).gen_converter()(data) == {
        2: "Bill",
        1: "John",
    }
    assert list(
        c.dict_comp(c.item("id"), c.item("name"))
        .sort(lambda k_v: (k_v[1], k_v[0]))
        .gen_converter()(data)
        .items()
    ) == [(2, "Bill"), (1, "John")]
    assert list(
        c.dict_comp(c.item("id"), c.item("name"))
        .sort(lambda k_v: (k_v[1], k_v[0]), reverse=True)
        .gen_converter()(data)
        .items()
    ) == [(1, "John"), (2, "Bill")]

    it = iter(range(10))
    result = c.dict_comp(c.this, c.this, where=False).execute(it)
    assert next(it, -1) == -1 and result == {}
    assert c.dict_comp(c.this, c.this, where=None).execute(range(1)) == {0: 0}


def test_comprehension_pipe_evaluates_iterable_once():
    def run(spec, data, expected):
        calls = []

        def heavy(x):
            calls.append(1)
            return x

        result = c.call_func(heavy, c.this).pipe(spec).execute(data)
        if isinstance(result, GeneratorType):
            result = list(result)
        assert result == expected
        assert calls == [1]

    iterable = c.if_(c.this.is_(None), [], c.this)
    run(iterable.iter(c.this + 1).as_type(list), [1, 2], [2, 3])
    run(iterable.pipe(c.list_comp(c.this + 1)), [1, 2], [2, 3])
    run(iterable.pipe(c.tuple_comp(c.this + 1)), [1, 2], (2, 3))
    run(iterable.pipe(c.set_comp(c.this + 1)), [1, 2], {2, 3})
    run(iterable.pipe(c.generator_comp(c.this + 1)), [1, 2], [2, 3])
    run(iterable.pipe(c.dict_comp(c.this, c.this + 1)), [1, 2], {1: 2, 2: 3})


def test_format_dt_fast_path_evaluates_input_once():
    from datetime import datetime

    def run(value, expected):
        calls = []

        def heavy(x):
            calls.append(1)
            return x

        assert (
            c.call_func(heavy, c.this).format_dt("%Y-%m-%d").execute(value)
            == expected
        )
        assert calls == [1]

    run(datetime(2020, 1, 2, 3, 4, 5), "2020-01-02")
    run(date(2020, 1, 2), "2020-01-02")


def test_filter():
    assert list(c.naive([1, 2, 3]).filter(c.this.gt(2)).execute(None)) == [3]
    assert c.filter(c.this.gt(1), cast=list).execute([1, 2, 3]) == [2, 3]
    assert c.filter(c.this.gt(1), cast=tuple).execute([1, 2, 3]) == (2, 3)
    assert c.filter(c.this.gt(1), cast=set).execute([1, 2, 3]) == {2, 3}
    assert c.filter(c.this.gt(1), cast=lambda x: list(x)).execute(
        [1, 2, 3]
    ) == [2, 3]
    assert c.list_comp(c.this).filter(c.this.gt(1)).execute(
        [1, 2, 3], debug=False
    ) == [
        2,
        3,
    ]
    assert c.this.filter(c.this.gt(1), cast=list).execute(
        [1, 2, 3], debug=False
    ) == [
        2,
        3,
    ]
    assert c.list_comp(c.this).filter(
        c.this > 1, cast=lambda x: list(x)
    ).execute(range(4)) == [2, 3]
    result = c.this.filter(c.this.gt(1), cast=None).execute(range(3))
    assert isinstance(result, GeneratorType) and list(result) == [2]


def test_sort():
    assert c.sort().execute([2, 3, 1]) == [1, 2, 3]
    assert c.sort(key=lambda x: x, reverse=True).execute([2, 3, 1]) == [
        3,
        2,
        1,
    ]
    assert c.this.sort().execute([2, 3, 1]) == [1, 2, 3]
    assert c.this.sort(key=lambda x: x, reverse=False).execute([2, 3, 1]) == [
        1,
        2,
        3,
    ]


def test_complex_labeling():
    conv1 = (
        c.this.add_label("input")
        .pipe(
            c.filter(c.this % 3 == 0),
            label_input={"input_type": c.call_func(type, c.this)},
        )
        .pipe(
            c.list_comp(c.this.as_type(str)),
            label_output={
                "list_length": c.call_func(len, c.this),
                "separator": c.if_(c.label("list_length") > 10, ",", ";"),
            },
        )
        .pipe(
            {
                "result": c.label("separator").call_method("join", c.this),
                "input_type": c.label("input_type"),
                "input_data": c.label("input"),
            }
        )
        .gen_converter()
    )
    assert conv1(range(30)) == {
        "result": "0;3;6;9;12;15;18;21;24;27",
        "input_type": range,
        "input_data": range(0, 30),
    }
    assert conv1(range(40)) == {
        "result": "0,3,6,9,12,15,18,21,24,27,30,33,36,39",
        "input_type": range,
        "input_data": range(0, 40),
    }


def test_caching_conversion():
    class CustomException(Exception):
        pass

    def f(number):
        if not f.first_time:
            raise CustomException
        f.first_time = False
        return number

    f.first_time = True

    conv = (
        c.call_func(f, c.this)
        .pipe(c.if_(c.this, c.this + 1, c.this + 2))
        .gen_converter()
    )
    assert conv(0) == 2
    with pytest.raises(CustomException):
        assert conv(0) == 2

    f.first_time = True
    assert conv(1) == 2

    with pytest.raises(CustomException):
        c.call_func(f, c.this).pipe(
            c.if_(c.this, c.this + 1, c.this + 2, no_input_caching=True)
        ).execute(0)


def test_slices():
    assert c.this[c.item(0) : c.input_arg("slice_to") : c.item(1)].execute(
        [2, 2, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], slice_to=8
    ) == [
        1,
        3,
        5,
    ]


def test_conversions_dependencies():
    input_arg = c.input_arg("abc")
    conv = c.item(input_arg)
    assert tuple(conv.get_dependencies()) == (input_arg, conv)


def test_namespaces():
    with pytest.raises(ValueError):
        LazyEscapedString("abc").execute([1])

    with pytest.raises(ValueError):
        Namespace(
            LazyEscapedString("abc"), name_to_code={"abc": None}
        ).execute([1])

    assert (
        Namespace(
            LazyEscapedString("abc"), name_to_code={"abc": True}
        ).execute(1)
        == 1
    )
    assert (
        Namespace(
            c.input_arg("abc") + LazyEscapedString("abc"),
            name_to_code={"abc": "abc"},
        ).execute(0.1, abc=2)
        == 4
    )
    assert Namespace(c.item(1), {}).execute([0, 10]) == 10
    assert (
        Namespace(
            Namespace(
                Namespace(
                    LazyEscapedString("abc"), name_to_code={"abc": True}
                )  # 1
                + LazyEscapedString("abc")  # 10
                + LazyEscapedString("foo")  # 1000
                + c.item() * 0.1,  # 0.1,
                name_to_code={"foo": "arg_foo2"},
            ),
            name_to_code={"abc": "arg_abc", "foo": "arg_foo"},
        )
    ).gen_converter(
        debug=False, signature="data_, arg_abc=10, arg_foo=100, arg_foo2=1000"
    )(
        1
    ) == 1011.1

    assert Namespace(
        c.call_func(list, (1,)).pipe(
            c.if_(
                c.this,
                c.this * LazyEscapedString("number"),
                c.this,
            )
        ),
        {"number": "3"},
    ).execute(None) == [1, 1, 1]


def test_name_generation():
    c.list_comp(
        {i: c.item(f"test{i}", default=1) for i in range(100)}
    ).gen_converter(debug=False)

    item = c.this
    ctx = c.BaseConversion._init_ctx()

    prev_allowed_symbols = c.BaseConversion.allowed_symbols
    c.BaseConversion.allowed_symbols = "01"
    for i in range(11):
        item.gen_name("abc", ctx, i)
    c.BaseConversion.allowed_symbols = prev_allowed_symbols

    same_tuple = (1, 2)
    assert item.gen_name("_", ctx, same_tuple) == item.gen_name(
        "_", ctx, same_tuple
    )
    obj = object()
    same_pair = (1, obj)
    assert item.gen_name("_", ctx, same_pair) == item.gen_name(
        "_", ctx, same_pair
    )
    obj = (1, [])
    assert item.gen_name("_", ctx, obj) == item.gen_name(
        "_",
        ctx,
        obj,
    )


def test_generator_exception_handling():
    class CustomException(Exception):
        pass

    def f_second_call_raises():
        if f_second_call_raises.counter:
            raise CustomException
        f_second_call_raises.counter += 1

    f_second_call_raises.counter = 0

    conv = c.generator_comp(c.call_func(f_second_call_raises)).gen_converter()
    with pytest.raises(CustomException):
        list(conv([1, 2]))


def test_inline_expr_pass_args_rebinding():
    bound = c.inline_expr("{0} + {1}").pass_args(c.this, 1)
    assert bound.execute(10) == 11

    # Already-bound expressions cannot be rebound (would discard args)
    with pytest.raises(ValueError, match="already has bound arguments"):
        bound.pass_args(c.this, 2)
    with pytest.raises(ValueError, match="already has bound arguments"):
        (c.this % 3).pass_args()


class CustomConversion(c.BaseConversion):
    def to_code(self, code_input, ctx):
        code = Code()
        code.add_line("return 1", 0)
        return code


def test_to_code():
    assert CustomConversion().execute(None) == 1
    assert (
        CustomConversion()
        .depends_on(c.input_arg("len"))
        .gen_converter()(None, len=1)
        == 1
    )


def test_generated_helper_skips_reserved_input_arg():
    class HelperConversion(c.BaseConversion):
        def gen_code_and_update_ctx(self, code_input, ctx):
            helper_name = self.gen_random_name("helper", ctx)
            self.compile_converter(
                helper_name, f"def {helper_name}():\n    return 1", ctx
            )
            return f"{helper_name}()"

    assert (
        HelperConversion()
        .depends_on(c.input_arg("_helper"))
        .execute(None, _helper=7)
        == 1
    )


def test_input_arg_reservation_not_generated():
    class ReservationConversion(c.BaseConversion):
        def gen_code_and_update_ctx(self, code_input, ctx):
            assert c.BaseConversion.strict_ctx
            for key in ("x", "_input_arg_x"):
                with pytest.raises(
                    AssertionError, match="unregistered ctx key"
                ):
                    ctx[key] = 1
            name = self.gen_random_name("ok", ctx)
            ctx[name] = 1
            return "1"

    converter = (
        ReservationConversion()
        .depends_on(c.input_arg("x"), c.input_arg("_input_arg_x"))
        .gen_converter()
    )
    assert converter(None, x=0, _input_arg_x=0) == 1


def test_item_default_with_hidden_input_usage():
    # if_multiple / dispatch defaults need the hidden data_ argument
    converter = (
        c.item("a")
        .item(
            "b", default=c.if_multiple((c.input_arg("strict"), None), else_=0)
        )
        .gen_converter()
    )
    assert converter({"a": {}}, strict=False) == 0
    assert converter({"a": {}}, strict=True) is None
    assert converter({"a": {"b": 1}}, strict=True) == 1
