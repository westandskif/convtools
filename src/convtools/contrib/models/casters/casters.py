"""
Contains implementation of base casters.
"""
from datetime import date, datetime
from decimal import Decimal as Decimal_
from decimal import InvalidOperation

from convtools import conversion as c

from ..base import BaseCaster, TypeValueCodeGenArgs
from .base import SimpleCaster


class CustomUnsafe(BaseCaster):
    """Defines unsafe custom caster, which runs passed callable and doesn't
    catch any exceptions"""

    def __init__(self, func):
        self._cast = func

    def to_code(self, args: TypeValueCodeGenArgs):
        cast_expression = (
            c.naive(
                self._cast,
                name_prefix=f"unsafe_cast{args.code_suffix}{args.level}",
            )
            .call(c.escaped_string(args.data_code))
            .gen_code_and_update_ctx("not needed", args.ctx)
        )
        args.code.add_line(
            f"{args.data_code} = {cast_expression}", 0, cast_expression
        )


class Str(SimpleCaster):
    """Into str caster"""

    ensures_type = str

    def __init__(self, encoding="utf-8"):
        super().__init__("into_str")
        self.encoding = encoding

    def _cast(self, field_name, data, errors):
        if isinstance(data, str):
            return data
        if isinstance(data, bytes):
            try:
                return data.decode(self.encoding)
            except Exception as e:  # pylint: disable=broad-except
                errors[field_name]["__ERRORS"] = {"decoding": str(e)}
        else:
            return str(data)


naive_exceptions = (TypeError, ValueError)
strptime_function = datetime.strptime


class DatetimeFromStr(SimpleCaster):
    """str to datetime caster"""

    ensures_type = datetime

    def __init__(self, fmt):
        super().__init__("datetime_from_str")
        self.fmt = fmt

    def _cast(self, field_name, data, errors):
        try:
            return strptime_function(data, self.fmt)
        except naive_exceptions:
            errors[field_name]["__ERRORS"] = {
                self.name: f"failed to parse date with: {self.fmt}"
            }


class DateFromStr(SimpleCaster):
    """str to date caster"""

    ensures_type = date

    def __init__(self, fmt):
        super().__init__("date_from_str")
        self.fmt = fmt

    def _cast(self, field_name, data, errors):
        try:
            return strptime_function(data, self.fmt).date()
        except naive_exceptions:
            errors[field_name]["__ERRORS"] = {
                self.name: f"failed to parse date with: {self.fmt}"
            }


class Enum(SimpleCaster):
    """casts anything to the provided Enum by calling it, passing data as
    argument"""

    def __init__(self, enum_cls):
        super().__init__("enum_caster")
        self.enum_cls = enum_cls
        self.ensures_type = enum_cls

    def _cast(self, field_name, data, errors):
        try:
            return self.enum_cls(data)
        except ValueError:
            errors[field_name]["__ERRORS"] = {
                self.name: f"{self.enum_cls.__name__}: unknown value = {data}"
            }


class IntLossy(SimpleCaster):
    """Tries to cast anything to int, doesn't prevent decimal part loss"""

    ensures_type = int

    def __init__(self):
        super().__init__("int_lossy_caster")

    def _cast(self, field_name, data, errors):
        if isinstance(data, int):
            return data
        try:
            return int(data)
        except naive_exceptions:
            pass
        try:
            return int(float(data))
        except naive_exceptions:
            errors[field_name]["__ERRORS"] = {
                self.name: f"failed for type {type(data).__name__}"
            }


class Int(SimpleCaster):
    """Tries to cast anything to int. Fails in cases where it's either not
    possible or it results in decimal part loss"""

    ensures_type = int

    def __init__(self):
        super().__init__("int_caster")

    def _cast(self, field_name, data, errors):
        if isinstance(data, int):
            return data
        try:
            if isinstance(data, str):
                return int(data)

            if data % 1 == 0:
                return int(data)
            else:
                errors[field_name]["__ERRORS"] = {
                    self.name: (
                        f"losing fractional part: {data}; "
                        "if desired, use casters.IntLossy"
                    )
                }
        except naive_exceptions:
            errors[field_name]["__ERRORS"] = {
                self.name: f"failed for type {type(data).__name__}"
            }


class Bool(BaseCaster):
    """Casts anything to bool"""

    ensures_type = bool

    def to_code(self, args: TypeValueCodeGenArgs):
        cast_expression = f"bool({args.data_code})"
        args.code.add_line(
            f"{args.data_code} = {cast_expression}", 0, cast_expression
        )


class NaiveCaster(SimpleCaster):
    """Tries to cast anything to a given type"""

    def __init__(self, name, type_, exceptions):
        super().__init__(name)
        self.type_ = type_
        self.exceptions = exceptions
        self.ensures_type = type_

    def _cast(self, field_name, data, errors):
        if isinstance(data, self.type_):
            return data
        try:
            return self.type_(data)
        except naive_exceptions:
            errors[field_name]["__ERRORS"] = {
                self.name: f"failed for type {type(data).__name__}"
            }


decimal_exceptions = (TypeError, InvalidOperation)


class DecimalLossy(SimpleCaster):
    """Tries to cast anything to Decimal, doesn't prevent initializing from
    floats with non-zero decimal parts"""

    ensures_type = Decimal_

    def __init__(self, quantize_exp=None, rounding=None):
        super().__init__("decimal_lossy_caster")
        self.quantize_exp = quantize_exp
        self.rounding = rounding

    def _cast(self, field_name, data, errors):
        try:
            if self.quantize_exp is None:
                return Decimal_(data)
            return Decimal_(data).quantize(self.quantize_exp, self.rounding)
        except decimal_exceptions:
            errors[field_name]["__ERRORS"] = {
                self.name: f"failed for type {type(data).__name__}"
            }


class Decimal(SimpleCaster):
    """Tries to cast anything to Decimal, prevents initializing from
    floats with non-zero decimal parts"""

    ensures_type = Decimal_

    exceptions = (TypeError, InvalidOperation)

    def __init__(self):
        super().__init__("decimal_caster")

    def _cast(self, field_name, data, errors):
        try:
            if isinstance(data, float) and data % 1:
                errors[field_name]["__ERRORS"] = {
                    self.name: (
                        f"imprecise init from float: {data}; "
                        "if desired, use casters.DecimalLossy"
                    )
                }
                return
            return Decimal_(data)
        except decimal_exceptions:
            errors[field_name]["__ERRORS"] = {
                self.name: f"failed for type {type(data).__name__}"
            }


class Custom(SimpleCaster):
    """Defines a caster, which tries to apply self.func to input data and
    catches self.exc_to_silence exceptions to silence them and return errors"""

    def __init__(self, caster_name, func, exc_to_silence):
        super().__init__(caster_name)
        self.func = func
        self.exc_to_silence = exc_to_silence

    def _cast(self, field_name, data, errors):
        try:
            return self.func(data)
        except self.exc_to_silence:
            errors[field_name]["__ERRORS"] = {self.name: "failed"}
