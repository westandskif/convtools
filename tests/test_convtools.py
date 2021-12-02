from collections import namedtuple
from datetime import date
from unittest.mock import MagicMock, Mock

import pytest

from convtools import conversion as c
from convtools.base import (
    ConversionWrapper,
    InlineExpr,
    NamedConversion,
    PipeConversion,
)

from .utils import total_size


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

    assert (
        "%abc"
        not in next(
            iter(c.naive("%abc").gen_converter()._name_to_converter.values())
        )["code_str"]
    )
    assert (
        "{abc"
        not in next(
            iter(c.naive("{abc").gen_converter()._name_to_converter.values())
        )["code_str"]
    )
    assert (
        "abc"
        in next(
            iter(c.naive("abc").gen_converter()._name_to_converter.values())
        )["code_str"]
    )


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


def test_naive_conversion_item():
    d = {1: 2, 10: {"test": 15, 2: 777}, 100: {"test2": 200}}
    assert c.naive(d).item(1).execute(100) == 2
    assert c.item(1).gen_converter()(d) == 2
    assert c.item(10, "test").gen_converter()(d) == 15

    assert c.item(11, "test", default=77).gen_converter()(d) == 77
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
    ).gen_converter(debug=False)
    assert conv4([1, 2, 3, 4]) == [-40, -300, -20, -100]

    conv5 = c.if_().gen_converter(debug=False)
    assert conv5(0) == 0 and conv5(1) == 1

    conv6 = c.list_comp(
        c.if_(c.this(), None, c.this(), no_input_caching=True)
    ).gen_converter(debug=False)
    assert conv6([1, False, 2, None, 3, 0]) == [
        None,
        False,
        None,
        None,
        None,
        0,
    ]

    assert PipeConversion.input_is_simple("'abc'")
    assert PipeConversion.input_is_simple("0")
    assert PipeConversion.input_is_simple("None")
    assert PipeConversion.input_is_simple("True")
    assert PipeConversion.input_is_simple("False")
    assert PipeConversion.input_is_simple("a[1]")
    assert PipeConversion.input_is_simple("a['1']")
    assert PipeConversion.input_is_simple("a[1][2]")
    assert not PipeConversion.input_is_simple("a[1][2][3]")
    assert not PipeConversion.input_is_simple("1 + 1")
    assert not PipeConversion.input_is_simple("x.a")
    assert not PipeConversion.input_is_simple("x()")


def test_callfunc():
    def func(i, abc=None):
        assert i == 1 and abc == 2

    c.call_func(func, 1, abc=2).gen_converter()(100)
    assert c.this().len().execute([1, 2]) == 2


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

    class CustomException(Exception):
        pass

    def f():
        yield 1
        raise CustomException

    wrapped_generator = c.generator_comp(c.this()).execute(f())
    with pytest.raises(CustomException):
        list(wrapped_generator)


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

    assert (
        c.set_comp(c.item("name")).sort(key=lambda x: x).execute(data)
    ) == [
        "Bill",
        "John",
    ]


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


def test_filter():
    assert list(c.naive([1, 2, 3]).filter(c.this().gt(2)).execute(None)) == [3]
    assert c.filter(c.this().gt(1), cast=list).execute([1, 2, 3]) == [2, 3]
    assert c.filter(c.this().gt(1), cast=tuple).execute([1, 2, 3]) == (2, 3)
    assert c.filter(c.this().gt(1), cast=set).execute([1, 2, 3]) == {2, 3}
    assert c.filter(c.this().gt(1), cast=lambda x: list(x)).execute(
        [1, 2, 3]
    ) == [2, 3]
    assert c.list_comp(c.this()).filter(c.this().gt(1)).execute(
        [1, 2, 3], debug=False
    ) == [
        2,
        3,
    ]
    assert c.this().filter(c.this().gt(1), cast=list).execute(
        [1, 2, 3], debug=False
    ) == [
        2,
        3,
    ]
    assert c.list_comp(c.this()).filter(
        c.this() > 1, cast=lambda x: list(x)
    ).execute(range(4)) == [2, 3]


def test_sort():
    assert c.sort().execute([2, 3, 1]) == [1, 2, 3]
    assert c.sort(key=lambda x: x, reverse=True).execute([2, 3, 1]) == [
        3,
        2,
        1,
    ]
    assert c.this().sort().execute([2, 3, 1]) == [1, 2, 3]
    assert c.this().sort(key=lambda x: x, reverse=False).execute(
        [2, 3, 1]
    ) == [1, 2, 3]


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
        .gen_converter(debug=False)
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


def test_slices():
    assert c.this()[
        c.item(0) : c.input_arg("slice_to") : c.item(1)
    ].gen_converter(debug=False)(
        [2, 2, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], slice_to=8
    ) == [
        1,
        3,
        5,
    ]


def test_named_conversion():
    assert NamedConversion("abc", c.item(0)).execute([1]) == 1


def test_conversions_dependencies():
    input_arg = c.input_arg("abc")
    conv = c.item(input_arg)
    assert tuple(conv.get_dependencies()) == (input_arg, conv)


def test_conversion_wrapper():
    assert ConversionWrapper(c.item(1)).execute([0, 10]) == 10
    assert (
        ConversionWrapper(
            ConversionWrapper(
                NamedConversion(
                    "abc",
                    NamedConversion("foo", c.item()) + c.item(),
                )
                + c.item(),
                name_to_code_input={"foo": "arg_foo2"},
            ),
            name_to_code_input={"abc": "arg_abc", "foo": "arg_foo"},
        )
    ).gen_converter(
        debug=False, signature="data_, arg_abc=10, arg_foo=20, arg_foo2=30"
    )(
        1
    ) == 41


def test_name_generation():
    c.list_comp(
        {i: c.item(f"test{i}", default=1) for i in range(100)}
    ).gen_converter(debug=False)

    item = c.this()
    ctx = c.BaseConversion._init_ctx()
    for i in range(11):
        item.gen_name("abc", ctx, i)

    assert item.gen_name("_", ctx, (1, 2)) == item.gen_name("_", ctx, (1, 2))
    obj = object()
    assert item.gen_name("_", ctx, (1, obj)) == item.gen_name(
        "_", ctx, (1, obj)
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


def test_call_like_methods():
    assert c.inline_expr("1").is_itself_callable_like()
    assert c.item(1).is_itself_callable_like() is None
