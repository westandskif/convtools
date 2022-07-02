"""Defines methods which should close the gap in typing functionality between
python 3.6 and 3.7+ """
# flake8: noqa
# pylint: disable=ungrouped-imports
import sys
from typing import TYPE_CHECKING

from .base import BaseModel, CastOverrides


if TYPE_CHECKING:
    from typing import Callable, Optional


PY_VERSION = sys.version_info[0:2]


if PY_VERSION <= (3, 6):

    from typing import Dict, List, Set, Tuple, Union

    UnionCls = Union[int, str].__class__
    GenericAlias = type(List[int])

    def is_union(obj):
        return obj.__class__ is UnionCls

    def is_generic_alias(obj):
        return isinstance(obj, GenericAlias)

    def is_generic_list_alias(alias):
        return alias.__origin__ is List

    def is_generic_tuple_alias(alias):
        return alias.__origin__ is Tuple

    def is_generic_dict_alias(alias):
        return alias.__origin__ is Dict

    def is_generic_set_alias(alias):
        return alias.__origin__ is Set

elif (
    (3, 7)
    <= PY_VERSION
    <= (
        3,
        8,
    )
):  # if PY_VERSION > (3, 6): -- comment for .coveragerc
    from typing import Union, _GenericAlias  # type: ignore

    def is_union(obj):
        return isinstance(obj, _GenericAlias) and obj.__origin__ is Union

    def is_generic_alias(obj):
        return isinstance(obj, _GenericAlias)

    def is_generic_list_alias(alias):
        return alias.__origin__ is list

    def is_generic_tuple_alias(alias):
        return alias.__origin__ is tuple

    def is_generic_dict_alias(alias):
        return alias.__origin__ is dict

    def is_generic_set_alias(alias):
        return alias.__origin__ is set

elif PY_VERSION == (3, 9):
    from typing import (  # type: ignore
        Dict,
        GenericAlias,
        List,
        Tuple,
        Union,
        _GenericAlias,
        _UnionGenericAlias,
    )

    alias_types = (GenericAlias, _GenericAlias)

    def is_union(obj):
        return isinstance(obj, _UnionGenericAlias)

    def is_generic_alias(obj):
        return isinstance(obj, alias_types)

    def is_generic_list_alias(alias):
        return alias.__origin__ is list

    def is_generic_tuple_alias(alias):
        return alias.__origin__ is tuple

    def is_generic_dict_alias(alias):
        return alias.__origin__ is dict

    def is_generic_set_alias(alias):
        return alias.__origin__ is set

elif PY_VERSION >= (3, 10):
    from types import UnionType  # type: ignore
    from typing import (  # type: ignore
        GenericAlias,
        _GenericAlias,
        _UnionGenericAlias,
    )

    alias_types = (GenericAlias, _GenericAlias)
    union_types = (UnionType, _UnionGenericAlias)

    def is_union(obj):
        return isinstance(obj, union_types)

    def is_generic_alias(obj):
        return isinstance(obj, alias_types)

    def is_generic_list_alias(alias):
        return alias.__origin__ is list

    def is_generic_tuple_alias(alias):
        return alias.__origin__ is tuple

    def is_generic_dict_alias(alias):
        return alias.__origin__ is dict

    def is_generic_set_alias(alias):
        return alias.__origin__ is set


if PY_VERSION <= (3, 7):

    def is_generic_literal_alias(obj):  # pylint: disable=unused-argument
        return False

else:

    from typing import Literal

    def is_generic_literal_alias(obj):
        return obj.__origin__ is Literal


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


class TypeValueWrapper:
    """We have to patch typing.Union hash method to make it order sensitive as
    it is required for lru_cache + Union type casting"""

    __slots__ = ("type_value", "cast", "cast_overrides", "union_args_getter")

    def __init__(self, type_value, cast: bool, cast_overrides: CastOverrides):
        self.type_value = type_value
        self.cast = cast
        self.cast_overrides = cast_overrides
        self.union_args_getter = None

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
            and (
                self.union_args_getter is None
                or (
                    self.union_args_getter(  # pylint: disable=not-callable
                        self.type_value
                    )
                    == self.union_args_getter(  # pylint: disable=not-callable
                        other.type_value
                    )
                )
            )
        )

    def __hash__(self):
        return hash(self.type_value)
