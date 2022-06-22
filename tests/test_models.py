import json
import re
import typing as t
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from random import random

import pytest

from convtools import conversion as c
from convtools.contrib.models import (
    DictModel,
    ObjectModel,
    ValidationError,
    cached_model_method,
    cast,
    casters,
    field,
    init,
    init_or_raise,
    json_dumps,
    set_max_cache_size,
    to_dict,
    validate,
    validators,
)
from convtools.contrib.models.models import TypeConversion


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
    obj, errors = init(TestModel, input_data)
    assert (
        obj.a == obj["a"] == 1
        and obj.b == obj["b"] == 1
        and obj.c == obj["c"] == "c_str"
        and obj.d is None
        and obj["d"] is None
        and obj.e == obj["e"] == []
    )
    input_data = {"a": 1, "b": 2, "c": "c_str", "d": "d_str", "e": [1, 2, 3]}
    obj, errors = init(TestModel, input_data)
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

    obj = init_or_raise(
        SecondModel,
        {"first": {"a": 1}, "dt": date(1970, 1, 1), "type_": Types.FIRST},
    )

    assert json_dumps(obj) == json.dumps(
        {"first": {"a": 1}, "dt": "1970-01-01", "type_": 1}
    )

    with pytest.raises(TypeError):
        json_dumps(object())

    with pytest.raises(ValidationError):
        obj = init_or_raise(SecondModel, None)


def test_model__objectmodel():
    class FirstModel(ObjectModel):
        a: int
        b: int = field("objects", 0, "value")

    class Value:
        value = 7

    class Data:
        a = 10
        objects = [Value]

    obj = init_or_raise(FirstModel, Data)
    assert obj.a == 10 and obj.b == 7


def test_model__any():
    class TestModel(DictModel):
        a: t.Any

    any_ = object()
    obj, errors = init(TestModel, {"a": any_})
    assert obj.a is any_

    class TestModel(DictModel):
        a: t.List[t.Any]

    obj, errors = init(TestModel, {"a": [any_, 1, "asd"]})
    assert obj.a == [any_, 1, "asd"]

    class TestModel(DictModel):
        a: t.List[t.Any] = cast()

    with pytest.raises(ValueError):
        init(TestModel, None)


def test_model__str():
    class TestModel(DictModel):
        a: str
        b: str = cast()
        c: str = cast(str)

    obj, errors = init(TestModel, {"a": None})
    assert errors["a"]["type"]

    obj, errors = init(TestModel, {"a": "abc", "b": 123, "c": 234})
    assert obj.a == "abc" and obj.b == "123" and obj.c == "234"

    class TestModel(DictModel):
        a: t.Optional[str]
        b: t.Optional[str] = cast()

    obj, errors = init(TestModel, {"a": None, "b": 1})
    assert obj.a is None and obj.b == "1"


def test_model__int():
    class TestModel(DictModel):
        a: int

    obj, errors = init(TestModel, None)
    assert errors["a"]["required"]

    obj, errors = init(TestModel, {"a": "1"})
    assert errors["a"]["type"]

    class TestModel(DictModel):
        a: int = cast()

    obj, errors = init(TestModel, {"a": "1.1"})
    assert errors["a"]["int_caster"]

    obj, errors = init(TestModel, {"a": 1.1})
    assert errors["a"]["int_caster"]

    obj, errors = init(TestModel, {"a": Decimal("1.1")})
    assert errors["a"]["int_caster"]

    obj, errors = init(TestModel, {"a": "1"})
    assert obj.a == 1

    obj, errors = init(TestModel, {"a": 1.0})
    assert obj.a == 1

    obj, errors = init(TestModel, {"a": Decimal("1.0")})
    assert obj.a == 1

    class TestModel(DictModel):
        a: int = cast(casters.IntLossy())

    obj, errors = init(TestModel, {"a": "b"})
    assert errors["a"]["int_lossy_caster"]

    obj, errors = init(TestModel, {"a": "1.1"})
    assert obj.a == 1

    obj, errors = init(TestModel, {"a": 1.1})
    assert obj.a == 1

    obj, errors = init(TestModel, {"a": Decimal("1.1")})
    assert obj.a == 1

    class TestModel(DictModel):
        a: int = cast(str)

    obj, errors = init(TestModel, {"a": "1"})
    assert errors["a"]["type"]

    class TestModel(DictModel):
        a: int = cast()

    obj, errors = init(TestModel, {"a": None})
    assert errors["a"]["int_caster"]


def test_model__decimal():
    class TestModel(DictModel):
        a: Decimal

    obj, errors = init(TestModel, None)
    assert errors["a"]["required"]

    obj, errors = init(TestModel, {"a": "1"})
    assert errors["a"]["type"]

    class TestModel(DictModel):
        a: Decimal = cast()

    obj, errors = init(TestModel, {"a": "b"})
    assert errors["a"]["decimal_caster"]

    obj, errors = init(TestModel, {"a": 1.1})
    assert errors["a"]["decimal_caster"]

    obj, errors = init(TestModel, {"a": None})
    assert errors["a"]["decimal_caster"]

    obj, errors = init(TestModel, {"a": "1.1"})
    assert obj.a == Decimal("1.1")

    obj, errors = init(TestModel, {"a": Decimal("1.1")})
    assert obj.a == Decimal("1.1")

    obj, errors = init(TestModel, {"a": 1.0})
    assert obj.a == Decimal("1.0")

    class TestModel(DictModel):
        a: Decimal = cast(casters.DecimalLossy())

    obj, errors = init(TestModel, {"a": "b"})
    assert errors["a"]["decimal_lossy_caster"]

    obj, errors = init(TestModel, {"a": 1.1})
    assert abs(obj.a - Decimal("1.1")) < Decimal("1e-16")


def test_model__dates():
    class TestModel(DictModel):
        a: date = cast(casters.DateFromStr("%Y-%m-%d"))

    obj, errors = init(TestModel, {"a": "1970-01-01"})
    assert obj.a == date(1970, 1, 1)

    obj, errors = init(TestModel, {"a": "1970-31-01"})
    assert errors["a"]

    obj, errors = init(TestModel, {"a": "abc"})
    assert errors["a"]

    obj, errors = init(TestModel, {"a": 1})
    assert errors["a"]

    class TestModel(DictModel):
        a: datetime = cast(casters.DatetimeFromStr("%Y-%m-%d"))

    obj, errors = init(TestModel, {"a": "1970-01-01"})
    assert obj.a == datetime(1970, 1, 1)

    obj, errors = init(TestModel, {"a": "1970-31-01"})
    assert errors["a"]

    obj, errors = init(TestModel, {"a": "abc"})
    assert errors["a"]

    obj, errors = init(TestModel, {"a": 1})
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

    obj, errors = init(TestModel, {"a": 1, "c": None, "d": None})
    assert (
        isinstance(obj.a, ValueTypes)
        and isinstance(obj.b, ValueTypes)
        and obj.a.value == obj.b.value == 1
        and obj.c is None
        and obj.d is None
    )
    obj, errors = init(TestModel, {"a": 1, "c": ValueTypes.SECOND, "d": 2})
    assert obj.c.value == 2 and obj.d.value == 2

    obj, errors = init(TestModel, {"a": 1, "c": 2, "d": None})
    assert errors["c"]["type"]

    obj, errors = init(TestModel, {"a": "1"})
    assert errors["a"]["enum_caster"]


def test_model__list():
    class TestModel(DictModel):
        a: t.List[int]

    obj, errors = init(TestModel, {"a": [1]})
    assert obj.a == [1]

    obj, errors = init(TestModel, {"a": [1, "2"]})
    assert errors["a"][1]["type"]

    obj, errors = init(TestModel, {"a": None})
    assert errors["a"]["type"]

    class TestModel(DictModel):
        a: t.Optional[t.List[int]]

    obj, errors = init(TestModel, {"a": None})
    assert obj.a is None

    obj, errors = init(TestModel, {"a": [1, 2]})
    assert obj.a == [1, 2]

    class TestModel(DictModel):
        a: t.Optional[t.Union[t.List[int], t.List[str]]]

    obj, errors = init(TestModel, {"a": None})
    assert obj.a is None
    obj, errors = init(TestModel, {"a": [1, 2]})
    assert obj.a == [1, 2]
    obj, errors = init(TestModel, {"a": ["1", "2"]})
    assert obj.a == ["1", "2"]
    obj, errors = init(TestModel, {"a": ["1", 2]})
    assert errors["a"][1]["type"]

    class TestModel(DictModel):
        a: t.List[t.Union[int, str, float]]

    obj, errors = init(TestModel, {"a": ["1", 2, 3.5]})
    assert obj.a == ["1", 2, 3.5]

    obj, errors = init(TestModel, {"a": ["1", 2, Decimal(3.5)]})
    assert errors["a"][2]["type"]

    class TestModel(DictModel):
        a: t.List[t.Optional[int]] = cast()

    obj, errors = init(TestModel, {"a": None})
    assert errors["a"]["type"]

    obj, errors = init(TestModel, {"a": [1, "2", 3.0, None]})
    assert obj.a == [1, 2, 3, None]

    obj, errors = init(TestModel, {"a": [1, "2", 3.0, None, 3.1]})
    assert errors["a"][4]["int_caster"]

    class AModel(DictModel):
        a: t.Optional[int] = cast()

    class TestModel(DictModel):
        a_objects: t.List[AModel]

    obj, errors = init(
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

    obj, errors = init(TestModel, {"a": [["1", 2, 3.0]]})
    assert obj.a == [[1, 2, 3]]


class TestModelWithForwardRef(DictModel):
    a: "t.Optional[t.Dict[str, int]]" = cast()


def test_model__dict():
    class TestModel(DictModel):
        a: dict
        b: dict = cast()

    obj, errors = init(TestModel, {"a": {"k": 1}, "b": [("j", 2)]})
    assert obj.a == {"k": 1} and obj.b == {"j": 2}

    obj, errors = init(TestModel, {"a": "k", "b": "j"})
    assert errors["a"]["type"] and errors["b"]["dict_caster"]

    class TestModel(DictModel):
        a: t.Dict[str, int]

    obj, errors = init(TestModel, {"a": {"k": 1}})
    assert obj.a == {"k": 1}

    obj, errors = init(TestModel, {"a": {2: 1}})
    assert errors["a"]["keys"][2]["type"]

    obj, errors = init(TestModel, {"a": {"k": "1"}})
    assert errors["a"]["values"]["k"]["type"]

    obj, errors = init(TestModelWithForwardRef, {"a": {1: "1"}})
    assert obj.a == {"1": 1}

    obj, errors = init(TestModelWithForwardRef, {"a": None})
    assert obj.a is None

    obj, errors = init(TestModelWithForwardRef, {"a": 1})
    assert errors["a"]["type"]

    obj, errors = init(TestModelWithForwardRef, {"a": {1: "1.1"}})
    assert errors["a"]["values"][1]["int_caster"]

    class InnerModel(DictModel):
        b: int = cast()

    class TestModel(DictModel):
        a: t.Dict[str, InnerModel]

    obj, errors = init(TestModel, {"a": {"key": {"b": "23"}}})
    assert obj.a["key"].b == 23

    obj, errors = init(TestModel, {"a": {7: {"b": "23"}}})
    assert errors["a"]["keys"][7]["type"]


def test_model__casters__custom():
    class TestModel(DictModel):
        a: int = cast(casters.Custom("tst", int, ValueError))

    obj, errors = init(TestModel, {"a": "1"})
    assert obj.a == 1

    obj, errors = init(TestModel, {"a": "1.1"})
    assert errors["a"]["tst"]

    with pytest.raises(TypeError):
        init(TestModel, {"a": None})

    class TestModel(DictModel):
        a: int = cast(casters.CustomUnsafe(int))

    obj, errors = init(TestModel, {"a": "1"})
    assert obj.a == 1

    with pytest.raises(ValueError):
        init(TestModel, {"a": "1.1"})


def test_model__validators__required():
    class TestModel(DictModel):
        a: str = field(default="default_a")
        b: str = "default_b"

    obj, errors = init(TestModel, {"a": "cde"})
    assert obj.a == "cde" and obj.b == "default_b"

    obj, errors = init(TestModel, {"a": None})
    assert errors["a"]["type"]

    obj, errors = init(TestModel, {"b": "new"})
    assert obj.a == "default_a" and obj.b == "new"

    class TestModel(DictModel):
        a: int = field(default_factory=int)

    obj, errors = init(TestModel, {"a": 1})
    assert obj.a == 1

    obj, errors = init(TestModel, {"b": 1})
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

    obj, errors = init(TestModel, 100.1)
    assert errors["a"]["too_big"]

    obj, errors = init(TestModel, 100.0)
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

    obj, errors = init(TestModel, {"a": 1})
    assert obj.a == "1"

    obj, errors = init(TestModel, {"a": "1"})
    assert errors["a"]["type"]


def test_model__validators__regex():
    class TestModel(DictModel):
        a: int = validate(validators.Regex(r"\d+")).cast()
        b: str = validate(validators.Regex(re.compile(r"\d+")))

    obj, errors = init(TestModel, {"a": "123", "b": "234"})
    assert obj.a == 123 and obj.b == "234"

    obj, errors = init(TestModel, {"a": " 123", "b": " 234"})
    assert errors["a"]["regex"] and errors["b"]["regex"]

    with pytest.raises(TypeError):
        init(TestModel, {"a": 123})


def test_model__validators__comparisons():
    class TestModel(DictModel):
        a: int = cast().validate(validators.Gt(10))
        b: int = validate(validators.Lt(10))
        c: int = validate(validators.Gte(10))
        d: int = validate(validators.Gte(10))
        e: int = validate(validators.Lte(10))
        f: int = validate(validators.Lte(10))

    obj, errors = init(
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

    obj, errors = init(TestModel, {"a": " 3", "b": 10, "c": 9, "e": 11})
    assert (
        errors["a"]["gt"]
        and errors["b"]["lt"]
        and errors["c"]["gte"]
        and errors["d"]["required"]
        and errors["e"]["lte"]
        and errors["f"]["required"]
    )


def test_model__validators__custom():
    class TestModel(DictModel):
        a: int = validate(validators.Custom("invalid", bool))
        b: int = validate(bool).cast()

    obj, errors = init(TestModel, {"a": 1, "b": False})
    assert obj.a == 1 and obj.b == 0

    obj, errors = init(TestModel, {"a": 0})
    assert errors["a"]["invalid"]

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

    with pytest.raises(ValueError):

        class TestModel(DictModel):
            a: t.Tuple[str, int] = cast(t.Tuple[str, int])

    from convtools.contrib.models.base import TypeValueCodeGenArgs
    from convtools.contrib.models.type_handlers import (
        prepare_model_type,
        type_value_to_code,
    )

    with pytest.raises(ValueError):
        prepare_model_type(object, None)

    with pytest.raises(Exception):
        type_value_to_code(
            TypeValueCodeGenArgs(
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
            )
        )

    with pytest.raises(Exception):

        class TestModel(DictModel):
            a: t.Tuple[int]

        init(TestModel, {"a": (1,)})


def test_model__generics():
    class ThirdModel(DictModel, t.Generic[T]):
        d: T = cast()

    class SecondModel(DictModel):
        c: int = cast()

    class FirstModel(DictModel, t.Generic[T]):
        a: SecondModel
        b: T

    with pytest.raises(ValueError):
        init(FirstModel, None)

    obj, errors = init(FirstModel[int], {"a": {"c": "123"}, "b": 345})
    assert obj.a.c == 123 and obj.b == 345

    obj, errors = init(
        FirstModel[ThirdModel[int]], {"a": {"c": "123"}, "b": {"d": "345"}}
    )
    assert obj.a.c == 123 and obj.b.d == 345

    class SecondModel(DictModel, t.Generic[T]):
        c: T = cast()

    class FirstModel(DictModel, t.Generic[T]):
        a: SecondModel[T]
        b: T = cast()

    obj, errors = init(
        t.List[FirstModel[int]], [{"a": {"c": "12"}, "b": "34 "}]
    )
    assert json.loads(json_dumps(obj)) == [{"a": {"c": 12}, "b": 34}]

    U = t.TypeVar("U")

    class ResponseModel(DictModel, t.Generic[U]):
        data: t.List[U]

    class UserModel(DictModel, t.Generic[U]):
        parameter: U = cast()

    response = init_or_raise(
        ResponseModel[UserModel[int]], {"data": [{"parameter": " 123 "}]}
    )
    assert response.data[0].parameter == 123


def test_model__casters_multiple():
    class TestModel(DictModel):
        a: Decimal = cast(int).cast(str).cast()

    obj, errors = init(TestModel, {"a": 1.0})
    assert obj.a == Decimal("1")


def test_model__unions():
    class TestModel(DictModel):
        a: t.Union[t.List[int], t.List[str]]

    obj, errors = init(TestModel, {"a": ["1"]})
    assert obj.a == ["1"]

    class TestModel(DictModel):
        a: t.List[t.Union[int, str]] = cast()
        b = 7

    obj, errors = init(TestModel, {"a": ["1", "1.1", 1.2, " 2 "]})
    assert obj.a == [1, "1.1", "1.2", 2] and obj.b == 7


def test_model__optional():
    class TestModel(DictModel):
        a: t.Optional[date] = cast(
            casters.Optional(casters.DateFromStr("%Y-%m-%d"))
        )

    obj, errors = init(TestModel, {"a": "2000-01-01"})
    assert obj.a == date(2000, 1, 1)

    obj, errors = init(TestModel, {"a": None})
    assert obj.a is None

    obj, errors = init(TestModel, {"a": "2000"})
    assert errors["a"]["date_from_str"]

    class TestModel(DictModel):
        a: t.Optional[str] = None

    obj, errors = init(TestModel, {"a": None})
    assert obj.a is None
    obj, errors = init(TestModel, {"a": "abc"})
    assert obj.a == "abc"
    obj, errors = init(TestModel, None)
    assert obj.a is None


def test_model__type_conversion():
    class TestModel(DictModel):
        a: t.List[int] = cast()

    result = (
        TypeConversion(TestModel)
        .pipe(c.item(0).attr("a"))
        .execute({"a": ["1", 2.0]}, debug=True)
    )
    assert result == [1, 2]


def test_model__cast_validate_independence():
    class TestModel(DictModel):
        a: t.List[int] = cast()
        b: t.List[int]

    obj, errors = init(TestModel, {"a": [1.1], "b": [2, "abc"]})
    assert errors["a"][0]["int_caster"] and errors["b"][1]["type"]


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

    obj, errors = init(TestModel, x1)
    assert obj.b.b.b.b.b.a == "2"

    obj, errors = init(TestModel2, x1)
    assert (
        errors["a"]["type"]
        and errors["b"]["a"]["type"]
        and errors["b"]["b"]["a"]["type"]
    )

    x1 = {"a": "1", "b": None}
    x2 = {"a": "2", "b": x1}
    obj, errors = init(TestModel3, x2)
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

    obj, errors = init(TestModel, None)
    assert errors["prepare"]["is_blank"]

    obj, errors = init(TestModel, '{"a": "1", "b": 2}')
    assert obj.to_dict() == {"a": 1, "b": "2", "c": 1.5}

    obj, errors = init(TestModel, '{"a": "101", "b": 2}')
    assert errors["validate"]["a_too_big"]

    obj, errors = init(TestModel, '{"a": "1", "b": ""}')
    assert errors["validate"]["b_blank"]

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

    obj, errors = init(TestModel, None)
    assert errors["validate__"]["a"] == "is positive"


def test_model__private_fields():
    class TestModel(DictModel):
        a: int
        b: str

        class Meta:
            private_fields = ("b",)

    obj, errors = init(TestModel, {"a": 1})
    assert obj.a == 1


def test_model__inferred_casters():
    class TestModel(DictModel):
        a: dict = cast()
        b: t.Optional[date] = cast()

    obj, errors = init(TestModel, {"a": [(1, 2)], "b": "2000-12-31"})
    assert obj.a == {1: 2} and obj.b == date(2000, 12, 31)


def test_model__to_dict():
    class TestModel(DictModel):
        a: int = cast()

    data, errors = init(t.Dict[str, t.List[TestModel]], {"abc": [{"a": "2"}]})
    assert data["abc"][0].a == 2
    assert to_dict(data) == {"abc": [{"a": 2}]}

    class WrapperModel(DictModel):
        b: t.Dict[str, t.List[TestModel]]

    obj, errors = init(WrapperModel, {"b": {"abc": [{"a": "2"}]}})
    assert obj.b["abc"][0].a == 2
    assert obj.to_dict() == {"b": {"abc": [{"a": 2}]}}


def test_model__cache_size():
    class AModel(DictModel):
        a: int

    class BModel(DictModel):
        a: int

    set_max_cache_size(1)

    obj1 = init_or_raise(AModel, {"a": 1})
    obj2 = init_or_raise(AModel, {"a": 1})
    assert obj1.__class__ is obj2.__class__

    obj3 = init_or_raise(BModel, {"a": 1})
    obj4 = init_or_raise(BModel, {"a": 1})
    assert (
        obj3.__class__ is obj4.__class__
        and obj3.__class__ is not obj1.__class__
    )

    obj5 = init_or_raise(AModel, {"a": 1})
    assert obj5.__class__ is not obj1.__class__

    set_max_cache_size(2)
    obj1 = init_or_raise(AModel, {"a": 1})
    obj2 = init_or_raise(BModel, {"a": 1})
    obj3 = init_or_raise(AModel, {"a": 1})
    assert obj1.__class__ is obj3.__class__

    set_max_cache_size(128)
