"""Defines base classes"""
import abc
from collections import namedtuple
from typing import Dict, List, Optional, Type, Union

from convtools.base import BaseConversion


_none = BaseConversion._none


class BaseStep:
    STEP_TYPE = "base_step"
    ensures_type: Optional[Type] = None


TypeValueCodeGenArgs = namedtuple(
    "TypeValueCodeGenArgs",
    [
        "code_suffix",
        "code",
        "type_value",
        "name_code",
        "data_code",
        "errors_code",
        "base_conversion",
        "ctx",
        "level",
        "type_var_to_type_value",
        "type_to_model_meta",
        "cast",
        "cast_overrides_stack",
        # to track top level unions, because order matters
        "path_before_model",
        "model_depth",
        "union_paths",
    ],
)


class BaseCaster(BaseStep, abc.ABC):
    """Defines base caster (object which casts input data to a necessary type
    or describes errors)"""

    STEP_TYPE = "cast"
    name = "base_caster"

    @abc.abstractmethod
    def to_code(self, args: TypeValueCodeGenArgs):
        raise NotImplementedError


CastOverrides = Union[
    None,
    Dict[Type, BaseCaster],
    Dict[Type, List[BaseCaster]],
]


class BaseModel:
    def __getitem__(self, key):
        return getattr(self, key)

    def to_dict(self):
        raise NotImplementedError


class ProxyObject:
    def __init__(self):
        self.wrapped_object__ = None

    def __getattr__(self, name):
        return getattr(self.wrapped_object__, name)


class DictModel(BaseModel):
    pass


class ObjectModel(BaseModel):
    pass


class BaseError(Exception):
    pass


class ValidationError(BaseError):
    pass


dict_getitem = dict.__getitem__
dict_contains = dict.__contains__
dict_delitem = dict.__delitem__


class ErrorsDict(dict):
    """This is a dict which acts like a defaultdict(dict) of any depth.
    It also supports lazy entries."""

    locked = False

    def lock(self):
        if self.locked is False:
            self.locked = True
        else:
            self.locked[None] = None

    def __getitem__(self, k):
        try:
            return dict_getitem(self, k)
        except KeyError:
            if self.locked:
                raise

            if k == "__ROOT":
                return self

            self[k] = value = ErrorsDict()
            if self.locked is False:
                value.locked = self.locked = {}
            else:
                value.locked = self.locked
            return value

    def __contains__(self, k):
        if k == "__ROOT":
            return self
        return dict_contains(self, k)

    def __delitem__(self, k):
        if k == "__ROOT":
            return self.clear()
        dict_delitem(self, k)

    def get_lazy_item(self, k):
        if k == "__ROOT":
            return self
        if k in self:
            return self[k]
        return LazyErrorsDict(self, k)


class LazyErrorsDict:
    """A helper class which is a lazy entry of
    :py:obj:`ErrorsDict<convtools.contrib.models.base.ErrorsDict>`"""

    __slots__ = ("parent_errors_dict", "key", "value")

    def __init__(self, parent_errors_dict, key):
        self.parent_errors_dict = parent_errors_dict
        self.key = key
        self.value = None

    def __getitem__(self, k):
        if self.value is None:
            self.value = self.parent_errors_dict[self.key]
        return self.value[k]

    def __setitem__(self, k, v):
        if self.value is None:
            self.value = self.parent_errors_dict[self.key]
        self.value[k] = v

    def __contains__(self, key):
        if self.value is None:
            return False
        return key in self.value

    def __delitem__(self, k):
        if self.value is not None:
            del self.value[k]

            if not self.value:
                del self.parent_errors_dict[self.key]
                self.value = None

    def __bool__(self):
        return bool(self.value)

    def get_lazy_item(self, k):
        if k == "__ROOT":
            return self
        return LazyErrorsDict(self, k)
