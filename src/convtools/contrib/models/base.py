"""Defines base classes"""
from collections import namedtuple


_none = object()


class BaseStep:
    STEP_TYPE = "base_step"


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
    ],
)
