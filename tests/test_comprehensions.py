from collections import OrderedDict
from types import GeneratorType

from convtools import conversion as c
from convtools.base import Call, FilterConversion, PipeConversion


def test_generator_type_casts():
    assert isinstance(c.generator_comp(c.this()).as_type(list), c.list_comp)
    assert isinstance(c.generator_comp(c.this()).as_type(tuple), c.tuple_comp)
    assert isinstance(c.generator_comp(c.this()).as_type(set), c.set_comp)
    conversion = c.this().iter(c.this()).as_type(set)
    assert isinstance(conversion, PipeConversion) and isinstance(
        conversion.where, c.set_comp
    )
    assert isinstance(
        c.generator_comp(c.this()).as_type(lambda x: list(x)), Call
    )
    conversion = c.this().iter(c.this()).as_type(lambda x: list(x))
    assert isinstance(conversion, PipeConversion) and isinstance(
        conversion.where, Call
    )


def test_comprehension_filter_cast_assumptions():
    assert isinstance(
        c.generator_comp(c.this()).filter(c.this()).execute(range(10)),
        GeneratorType,
    )
    assert isinstance(
        c.generator_comp(c.this())
        .filter(c.this(), cast=None)
        .execute(range(10)),
        GeneratorType,
    )
    assert (c.list_comp(c.this()).filter(c.this()).execute(range(3))) == [
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
        c.set_comp(c.this())
        .filter(c.call_func(f, c.this()))
        .execute([0, 0, 1])
    ) == {
        1,
    }
    assert (
        c.set_comp(c.this()).filter(c.this(), cast=list).execute([0, 0, 1])
    ) == [
        1,
    ]
    assert (c.set_comp(c.this()).filter(c.this()).execute(range(3))) == {
        1,
        2,
    }
    assert (c.tuple_comp(c.this()).filter(c.this()).execute(range(3))) == (
        1,
        2,
    )
    assert (
        c.tuple_comp(c.this()).filter(c.this(), list).execute(range(3))
    ) == [
        1,
        2,
    ]
    assert (
        c.dict_comp(c.this(), c.this()).filter(c.item(0)).execute(range(3))
    ) == {
        1: 1,
        2: 2,
    }
    assert (
        c.dict_comp(c.this(), c.this())
        .filter(c.item(0), dict)
        .execute(range(3))
    ) == {
        1: 1,
        2: 2,
    }


def test_comprehension_filter_concats():
    assert c.generator_comp(c.this()).filter(c.this() > 5).filter(
        c.this() < 10
    ).as_type(list).execute(range(20), debug=True) == [6, 7, 8, 9]
    assert c.this().iter(c.this()).filter(c.this() > 5).filter(
        c.this() < 10
    ).as_type(list).execute(range(20), debug=True) == [6, 7, 8, 9]


def test_comprehensions_sorting():
    assert c.generator_comp(c.this()).sort().execute(
        [2, 1, 3], debug=True
    ) == [1, 2, 3]
    assert c.list_comp(c.this()).sort().execute([2, 1, 3], debug=True) == [
        1,
        2,
        3,
    ]
    assert c.this().pipe(c.list_comp(c.this())).sort().execute(
        [2, 1, 3], debug=True
    ) == [
        1,
        2,
        3,
    ]
    assert c.list_comp(c.this()).sort().sort(reverse=True).execute(
        [2, 1, 3], debug=True
    ) == [3, 2, 1]

    assert c.set_comp(c.this()).sort().execute([2, 2, 1, 3], debug=True) == [
        1,
        2,
        3,
    ]
    assert c.tuple_comp(c.this()).sort().execute([2, 2, 1, 3], debug=True) == (
        1,
        2,
        2,
        3,
    )
    assert c.dict_comp(c.this() * -1, c.this()).sort().execute(
        [2, 2, 1, 3], debug=True
    ) == OrderedDict(
        [
            (-3, 3),
            (-2, 2),
            (-1, 1),
        ]
    )
