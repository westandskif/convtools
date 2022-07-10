import json
import re
import sys
import typing as t
from datetime import date, datetime
from decimal import ROUND_DOWN, Decimal
from enum import Enum
from random import random

import pytest

from convtools import conversion as c
from convtools.contrib.models import (
    DictModel,
    ObjectModel,
    ValidationError,
    build,
    build_or_raise,
    cached_model_method,
    cast,
    casters,
    field,
    json_dumps,
    set_max_cache_size,
    to_dict,
    validate,
    validators,
)
from convtools.contrib.models.base import ErrorsDict
from convtools.contrib.models.models import TypeConversion
from convtools.contrib.models.utils import TypeValueWrapper


PY_VERSION = sys.version_info[0:2]

T = t.TypeVar("T")
U = t.TypeVar("U")


def test_model__dictmodel__base():
    class TestModel(DictModel):
        a: int
        b: int = 1
        c: str
        d: t.Optional[str]
        e: t.List[int]

    input_data = {"a": 1, "c": "c_str", "d": None, "e": []}
    obj, errors = build(TestModel, input_data)
    assert (
        obj.a == obj["a"] == 1
        and obj.b == obj["b"] == 1
        and obj.c == obj["c"] == "c_str"
        and obj.d is None
        and obj["d"] is None
        and obj.e == obj["e"] == []
    )
    input_data = {"a": 1, "b": 2, "c": "c_str", "d": "d_str", "e": [1, 2, 3]}
    obj, errors = build(TestModel, input_data)
    assert (
        obj.a == 1
        and obj.b == 2
        and obj.c == "c_str"
        and obj.d == "d_str"
        and obj.e == [1, 2, 3]
    )

    class Types(Enum):
        FIRST = 1
        SECOND = 2

    class FirstModel(DictModel):
        a: int

    class SecondModel(DictModel):
        first: FirstModel
        dt: date
        type_: Types

    input_data = {
        "first": {"a": 1},
        "dt": date(1970, 1, 1),
        "type_": Types.FIRST,
    }
    obj = build_or_raise(
        SecondModel,
        input_data,
    )

    assert json_dumps(obj) == json.dumps(
        {"first": {"a": 1}, "dt": "1970-01-01", "type_": 1}
    )

    assert obj.to_dict() == input_data

    with pytest.raises(TypeError):
        json_dumps(object())

    with pytest.raises(ValidationError):
        obj = build_or_raise(SecondModel, None)


def test_model__objectmodel():
    class FirstModel(ObjectModel):
        a: int
        b: int = field("objects", 0, "value")

    class Value:
        value = 7

    class Data:
        a = 10
        objects = [Value]

    obj = build_or_raise(FirstModel, Data)
    assert obj.a == 10 and obj.b == 7


def test_model__any():
    class TestModel(DictModel):
        a: t.Any

    any_ = object()
    obj, errors = build(TestModel, {"a": any_})
    assert obj.a is any_

    class TestModel(DictModel):
        a: t.List[t.Any]

    obj, errors = build(TestModel, {"a": [any_, 1, "asd"]})
    assert obj.a == [any_, 1, "asd"]

    class TestModel(DictModel):
        a: t.List[t.Any] = cast()

    obj, errors = build(TestModel, None)
    assert errors["a"]["__ERRORS"]["required"]

    obj, errors = build(TestModel, {"a": [1, "a"]})
    assert obj.a == [1, "a"]


def test_model__str():
    class TestModel(DictModel):
        a: str
        b: str = cast()
        c: str = cast(str)

    obj, errors = build(TestModel, {"a": None})
    assert errors["a"]["__ERRORS"]["type"]

    obj, errors = build(TestModel, {"a": "abc", "b": 123, "c": 234})
    assert obj.a == "abc" and obj.b == "123" and obj.c == "234"

    class TestModel(DictModel):
        a: t.Optional[str]
        b: t.Optional[str] = cast()

    obj, errors = build(TestModel, {"a": None, "b": 1})
    assert obj.a is None and obj.b == "1"

    class TestModel(DictModel):
        a: t.Union[int, str] = cast()

    obj, errors = build(t.List[TestModel], [{"a": "1"}, {"a": b"abc"}])
    assert obj[0].a == 1 and obj[1].a == "abc"

    class TestModel(DictModel):
        a: str = cast(casters.Str())

    obj, errors = build(TestModel, {"a": b"abc"})
    assert obj.a == "abc"
    obj, errors = build(TestModel, {"a": "абв".encode("cp1251")})
    assert errors["a"]["__ERRORS"]["decoding"]


def test_model__naive():
    class TestModel(DictModel):
        a: float = cast()

    obj, errors = build(TestModel, {"a": "abc"})
    assert errors["a"]["__ERRORS"]["float_caster"]
    obj, errors = build(TestModel, {"a": "1.1"})
    assert obj.a == 1.1
    obj, errors = build(TestModel, {"a": 1.1})
    assert obj.a == 1.1


def test_model__int():
    class TestModel(DictModel):
        a: int

    obj, errors = build(TestModel, None)
    assert errors["a"]["__ERRORS"]["required"]

    obj, errors = build(TestModel, {"a": "1"})
    assert errors["a"]["__ERRORS"]["type"]

    class TestModel(DictModel):
        a: int = cast()

    obj, errors = build(TestModel, {"a": "1.1"})
    assert errors["a"]["__ERRORS"]["int_caster"]

    obj, errors = build(TestModel, {"a": 1.1})
    assert errors["a"]["__ERRORS"]["int_caster"]

    obj, errors = build(TestModel, {"a": Decimal("1.1")})
    assert errors["a"]["__ERRORS"]["int_caster"]

    obj, errors = build(TestModel, {"a": "1"})
    assert obj.a == 1

    obj, errors = build(TestModel, {"a": 1.0})
    assert obj.a == 1

    obj, errors = build(TestModel, {"a": Decimal("1.0")})
    assert obj.a == 1

    class TestModel(DictModel):
        a: int = cast(casters.IntLossy())

    obj, errors = build(TestModel, {"a": "b"})
    assert errors["a"]["__ERRORS"]["int_lossy_caster"]

    obj, errors = build(TestModel, {"a": "1.1"})
    assert obj.a == 1

    obj, errors = build(TestModel, {"a": 1})
    assert obj.a == 1

    obj, errors = build(TestModel, {"a": 1.1})
    assert obj.a == 1

    obj, errors = build(TestModel, {"a": Decimal("1.1")})
    assert obj.a == 1

    class TestModel(DictModel):
        a: int = cast(str)

    obj, errors = build(TestModel, {"a": "1"})
    assert errors["a"]["__ERRORS"]["type"]

    class TestModel(DictModel):
        a: int = cast()

    obj, errors = build(TestModel, {"a": None})
    assert errors["a"]["__ERRORS"]["int_caster"]


def test_model__decimal():
    class TestModel(DictModel):
        a: Decimal

    obj, errors = build(TestModel, None)
    assert errors["a"]["__ERRORS"]["required"]

    obj, errors = build(TestModel, {"a": "1"})
    assert errors["a"]["__ERRORS"]["type"]

    class TestModel(DictModel):
        a: Decimal = cast()

    obj, errors = build(TestModel, {"a": "b"})
    assert errors["a"]["__ERRORS"]["decimal_caster"]

    obj, errors = build(TestModel, {"a": 1.1})
    assert errors["a"]["__ERRORS"]["decimal_caster"]

    obj, errors = build(TestModel, {"a": None})
    assert errors["a"]["__ERRORS"]["decimal_caster"]

    obj, errors = build(TestModel, {"a": "1.1"})
    assert obj.a == Decimal("1.1")

    obj, errors = build(TestModel, {"a": Decimal("1.1")})
    assert obj.a == Decimal("1.1")

    obj, errors = build(TestModel, {"a": 1.0})
    assert obj.a == Decimal("1.0")

    class TestModel(DictModel):
        a: Decimal = cast(casters.DecimalLossy())

    obj, errors = build(TestModel, {"a": "b"})
    assert errors["a"]["__ERRORS"]["decimal_lossy_caster"]

    obj, errors = build(TestModel, {"a": 1.1})
    assert abs(obj.a - Decimal("1.1")) < Decimal("1e-16")

    class TestModel(DictModel):
        a: Decimal = cast().validate(
            validators.Decimal(max_digits=3, decimal_places=2)
        )

    obj, errors = build(TestModel, {"a": "12"})
    assert errors["a"]["__ERRORS"]["integer_digits"]
    obj, errors = build(TestModel, {"a": "0.034"})
    assert errors["a"]["__ERRORS"]["decimal_places"]
    obj, errors = build(TestModel, {"a": "1.234"})
    assert errors["a"]["__ERRORS"]["max_digits"]
    obj, errors = build(TestModel, {"a": "1.23"})
    assert obj.a == Decimal("1.23")

    class TestModel(DictModel):
        a: Decimal = cast(
            casters.DecimalLossy(
                quantize_exp=Decimal("1e-2"), rounding=ROUND_DOWN
            )
        )

    obj, errors = build(TestModel, {"a": "1.345"})
    assert obj.a == Decimal("1.34")
    obj, errors = build(TestModel, {"a": "abc"})
    assert errors["a"]["__ERRORS"]["decimal_lossy_caster"]

    class TestModel(DictModel):
        a: Decimal = cast(
            casters.DecimalLossy(quantize_exp=Decimal("1e-2"))
        ).validate(validators.Decimal(max_digits=4, decimal_places=2))

    obj, errors = build(TestModel, {"a": "12.355"})
    assert obj.a == Decimal("12.36")
    obj, errors = build(TestModel, {"a": "120.355"})
    assert errors["a"]["__ERRORS"]["max_digits"]

    with pytest.raises(ValueError):
        validators.Decimal(1, 2)

    class TestModel(DictModel):
        a: Decimal = validate(validators.Decimal(5, 2))

    obj, errors = build(TestModel, {"a": 1})
    assert errors["a"]["__ERRORS"]["type"]


def test_model__dates():
    class TestModel(DictModel):
        a: date = cast(casters.DateFromStr("%Y-%m-%d"))

    obj, errors = build(TestModel, {"a": "1970-01-01"})
    assert obj.a == date(1970, 1, 1)

    obj, errors = build(TestModel, {"a": "1970-31-01"})
    assert errors["a"]

    obj, errors = build(TestModel, {"a": "abc"})
    assert errors["a"]

    obj, errors = build(TestModel, {"a": 1})
    assert errors["a"]

    class TestModel(DictModel):
        a: datetime = cast(casters.DatetimeFromStr("%Y-%m-%d"))

    obj, errors = build(TestModel, {"a": "1970-01-01"})
    assert obj.a == datetime(1970, 1, 1)

    obj, errors = build(TestModel, {"a": "1970-31-01"})
    assert errors["a"]

    obj, errors = build(TestModel, {"a": "abc"})
    assert errors["a"]

    obj, errors = build(TestModel, {"a": 1})
    assert errors["a"]


def test_model__enum():
    class ValueTypes(Enum):
        FIRST = 1
        SECOND = 2

    class TestModel(DictModel):
        a: ValueTypes = cast()
        b: ValueTypes = field("a").cast(ValueTypes)
        c: t.Optional[ValueTypes]
        d: t.Optional[ValueTypes] = cast()

    obj, errors = build(TestModel, {"a": 1, "c": None, "d": None})
    assert (
        isinstance(obj.a, ValueTypes)
        and isinstance(obj.b, ValueTypes)
        and obj.a.value == obj.b.value == 1
        and obj.c is None
        and obj.d is None
    )
    obj, errors = build(TestModel, {"a": 1, "c": ValueTypes.SECOND, "d": 2})
    assert obj.c.value == 2 and obj.d.value == 2

    obj, errors = build(TestModel, {"a": 1, "c": 2, "d": None})
    assert errors["c"]["__ERRORS"]["type"]

    obj, errors = build(TestModel, {"a": "1"})
    assert errors["a"]["__ERRORS"]["enum_caster"]

    class TestModel(DictModel):
        a: int = validate(validators.Enum(ValueTypes))

    obj, errors = build(TestModel, {"a": "1"})
    assert errors["a"]["__ERRORS"]["enum"]
    obj, errors = build(TestModel, {"a": 3})
    assert errors["a"]["__ERRORS"]["enum"]
    obj, errors = build(TestModel, {"a": 1})
    assert obj.a == 1

    class TestModel(DictModel):
        a: int = cast().validate(validators.Enum(ValueTypes))

    obj, errors = build(TestModel, {"a": "1"})
    assert obj.a == 1
    obj, errors = build(TestModel, {"a": "2"})
    assert obj.a == 2
    obj, errors = build(TestModel, {"a": "3"})
    assert errors["a"]["__ERRORS"]["enum"]

    with pytest.raises(ValueError):

        class TestModel(DictModel):
            a: int = validate(validators.Enum(int))


def test_model__list():
    class TestModel(DictModel):
        a: t.List[int]

    obj, errors = build(TestModel, {"a": [1]})
    assert obj.a == [1]

    obj, errors = build(TestModel, {"a": [1, "2"]})
    assert errors["a"][1]["__ERRORS"]["type"]

    obj, errors = build(TestModel, {"a": None})
    assert errors["a"]["__ERRORS"]["type"]

    class TestModel(DictModel):
        a: t.Optional[t.List[int]]

    obj, errors = build(TestModel, {"a": None})
    assert obj.a is None

    obj, errors = build(TestModel, {"a": [1, 2]})
    assert obj.a == [1, 2]

    class TestModel(DictModel):
        a: t.Optional[t.Union[t.List[int], t.List[str]]]

    obj, errors = build(TestModel, {"a": None})
    assert obj.a is None
    obj, errors = build(TestModel, {"a": [1, 2]})
    assert obj.a == [1, 2]
    obj, errors = build(TestModel, {"a": ["1", "2"]})
    assert obj.a == ["1", "2"]
    obj, errors = build(TestModel, {"a": ["1", 2]})
    assert errors["a"]["__ERRORS"]["type"]

    class TestModel(DictModel):
        a: t.List[t.Union[int, str, float]]

    obj, errors = build(TestModel, {"a": ["1", 2, 3.5]})
    assert obj.a == ["1", 2, 3.5]

    obj, errors = build(TestModel, {"a": ["1", 2, Decimal(3.5)]})
    assert errors["a"][2]["__ERRORS"]["type"]

    class TestModel(DictModel):
        a: t.List[t.Optional[int]] = cast()

    obj, errors = build(TestModel, {"a": None})
    assert errors["a"]["__ERRORS"]["type"]

    obj, errors = build(TestModel, {"a": [1, "2", 3.0, None]})
    assert obj.a == [1, 2, 3, None]

    obj, errors = build(TestModel, {"a": [1, "2", 3.0, None, 3.1]})
    assert errors["a"][4]["__ERRORS"]["int_caster"]

    class AModel(DictModel):
        a: t.Optional[int] = cast()

    class TestModel(DictModel):
        a_objects: t.List[AModel]

    obj, errors = build(
        TestModel,
        {"a_objects": [{"a": 1}, {"a": "2"}, {"a": 3.0}, {"a": None}]},
    )
    assert (
        obj.a_objects[0].a == 1
        and obj.a_objects[1].a == 2
        and obj.a_objects[2].a == 3
        and obj.a_objects[3].a is None
    )

    class TestModel(DictModel):
        a: t.List[t.List[int]] = cast()

    obj, errors = build(TestModel, {"a": [["1", 2, 3.0]]})
    assert obj.a == [[1, 2, 3]]


class TestModelWithForwardRef(DictModel):
    a: "t.Optional[t.Dict[str, int]]" = cast()


def test_model__dict():
    class TestModel(DictModel):
        a: dict
        b: dict = cast()

    obj, errors = build(TestModel, {"a": {"k": 1}, "b": [("j", 2)]})
    assert obj.a == {"k": 1} and obj.b == {"j": 2}

    obj, errors = build(TestModel, {"a": "k", "b": "j"})
    assert (
        errors["a"]["__ERRORS"]["type"]
        and errors["b"]["__ERRORS"]["dict_caster"]
    )

    class TestModel(DictModel):
        a: t.Dict[str, int]

    obj, errors = build(TestModel, {"a": {"k": 1}})
    assert obj.a == {"k": 1}

    obj, errors = build(TestModel, {"a": {2: 1}})
    assert errors["a"]["__KEYS"][2]["__ERRORS"]["type"]

    obj, errors = build(TestModel, {"a": {"k": "1"}})
    assert errors["a"]["__VALUES"]["k"]["__ERRORS"]["type"]

    obj, errors = build(TestModelWithForwardRef, {"a": {1: "1"}})
    assert obj.a == {"1": 1}

    obj, errors = build(TestModelWithForwardRef, {"a": None})
    assert obj.a is None

    obj, errors = build(TestModelWithForwardRef, {"a": 1})
    assert errors["a"]["__ERRORS"]["type"]

    obj, errors = build(TestModelWithForwardRef, {"a": {1: "1.1"}})
    assert errors["a"]["__VALUES"][1]["__ERRORS"]["int_caster"]

    class InnerModel(DictModel):
        b: int = cast()

    class TestModel(DictModel):
        a: t.Dict[str, InnerModel]

    obj, errors = build(TestModel, {"a": {"key": {"b": "23"}}})
    assert obj.a["key"].b == 23

    obj, errors = build(TestModel, {"a": {7: {"b": "23"}}})
    assert errors["a"]["__KEYS"][7]["__ERRORS"]["type"]

    class TestModel(DictModel):
        a: t.Dict[float, int] = cast()

    obj, errors = build(TestModel, {"a": {"7.1": "2"}})
    assert obj.a == {7.1: 2}

    obj, errors = build(TestModel, {"a": {"7.1": "2"}})
    assert obj.a == {7.1: 2}

    obj, errors = build(TestModel, {"a": [("7.1", "2")]})
    assert obj.a == {7.1: 2}

    obj, errors = build(TestModel, {"a": [("7.1", "2.0")]})
    assert errors["a"]["__VALUES"]["7.1"]["__ERRORS"]["int_caster"]

    obj, errors = build(TestModel, {"a": [("7.1", "2"), (1.5,)]})
    assert errors["a"][1]["__ERRORS"]["pair"]


def test_model__casters__custom():
    class TestModel(DictModel):
        a: int = cast(casters.Custom("tst", int, ValueError))

    obj, errors = build(TestModel, {"a": "1"})
    assert obj.a == 1

    obj, errors = build(TestModel, {"a": "1.1"})
    assert errors["a"]["__ERRORS"]["tst"]

    with pytest.raises(TypeError):
        build(TestModel, {"a": None})

    class TestModel(DictModel):
        a: int = cast(casters.CustomUnsafe(int))

    obj, errors = build(TestModel, {"a": "1"})
    assert obj.a == 1

    with pytest.raises(ValueError):
        build(TestModel, {"a": "1.1"})


def test_model__validators__required():
    class TestModel(DictModel):
        a: str = field(default="default_a")
        b: str = "default_b"

    obj, errors = build(TestModel, {"a": "cde"})
    assert obj.a == "cde" and obj.b == "default_b"

    obj, errors = build(TestModel, {"a": None})
    assert errors["a"]["__ERRORS"]["type"]

    obj, errors = build(TestModel, {"b": "new"})
    assert obj.a == "default_a" and obj.b == "new"

    class TestModel(DictModel):
        a: int = field(default_factory=int)

    obj, errors = build(TestModel, {"a": 1})
    assert obj.a == 1

    obj, errors = build(TestModel, {"b": 1})
    assert obj.a == 0

    with pytest.raises(ValueError):

        class TestModel(DictModel):
            a: int = field(default=0, default_factory=int)

    with pytest.raises(ValueError):

        class TestModel(DictModel):
            a: int = field(cls_method=True, default=0)

    with pytest.raises(ValueError):

        class TestModel(DictModel):
            a: int = field(cls_method=True, default_factory=int)


def test_model__cls_method():
    class TestModel(DictModel):
        a: int = field(cls_method=True)
        b: float = field(cls_method="get_random")
        c: float = field(cls_method="get_random")
        d: float = field(cls_method="get_random2")

        @classmethod
        def get_a(cls, data):
            if data > 100:
                return None, {"too_big": True}
            return int(data), None

        @cached_model_method
        def get_random(cls, data):
            return random(), None

        @classmethod
        def get_random2(cls, data):
            return random(), None

    obj, errors = build(TestModel, 100.1)
    assert errors["a"]["__ERRORS"]["too_big"]

    obj, errors = build(TestModel, 100.0)
    assert obj.a == 100 and obj.b == obj.c and obj.b != obj.d

    with pytest.raises(RuntimeError):

        class TestModel(DictModel):
            a: int = field(cls_method=True)

    with pytest.raises(RuntimeError):

        class TestModel(DictModel):
            a: int = field(cls_method=True)

            def get_a(self, data):
                pass


def test_model__validators__type():
    with pytest.raises(ValueError):
        validators.Type(t.List[int])

    class TestModel(DictModel):
        a: str = validate(validators.Type(int)).cast()

    obj, errors = build(TestModel, {"a": 1})
    assert obj.a == "1"

    obj, errors = build(TestModel, {"a": "1"})
    assert errors["a"]["__ERRORS"]["type"]


def test_model__validators__regex():
    class TestModel(DictModel):
        a: int = validate(validators.Regex(r"\d+")).cast()
        b: str = validate(validators.Regex(re.compile(r"\d+")))

    obj, errors = build(TestModel, {"a": "123", "b": "234"})
    assert obj.a == 123 and obj.b == "234"

    obj, errors = build(TestModel, {"a": " 123", "b": " 234"})
    assert (
        errors["a"]["__ERRORS"]["regex"] and errors["b"]["__ERRORS"]["regex"]
    )

    with pytest.raises(TypeError):
        build(TestModel, {"a": 123})


def test_model__validators__length():
    with pytest.raises(ValueError):

        class TestModel(DictModel):
            a: str = validate(validators.Length())

    class TestModel(DictModel):
        a: str = validate(validators.Length(min_length=1))
        b: str = validate(validators.Length(max_length=2))
        c: str = validate(validators.Length(min_length=1, max_length=2))

    obj, errors = build(TestModel, {"a": "x", "b": "x", "c": "x"})
    assert obj.a == "x" and obj.b == "x" and obj.c == "x"
    obj, errors = build(TestModel, {"a": "xx", "b": "xx", "c": "xx"})
    assert obj.a == "xx" and obj.b == "xx" and obj.c == "xx"
    obj, errors = build(TestModel, {"a": "", "b": "xxx", "c": ""})
    assert (
        errors["a"]["__ERRORS"]["min_length"]
        and errors["b"]["__ERRORS"]["max_length"]
        and errors["c"]["__ERRORS"]["min_length"]
    )
    obj, errors = build(TestModel, {"a": "x", "b": "x", "c": "xxx"})
    assert errors["c"]["__ERRORS"]["max_length"]

    for kwargs in [
        {"min_length": 1},
        {"max_length": 1},
        {"min_length": 1, "max_length": 2},
    ]:

        class TestModel(DictModel):
            a: str = validate(validators.Length(**kwargs))

        obj, errors = build(TestModel, {"a": None})
        assert errors["a"]["__ERRORS"]["type"]


def test_model__validators__comparisons():
    class TestModel(DictModel):
        a: int = cast().validate(validators.Gt(10))
        b: int = validate(validators.Lt(10))
        c: int = validate(validators.Gte(10))
        d: int = validate(validators.Gte(10))
        e: int = validate(validators.Lte(10))
        f: int = validate(validators.Lte(10))

    obj, errors = build(
        TestModel, {"a": "123", "b": 9, "c": 10, "d": 11, "e": 10, "f": 9}
    )
    assert obj.to_dict() == {
        "a": 123,
        "b": 9,
        "c": 10,
        "d": 11,
        "e": 10,
        "f": 9,
    }

    obj, errors = build(TestModel, {"a": " 3", "b": 10, "c": 9, "e": 11})
    assert (
        errors["a"]["__ERRORS"]["gt"]
        and errors["b"]["__ERRORS"]["lt"]
        and errors["c"]["__ERRORS"]["gte"]
        and errors["d"]["__ERRORS"]["required"]
        and errors["e"]["__ERRORS"]["lte"]
        and errors["f"]["__ERRORS"]["required"]
    )


def test_model__validators__custom():
    class TestModel(DictModel):
        a: int = validate(validators.Custom("invalid", bool))
        b: int = validate(bool).cast()

    obj, errors = build(TestModel, {"a": 1, "b": False})
    assert obj.a == 1 and obj.b == 0

    obj, errors = build(TestModel, {"a": 0})
    assert errors["a"]["__ERRORS"]["invalid"]

    with pytest.raises(ValueError):

        class TestModel(DictModel):
            a: int = validate(validators.Custom("invalid", object()))


def test_model__exceptions():
    with pytest.raises(ValueError):

        class TestModel(DictModel):
            a: int = validate()

    with pytest.raises(ValueError):

        class TestModel(DictModel):
            a: int = cast(object)

        build(TestModel, {"a": None})

    with pytest.raises(ValueError):

        class TestModel(DictModel):
            a: t.Sequence[str] = cast(t.Sequence[str])

        build(TestModel, {"a": None})

    from convtools.contrib.models.base import TypeValueCodeGenArgs
    from convtools.contrib.models.type_handlers import type_value_to_code

    args = TypeValueCodeGenArgs(
        None,
        None,
        object(),
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )
    with pytest.raises(Exception):
        type_value_to_code(args)

    with pytest.raises(Exception):

        class TestModel(DictModel):
            a: t.Sequence[int]

        build(TestModel, {"a": (1,)})

    class TestModel(DictModel):
        a: int = cast(object())

    with pytest.raises(ValueError):
        build(TestModel, None)


def test_model__generics():
    class ThirdModel(DictModel, t.Generic[T]):
        d: T = cast()

    class SecondModel(DictModel):
        c: int = cast()

    class FirstModel(DictModel, t.Generic[T]):
        a: SecondModel
        b: T

    with pytest.raises(ValueError):
        build(FirstModel, None)

    obj, errors = build(FirstModel[int], {"a": {"c": "123"}, "b": 345})
    assert obj.a.c == 123 and obj.b == 345

    obj, errors = build(
        FirstModel[ThirdModel[int]], {"a": {"c": "123"}, "b": {"d": "345"}}
    )
    assert obj.a.c == 123 and obj.b.d == 345

    class SecondModel(DictModel, t.Generic[T]):
        c: T = cast()

    class FirstModel(DictModel, t.Generic[T]):
        a: SecondModel[T]
        b: T = cast()

    obj, errors = build(
        t.List[FirstModel[int]], [{"a": {"c": "12"}, "b": "34 "}]
    )
    assert json.loads(json_dumps(obj)) == [{"a": {"c": 12}, "b": 34}]

    U = t.TypeVar("U")

    class ResponseModel(DictModel, t.Generic[U]):
        data: t.List[U]

    class UserModel(DictModel, t.Generic[U]):
        parameter: U = cast()

    response = build_or_raise(
        ResponseModel[UserModel[int]], {"data": [{"parameter": " 123 "}]}
    )
    assert response.data[0].parameter == 123

    class TestModel(DictModel):
        data: t.List[t.Any] = cast(t.List[int])

    obj, errors = build(TestModel, {"data": [1, "2", 3.0]})
    assert obj.data == [1, 2, 3]


def test_model__casters_multiple():
    class TestModel(DictModel):
        a: Decimal = cast(int).cast(str).cast()

    obj, errors = build(TestModel, {"a": 1.0})
    assert obj.a == Decimal("1")


def test_model__unions():
    # class TestModel(DictModel):
    #     a: t.Union[t.List[int], t.List[str]]

    # obj, errors = build(TestModel, {"a": ["1"]})
    # assert obj.a == ["1"]

    class TestModel(DictModel):
        a: t.List[t.Union[int, str]] = cast()
        b = 7

    obj, errors = build(TestModel, {"a": ["1", "1.1", 1.2, " 2 "]})
    assert obj.a == [1, "1.1", "1.2", 2] and obj.b == 7

    class TestModel(DictModel):
        a: t.Union[t.Dict[int, int], t.List[int]] = cast()

    obj, errors = build(
        t.List[TestModel],
        [
            {"a": ["1", 1.0, 2, " 3 "]},
            {"a": {1.0: "1", 2: " 3 "}},
        ],
    )
    assert to_dict(obj) == [{"a": [1, 1, 2, 3]}, {"a": {1: 1, 2: 3}}]

    obj, errors = build(
        t.List[TestModel],
        [
            {"a": ["1", 1.0, 2.5, " 3 "]},
            {"a": {1.0: "1", 2: " 3 "}},
        ],
    )
    assert errors[0]["a"][2]["__ERRORS"]["int_caster"]


def test_model__optional():
    class TestModel(DictModel):
        a: t.Optional[date] = cast()

    obj, errors = build(TestModel, {"a": "2000-01-01"})
    assert obj.a == date(2000, 1, 1)

    obj, errors = build(TestModel, {"a": None})
    assert obj.a is None

    obj, errors = build(TestModel, {"a": "2000"})
    assert errors["a"]["__ERRORS"]["date_from_str"]

    class TestModel(DictModel):
        a: t.Optional[str] = None

    obj, errors = build(TestModel, {"a": None})
    assert obj.a is None
    obj, errors = build(TestModel, {"a": "abc"})
    assert obj.a == "abc"
    obj, errors = build(TestModel, None)
    assert obj.a is None


def test_model__type_conversion():
    class TestModel(DictModel):
        a: t.List[int] = cast()

    result = (
        TypeConversion(TypeValueWrapper(TestModel, False, None))
        .pipe(c.item(0).attr("a"))
        .execute({"a": ["1", 2.0]}, debug=True)
    )
    assert result == [1, 2]


def test_model__cast_validate_independence():
    class TestModel(DictModel):
        a: t.List[int] = cast()
        b: t.List[int]

    obj, errors = build(TestModel, {"a": [1.1], "b": [2, "abc"]})
    assert (
        errors["a"][0]["__ERRORS"]["int_caster"]
        and errors["b"][1]["__ERRORS"]["type"]
    )


class TestModel(DictModel):
    a: str
    b: "TestModel"


class TestModel2(DictModel):
    a: int
    b: "TestModel2"


class TestModel3(DictModel):
    a: int = cast()
    b: "t.Optional[TestModel3]"


def test_model__self_type():
    x1 = {"a": "1", "b": None}
    x2 = {"a": "2", "b": x1}
    x3 = {"a": "3", "b": x2}
    x1["b"] = x3

    obj, errors = build(TestModel, x1)
    assert obj.b.b.b.b.b.a == "2"

    obj, errors = build(TestModel2, x1)
    assert (
        errors["a"]["__ERRORS"]["type"]
        and errors["b"]["a"]["__ERRORS"]["type"]
        and errors["b"]["b"]["a"]["__ERRORS"]["type"]
    )

    x1 = {"a": "1", "b": None}
    x2 = {"a": "2", "b": x1}
    obj, errors = build(TestModel3, x2)
    assert obj.a == 2 and obj.b.a == 1 and obj.b.b is None


def test_model__prepare_validate():
    class TestModel(DictModel):
        a: int = cast()
        b: str = cast()
        c: float = field(cls_method=True).cast()

        @classmethod
        def get_c(cls, data):
            return Decimal("1.5"), None

        @classmethod
        def prepare(cls, data):
            if data:
                return json.loads(data), None
            return None, {"is_blank": True}

        @classmethod
        def validate(cls, model):
            if model.a > 100:
                return None, {"a_too_big": True}

            if not model.b:
                return None, {"b_blank": True}
            return model, None

    obj, errors = build(TestModel, None)
    assert errors["__ERRORS"]["is_blank"]

    obj, errors = build(TestModel, '{"a": "1", "b": 2}')
    assert obj.to_dict() == {"a": 1, "b": "2", "c": 1.5}

    obj, errors = build(TestModel, '{"a": "101", "b": 2}')
    assert errors["__ERRORS"]["a_too_big"]

    obj, errors = build(TestModel, '{"a": "1", "b": ""}')
    assert errors["__ERRORS"]["b_blank"]

    class TestModel(DictModel):
        a: int

        @classmethod
        def prepare__(cls, data):
            return {"a": 1}, None

        @classmethod
        def validate__(cls, model):
            if model.a > 0:
                return None, {"a": "is positive"}
            return model, None

    obj, errors = build(TestModel, None)
    assert errors["__ERRORS"]["a"] == "is positive"


def test_model__private_fields():
    class TestModel(DictModel):
        a: int
        b: str

        class Meta:
            private_fields = ("b",)

    obj, errors = build(TestModel, {"a": 1})
    assert obj.a == 1


def test_model__inferred_casters():
    class TestModel(DictModel):
        a: dict = cast()
        b: t.Optional[date] = cast()

    obj, errors = build(TestModel, {"a": [(1, 2)], "b": "2000-12-31"})
    assert obj.a == {1: 2} and obj.b == date(2000, 12, 31)


def test_model__to_dict():
    class TestModel(DictModel):
        a: int = cast()

    data, errors = build(t.Dict[str, t.List[TestModel]], {"abc": [{"a": "2"}]})
    assert data["abc"][0].a == 2
    assert to_dict(data) == {"abc": [{"a": 2}]}

    class WrapperModel(DictModel):
        b: t.Dict[str, t.List[TestModel]]

    obj, errors = build(WrapperModel, {"b": {"abc": [{"a": "2"}]}})
    assert obj.b["abc"][0].a == 2
    assert obj.to_dict() == {"b": {"abc": [{"a": 2}]}}


def test_model__cache_size():
    class AModel(DictModel):
        a: int

    class BModel(DictModel):
        a: int

    set_max_cache_size(1)

    obj1 = build_or_raise(AModel, {"a": 1})
    obj2 = build_or_raise(AModel, {"a": 1})
    assert obj1.__class__ is obj2.__class__

    obj3 = build_or_raise(BModel, {"a": 1})
    obj4 = build_or_raise(BModel, {"a": 1})
    assert (
        obj3.__class__ is obj4.__class__
        and obj3.__class__ is not obj1.__class__
    )

    obj5 = build_or_raise(AModel, {"a": 1})
    assert obj5.__class__ is not obj1.__class__

    set_max_cache_size(2)
    obj1 = build_or_raise(AModel, {"a": 1})
    obj2 = build_or_raise(BModel, {"a": 1})
    obj3 = build_or_raise(AModel, {"a": 1})
    assert obj1.__class__ is obj3.__class__

    set_max_cache_size(128)


def test_model__errors():
    for type_ in (
        int,
        float,
        list,
        dict,
        t.List[int],
        t.Tuple[int],
        t.Tuple[int, ...],
        t.Dict[str, int],
        t.Union[float, int],
    ):
        _, errors = build(type_, "")
        assert errors["__ERRORS"]["type"]

    _, errors = build(t.List[int], [0, 1.0])
    assert errors[1]["__ERRORS"]["type"]

    _, errors = build(t.Dict[int, int], {0: 1.0})
    assert errors["__VALUES"][0]["__ERRORS"]["type"]

    _, errors = build(t.Dict[int, int], {1.0: 2})
    assert errors["__KEYS"][1.0]["__ERRORS"]["type"]

    class TestModel(DictModel):
        a: int

    _, errors = build(t.Union[int, TestModel], {"a": 1.0})
    assert errors["a"]["__ERRORS"]["type"]

    _, errors = build(t.Union[TestModel, int], {"a": 1.0})
    assert errors["__ERRORS"]["type"]

    _, errors = build(t.List[TestModel], [{"a": 1.0}])
    assert errors[0]["a"]["__ERRORS"]["type"]

    _, errors = build(t.Dict[int, TestModel], {1: {"a": 1.0}})
    assert errors["__VALUES"][1]["a"]["__ERRORS"]["type"]

    _, errors = build(TestModel, {"a": "123"})
    assert errors["a"]["__ERRORS"]["type"]


def test_model__errors_dict():
    errors = ErrorsDict()
    errors_2 = errors.get_lazy_item("a")
    errors_2["b"] = "c"
    errors_2["d"] = "e"
    assert errors["a"]["b"] == "c" and errors["a"]["d"] == "e"

    errors = ErrorsDict()
    errors["b"] = 1
    errors_2 = errors.get_lazy_item("a")
    del errors_2["b"]
    assert errors["b"] == 1

    errors = ErrorsDict()
    errors_2 = errors.get_lazy_item("a")
    errors_3 = errors_2.get_lazy_item("b")
    errors_3["c"] = 1
    assert errors["a"]["b"]["c"] == 1
    del errors_3["c"]
    assert errors == {}

    errors = ErrorsDict()
    errors_2 = errors.get_lazy_item("a")
    errors_3 = errors_2.get_lazy_item("b")
    errors_3["c"] = 1
    errors_3["d"] = 2
    del errors_3["c"]
    assert errors["a"]["b"]["d"] == 2

    errors = ErrorsDict()
    errors_2 = errors.get_lazy_item("a")
    assert not errors_2
    errors_2["b"] = 1
    assert errors_2

    errors = ErrorsDict()
    errors_2 = errors.get_lazy_item("a")
    errors_3 = errors_2.get_lazy_item("__ROOT")
    errors_2["b"] = 1
    errors_3["c"] = 2
    assert errors == {"a": {"b": 1, "c": 2}}
    errors.lock()
    with pytest.raises(KeyError):
        errors["d"]
    with pytest.raises(KeyError):
        errors_3["d"]

    errors = ErrorsDict()
    errors["a"] = 1
    errors_2 = errors.get_lazy_item("a")
    assert errors_2 is errors["a"]

    class TestModel(DictModel):
        a: int
        list_: t.List[int]
        dict_: t.Dict[int, int]
        tuple_: t.Tuple[int, int]
        set_: t.Set[int]

    obj, errors = build(
        TestModel,
        {
            "a": "b",
            "list_": [1, "2"],
            "dict_": {7.0: "10"},
            "tuple_": (3.0, 4.0),
            "set_": {"5", "6"},
        },
    )
    assert (
        errors["a"]["__ERRORS"]["type"]
        and errors["dict_"]["__KEYS"][7.0]["__ERRORS"]["type"]
        and errors["dict_"]["__VALUES"][7.0]["__ERRORS"]["type"]
        and errors["list_"][1]["__ERRORS"]["type"]
        and errors["set_"]["__SET_ITEMS"]["5"]["__ERRORS"]["type"]
        and errors["set_"]["__SET_ITEMS"]["6"]["__ERRORS"]["type"]
        and errors["tuple_"][0]["__ERRORS"]["type"]
        and errors["tuple_"][1]["__ERRORS"]["type"]
    )


def test_model__tuple():
    obj, errors = build(t.Tuple[int, str], (1, "abc"))
    assert obj == (1, "abc")
    obj, errors = build(t.Tuple[int, str], ("1", "abc"))
    assert errors[0]["__ERRORS"]["type"]
    obj, errors = build(t.Tuple[int, str], ("1", 234))
    assert errors[0]["__ERRORS"]["type"] and errors[1]["__ERRORS"]["type"]

    obj, errors = build(t.Tuple[int, str], ("1",))
    assert errors["__ERRORS"]["length"]

    obj, errors = build(t.Tuple[int, ...], ("1", 234, "2"))
    assert (
        errors[0]["__ERRORS"]["type"]
        and 1 not in errors
        and errors[2]["__ERRORS"]["type"]
    )

    obj, errors = build(
        t.List[t.Union[float, t.Tuple[int, str]]], [1.5, (1, "abc")]
    )
    assert obj == [1.5, (1, "abc")]
    obj, errors = build(
        t.List[t.Union[float, t.Tuple[int, str]]], [1, ("1", "abc")]
    )
    assert errors[0]["__ERRORS"]["type"] and errors[1][0]["__ERRORS"]["type"]

    # casting
    class TestModel(DictModel):
        a: t.Tuple[int, ...] = cast()

    obj, errors = build(TestModel, {"a": ("1", 234, "2")})
    assert obj.a == (1, 234, 2)

    class TestModel(DictModel):
        a: t.List[t.Union[float, t.Tuple[int, str]]] = cast()

    obj, errors = build(TestModel, {"a": [1, ("1", "abc")]})
    assert obj.a == [1.0, (1, "abc")]

    class TestModel(DictModel):
        a: t.Tuple[int, str] = cast()

    obj, errors = build(TestModel, {"a": (1,)})
    assert errors["a"]["__ERRORS"]["length"]

    obj, errors = build(TestModel, {"a": (1.0, 1)})
    assert obj.a == (1, "1")

    obj, errors = build(TestModel, {"a": (1.5, 1)})
    assert errors["a"][0]["__ERRORS"]["int_caster"]

    obj, errors = build(TestModel, {"a": None})
    assert errors["a"]["__ERRORS"]["type"]

    class AModel(DictModel):
        a: int = cast()

    obj, errors = build(t.Tuple[str, AModel], ("abc", {"a": "1"}))
    assert isinstance(obj, tuple) and obj[0] == "abc" and obj[1].a == 1

    obj, errors = build(t.Tuple[str, AModel], ("abc", {"a": "1.0"}))
    assert errors[1]["a"]["__ERRORS"]["int_caster"]

    class TestModel(DictModel):
        a: t.Tuple[int, ...] = cast()

    obj, errors = build(TestModel, {"a": None})
    assert errors["a"]["__ERRORS"]["type"]

    obj, errors = build(TestModel, {"a": [1, "2", 3.0]})
    assert obj.a == (1, 2, 3)

    obj, errors = build(TestModel, {"a": [1, "2", 3.5]})
    assert errors["a"][2]["__ERRORS"]["int_caster"]

    class AModel(DictModel):
        a: int = cast()

    class TestModel(DictModel):
        objs: t.Tuple[AModel, ...] = cast()

    obj, errors = build(TestModel, {"objs": [{"a": "1"}, {"a": 2.0}]})
    assert (
        isinstance(obj.objs, tuple)
        and obj.objs[0].a == 1
        and obj.objs[1].a == 2
    )

    class TestModel(DictModel):
        objs: t.Tuple[t.Optional[TestModel], ...] = cast()

    obj, errors = build(TestModel, {"objs": []})
    assert obj.objs == ()

    class TestModel(DictModel):
        value: t.Any = cast(t.Tuple[int])

    obj, errors = build(TestModel, {"value": ["1"]})
    assert obj.value == (1,)


def test_model__set():
    class TestModel(DictModel):
        a: t.Set[str]

    obj, errors = build(TestModel, {"a": {"1", "2"}})
    assert obj.a == {"1", "2"}
    obj, errors = build(TestModel, {"a": {1, "2"}})
    assert errors["a"]["__SET_ITEMS"][1]["__ERRORS"]["type"]

    class TestModel(DictModel):
        a: t.Set[str] = cast()

    obj, errors = build(TestModel, {"a": {1, "2"}})
    assert obj.a == {"1", "2"}

    class TestModel(DictModel):
        a: t.Set[t.Union[int, str]] = cast()

    obj, errors = build(TestModel, {"a": {1, "2", 3.0, "4.0"}})
    assert obj.a == {1, 2, 3, "4.0"}


def test_model__cast_overrides():
    class TestModel(DictModel):
        a: date = cast(casters.DateFromStr("%m/%d/%Y"))

    obj, errors = build(TestModel, {"a": "1/1/2000"})
    assert obj.a == date(2000, 1, 1)
    obj, errors = build(TestModel, {"a": "2000-01-01"})
    assert errors["a"]["__ERRORS"]["date_from_str"]

    class TestModel(DictModel):
        a: date = cast()

    obj, errors = build(TestModel, {"a": "2000-01-01"})
    assert obj.a == date(2000, 1, 1)
    obj, errors = build(TestModel, {"a": "2000_01_01"})
    assert errors["a"]["__ERRORS"]["date_from_str"]

    class TestModel(DictModel):
        a: t.Any = cast(t.Optional[date])

    obj, errors = build(TestModel, {"a": "2000-01-01"})
    assert obj.a == date(2000, 1, 1)
    obj, errors = build(TestModel, {"a": None})
    assert obj.a is None
    obj, errors = build(TestModel, {"a": "2000_01_01"})
    assert errors["a"]["__ERRORS"]["date_from_str"]

    class TestModel(DictModel):
        a: date

        class Meta:
            cast = True

    obj, errors = build(TestModel, {"a": "2000-01-01"})
    assert obj.a == date(2000, 1, 1)
    obj, errors = build(TestModel, {"a": "2000_01_01"})
    assert errors["a"]["__ERRORS"]["date_from_str"]

    class TestModel(DictModel):
        a: date = cast(overrides={date: casters.DateFromStr("%m/%d/%Y")})

    obj, errors = build(TestModel, {"a": "1/1/2000"})
    assert obj.a == date(2000, 1, 1)
    obj, errors = build(TestModel, {"a": "2000-01-01"})
    assert errors["a"]["__ERRORS"]["date_from_str"]

    class TestModel(DictModel):
        a: t.Union[date, str] = cast(
            overrides={
                date: [
                    casters.DateFromStr("%m/%d/%Y"),
                    casters.DateFromStr("%Y_%m_%d"),
                ]
            }
        )

    obj, errors = build(TestModel, {"a": "1/1/2000"})
    assert obj.a == date(2000, 1, 1)
    obj, errors = build(TestModel, {"a": "2000_01_01"})
    assert obj.a == date(2000, 1, 1)
    obj, errors = build(TestModel, {"a": "not a date"})
    assert obj.a == "not a date"

    class TestModel(DictModel):
        a: t.Any = cast(
            t.Union[date, str],
            overrides={
                date: [
                    casters.DateFromStr("%m/%d/%Y"),
                    casters.DateFromStr("%Y_%m_%d"),
                ]
            },
        )

    obj, errors = build(TestModel, {"a": "1/1/2000"})
    assert obj.a == date(2000, 1, 1)
    obj, errors = build(TestModel, {"a": "2000_01_01"})
    assert obj.a == date(2000, 1, 1)
    obj, errors = build(TestModel, {"a": "not a date"})
    assert obj.a == "not a date"

    class TestModel(DictModel):
        a: t.Union[date, str] = cast(
            overrides={date: casters.DateFromStr("%m/%d/%Y")}
        )
        b: t.Optional[date]
        c: date = cast(casters.DateFromStr("%Y-%m-%d"))

        class Meta:
            cast = True
            cast_overrides = {date: casters.DateFromStr("%Y_%m_%d")}

    obj, errors = build(
        TestModel, {"a": "1/1/2000", "b": "2000_12_31", "c": "2000-11-30"}
    )
    assert (
        obj.a == date(2000, 1, 1)
        and obj.b == date(2000, 12, 31)
        and obj.c == date(2000, 11, 30)
    )
    obj, errors = build(
        TestModel, {"a": "2000_01_01", "b": None, "c": "2000-11-30"}
    )
    assert (
        obj.a == "2000_01_01" and obj.b is None and obj.c == date(2000, 11, 30)
    )

    class TestModel(DictModel):
        a: t.Optional[date]
        b: int

        class Meta:
            cast = True
            cast_overrides = {
                date: casters.DateFromStr("%m/%d/%Y"),
                int: casters.IntLossy(),
            }

    obj, errors = build(TestModel, {"a": "12/31/2000", "b": 1.5})
    assert obj.a == date(2000, 12, 31) and obj.b == 1
    obj, errors = build(TestModel, {"a": "2000-12-31", "b": "abc"})
    assert (
        errors["a"]["__ERRORS"]["date_from_str"]
        and errors["b"]["__ERRORS"]["int_lossy_caster"]
    )

    data, errors = build(
        t.List[t.Union[date, str]],
        ["12/31/2000", "2000-12-30", "2000_12_29"],
        cast=True,
        cast_overrides={
            date: [
                casters.DateFromStr("%m/%d/%Y"),
                casters.DateFromStr("%Y_%m_%d"),
            ]
        },
    )
    assert data == [date(2000, 12, 31), "2000-12-30", date(2000, 12, 29)]

    class TestModel(DictModel):
        a: t.Optional[date]

    data, errors = build(
        t.List[t.Union[date, TestModel]],
        [
            "12/31/2000",
            "2000-12-30",
            "2000_12_29",
            {"a": None},
            {"a": date(2000, 5, 31)},
            {"a": "2000-06-30"},
        ],
        cast=True,
        cast_overrides={
            date: [
                casters.DateFromStr("%m/%d/%Y"),
                casters.DateFromStr("%Y_%m_%d"),
            ]
        },
    )
    assert (
        errors[1]["a"]["__ERRORS"]["required"]
        and errors[5]["a"]["__ERRORS"]["type"]
    )

    class TestAModel(DictModel):
        a: t.Optional[date] = cast()

    class TestBModel(DictModel):
        obj: TestAModel
        b: t.Optional[date] = cast()

        class Meta:
            cast_overrides = {date: casters.DateFromStr("%m/%d/%Y")}

    obj, errors = build(
        TestBModel, {"obj": {"a": "2000-01-31"}, "b": "4/3/2000"}
    )
    assert obj.obj.a == date(2000, 1, 31) and obj.b == date(2000, 4, 3)

    with pytest.raises(ValueError):
        build(
            t.List[t.Union[date, TestModel]],
            [],
            cast_overrides={date: casters.DateFromStr("%m/%d/%Y")},
        )

    with pytest.raises(ValueError):
        build(
            t.List[t.Union[date, TestModel]],
            [],
            cast=False,
            cast_overrides={date: casters.DateFromStr("%m/%d/%Y")},
        )

    with pytest.raises(ValueError):
        build(TestModel, None, cast=True)

    class TestModel(DictModel, t.Generic[T]):
        a: t.Optional[T] = cast()

    with pytest.raises(ValueError):
        build(TestModel, None, cast=True)

    class TestModel(DictModel, t.Generic[T]):
        a: t.Optional[T]

        class Meta:
            cast = True
            cast_overrides = {int: casters.IntLossy()}

    obj, errors = build(TestModel[int], {"a": 1.5})
    assert obj.a == 1


if PY_VERSION >= (3, 8):

    def test_model__literal():
        class TestModel(DictModel):
            a: t.Literal[1, "2"]

        obj, errors = build(TestModel, {"a": 1})
        assert obj.a == 1
        obj, errors = build(TestModel, {"a": 2})
        assert errors["a"]["__ERRORS"]["literal"]
        obj, errors = build(TestModel, {"a": "2"})
        assert obj.a == "2"

        d = {}

        class TestModel(DictModel):
            a: t.Literal[1, d]

        obj, errors = build(TestModel, {"a": 1})
        assert obj.a == 1
        obj, errors = build(TestModel, {"a": d})
        assert obj.a is d
        obj, errors = build(TestModel, {"a": {}})
        assert obj.a is not d and obj.a == d
        obj, errors = build(TestModel, {"a": {"abc": 1}})
        assert errors["a"]["__ERRORS"]["literal"]

        class TestModel(DictModel):
            a: t.Optional[t.Literal[1, "2"]] = cast()

        obj, errors = build(TestModel, {"a": 1})
        assert obj.a == 1
        obj, errors = build(TestModel, {"a": 2})
        assert errors["a"]["__ERRORS"]["literal"]
        obj, errors = build(TestModel, {"a": "2"})
        assert obj.a == "2"
        obj, errors = build(TestModel, {"a": None})
        assert obj.a is None


def test_model__bool():
    class TestModel(DictModel):
        a: bool

    obj, errors = build(TestModel, {"a": 1})
    assert errors["a"]["__ERRORS"]["type"]
    obj, errors = build(TestModel, {"a": None})
    assert errors["a"]["__ERRORS"]["type"]
    obj, errors = build(TestModel, {"a": True})
    assert obj.a is True
    obj, errors = build(TestModel, {"a": False})
    assert obj.a is False

    class TestModel(DictModel):
        a: bool = cast()

    obj, errors = build(TestModel, {"a": 1})
    assert obj.a is True
    obj, errors = build(TestModel, {"a": None})
    assert obj.a is False
    obj, errors = build(TestModel, {"a": True})
    assert obj.a is True
    obj, errors = build(TestModel, {"a": False})
    assert obj.a is False


# TODO: support sets
if PY_VERSION >= (3, 10):

    def test_model__simplified_typing():
        class TestModel(DictModel):
            a_1: list[int] = field("a").cast()
            a_2: t.List[int] = field("a").cast()
            b_1: int | str = field("b").cast()
            b_2: t.Union[int, str] = field("b").cast()

        obj, errors = build(TestModel, {"a": ("1", 2.0), "b": 3.5})
        assert (
            obj.a_1 == [1, 2]
            and obj.a_2 == [1, 2]
            and obj.b_1 == "3.5"
            and obj.b_2 == "3.5"
        )


if PY_VERSION == (3, 9):

    def test_model__simplified_typing():
        class TestModel(DictModel):
            a_1: list[int] = field("a").cast()
            a_2: t.List[int] = field("a").cast()

        obj, errors = build(TestModel, {"a": ("1", 2.0)})
        assert obj.a_1 == [1, 2] and obj.a_2 == [1, 2]


@pytest.fixture
def benchmark_data_1():
    return {
        "name": "John",
        "age": 42,
        "friends": list(range(200)),
        "settings": {f"v_{i}": i / 2.0 for i in range(50)},
        # "settings": [(f"v_{i}", i / 2.0) for i in range(50)],
    }


@pytest.fixture
def benchmark_data_2():
    return {
        "name": 123,
        "age": 42.0,
        "friends": list(map(str, range(200))),
        "settings": {i: str(i / 2.0) for i in range(50)},
        # "settings": [(f"v_{i}", i / 2.0) for i in range(50)],
    }


def test_model__benchmark_1_pydantic_validation(benchmark, benchmark_data_1):
    try:
        from pydantic import BaseModel, StrictFloat, StrictInt, StrictStr
    except ImportError:
        return

    class PydanticModel(BaseModel):
        name: StrictStr
        age: StrictInt
        friends: t.List[StrictInt]
        settings: t.Dict[StrictStr, StrictFloat]

    benchmark(PydanticModel.parse_obj, benchmark_data_1)


def test_model__benchmark_1_pydantic_validation_failed(
    benchmark, benchmark_data_2
):
    try:
        from pydantic import BaseModel, StrictFloat, StrictInt, StrictStr
    except ImportError:
        return

    class PydanticModel(BaseModel):
        name: StrictStr
        age: StrictInt
        friends: t.List[StrictInt]
        settings: t.Dict[StrictStr, StrictFloat]

    def f(data):
        try:
            PydanticModel.parse_obj(data)
        except Exception:
            pass

    benchmark(f, benchmark_data_2)


def test_model__benchmark_1_pydantic_casting(benchmark, benchmark_data_1):
    try:
        from pydantic import BaseModel
    except ImportError:
        return

    class PydanticModel(BaseModel):
        name: str
        age: int
        friends: t.List[int]
        settings: t.Dict[str, float]

    benchmark(PydanticModel.parse_obj, benchmark_data_1)


def test_model__benchmark_1_validation(benchmark, benchmark_data_1):
    class TestModel(DictModel):
        name: str
        age: int
        friends: t.List[int]
        settings: t.Dict[str, float]

    benchmark(build, TestModel, benchmark_data_1)


def test_model__benchmark_2_validation_failed(benchmark, benchmark_data_2):
    class TestModel(DictModel):
        name: str
        age: int
        friends: t.List[int]
        settings: t.Dict[str, float]

    benchmark(build, TestModel, benchmark_data_2)


def test_model__benchmark_1_casting(benchmark, benchmark_data_1):
    class TestCastingModel(DictModel):
        name: str = cast()
        age: int = cast()
        friends: t.List[int] = cast()
        settings: t.Dict[str, float] = cast()

    obj, errors = build(TestCastingModel, benchmark_data_1)
    assert obj
    benchmark(build, TestCastingModel, benchmark_data_1)


def test_model__benchmark_1_cattrs(benchmark, benchmark_data_1):
    try:
        import attrs
        import cattrs
    except ImportError:
        return

    @attrs.define
    class AttrsModel:
        name: str
        age: int
        friends: t.List[int]
        settings: t.Dict[str, float]

    benchmark(cattrs.structure, benchmark_data_1, AttrsModel)


def test_model__benchmark_2_pydantic_casting(benchmark, benchmark_data_2):
    try:
        from pydantic import BaseModel
    except ImportError:
        return

    class PydanticModel(BaseModel):
        name: str
        age: int
        friends: t.List[int]
        settings: t.Dict[str, float]

    benchmark(PydanticModel.parse_obj, benchmark_data_2)


def test_model__benchmark_2_casting(benchmark, benchmark_data_2):
    class TestCastingModel(DictModel):
        name: str = cast()
        age: int = cast()
        friends: t.List[int] = cast()
        settings: t.Dict[str, float] = cast()

    obj, errors = build(TestCastingModel, benchmark_data_2)
    assert obj
    benchmark(build, TestCastingModel, benchmark_data_2)

    # import cProfile
    # import pstats

    # with cProfile.Profile() as pr:
    #     for i in range(10000):
    #         build(TestCastingModel, benchmark_data_2)

    # pstats.Stats(pr).sort_stats("cumulative").print_stats()
    # pstats.Stats(pr).sort_stats("time").print_stats()


def test_model__benchmark_2_cattrs(benchmark, benchmark_data_2):
    try:
        import attrs
        import cattrs
    except ImportError:
        return

    @attrs.define
    class AttrsModel:
        name: str
        age: int
        friends: t.List[int]
        settings: t.Dict[str, float]

    benchmark(cattrs.structure, benchmark_data_2, AttrsModel)
