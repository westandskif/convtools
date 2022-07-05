"""
Contains base casters - objects which define type casting operation, including
checking for corresponding validation errors.
"""
import abc
from typing import TYPE_CHECKING

from convtools import conversion as c
from convtools.contrib.models.base import (
    BaseCaster,
    CastOverrides,
    TypeValueCodeGenArgs,
)


if TYPE_CHECKING:
    from typing import Type


class SimpleCaster(BaseCaster, abc.ABC):
    """Defines simple caster where self._cast method contains cast/validate
    logic"""

    def __init__(self, name):
        self.name = name

    @abc.abstractmethod
    def _cast(self, field_name, data, errors):
        """to be defined"""

    def to_code(self, args: TypeValueCodeGenArgs):
        cast_expression = (
            c.naive(
                self._cast,
                name_prefix=f"{self.name}{args.code_suffix}{args.level}",
            )
            .call(
                c.escaped_string(args.name_code),
                c.escaped_string(args.data_code),
                c.escaped_string(args.errors_code),
            )
            .gen_code_and_update_ctx("not needed", args.ctx)
        )
        args.code.add_line(
            f"{args.data_code} = {cast_expression}",
            0,
            cast_expression,
        )


class CasterToFinalType(BaseCaster):
    """Caster placeholder to be initialized with the caster to the output
    type"""

    def __init__(self, overrides: CastOverrides):
        self.overrides = overrides

    def to_code(self, args: TypeValueCodeGenArgs):
        raise AssertionError("cannot be used directly")


class TypeCaster(BaseCaster):
    """Main caster which casts to a required type"""

    def __init__(self, type_value: "Type", overrides: CastOverrides):
        self.type_value = self.ensures_type = type_value
        self.overrides = overrides

    def to_code(self, args: TypeValueCodeGenArgs):
        from ..type_handlers import (  # pylint: disable=import-outside-toplevel
            type_value_to_code,
        )

        if self.overrides is None:
            return type_value_to_code(
                args._replace(type_value=self.type_value, cast=True)
            )
        return type_value_to_code(
            args._replace(
                type_value=self.type_value,
                cast=True,
                cast_overrides_stack=(
                    (self.overrides,) + args.cast_overrides_stack
                ),
            )
        )
