from collections import OrderedDict
from types import GeneratorType

from convtools import conversion as c
from convtools.base import (
    BaseConversion,
    Call,
    ListComp,
    PipeConversion,
    SetComp,
    TupleComp,
)

from .utils import get_code_str


_none = BaseConversion._none


def test_generator_type_casts():
    assert isinstance(c.generator_comp(c.this).as_type(list), ListComp)
    assert isinstance(c.generator_comp(c.this).as_type(tuple), TupleComp)
    assert isinstance(c.generator_comp(c.this).as_type(set), SetComp)
    conversion = c.this.iter(c.this).as_type(set)
    assert isinstance(conversion, SetComp)
    assert isinstance(
        c.generator_comp(c.this).as_type(lambda x: list(x)), Call
    )
    conversion = c.this.iter(c.this).as_type(lambda x: list(x))
    assert isinstance(conversion, Call)
    assert isinstance(
        c.list_comp(c.this).iter(c.this).execute(range(10)), GeneratorType
    )

    conversion = c.list_comp(c.this)
    assert conversion is conversion.as_type(list)
    conversion = c.set_comp(c.this)
    assert conversion is conversion.as_type(set)
    conversion = c.tuple_comp(c.this)
    assert conversion is conversion.as_type(tuple)

    assert c.set_comp(c.this).as_type(tuple).execute([1, 1, 2]) == (1, 2)

    converter = c.list_comp(c.this + 1).iter(c.this * -1).gen_converter()
    assert list(converter(range(3))) == [-1, -2, -3]
    code_str = get_code_str(converter).replace("__naive_values__[", "")
    assert "[" not in code_str and code_str.count("for ") == 1

    converter = (
        c.list_comp(c.this + 1, where=c.this > 0)
        .iter(c.this * -1)
        .gen_converter()
    )
    assert list(converter(range(3))) == [-2, -3]
    code_str = get_code_str(converter).replace("__naive_values__[", "")
    assert "[" not in code_str and code_str.count("for ") == 1

    converter = (
        c.list_comp(c.this + 1)
        .iter(c.this * -1, where=c.this > 1)
        .gen_converter()
    )
    assert list(converter(range(3))) == [-2, -3]
    code_str = get_code_str(converter).replace("__naive_values__[", "")
    assert "[" not in code_str and code_str.count("for ") == 2

    assert c.list_comp(c.this).as_type(tuple).execute(range(2)) == (0, 1)
    assert c.list_comp(c.this).as_type(set).execute([1, 1, 2]) == {1, 2}
    assert c.list_comp(c.this).as_type(frozenset).execute(
        [1, 1, 2]
    ) == frozenset((1, 2))

    assert list(
        c.tuple_comp(c.this + 1).iter(c.this + 2).execute(range(3))
    ) == [3, 4, 5]
    assert list(
        c.tuple_comp(c.this + 1)
        .iter(c.this + 2, where=c.this > 1)
        .execute(range(3))
    ) == [4, 5]

    assert c.tuple_comp(c.this + 1).as_type(list).execute(range(3)) == [
        1,
        2,
        3,
    ]
    assert c.tuple_comp(c.this + 1).as_type(set).execute({1, 2, 2}) == {2, 3}
    assert c.tuple_comp(c.this + 1).as_type(frozenset).execute(
        {1, 2, 2}
    ) == frozenset((2, 3))


def test_comprehension_filter_cast_assumptions():
    assert isinstance(
        c.generator_comp(c.this).filter(c.this).execute(range(10)),
        GeneratorType,
    )
    assert isinstance(
        c.generator_comp(c.this).filter(c.this).execute(range(10)),
        GeneratorType,
    )
    assert (c.list_comp(c.this).filter(c.this).execute(range(3))) == [
        1,
        2,
    ]

    def f(x):
        f.number_of_calls += 1
        if f.number_of_calls > f.max_number_of_calls:
            raise ValueError
        return bool(x)

    f.max_number_of_calls = 2
    f.number_of_calls = 0

    assert (
        c.set_comp(c.this).filter(c.call_func(f, c.this)).execute([0, 0, 1])
    ) == {
        1,
    }
    assert (
        c.set_comp(c.this).filter(c.this, cast=list).execute([0, 0, 1])
    ) == [
        1,
    ]
    assert (c.set_comp(c.this).filter(c.this).execute(range(3))) == {
        1,
        2,
    }
    assert (c.tuple_comp(c.this).filter(c.this).execute(range(3))) == (
        1,
        2,
    )
    assert (c.tuple_comp(c.this).filter(c.this, list).execute(range(3))) == [
        1,
        2,
    ]
    assert (
        c.dict_comp(c.this, c.this).filter(c.item(0)).execute(range(3))
    ) == {
        1: 1,
        2: 2,
    }
    assert (
        c.dict_comp(c.this, c.this).filter(c.item(0), dict).execute(range(3))
    ) == {
        1: 1,
        2: 2,
    }


def test_comprehension_filter_concats():
    assert c.generator_comp(c.this).filter(c.this > 5).filter(
        c.this < 10
    ).as_type(list).execute(range(20), debug=False) == [6, 7, 8, 9]
    assert c.this.iter(c.this).filter(c.this > 5).filter(c.this < 10).as_type(
        list
    ).execute(range(20), debug=False) == [6, 7, 8, 9]


def test_comprehension_where():
    assert (
        c.generator_comp(c.this.neg(), where=c.this > 6)
        .as_type(list)
        .filter(c.this > -9)
        .execute(range(10), debug=False)
    ) == [-7, -8]
    assert (
        c.this.iter(c.this.neg(), where=c.this > 6)
        .as_type(list)
        .filter(c.this > -9)
        .execute(range(10), debug=True)
    ) == [-7, -8]
    assert (
        c.iter(c.this.neg(), where=c.this > 6)
        .as_type(list)
        .filter(c.this > -9)
        .execute(range(10), debug=False)
    ) == [-7, -8]

    assert c.iter(c.this, where=c.and_(default=True)).as_type(list).execute(
        range(3)
    ) == [0, 1, 2]
    assert c.iter(c.this, where=True).as_type(list).execute(range(3)) == [
        0,
        1,
        2,
    ]
    assert (
        c.iter(c.this, where=c.and_(default=False))
        .as_type(list)
        .execute(range(3))
        == []
    )


def test_comprehensions_sorting():
    assert c.generator_comp(c.this).sort().execute([2, 1, 3], debug=False) == [
        1,
        2,
        3,
    ]
    assert c.list_comp(c.this).sort().execute([2, 1, 3], debug=False) == [
        1,
        2,
        3,
    ]
    assert c.this.pipe(c.list_comp(c.this)).sort().execute(
        [2, 1, 3], debug=False
    ) == [
        1,
        2,
        3,
    ]
    assert c.list_comp(c.this).sort().sort(reverse=True).execute(
        [2, 1, 3], debug=False
    ) == [3, 2, 1]

    assert c.set_comp(c.this).sort().execute([2, 2, 1, 3], debug=False) == [
        1,
        2,
        3,
    ]
    assert c.tuple_comp(c.this).sort().execute([2, 2, 1, 3], debug=False) == (
        1,
        2,
        2,
        3,
    )
    assert c.dict_comp(c.this * -1, c.this).sort().execute(
        [2, 2, 1, 3], debug=False
    ) == OrderedDict(
        [
            (-3, 3),
            (-2, 2),
            (-1, 1),
        ]
    )
