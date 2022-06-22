"""Contains validators - objects which only check the data and populate error
objects"""
import abc
import re
import typing as t
from typing import TYPE_CHECKING

from convtools import conversion as c

from ..base import BaseModel, BaseStep, TypeValueCodeGenArgs, _none


if TYPE_CHECKING:
    from convtools.base import BaseConversion  # pragma: no cover


class BaseValidator(abc.ABC, BaseStep):
    name: str
    STEP_TYPE = "validate"

    @abc.abstractmethod
    def validate(self, field_name, data, errors):
        """abstract validate method"""


class Required(BaseValidator):
    """Internally used validator, which checks fields without defaults for
    existence"""

    name = "required"
    __slots__ = ()

    def validate(self, field_name, data, errors):
        if data is _none:
            errors[field_name][self.name] = True
        else:
            return True


class Type(BaseValidator):
    """Type validator (also used internally). It runs isinstance(data, types)
    on input data and it doesn't support typing generics"""

    name = "type"

    def __init__(self, *types):
        _, _, other_types = self.split_types(*types)
        if other_types:
            raise ValueError(
                "Type validator doesn't support generics on this level"
            )
        isinstance(None, types)  # make sure types are valid
        self.type_ = types if len(types) > 1 else types[0]
        self.type_verbose = "/".join(type_.__name__ for type_ in types)

    def validate(self, field_name, data, errors):
        if not isinstance(data, self.type_):
            errors[field_name][
                self.name
            ] = f"{type(data).__name__} instead of {self.type_verbose}"
        else:
            return True

    @classmethod
    def split_types(cls, *types):
        NoneType = type(None)

        has_none = False
        simple_types = []
        other_types = []
        for type_ in types:
            if type_ is NoneType:
                has_none = True
            elif not isinstance(type_, t._GenericAlias) and not (
                isinstance(type_, type) and issubclass(type_, BaseModel)
            ):
                simple_types.append(type_)
            else:
                other_types.append(type_)

        return has_none, simple_types, other_types

    @classmethod
    def to_code(cls, has_none, simple_types, args: TypeValueCodeGenArgs):
        type_verbose = (
            f"{'NoneType/' if has_none else ''}"
            f"{'/'.join(type_.__name__ for type_ in simple_types)}"
        )
        conditions: "t.List[BaseConversion]" = []
        if has_none:
            conditions.append(c.this.is_(None))
        if simple_types:
            conditions.append(
                c.escaped_string("isinstance").call(
                    c.this,
                    c.naive(
                        tuple(simple_types)
                        if len(simple_types) > 1
                        else simple_types[0],
                        name_prefix="_".join(
                            type_.__name__ for type_ in simple_types
                        ),
                    ),
                )
            )

        bad_type_condition_code = (
            c.or_(*conditions)
            .not_()
            .gen_code_and_update_ctx(args.data_code, args.ctx)
        )
        set_error_code = (
            f'{args.errors_code}[{args.name_code}]["type"] = '
            f'f"{{type({args.data_code}).__name__}} instead of {type_verbose}"'
        )
        return bad_type_condition_code, set_error_code


class Regex(BaseValidator):
    r"""Defines regex validator.

    >>> Regex(r"\d+")
    >>> # or pass an already compiled pattern
    >>> Regex(re.compile(r"\d+"))

    """

    name = "regex"

    def __init__(self, pattern):
        self.pattern = (
            pattern if isinstance(pattern, re.Pattern) else re.compile(pattern)
        )

    def validate(self, field_name, data, errors):
        if not self.pattern.fullmatch(data):
            errors[field_name][self.name] = "failed"
        else:
            return True


class Gt(BaseValidator):
    """Defines validator which checks whether input data is greater than
    self.value"""

    name = "gt"

    def __init__(self, value):
        self.value = value

    def validate(self, field_name, data, errors):
        if data > self.value:
            return True
        else:
            errors[field_name][self.name] = f"should be > {self.value}"


class Gte(BaseValidator):
    """Defines validator which checks whether input data is greater than or
    equal to self.value"""

    name = "gte"

    def __init__(self, value):
        self.value = value

    def validate(self, field_name, data, errors):
        if data >= self.value:
            return True
        else:
            errors[field_name][self.name] = f"should be >= {self.value}"


class Lt(BaseValidator):
    """Defines validator which checks whether input data is less than
    self.value"""

    name = "lt"

    def __init__(self, value):
        self.value = value

    def validate(self, field_name, data, errors):
        if data < self.value:
            return True
        else:
            errors[field_name][self.name] = f"should be < {self.value}"


class Lte(BaseValidator):
    """Defines validator which checks whether input data is less than or
    equal to self.value"""

    name = "lte"

    def __init__(self, value):
        self.value = value

    def validate(self, field_name, data, errors):
        if data <= self.value:
            return True
        else:
            errors[field_name][self.name] = f"should be <= {self.value}"


class Custom(BaseValidator):
    """Defines custom validator.

    >>> Custom("validator_name", lambda x: x > 10))

    """

    def __init__(self, name, func):
        if not callable(func):
            raise ValueError("func should be callable")

        self.name = name
        self.func = func

    def validate(self, field_name, data, errors):
        if self.func(data):
            return True
        else:
            errors[field_name][self.name] = "failed"
