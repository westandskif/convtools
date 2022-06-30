"""
Contains implementation of base casters.
"""
from datetime import datetime
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
        args.code.add_line(
            "{} = {}".format(  # pylint: disable=consider-using-f-string
                args.data_code,
                (
                    c.naive(
                        self._cast,
                        name_prefix=f"unsafe_cast{args.code_suffix}{args.level}",
                    )
                    .call(c.escaped_string(args.data_code))
                    .gen_code_and_update_ctx("not needed", args.ctx)
                ),
            ),
            0,
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


class DatetimeFromStr(SimpleCaster):
    """str to datetime caster"""

    def __init__(self, fmt):
        super().__init__("datetime_from_str")
        self.fmt = fmt

    def _cast(self, field_name, data, errors):
        try:
            return datetime.strptime(data, self.fmt)
        except (ValueError, TypeError):
            errors[field_name]["__ERRORS"] = {
                self.name: f"failed to parse date with: {self.fmt}"
            }


class DateFromStr(SimpleCaster):
    """str to date caster"""

    def __init__(self, fmt):
        super().__init__("date_from_str")
        self.fmt = fmt

    def _cast(self, field_name, data, errors):
        try:
            return datetime.strptime(data, self.fmt).date()
        except (ValueError, TypeError):
            errors[field_name]["__ERRORS"] = {
                self.name: f"failed to parse date with: {self.fmt}"
            }


class Enum(SimpleCaster):
    def __init__(self, enum_cls):
        super().__init__("enum_caster")
        self.enum_cls = enum_cls

    def _cast(self, field_name, data, errors):
        try:
            return self.enum_cls(data)
        except ValueError:
            errors[field_name]["__ERRORS"] = {
                self.name: f"{self.enum_cls.__name__}: unknown value = {data}"
            }


class IntLossy(SimpleCaster):
    """Tries to cast anything to int, doesn't prevent decimal part loss"""

    exceptions = (TypeError, ValueError)

    def __init__(self):
        super().__init__("int_lossy_caster")

    def _cast(self, field_name, data, errors):
        if isinstance(data, int):
            return data
        try:
            return int(data)
        except self.exceptions:
            pass
        try:
            return int(float(data))
        except self.exceptions:
            errors[field_name]["__ERRORS"] = {
                self.name: f"failed for type {type(data).__name__}"
            }


class Int(SimpleCaster):
    """Tries to cast anything to int. Fails in cases where it's either not
    possible or it results in decimal part loss"""

    exceptions = (TypeError, ValueError)

    def __init__(self):
        super().__init__("int_caster")

    def _cast(self, field_name, data, errors):
        if isinstance(data, int):
            return data
        try:
            if not isinstance(data, str) and data % 1:
                errors[field_name]["__ERRORS"] = {
                    self.name: (
                        f"losing fractional part: {data}; "
                        "if desired, use casters.IntLossy"
                    )
                }
            else:
                return int(data)
        except self.exceptions:
            errors[field_name]["__ERRORS"] = {
                self.name: f"failed for type {type(data).__name__}"
            }


class NaiveCaster(SimpleCaster):
    """Tries to cast anything to float"""

    exceptions = (TypeError, ValueError)

    def __init__(self, name, type_, exceptions):
        super().__init__(name)
        self.type_ = type_
        self.exceptions = exceptions

    def _cast(self, field_name, data, errors):
        if isinstance(data, self.type_):
            return data
        try:
            return self.type_(data)
        except self.exceptions:
            errors[field_name]["__ERRORS"] = {
                self.name: f"failed for type {type(data).__name__}"
            }


class DecimalLossy(SimpleCaster):
    """Tries to cast anything to Decimal, doesn't prevent initializing from
    floats with non-zero decimal parts"""

    ensures_type = Decimal_

    exceptions = (TypeError, InvalidOperation)

    def __init__(self, quantize_exp=None, rounding=None):
        super().__init__("decimal_lossy_caster")
        self.quantize_exp = quantize_exp
        self.rounding = rounding

    def _cast(self, field_name, data, errors):
        try:
            if self.quantize_exp is None:
                return Decimal_(data)
            return Decimal_(data).quantize(self.quantize_exp, self.rounding)
        except self.exceptions:
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
        except self.exceptions:
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
