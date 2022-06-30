"""Defines methods which should close the gap in typing functionality between
python 3.6 and 3.7+ """
# flake8: noqa
import sys
from threading import RLock
from typing import Dict, List, Tuple, Union

from .base import BaseModel, CastOverrides


PY_VERSION = sys.version_info[0:2]

UnionCls = Union[int, str].__class__

if PY_VERSION <= (3, 6):

    GenericAlias = type(List[int])

    def is_generic_alias(obj):
        return isinstance(obj, GenericAlias) or is_generic_union_alias(obj)

    def is_generic_union_alias(obj):
        return obj.__class__ is UnionCls

    def is_generic_list_alias(alias):
        return alias.__origin__ is List

    def is_generic_tuple_alias(alias):
        return alias.__origin__ is Tuple

    def is_generic_dict_alias(alias):
        return alias.__origin__ is Dict

else:  # if PY_VERSION > (3, 6): -- comment for .coveragerc
    from typing import _GenericAlias  # type: ignore

    def is_generic_alias(obj):
        return isinstance(obj, _GenericAlias)

    def is_generic_union_alias(obj):
        return obj.__origin__ is Union

    def is_generic_list_alias(alias):
        return alias.__origin__ is list

    def is_generic_tuple_alias(alias):
        return alias.__origin__ is tuple

    def is_generic_dict_alias(alias):
        return alias.__origin__ is dict


def ensure_generic_alias_has_args(alias, type_var_to_type_value):
    if is_generic_alias(alias):
        if alias.__parameters__:
            return type(alias).__getitem__(
                alias,
                *tuple(
                    type_var_to_type_value[p] for p in alias.__parameters__
                ),
            )
    return alias


def is_model_cls(cls):
    return isinstance(cls, type) and issubclass(cls, BaseModel)


def __hash__(self):  # pylint: disable=invalid-name
    return hash(tuple(self.__args__))


patching_lock = RLock()


class TypeValueWrapper:
    """We have to patch typing.Union hash method to make it order sensitive as
    it is required for lru_cache + Union type casting"""

    __slots__ = ("type_value", "cast", "cast_overrides")

    def __init__(self, type_value, cast: bool, cast_overrides: CastOverrides):
        self.type_value = type_value
        self.cast = cast
        self.cast_overrides = cast_overrides

    def validate_args(self):
        if not self.cast and self.cast_overrides:
            raise ValueError("remove cast_overrides when cast is not True")

        if self.cast and is_model_cls(self.type_value):
            raise ValueError(
                "build(..., cast=True) doesn't affect inner models, either use field-level cast() or Meta.cast"
            )

    def __eq__(self, other):
        return (
            self.type_value == other.type_value
            and self.cast == other.cast
            and self.cast_overrides == other.cast_overrides
        )

    def __hash__(self):
        with patching_lock:
            prev_hash = UnionCls.__hash__
            UnionCls.__hash__ = __hash__
            try:
                return hash(self.type_value)
            finally:
                UnionCls.__hash__ = prev_hash
