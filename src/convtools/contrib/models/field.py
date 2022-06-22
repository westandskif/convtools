"""Defines model field level processing pipeline"""
import inspect
import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from functools import wraps
from typing import TYPE_CHECKING

from .base import BaseModel, _none
from .casters.casters import BaseCaster, CasterToFinalType
from .casters.casters import Custom as CustomCaster
from .casters.casters import DateFromStr as DateFromStrCaster
from .casters.casters import Decimal as DecimalCaster
from .casters.casters import Dict as DictCaster
from .casters.casters import Enum as EnumCaster
from .casters.casters import Int as IntCaster
from .casters.casters import List as ListCaster
from .casters.casters import Union as UnionCaster
from .utils import (
    is_generic_alias,
    is_generic_dict_alias,
    is_generic_list_alias,
    is_generic_union_alias,
)
from .validators.validators import BaseValidator, Required
from .validators.validators import Type as TypeValidator


if TYPE_CHECKING:  # pragma: no cover
    from typing import Type, Union


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

    _required_validator = Required()

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
        else:
            self.steps = [self._required_validator]

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
    ) -> "FieldProcessingPipeline":
        if args:
            for arg in args:
                self.steps.append(ensure_caster(arg))
        else:
            self.steps.append(CasterToFinalType())
        return self


type_to_predefined_caster = {
    list: CustomCaster("list_caster", list, TypeError),
    dict: CustomCaster("dict_caster", dict, (TypeError, ValueError)),
    str: CustomCaster("str_caster", str, ()),
    int: IntCaster(),
    float: CustomCaster("float_caster", float, (TypeError, ValueError)),
    Decimal: DecimalCaster(),
    date: DateFromStrCaster("%Y-%m-%d"),
}


def ensure_caster(caster: "Union[Type, BaseCaster]"):
    if isinstance(caster, BaseCaster):
        return caster
    if caster in type_to_predefined_caster:
        return type_to_predefined_caster[caster]
    if isinstance(caster, type) and issubclass(caster, Enum):
        return EnumCaster(caster)
    if is_generic_alias(caster):
        if is_generic_union_alias(caster):
            NoneType = type(None)
            caster_instances = [
                ensure_caster(arg)
                for arg in caster.__args__
                if arg is not NoneType
            ]
            accepts_none = len(caster_instances) < len(caster.__args__)
            return UnionCaster(*caster_instances, accept_none=accepts_none)
        elif is_generic_list_alias(caster):
            # TODO: replace with direct imports
            return ListCaster(ensure_caster(caster.__args__[0]))
        elif is_generic_dict_alias(caster):
            return DictCaster(
                ensure_caster(caster.__args__[0]),
                ensure_caster(caster.__args__[1]),
            )

    raise ValueError(
        f"{caster} caster is not supported, "
        "consider wrapping with caster.Custom"
    )


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


def cast(*args: "BaseCaster") -> "FieldProcessingPipeline":
    return FieldProcessingPipeline().cast(*args)


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
