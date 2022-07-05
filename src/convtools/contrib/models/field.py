"""Defines model field level processing pipeline"""
import inspect
import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from functools import wraps
from typing import TYPE_CHECKING

from .base import BaseCaster, BaseModel, CastOverrides, _none
from .casters.base import CasterToFinalType, TypeCaster
from .casters.casters import Bool as BoolCaster
from .casters.casters import DateFromStr as DateFromStrCaster
from .casters.casters import Decimal as DecimalCaster
from .casters.casters import Enum as EnumCaster
from .casters.casters import Int as IntCaster
from .casters.casters import NaiveCaster
from .casters.casters import Str as StrCaster
from .validators.validators import BaseValidator
from .validators.validators import Type as TypeValidator


if TYPE_CHECKING:
    from typing import Optional, Type, Union


def cached_model_method(func):
    ctx = {"key": (None, -1)}

    @wraps(func)
    def wrapper(cls, data, version):
        result, version_ = ctx["key"]
        if version_ == version:
            return result

        result = func(cls, data)
        ctx["key"] = result, version
        return result

    wrapper.cached_model_method = True

    return classmethod(wrapper)


class FieldProcessingPipeline:
    """Defines model field level processing pipeline: how to fetch, steps to
    validate/cast."""

    def __init__(
        self,
        *path,
        cls_method=None,
        default=_none,
        default_factory=_none,
    ):
        if default is not _none and default_factory is not _none:
            raise ValueError(
                "default and default_factory are mutually exclusive"
            )
        if default is not _none or default_factory is not _none:
            if cls_method:
                raise ValueError("cls_method doesn't need defaults")
            self.steps = []
            self.required_check = False
        else:
            self.steps = []
            self.required_check = True

        self.cls_method = cls_method
        self.path = path
        self.default = default
        self.default_factory = default_factory

    def __set_name__(self, owner, name):
        if self.cls_method is True:
            self.cls_method = f"get_{name}"

        if self.cls_method:
            method = getattr(owner, self.cls_method, None)
            if not inspect.ismethod(method):
                raise AssertionError(
                    f"{owner.__name__} should have {self.cls_method} class method"
                )

    def validate(
        self, *args: "Union[Type, BaseValidator]"
    ) -> "FieldProcessingPipeline":
        if not args:
            raise ValueError("unnecessary method call")
        for arg in args:
            if not isinstance(arg, BaseValidator):
                arg = TypeValidator(arg)
            self.steps.append(arg)
        return self

    def cast(
        self,
        *args: "BaseCaster",
        overrides: CastOverrides = None,
    ) -> "FieldProcessingPipeline":
        if args:
            for arg in args:
                self.steps.append(ensure_caster(arg, overrides))
        else:
            self.steps.append(CasterToFinalType(overrides))
        return self


type_to_predefined_caster = {
    bool: BoolCaster(),
    list: NaiveCaster("list_caster", list, TypeError),
    tuple: NaiveCaster("tuple_caster", tuple, TypeError),
    dict: NaiveCaster("dict_caster", dict, (TypeError, ValueError)),
    str: StrCaster(),
    int: IntCaster(),
    float: NaiveCaster("float_caster", float, (TypeError, ValueError)),
    Decimal: DecimalCaster(),
    date: DateFromStrCaster("%Y-%m-%d"),
}


def try_simple_type_to_caster(type_value: "Type") -> "Optional[BaseCaster]":
    if type_value in type_to_predefined_caster:
        return type_to_predefined_caster[type_value]
    if isinstance(type_value, type) and issubclass(type_value, Enum):
        return EnumCaster(type_value)
    return None


def ensure_caster(
    caster: "Union[Type, BaseCaster]",
    overrides: CastOverrides,
):
    if isinstance(caster, BaseCaster):
        return caster

    return TypeCaster(caster, overrides)


def field(
    *path,
    cls_method=None,
    default=_none,
    default_factory=_none,
) -> "FieldProcessingPipeline":
    return FieldProcessingPipeline(
        *path,
        cls_method=cls_method,
        default=default,
        default_factory=default_factory,
    )


def validate(*args: "BaseValidator") -> "FieldProcessingPipeline":
    return FieldProcessingPipeline().validate(*args)


def cast(
    *args: "BaseCaster", overrides: CastOverrides = None
) -> "FieldProcessingPipeline":
    return FieldProcessingPipeline().cast(*args, overrides=overrides)


_base_json_encoder_default = json.JSONEncoder().default


def json_encoder_default(obj):
    if isinstance(obj, BaseModel):
        return obj.to_dict()
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    return _base_json_encoder_default(obj)


def json_dumps(data):
    return json.dumps(data, default=json_encoder_default)
