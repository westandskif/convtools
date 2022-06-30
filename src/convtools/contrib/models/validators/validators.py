"""Contains validators - objects which only check the data and populate error
objects"""
import abc
import re
from decimal import Decimal as Decimal_
from typing import TYPE_CHECKING

from convtools import conversion as c

from ..base import BaseStep, TypeValueCodeGenArgs, _none
from ..utils import is_generic_alias, is_model_cls


if TYPE_CHECKING:
    from typing import List

    from convtools.base import BaseConversion


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
    _error = {"required": True}

    def validate(self, field_name, data, errors):
        if data is _none:
            errors[field_name]["__ERRORS"] = self._error
        else:
            return True


class Type(BaseValidator):
    """Type validator (also used internally). It runs isinstance(data, types)
    on input data and it doesn't support typing generics"""

    name = "type"

    def __init__(self, *types):
        chunks = self.chunk_types_to_simple_and_other(types)
        if len(chunks) != 1 or chunks[0]["chunk_type"] != "simple":
            raise ValueError(
                "Type validator doesn't support generics on this level"
            )

        isinstance(None, types)  # make sure types are valid
        self.type_ = types if len(types) > 1 else types[0]
        self.type_verbose = "/".join(type_.__name__ for type_ in types)

    def validate(self, field_name, data, errors):
        if not isinstance(data, self.type_):
            errors[field_name]["__ERRORS"] = {
                self.name: f"{type(data).__name__} instead of {self.type_verbose}"
            }
        else:
            return True

    chunk_types_to_simple_and_other = (
        c.iter(
            (
                c.if_(
                    c.or_(
                        c.call_func(is_generic_alias, c.this),
                        c.call_func(is_model_cls, c.this),
                    ),
                    "other",
                    "simple",
                ),
                c.this,
            )
        )
        .pipe(
            c.chunk_by_condition(
                c.and_(c.CHUNK.item(-1, 0) == c.item(0), c.item(0) == "simple")
            ).aggregate(
                {
                    "chunk_type": c.ReduceFuncs.First(c.item(0)),
                    "types": c.ReduceFuncs.Array(c.item(1)),
                }
            )
        )
        .as_type(list)
        .gen_converter(class_method=True)
    )

    @classmethod
    def to_code(cls, simple_types, args: TypeValueCodeGenArgs):
        length_before = len(simple_types)
        NoneType = type(None)
        simple_types = [
            type_ for type_ in simple_types if type_ is not NoneType
        ]
        has_none = len(simple_types) < length_before

        type_verbose = (
            f"{'NoneType/' if has_none else ''}"
            f"{'/'.join(type_.__name__ for type_ in simple_types)}"
        )
        conditions: "List[BaseConversion]" = []

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
        set_error_code = f'{args.errors_code}[{args.name_code}]["__ERRORS"] = {{{repr(cls.name)}: f"{{type({args.data_code}).__name__}} instead of {type_verbose}"}}'
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
            re.compile(pattern) if isinstance(pattern, str) else pattern
        )

    def validate(self, field_name, data, errors):
        if not self.pattern.fullmatch(data):
            errors[field_name]["__ERRORS"] = {self.name: "failed"}
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
            errors[field_name]["__ERRORS"] = {
                self.name: f"should be > {self.value}"
            }


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
            errors[field_name]["__ERRORS"] = {
                self.name: f"should be >= {self.value}"
            }


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
            errors[field_name]["__ERRORS"] = {
                self.name: f"should be < {self.value}"
            }


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
            errors[field_name]["__ERRORS"] = {
                self.name: f"should be <= {self.value}"
            }


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
            errors[field_name]["__ERRORS"] = {self.name: "failed"}


class Decimal(BaseValidator):
    """Decimal validator, which checks max_digits and decimal_places (precision
    and scale PostgreSQL counterparts)"""

    ensures_type = Decimal_
    name = "decimal"

    def __init__(self, max_digits, decimal_places):
        if max_digits < decimal_places:
            raise ValueError(
                "max_digits should be greater than or equal to decimal_places"
            )
        self.max_digits = max_digits
        self.decimal_places = decimal_places

    def validate(self, field_name, data, errors):
        if isinstance(data, Decimal_):
            decimal_tuple = data.as_tuple()
            digits_length = len(decimal_tuple.digits)
            if digits_length > self.max_digits:
                errors[field_name]["__ERRORS"] = {
                    "max_digits": f"{data} should have <= {self.max_digits} total digits"
                }
            elif -decimal_tuple.exponent > self.decimal_places:
                errors[field_name]["__ERRORS"] = {
                    "decimal_places": f"{data} should have <= {self.decimal_places} decimal places"
                }
            elif (
                digits_length + min(decimal_tuple.exponent, 0)
                > self.max_digits - self.decimal_places
            ):
                errors[field_name]["__ERRORS"] = {
                    "integer_digits": f"{data} should have <= {self.max_digits - self.decimal_places} integer digits"
                }
        else:
            errors[field_name]["__ERRORS"] = {"type": "not a Decimal"}
