import linecache
from collections import namedtuple
from datetime import date, datetime
from decimal import Decimal
from types import GeneratorType
from unittest.mock import MagicMock, Mock

import pytest

from convtools import conversion as c
from convtools.base import (
    CachingConversion,
    CodeGenerationOptionsCtx,
    ConversionWrapper,
    NamedConversion,
    _ConverterCallable,
)

from .utils import total_size


class MemoryProfilingConverterCallable(_ConverterCallable):
    def __call__(self, *args, **kwargs):
        size_before = total_size(self.__dict__)
        result = super(MemoryProfilingConverterCallable, self).__call__(
            *args, **kwargs
        )
        if isinstance(result, GeneratorType):
            return self.wrap_generator(result, size_before)

        size_after = total_size(self.__dict__)
        assert size_after <= size_before
        return result

    def wrap_generator(self, generator_, size_before):
        yield from generator_
        size_after = total_size(self.__dict__)
        assert size_after <= size_before


CodeGenerationOptionsCtx.options_cls.converter_callable_cls = (
    MemoryProfilingConverterCallable
)


def test_docs():
    print(1 < c.naive(2))


def test_naive_conversion():
    d = {1: 2}
    prev_max_counter = c.BaseConversion.max_counter
    c.BaseConversion.max_counter = 3
    try:
        assert c.naive(d).gen_converter()(1) == d
        assert c.naive("abc").gen_converter()(1) == "abc"
        assert c.naive(1).gen_converter()(10) == 1
        assert c.naive(True).gen_converter()(10) is True
        assert c.naive(False).gen_converter()(10) is False
        assert c.naive(None).gen_converter()(10) is None
        assert c.naive("1").as_type(int).gen_converter()(10) == 1
        assert c.naive(1).gen_converter(method=True)(None, 10) == 1
    finally:
        c.BaseConversion.max_counter = prev_max_counter


def test_gen_converter():
    class A:
        x = 10

        def __init__(self):
            self.x = 20

        conv1 = (c.this() + c.input_arg("self").attr("x")).gen_converter(
            method=True
        )
        conv2 = (c.this() + c.input_arg("cls").attr("x")).gen_converter(
            method=True
        )

        conv3 = classmethod(
            (c.this() + c.input_arg("cls").attr("x")).gen_converter(
                class_method=True
            )
        )
        conv4 = classmethod(
            (c.this() + c.input_arg("self").attr("x")).gen_converter(
                class_method=True
            )
        )

        conv5 = (
            c.this() + c.input_arg("self").attr("x") + c.input_arg("n")
        ).gen_converter(signature="self, n=1000, data_=15")

        conv6 = staticmethod(
            (
                (c.this() + c.call_func(sum, c.input_arg("args")))
                * c.input_arg("kwargs").call_method("get", "multiplicator", 1)
            ).gen_converter(signature="data_, *args, **kwargs")
        )

    assert A().conv1(100) == 120
    assert A.conv3(100) == 110

    with pytest.raises(NameError):
        A().conv2(100)
    with pytest.raises(NameError):
        A.conv4(100)

    assert A().conv5() == 1035
    assert A().conv5(data_=7) == 1027
    assert A().conv5(n=100) == 135

    assert A.conv6(20) == 20
    assert A.conv6(20, 1, 2, 3) == 26
    assert A.conv6(20, 1, 2, 3, multiplicator=10) == 260

    assert (
        c.call_func(sum, c.this()).gen_converter(signature="*data_")(1, 2, 3)
        == 6
    )
    assert (
        c.call_func(
            lambda i: globals().__setitem__("A", 1) or sum(i), c.this()
        ).gen_converter(signature="*data_")(1, 2, 3)
        == 6
    )
    assert c(
        {
            c.naive("-").call_method(
                "join", c.this().call_method("keys")
            ): c.call_func(sum, c.this().call_method("values"))
        }
    ).gen_converter(signature="**data_")(a=1, b=2, c=3) == {"a-b-c": 6}
    with pytest.raises(c.ConversionException):
        c.call_func(sum, c.input_arg("x")).gen_converter(signature="*data_")(
            1, 2, 3
        )
    with pytest.raises(c.ConversionException):
        c.this().gen_converter(method=True, class_method=True)


def test_hashes():
    assert hash(c.input_arg("abc")) == hash(c.input_arg("abc"))
    assert hash(c.input_arg("abd")) != hash(c.input_arg("abc"))
    assert hash(c.inline_expr("abc")) == hash(c.inline_expr("abc"))
    assert hash(c.inline_expr("abd")) != hash(c.inline_expr("abc"))


def test_naive_conversion_item():
    d = {1: 2, 10: {"test": 15, 2: 777}, 100: {"test2": 200}}
    assert c.naive(d).item(1).execute(100) == 2
    assert c.item(1).gen_converter()(d) == 2
    assert c.item(10, "test").gen_converter()(d) == 15

    assert c.item(11, "test", default=77).gen_converter()(d) == 77
    assert (
        c.item(11, "test", default=77).gen_converter(method=True)(None, d)
        == 77
    )
    assert c.item(10, "testt", default=77).gen_converter()(d) == 77

    assert c.item(10, "testt", default=c.this()).gen_converter()(d) == d

    assert c.item(10, c.item(1)).gen_converter()(d) == 777
    assert c.item(10).item(2).gen_converter()(d) == 777

    with pytest.raises(KeyError):
        c.naive(d).item(11).gen_converter()(100)
    with pytest.raises(IndexError):
        c.naive([]).item(11).gen_converter()(100)
    with pytest.raises(TypeError):
        c.naive(None).item(11).gen_converter()(100)

    assert (
        c.naive(d).item(100).item("test2").gen_converter(debug=False)(100)
        == 200
    )
    assert (
        c.naive(d).item(c.this(), "test2").gen_converter(debug=False)(100)
        == 200
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
    assert c.naive(1).not_in({3, 2}).execute(100) is True
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

    assert c.this().neg().execute(2) == -2
    assert (-c.this()).execute(2) == -2
    assert (c.this() + c.this()).execute(2) == 4
    assert (c.this() * c.this()).execute(3) == 9
    assert (c.this() - c.this()).execute(2) == 0
    assert (c.naive(5) / c.this()).execute(2) == 2.5
    assert (c.naive(5) // c.this()).execute(2) == 2
    assert (c.naive(5) % c.this()).execute(2) == 1


def test_item():
    assert c.item("key1").as_type(int).execute({"key1": "15"}) == 15


def test_input_arg():
    assert c.input_arg("x").as_type(int).execute(None, x="10") == 10
    assert (
        c.inline_expr(""""{{}}_{{}}".format(type({x}).__name__, {x})""")
        .pass_args(x=c.item("value"))
        .gen_converter()
    )({"value": 123}) == "int_123"


def test_naive_conversion_attr():
    TestType = namedtuple("TestType", ["field_a", "field_b"])
    obj = TestType(1, 2)

    assert c.naive(obj).attr("field_b").gen_converter()(100) == 2
    assert c.naive(obj).attr("field_b", "real").gen_converter()(100) == 2
    with pytest.raises(AttributeError):
        c.naive(obj).attr("field_c").gen_converter()(100)

    assert c.attr(c.naive(["field_a"]).item(0)).gen_converter()(obj) == 1


def test_naive_conversion_call():
    assert c.naive("TEST").attr("lower").call().gen_converter()(100) == "test"
    assert c.call_func(str.lower, c.this()).gen_converter()("TEST") == "test"
    assert (
        c.naive("TE ST").attr("replace").call(" ", "").gen_converter()(100)
        == "TEST"
    )

    f = MagicMock(return_value=1)
    c.naive(f).call(1, 2, test1=True, test2="test3").gen_converter()(100)
    f.assert_called_with(1, 2, test1=True, test2="test3")
    c.call(10, test="abc").gen_converter()(f)
    f.assert_called_with(10, test="abc")


def test_naive_conversion_callmethod():
    mock = Mock()
    c.naive(mock).call_method("test_method", 1, abc=2).gen_converter()(100)
    mock.test_method.assert_called_with(1, abc=2)


def test_naive_conversion_or_and():
    assert c.naive(False).or_(c.naive(False)).gen_converter()(100) is False
    assert (c.naive(False) | c.naive(False)).gen_converter()(100) is False
    assert c.naive(0).or_(c.naive(10)).gen_converter()(100) == 10
    assert c.naive(10).and_(c.naive(0)).gen_converter()(100) == 0
    assert (c.naive(10) & c.naive(0)).gen_converter()(100) == 0


def test_escaped_string_conversion():
    assert c.escaped_string("1 == 1").gen_converter()(1) is True
    assert c.escaped_string("'1 == 1'").gen_converter()(1) == "1 == 1"


def test_or_and_not():
    assert c.or_(None, 0).gen_converter()(100) == 0
    assert c.and_(None, 0).gen_converter()(100) is None
    assert c.not_(True).gen_converter()(100) is False
    assert (~c.this()).gen_converter()(True) is False
    assert c.naive(None).not_().execute(100) is True


def test_debug_true():
    with c.OptionsCtx() as options:
        options.debug = True
        assert c.this().gen_converter(debug=True)(1) == 1

    with pytest.raises(TypeError):
        assert c.item(0).gen_converter(debug=True)(1) == 1


def test_if():
    conv1 = c.if_(True, c.this() * 2, c.this() - 1000).gen_converter(
        debug=False
    )
    assert conv1(0) == -1000
    assert conv1(10) == 20

    conv2 = c.list_comp(
        c.if_(c.this() % 2 == 0, c.this() * 10, c.this() * 100)
    ).gen_converter(debug=False)
    conv3 = c.list_comp(
        c.if_(
            c.this() % 2 == 0,
            c.this() * 10,
            c.this() * 100,
            no_input_caching=True,
        )
    ).gen_converter(debug=False)
    assert conv2([1, 2, 3, 4]) == [100, 20, 300, 40]
    assert conv3([1, 2, 3, 4]) == [100, 20, 300, 40]

    conv4 = c.list_comp(
        (c.this() - 5).pipe(
            c.if_(c.this() % 2 == 0, c.this() * 10, c.this() * 100)
        )
    ).gen_converter(debug=True)
    assert conv4([1, 2, 3, 4]) == [-40, -300, -20, -100]

    conv5 = c.if_().gen_converter(debug=False)
    assert conv5(0) == 0 and conv5(1) == 1

    conv6 = c.list_comp(
        c.if_(c.this(), None, c.this(), no_input_caching=True)
    ).gen_converter(debug=True)
    assert conv6([1, False, 2, None, 3, 0]) == [
        None,
        False,
        None,
        None,
        None,
        0,
    ]

    assert c.if_().input_is_simple("'abc'")
    assert c.if_().input_is_simple("0")
    assert c.if_().input_is_simple("None")
    assert c.if_().input_is_simple("True")
    assert c.if_().input_is_simple("False")
    assert not c.if_().input_is_simple("1 + 1")
    assert not c.if_().input_is_simple("x.a")
    assert not c.if_().input_is_simple("x[0]")
    assert not c.if_().input_is_simple("x()")


def test_callfunc():
    def func(i, abc=None):
        assert i == 1 and abc == 2

    c.call_func(func, 1, abc=2).gen_converter()(100)


def test_list():
    assert c.list(c.item(1), c.item(0), 3).gen_converter()([2, 1]) == [1, 2, 3]
    assert c([[c.item(1), c.item(0), 3]]).gen_converter()([2, 1]) == [
        [1, 2, 3]
    ]


def test_tuple():
    assert c.tuple(c.item(1), c.item(0), 3).gen_converter()([2, 1]) == (
        1,
        2,
        3,
    )
    assert c.tuple((c.item(1), c.item(0), 3)).gen_converter()([2, 1]) == (
        (1, 2, 3),
    )


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
    assert c.list_comp({(c.item("name"),)},).execute(data) == [
        {("John",)},
        {("Bill",)},
        {("Nick",)},
    ]


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


def test_set_comprehension():
    assert c.set_comp(1).gen_converter()(range(5)) == {1}
    data = [
        {"name": "John"},
        {"name": "Bill"},
        {"name": "Bill"},
    ]
    assert c.set_comp(c.item("name")).gen_converter()(data) == {"John", "Bill"}
    with pytest.raises(c.ConversionException):
        c.set_comp(c.item("name")).sort(key=lambda x: x)


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


def test_pipes():
    assert c.list_comp(c.inline_expr("{0} ** 2").pass_args(c.this())).pipe(
        c.call_func(sum, c.this())
    ).pipe(
        c.call_func(
            lambda x, a: x + a,
            c.this(),
            c.naive({"abc": 10}).item(c.input_arg("key_name")),
        )
    ).pipe(
        [c.this(), c.this()]
    ).execute(
        [1, 2, 3], key_name="abc", debug=False
    ) == [
        24,
        24,
    ]
    assert c.item(0).pipe(datetime.strptime, "%Y-%m-%d").pipe(
        c.call_func(lambda dt: dt.date(), c.this())
    ).execute(["2019-01-01"], debug=False) == date(2019, 1, 1)

    assert c.item(0).pipe(datetime.strptime, "%Y-%m-%d").pipe(
        c.this().call_method("date")
    ).execute(["2019-01-01"], debug=False) == date(2019, 1, 1)

    with c.OptionsCtx() as options:
        max_pipe_length = options.max_pipe_length = 10
        with pytest.raises(c.ConversionException):
            conv = c.this()
            for i in range(max_pipe_length + 1):
                conv = c.this().pipe(conv)

        with c.OptionsCtx() as options2, pytest.raises(c.ConversionException):
            options2.max_pipe_length = 5
            conv.clone()

    conv = c.dict_comp(
        c.item("name"),
        c.item("transactions").pipe(
            c.list_comp(
                {
                    "id": c.item(0).as_type(str),
                    "amount": c.item(1).pipe(
                        c.if_(c.this(), c.this().as_type(Decimal), None)
                    ),
                }
            )
        ),
    ).gen_converter(debug=True)
    assert conv([{"name": "test", "transactions": [(0, 0), (1, 10)]}]) == {
        "test": [
            {"id": "0", "amount": None},
            {"id": "1", "amount": Decimal("10")},
        ]
    }

    with c.OptionsCtx() as options:
        max_pipe_length = options.max_pipe_length = 10
        conv1 = c.item(0).pipe(c.item(1).pipe(c.item(2)))

        def measure_pipe_length(conv):
            length = 0
            for i in range(max_pipe_length):
                if conv._predefined_input is not None:
                    length += 1
                    conv = conv._predefined_input
                else:
                    break
            return length

        pipe_length_before = measure_pipe_length(conv1)
        for i in range(max_pipe_length + 20):
            c.generator_comp(c.this().pipe(conv1))
        pipe_length_after = measure_pipe_length(conv1)
        assert pipe_length_after == pipe_length_before


def test_filter():
    assert list(c.naive([1, 2, 3]).filter(c.this().gt(2)).execute(None)) == [3]
    assert c.filter(c.this().gt(1), cast=list).execute([1, 2, 3]) == [2, 3]
    assert c.filter(c.this().gt(1), cast=tuple).execute([1, 2, 3]) == (2, 3)
    assert c.filter(c.this().gt(1), cast=set).execute([1, 2, 3]) == {2, 3}
    assert c.filter(c.this().gt(1), cast=lambda x: list(x)).execute(
        [1, 2, 3]
    ) == [2, 3]
    assert c.list_comp(c.this()).filter(c.this().gt(1)).execute([1, 2, 3]) == [
        2,
        3,
    ]
    assert c.this().filter(c.this().gt(1), cast=list).execute([1, 2, 3]) == [
        2,
        3,
    ]


def test_manually_defined_reducers():
    data = [
        {"name": "John", "category": "Games", "debit": 10, "balance": 90},
        {"name": "John", "category": "Games", "debit": 200, "balance": -110},
        {"name": "John", "category": "Food", "debit": 30, "balance": -140},
        {"name": "John", "category": "Games", "debit": 300, "balance": 0},
        {"name": "Nick", "category": "Food", "debit": 7, "balance": 50},
        {"name": "Nick", "category": "Games", "debit": 18, "balance": 32},
        {"name": "Bill", "category": "Games", "debit": 18, "balance": 120},
    ]
    grouper = (
        c.group_by(c.item("name"))
        .aggregate(
            c.reduce(
                lambda a, b: a + b, c.item(c.input_arg("group_key")), initial=0
            )
        )
        .filter(c.this() > 20)
        .gen_converter(signature="data_, group_key='debit'")
    )
    assert grouper(data) == [540, 25]
    assert grouper(data, group_key="balance") == [82, 120]


def test_grouping():
    data = [
        {"name": "John", "category": "Games", "debit": 10, "balance": 90},
        {"name": "John", "category": "Games", "debit": 200, "balance": -110},
        {"name": "John", "category": "Food", "debit": 30, "balance": -140},
        {"name": "John", "category": "Games", "debit": 300, "balance": 0},
        {"name": "Nick", "category": "Food", "debit": 7, "balance": 50},
        {"name": "Nick", "category": "Games", "debit": 18, "balance": 32},
        {"name": "Bill", "category": "Games", "debit": 18, "balance": 120},
    ]
    with pytest.raises(c.ConversionException):
        # there's a single group by field, while we use separate items
        # of this tuple in aggregate
        result = (
            c.group_by(c.item("name"))
            .aggregate(
                (
                    c.item("category"),
                    c.reduce(c.ReduceFuncs.Sum, c.item("debit")),
                )
            )
            .execute(data, debug=False)
        )
    result = (
        c.group_by(c.item("name"))
        .aggregate(
            (
                c.item("name"),
                c.item("name").call_method("lower"),
                c.call_func(str.lower, c.item("name")),
                c.reduce(
                    lambda a, b: a + b,
                    c.item("debit"),
                    initial=c.input_arg("arg1"),
                    unconditional_init=True,
                ),
                c.reduce(
                    c.inline_expr("{0} + {1}"),
                    c.item("debit"),
                    initial=lambda: 100,
                    unconditional_init=True,
                ),
                c.reduce(
                    max, c.item("debit"), default=c.input_arg("arg1")
                ).filter(c.call_func(lambda x: x < 0, c.item("balance"))),
                c.call_func(
                    lambda max_debit, n: max_debit * n,
                    c.reduce(max, c.item("debit"), default=0).filter(
                        c.call_func(lambda x: x < 0, c.item("balance"))
                    ),
                    1000,
                ),
                c.call_func(
                    lambda max_debit, n: max_debit * n,
                    c.reduce(
                        c.ReduceFuncs.Max, c.item("debit"), default=1000,
                    ).filter(
                        c.inline_expr("{0} > {1}").pass_args(
                            c.item("balance"), c.input_arg("arg2"),
                        )
                    ),
                    -1,
                ),
                c.reduce(c.ReduceFuncs.MaxRow, c.item("debit")).item(
                    "balance"
                ),
                c.reduce(c.ReduceFuncs.MinRow, c.item("debit")).item(
                    "balance"
                ),
            )
        )
        .sort(key=lambda t: t[0].lower(), reverse=True)
        .execute(data, arg1=100, arg2=0, debug=False)
    )
    # fmt: off
    assert result == [('Nick', 'nick', 'nick', 125, 125, 100, 0, -18, 32, 50),
                     ('John', 'john', 'john', 640, 640, 200, 200000, -10, 0, 90),
                     ('Bill', 'bill', 'bill', 118, 118, 100, 0, -18, 120, 120)]
    # fmt: on

    aggregation = {
        c.call_func(
            tuple, c.reduce(c.ReduceFuncs.Array, c.item("name"), default=None),
        ): c.item("category").call_method("lower"),
        "count": c.reduce(c.ReduceFuncs.Count),
        "max": c.reduce(c.ReduceFuncs.Max, c.item("debit")),
        "min": c.reduce(c.ReduceFuncs.Min, c.item("debit")),
        "count_distinct": c.reduce(
            c.ReduceFuncs.CountDistinct, c.item("name")
        ),
        "array_agg_distinct": c.reduce(
            c.ReduceFuncs.ArrayDistinct, c.item("name"),
        ),
        "dict": c.reduce(
            c.ReduceFuncs.Dict, (c.item("debit"), c.item("name"))
        ),
    }
    result = (
        c.group_by(c.item("category"))
        .aggregate(aggregation)
        .execute(data, debug=True)
    )
    result2 = (
        c.group_by(c.item("category"))
        .aggregate(c.dict(*aggregation.items()))
        .execute(data, debug=False)
    )
    # fmt: off
    assert result == result2 == [{'array_agg_distinct': ['John', 'Nick', 'Bill'],
          'count': 5,
          'count_distinct': 3,
          'dict': {10: 'John', 18: 'Bill', 200: 'John', 300: 'John'},
          'max': 300,
          'min': 10,
          ('John', 'John', 'John', 'Nick', 'Bill'): 'games'},
         {'array_agg_distinct': ['John', 'Nick'],
          'count': 2,
          'count_distinct': 2,
          'dict': {7: 'Nick', 30: 'John'},
          'max': 30,
          'min': 7,
          ('John', 'Nick'): 'food'}]
    # fmt: on
    result3 = (
        c.aggregate(c.reduce(c.ReduceFuncs.Sum, c.item("debit")))
        .pipe(c.inline_expr("{0} + {1}").pass_args(c.this(), c.this()))
        .execute(data, debug=False)
    )
    assert result3 == 583 * 2

    by = c.item("name"), c.item("category")
    result4 = (
        c.group_by(*by)
        .aggregate(by + (c.reduce(c.ReduceFuncs.Sum, c.item("debit")),))
        .execute(data, debug=False)
    )
    # fmt: off
    assert result4 == [('John', 'Games', 510),
         ('John', 'Food', 30),
         ('Nick', 'Food', 7),
         ('Nick', 'Games', 18),
         ('Bill', 'Games', 18)]
    # fmt: on
    result5 = (
        c.group_by()
        .aggregate(c.reduce(c.ReduceFuncs.Sum, c.item("debit")))
        .execute(data, debug=False)
    )
    assert result5 == 583

    with pytest.raises(c.ConversionException):
        # there's a single group by field, while we use separate items
        # of this tuple in aggregate
        (
            c.group_by(by)
            .aggregate(by + (c.reduce(c.ReduceFuncs.Sum, c.item("debit")),))
            .execute(data, debug=True)
        )


# fmt: off
reducer_data1 = [
    {"name": "Bill", "debit": 100},
    {"name": "Bill", "debit": 50},
    {"name": "Nick", "debit": 1},
]
reducer_data2 = [
    {"name": "Bill", "debit": None},
    {"name": "Nick", "debit": 2},
]
reducer_data3 = [
    {"name": "Bill", "debit": 50},
    {"name": "Nick", "debit": 2},
    {"name": "Nick", "debit": 2},
]
reducer_data4 = [
    {"name": "Bill", "debit": 25},
    {"name": "Nick", "debit": 3},
]

reducers_in_out = [
    dict(
        groupby=c.item("name"),
        reduce=c.reduce(c.ReduceFuncs.Sum, c.item("debit")),
        data=reducer_data1,
        output=[('Bill', 150), ('Nick', 1)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.reduce(c.ReduceFuncs.Sum, c.item("debit")),
        data=reducer_data1 + reducer_data2,
        output=[('Bill', 150), ('Nick', 3)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.reduce(c.ReduceFuncs.SumOrNone, c.item("debit")),
        data=reducer_data1 + reducer_data2,
        output=[('Bill', None), ('Nick', 3)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.reduce(c.ReduceFuncs.Max, c.item("debit")),
        data=reducer_data1,
        output=[('Bill', 100), ('Nick', 1)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.reduce(c.ReduceFuncs.Max, c.item("debit")),
        data=reducer_data1 + reducer_data2,
        output=[('Bill', 100), ('Nick', 2)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.reduce(c.ReduceFuncs.MaxRow, c.item("debit")),
        data=reducer_data1 + reducer_data2,
        output=[('Bill', {'debit': 100, 'name': 'Bill'}),
                 ('Nick', {'debit': 2, 'name': 'Nick'})],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.reduce(c.ReduceFuncs.Min, c.item("debit")),
        data=reducer_data1,
        output=[('Bill', 50), ('Nick', 1)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.reduce(c.ReduceFuncs.Min, c.item("debit")),
        data=reducer_data1 + reducer_data2,
        output=[('Bill', 50), ('Nick', 1)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.reduce(c.ReduceFuncs.MinRow, c.item("debit")),
        data=reducer_data1 + reducer_data2,
        output=[('Bill', {'debit': 50, 'name': 'Bill'}),
                 ('Nick', {'debit': 1, 'name': 'Nick'})],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.reduce(c.ReduceFuncs.Count, c.item("debit")),
        data=reducer_data1 + reducer_data2,
        output=[('Bill', 3), ('Nick', 2)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.reduce(c.ReduceFuncs.Count, c.item("debit")).filter(
            c.item("debit").is_(None)
        ),
        data=reducer_data1 + reducer_data2,
        output=[('Bill', 1), ('Nick', 0)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.reduce(c.ReduceFuncs.CountDistinct, c.item("debit")),
        data=reducer_data1 + reducer_data2 + reducer_data3 + reducer_data4,
        output=[('Bill', 4), ('Nick', 3)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.reduce(c.ReduceFuncs.First, c.item("debit")),
        data=reducer_data1 + reducer_data2,
        output=[('Bill', 100), ('Nick', 1)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.reduce(c.ReduceFuncs.Last, c.item("debit")),
        data=reducer_data1 + reducer_data2,
        output=[('Bill', None), ('Nick', 2)],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.reduce(c.ReduceFuncs.Array, c.item("debit")),
        data=reducer_data1 + reducer_data2 + reducer_data3,
        output=[('Bill', [100, 50, None, 50]), ('Nick', [1, 2, 2, 2])],
        raises=None,
    ),
    dict(
        groupby=c.item("name"),
        reduce=c.reduce(c.ReduceFuncs.ArrayDistinct, c.item("debit")),
        data=reducer_data1 + reducer_data2 + reducer_data3,
        output=[('Bill', [100, 50, None]), ('Nick', [1, 2])],
        raises=None,
    ),
    dict(
        groupby=True,
        reduce=c.reduce(c.ReduceFuncs.Dict, (c.item("name"), c.item("debit"))),
        data=reducer_data1 + reducer_data2 + reducer_data3,
        output=[(True, {'Bill': 50, 'Nick': 2})],
        raises=None,
    ),
    dict(
        groupby=True,
        reduce=c.reduce(c.ReduceFuncs.DictArray, (c.item("name"), c.item("debit"))),
        data=reducer_data1 + reducer_data2 + reducer_data3,
        output=[(True, {'Bill': [100, 50, None, 50], 'Nick': [1, 2, 2, 2]})],
        raises=None,
    ),
    dict(
        groupby=True,
        reduce=c.reduce(c.ReduceFuncs.DictArrayDistinct, (c.item("name"), c.item("debit"))),
        data=reducer_data1 + reducer_data2 + reducer_data3,
        output=[(True, {'Bill': [100, 50, None], 'Nick': [1, 2]})],
        raises=None,
    ),
    dict(
        groupby=True,
        reduce=c.reduce(c.ReduceFuncs.DictSum, (c.item("name"), c.item("debit"))),
        data=reducer_data1 + reducer_data2 + reducer_data3,
        output=[(True, {'Bill': 200, 'Nick': 7})],
        raises=None,
    ),
    dict(
        groupby=True,
        reduce=c.reduce(c.ReduceFuncs.DictSumOrNone, (c.item("name"), c.item("debit"))),
        data=reducer_data1 + reducer_data2 + reducer_data3,
        output=[(True, {'Bill': None, 'Nick': 7})],
        raises=None,
    ),
    dict(
        groupby=True,
        reduce=c.reduce(c.ReduceFuncs.DictMax, (c.item("name"), c.item("debit"))),
        data=reducer_data1 + reducer_data2 + reducer_data3,
        output=[(True, {'Bill': 100, 'Nick': 2})],
        raises=None,
    ),
    dict(
        groupby=True,
        reduce=c.reduce(c.ReduceFuncs.DictMin, (c.item("name"), c.item("debit"))),
        data=reducer_data1 + reducer_data2 + reducer_data3,
        output=[(True, {'Bill': 50, 'Nick': 1})],
        raises=None,
    ),
    dict(
        groupby=True,
        reduce=c.reduce(c.ReduceFuncs.DictCount, (c.item("name"), c.item("debit"))),
        data=reducer_data1 + reducer_data2 + reducer_data3,
        output=[(True, {'Bill': 4, 'Nick': 4})],
        raises=None,
    ),
    dict(
        groupby=True,
        reduce=c.reduce(c.ReduceFuncs.DictCountDistinct, (c.item("name"), c.item("debit"))),
        data=reducer_data1 + reducer_data2 + reducer_data3 + reducer_data4,
        output=[(True, {'Bill': 4, 'Nick': 3})],
        raises=None,
        debug=False,
    ),
    dict(
        groupby=True,
        reduce=c.reduce(c.ReduceFuncs.DictFirst, (c.item("name"), c.item("debit"))),
        data=reducer_data1 + reducer_data2 + reducer_data3,
        output=[(True, {'Bill': 100, 'Nick': 1})],
        raises=None,
    ),
    dict(
        groupby=True,
        reduce=c.reduce(c.ReduceFuncs.DictLast, (c.item("name"), c.item("debit"))),
        data=reducer_data1 + reducer_data2 + reducer_data3 + reducer_data4,
        output=[(True, {'Bill': 25, 'Nick': 3})],
        raises=None,
    ),

]
# fmt: on
def test_reducers():
    for config in reducers_in_out:
        converter = (
            c.group_by(config["groupby"])
            .aggregate((config["groupby"], config["reduce"]))
            .gen_converter(debug=config.get("debug", False))
        )

        if config["raises"]:
            with pytest.raises(config["raises"]):
                converter(config["data"])
        else:
            data = converter(config["data"])
            assert data == config["output"]


def test_base_reducer():
    from convtools.aggregations import _ReducerExpression, _ReducerStatements

    assert c.aggregate(
        (
            c.reduce(
                _ReducerExpression(
                    lambda a, b: a + b, expr=c.this(), initial=0
                )
            ),
            c.reduce(
                _ReducerExpression(
                    c.naive(lambda a, b: a + b), expr=c.this(), initial=int
                )
            ),
            c.reduce(
                _ReducerExpression("{0} + {1}", expr=c.this(), default=0)
            ),
            c.reduce(
                _ReducerExpression(
                    "{0} + {1}",
                    expr=c.this(),
                    initial_from_first=int,
                    default=0,
                )
            ),
            c.reduce(
                _ReducerStatements(
                    reduce="%(result)s += ({1} or 0)",
                    initial_from_first="%(result)s = ({0} or 0)",
                    default=0,
                ),
                c.this(),
            ),
            c.reduce(
                _ReducerStatements(
                    reduce="%(result)s += ({1} or 0)", default=c.naive(int),
                ),
                c.this(),
            ),
            c.reduce(
                _ReducerStatements(
                    reduce="%(result)s = ({1} or 0)", initial=0,
                ),
                c.this(),
            ),
        )
    ).filter(c.this() > 5, cast=tuple).gen_converter(debug=True)(
        [1, 2, 3]
    ) == (
        6,
        6,
        6,
        6,
        6,
        6,
    )

    with pytest.raises(AssertionError):
        c.aggregate(
            (c.reduce(c.ReduceFuncs.Sum, c.reduce(c.ReduceFuncs.Count)),)
        ).gen_converter()

    conv = c.aggregate(
        c.reduce(c.ReduceFuncs.DictArray, (c.item(0), c.item(1)))
    ).gen_converter(debug=True)
    data = [
        ("a", 1),
        ("a", 2),
        ("b", 3),
    ]
    result = {"a": [1, 2], "b": [3]}
    assert conv(data) == result
    assert conv([]) is None

    conv2 = c.aggregate(
        {"key": c.reduce(c.ReduceFuncs.DictArray, (c.item(0), c.item(1)))}
    ).gen_converter(debug=True)
    assert conv2([]) == {"key": None}
    assert conv2(data) == {"key": result}


def test_simple_label():
    conv1 = (
        c.tuple(c.item(1).add_label("a"), c.this())
        .pipe(c.item(1).pipe(c.list_comp((c.this(), c.label("a")))))
        .gen_converter(debug=False)
    )
    assert conv1([1, 2, 3, 4]) == [(1, 2), (2, 2), (3, 2), (4, 2)]

    conv2 = (
        c.tuple(c.item(1).add_label("a"), c.this())
        .pipe(
            c.item(1),
            label_input={"aa": c.item(0), "bb": c.item(0)},
            label_output="collection1",
        )
        .pipe(
            c.label("collection1").pipe(
                c.aggregate(
                    c.reduce(
                        c.ReduceFuncs.Sum,
                        c.this()
                        + c.label("a")
                        + c.label("aa")
                        + c.input_arg("x")
                        + c.label("collection1").item(0),
                    )
                )
            ),
            label_output="b",
        )
        .pipe(c.this() + c.label("b"))
        .gen_converter(debug=False)
    )
    assert conv2([1, 2, 3, 4], x=10) == 140

    conv3 = (
        c.tuple(c.item("default").add_label("default"), c.this())
        .pipe(c.item(1).pipe(c.item("abc", default=c.label("default"))))
        .gen_converter(debug=True)
    )
    assert conv3({"default": 1}) == 1

    with pytest.raises(c.ConversionException):
        c.this().pipe(c.this(), label_input=1)
    with pytest.raises(c.ConversionException):
        CachingConversion(c.this()).add_label("a", c.this()).add_label(
            "a", c.this()
        )


def test_complex_labeling():
    conv1 = (
        c.this()
        .add_label("input")
        .pipe(
            c.filter(c.this() % 3 == 0),
            label_input={"input_type": c.call_func(type, c.this())},
        )
        .pipe(
            c.list_comp(c.this().as_type(str)),
            label_output={
                "list_length": c.call_func(len, c.this()),
                "separator": c.if_(c.label("list_length") > 10, ",", ";"),
            },
        )
        .pipe(
            {
                "result": c.label("separator").call_method("join", c.this()),
                "input_type": c.label("input_type"),
                "input_data": c.label("input"),
            }
        )
        .gen_converter(debug=True)
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
        c.call_func(f, c.this())
        .pipe(c.if_(c.this(), c.this() + 1, c.this() + 2))
        .gen_converter()
    )
    assert conv(0) == 2
    with pytest.raises(CustomException):
        assert conv(0) == 2

    f.first_time = True
    assert conv(1) == 2

    with pytest.raises(CustomException):
        c.call_func(f, c.this()).pipe(
            c.if_(c.this(), c.this() + 1, c.this() + 2, no_input_caching=True)
        ).execute(0)


def test_memory_freeing():
    converter = (
        c.this()
        .pipe(
            c.list_comp(c.this() + c.label("input_data").item(0)),
            label_input=dict(input_data=c.this()),
        )
        .gen_converter(debug=True)
    )

    sizes = []
    sizes.append(total_size(converter.__dict__))

    for i in range(100):
        l_input = [i + j for j in range(3)]
        l_out = [j + l_input[0] for j in l_input]
        assert converter(l_input) == l_out
        sizes.append(total_size(converter.__dict__))
    assert all(sizes[0] == size for size in sizes[1:]), sizes

    conv2 = (
        c.inline_expr("globals().__setitem__('a', {}) or 1")
        .pass_args(c.this())
        .gen_converter()
    )
    with pytest.raises(AssertionError):
        # should raise because of a memory leak
        conv2(123)


def test_slices():
    assert c.this()[
        c.item(0) : c.input_arg("slice_to") : c.item(1)
    ].gen_converter(debug=True)(
        [2, 2, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], slice_to=8
    ) == [
        1,
        3,
        5,
    ]


def test_linecache_cleaning():
    length_before = len(linecache.cache)
    for i in range(100):
        c.this().gen_converter(debug=True)
    length_after_100 = len(linecache.cache)

    for i in range(10):
        c.this().gen_converter(debug=True)
    length_after_10 = len(linecache.cache)

    assert (
        length_after_10 == length_after_100
        and length_before + 100 >= length_after_100
    )

    for key in list(linecache.cache.keys()):
        del linecache.cache[key]
    c.this().gen_converter(debug=True)


def test_named_conversion():
    assert NamedConversion("abc", c.item(0)).execute([1]) == 1


def test_conversions_dependencies():
    input_arg = c.input_arg("abc")
    conv = c.item(input_arg)
    assert tuple(conv._get_dependencies()) == (input_arg, conv)


def test_conversion_wrapper():
    assert ConversionWrapper(c.item(1)).execute([0, 10]) == 10
    assert (
        (
            ConversionWrapper(
                ConversionWrapper(
                    NamedConversion(
                        "abc", NamedConversion("foo", c.item()) + c.item(),
                    )
                    + c.item(),
                    name_to_code_input={"foo": "arg_foo2"},
                ),
                name_to_code_input={"abc": "arg_abc", "foo": "arg_foo"},
            )
        ).gen_converter(
            debug=True, signature="data_, arg_abc=10, arg_foo=20, arg_foo2=30"
        )(
            1
        )
        == 41
    )
