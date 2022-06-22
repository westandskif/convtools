"""
Contains casters - objects which define type casting operation, including
checking for corresponding validation errors.
"""
import abc
from collections import defaultdict
from datetime import datetime
from decimal import Decimal as Decimal_
from decimal import InvalidOperation

from convtools import conversion as c
from convtools.utils import Code

from ..base import BaseStep


class BaseCaster(BaseStep):
    """Defines base caster (object which casts input data to a necessary type
    or describes errors)"""

    STEP_TYPE = "code_generative_caster"
    name = "base_caster"

    def as_conversion(
        self,
        code_suffix,
        name_code,
        data_code,
        errors_code,
        base_conversion,
        ctx,
        level,
    ):
        raise NotImplementedError

    def as_conversion_function(
        self,
        caster_name_prefix,
        code_suffix,
        name_code,  # pylint: disable=unused-argument
        data_code,  # pylint: disable=unused-argument
        errors_code,  # pylint: disable=unused-argument
        base_conversion,
        ctx,
        level,
    ):
        # TODO: think about carving this out to a separate function
        converter_name = base_conversion.gen_name(
            caster_name_prefix, ctx, self
        )
        code = Code()
        code.add_line(f"def {converter_name}(name_, data_, errors_):", 1)
        code.add_line("global __naive_values__", 0)
        code.add_line("_naive = __naive_values__", 0)
        conversion_code = self.as_conversion(
            code_suffix,
            "name_",
            "data_",
            "errors_",
            base_conversion,
            ctx,
            level,
        ).gen_code_and_update_ctx("data_", ctx)
        code.add_line(f"return {conversion_code}", 0)
        base_conversion.compile_converter(
            converter_name=converter_name,
            code=code.to_string(base_indent_level=0),
            ctx=ctx,
        )
        return c.escaped_string(converter_name)


class SimpleCaster(BaseCaster, abc.ABC):
    """Defines simple caster where self.cast method contains cast/validate
    logic"""

    STEP_TYPE = "simple_caster"

    def __init__(self, name):
        self.name = name

    @abc.abstractmethod
    def cast(self, field_name, data, errors):
        """to be defined"""

    def as_conversion_function(
        self,
        caster_name_prefix,
        code_suffix,
        name_code,
        data_code,
        errors_code,
        base_conversion,
        ctx,
        level,
    ):
        return c.naive(self.cast, name_prefix=self.name)

    def as_conversion(
        self,
        code_suffix,
        name_code,
        data_code,
        errors_code,
        base_conversion,
        ctx,
        level,
    ):
        return c.naive(
            self.cast, name_prefix=f"{self.name}{code_suffix}"
        ).call(
            c.escaped_string(name_code), c.this, c.escaped_string(errors_code)
        )


class CustomUnsafe(BaseCaster):
    """Defines unsafe custom caster, which runs passed callable and doesn't
    catch any exceptions"""

    def __init__(self, func):
        self.cast = func

    def as_conversion(
        self,
        code_suffix,
        name_code,
        data_code,
        errors_code,
        base_conversion,
        ctx,
        level,
    ):
        return c.naive(
            self.cast, name_prefix=f"unsafe_cast{code_suffix}"
        ).call(c.this)


class List(BaseCaster):
    """Defines list caster which makes sure that it works with iterable and
    then rebuilds a new list, running self.item_caster on every collection
    item"""

    name = "generic_list"

    def __init__(self, item_caster):
        self.item_caster = item_caster

    def as_conversion(
        self,
        code_suffix,
        name_code,
        data_code,
        errors_code,
        base_conversion,
        ctx,
        level,
    ):
        return c.naive(
            self.cast, name_prefix=f"{self.name}{code_suffix}"
        ).call(
            self.item_caster.as_conversion_function(
                "item_caster",
                code_suffix,
                name_code,
                data_code,
                errors_code,
                base_conversion,
                ctx,
                level,
            ),
            c.escaped_string(name_code),
            c.this,
            c.escaped_string(errors_code),
        )

    def cast(self, item_caster, field_name, data, errors):
        try:
            it = iter(data)
        except TypeError:
            errors[field_name]["type"] = f"{type(data).__name__} not iterable"
            return

        new_errors = defaultdict(dict)
        new_data = [
            item_caster(index, item, new_errors)
            for index, item in enumerate(it)
        ]
        if new_errors:
            errors[field_name] = new_errors
        else:
            return new_data


class Dict(BaseCaster):
    """Defines list caster which makes sure that it works with a dict and then
    rebuilds a new dict, running self.key_caster and self.value_caster on every
    key-value pair"""

    name = "generic_dict"

    def __init__(self, key_caster, value_caster):
        self.key_caster = key_caster
        self.value_caster = value_caster
        self.name = f"{self.name}_{key_caster.name}_{value_caster.name}"

    def as_conversion(
        self,
        code_suffix,
        name_code,
        data_code,
        errors_code,
        base_conversion,
        ctx,
        level,
    ):
        return c.naive(
            self.cast, name_prefix=f"{self.name}{code_suffix}{level}"
        ).call(
            self.key_caster.as_conversion_function(
                "key_caster",
                code_suffix,
                name_code,
                data_code,
                errors_code,
                base_conversion,
                ctx,
                level,
            ),
            self.value_caster.as_conversion_function(
                "value_caster",
                code_suffix,
                name_code,
                data_code,
                errors_code,
                base_conversion,
                ctx,
                level,
            ),
            c.escaped_string(name_code),
            c.this,
            c.escaped_string(errors_code),
        )

    def cast(self, key_caster, value_caster, field_name, data, errors):
        if not isinstance(data, dict):
            errors[field_name][
                "type"
            ] = f"expected dict, got {type(data).__name__}"
            return
        key_errors = defaultdict(dict)
        value_errors = defaultdict(dict)
        new_data = {
            key_caster(key, key, key_errors): value_caster(
                key, value, value_errors
            )
            for key, value in data.items()
        }
        if key_errors or value_errors:
            errors[field_name]["keys"] = key_errors
            errors[field_name]["values"] = value_errors
        else:
            return new_data


class CasterToFinalType(BaseCaster):
    """Caster placeholder to be initialized with the caster to the output
    type"""


class Union(BaseCaster):
    """Defines a caster which tries to run passed casters until the first
    success."""

    def __init__(self, *casters, accept_none=False):
        self.casters = casters
        self.accept_none = accept_none

    def as_conversion(
        self,
        code_suffix,
        name_code,
        data_code,
        errors_code,
        base_conversion,
        ctx,
        level,
    ):
        return self.as_conversion_function(
            "union",
            code_suffix,
            name_code,
            data_code,
            errors_code,
            base_conversion,
            ctx,
            level,
        ).call(
            c.escaped_string(name_code), c.this, c.escaped_string(errors_code)
        )

    def as_conversion_function(
        self,
        caster_name_prefix,
        code_suffix,
        name_code,
        data_code,
        errors_code,
        base_conversion,
        ctx,
        level,
    ):
        converter_name = base_conversion.gen_name(
            caster_name_prefix, ctx, self
        )
        code = Code()
        code.add_line(f"def {converter_name}(name_, data_, errors_):", 1)
        code.add_line("global __naive_values__", 0)
        code.add_line("_naive = __naive_values__", 0)

        if self.accept_none:
            code.add_line("if data_ is not None:", 1)

        last_index = len(self.casters) - 1
        for index, caster in enumerate(self.casters):
            caster_code = caster.as_conversion(
                code_suffix,
                "name_",
                "data_",
                "errors_",
                base_conversion,
                ctx,
                level,
            ).gen_code_and_update_ctx("data_", ctx)

            if index == last_index:
                code.add_line(f"return {caster_code}", 0)
            else:
                code.add_line(f"result_ = {caster_code}", 0)
                code.add_line("if name_ not in errors_:", 1)
                code.add_line("return result_", -1)
                code.add_line("del errors_[name_]", 0)

        base_conversion.compile_converter(
            converter_name=converter_name,
            code=code.to_string(base_indent_level=0),
            ctx=ctx,
        )
        return c.escaped_string(converter_name)


def Optional(caster) -> Union:  # pylint: disable=invalid-name
    return Union(caster, accept_none=True)


class DatetimeFromStr(SimpleCaster):
    """str to datetime caster"""

    def __init__(self, fmt):
        super().__init__("datetime_from_str")
        self.fmt = fmt

    def cast(self, field_name, data, errors):
        try:
            return datetime.strptime(data, self.fmt)
        except (ValueError, TypeError):
            errors[field_name][
                self.name
            ] = f"failed to parse date with: {self.fmt}"


class DateFromStr(SimpleCaster):
    """str to date caster"""

    def __init__(self, fmt):
        super().__init__("date_from_str")
        self.fmt = fmt

    def cast(self, field_name, data, errors):
        try:
            return datetime.strptime(data, self.fmt).date()
        except (ValueError, TypeError):
            errors[field_name][
                self.name
            ] = f"failed to parse date with: {self.fmt}"


class Enum(SimpleCaster):
    def __init__(self, enum_cls):
        super().__init__("enum_caster")
        self.enum_cls = enum_cls

    def cast(self, field_name, data, errors):
        try:
            return self.enum_cls(data)
        except ValueError:
            errors[field_name][
                self.name
            ] = f"{self.enum_cls.__name__}: unknown value = {data}"


class IntLossy(SimpleCaster):
    """Tries to cast anything to int, doesn't prevent decimal part loss"""

    exceptions = (TypeError, ValueError)

    def __init__(self):
        super().__init__("int_lossy_caster")

    def cast(self, field_name, data, errors):
        try:
            return int(data)
        except self.exceptions:
            pass
        try:
            return int(float(data))
        except self.exceptions:
            errors[field_name][
                self.name
            ] = f"failed for type {type(data).__name__}"


class Int(SimpleCaster):
    """Tries to cast anything to int. Fails in cases where it's either not
    possible or it results in decimal part loss"""

    exceptions = (TypeError, ValueError)

    def __init__(self):
        super().__init__("int_caster")

    def cast(self, field_name, data, errors):
        try:
            if not isinstance(data, str) and data % 1:
                errors[field_name][self.name] = (
                    f"losing fractional part: {data}; "
                    "if desired, use casters.IntLossy"
                )
                return
            return int(data)
        except self.exceptions:
            errors[field_name][
                self.name
            ] = f"failed for type {type(data).__name__}"


class DecimalLossy(SimpleCaster):
    """Tries to cast anything to Decimal, doesn't prevent initializing from
    floats with non-zero decimal parts"""

    exceptions = (TypeError, InvalidOperation)

    def __init__(self):
        super().__init__("decimal_lossy_caster")

    def cast(self, field_name, data, errors):
        try:
            return Decimal_(data)
        except self.exceptions:
            errors[field_name][
                self.name
            ] = f"failed for type {type(data).__name__}"


class Decimal(SimpleCaster):
    """Tries to cast anything to Decimal, prevents initializing from
    floats with non-zero decimal parts"""

    exceptions = (TypeError, InvalidOperation)

    def __init__(self):
        super().__init__("decimal_caster")

    def cast(self, field_name, data, errors):
        try:
            if isinstance(data, float) and data % 1:
                errors[field_name][self.name] = (
                    f"imprecise init from float: {data}; "
                    "if desired, use casters.DecimalLossy"
                )
                return
            return Decimal_(data)
        except self.exceptions:
            errors[field_name][
                self.name
            ] = f"failed for type {type(data).__name__}"


class Custom(SimpleCaster):
    """Defines a caster, which tries to apply self.func to input data and
    catches self.exc_to_silence exceptions to silence them and return errors"""

    def __init__(self, caster_name, func, exc_to_silence):
        super().__init__(caster_name)
        self.func = func
        self.exc_to_silence = exc_to_silence

    def cast(self, field_name, data, errors):
        try:
            return self.func(data)
        except self.exc_to_silence:
            errors[field_name][self.name] = "failed"
