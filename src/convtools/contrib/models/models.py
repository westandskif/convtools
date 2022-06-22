"""Defines top-level models and methods to initialize them"""
from collections import defaultdict
from functools import lru_cache
from typing import Tuple, Type, TypeVar, Union

from convtools import conversion as c
from convtools.base import BaseConversion
from convtools.utils import Code

from .base import TypeValueCodeGenArgs, ValidationError
from .type_handlers import type_value_to_code


class TypeConversionRunCtx:
    __slots__ = ("version", "visited_model_data")
    counter = 0

    def __init__(self, tracks_visited):
        self.visited_model_data = {} if tracks_visited else None
        self.version = self.counter
        TypeConversionRunCtx.counter += 1


class TypeConversion(BaseConversion):
    """Defines convtools conversion, which generates data validation/casting
    code."""

    self_content_type = (
        BaseConversion.self_content_type
        | BaseConversion.ContentTypes.NAIVE_USAGE
    )

    def __init__(self, type_value):
        super().__init__()
        self.type_value = type_value
        self.tracks_visited = False
        self.requires_versions = False

    def _to_code(self, code_input, ctx):
        code = Code()
        ctx["defaultdict"] = defaultdict
        ctx["TypeConversionRunCtx"] = TypeConversionRunCtx

        # hiding this parameter from gen_converter
        self.ensure_conversion(c.input_arg("run_ctx_"))
        code.add_line("RUN_CTX_ PLACEHOLDER", 0)
        run_ctx_line = len(code.lines_info) - 1

        code.add_line("errors_ = defaultdict(dict)", 0)

        type_value_to_code(
            TypeValueCodeGenArgs(
                code_suffix=self.gen_name("", ctx, self.type_value),
                code=code,
                type_value=self.type_value,
                name_code=repr("root"),
                data_code="data_",
                errors_code="errors_",
                base_conversion=self,
                ctx=ctx,
                level=0,
                type_var_to_type_value={},
                type_to_model_meta={},
            )
        )
        code.lines_info[run_ctx_line] = (
            code.lines_info[run_ctx_line][0],
            f"run_ctx_ = TypeConversionRunCtx({self.tracks_visited})"
            if self.tracks_visited or self.requires_versions
            else "run_ctx_ = None",
        )
        code.add_line("if errors_:", 1)
        code.add_line("return None, errors_", -1)
        code.add_line("return data_, None", 0)
        return code

    def _gen_code_and_update_ctx(self, code_input, ctx):
        function_ctx = self.as_function_ctx(ctx, args_to_skip=("run_ctx_",))
        with function_ctx:
            function_ctx.add_arg("data_", c.this)

            code_suffix = self.gen_name("", ctx, self.type_value)
            converter_name = f"type_conversion{code_suffix}"

            code = Code()
            code.add_line(
                f"def {converter_name}({function_ctx.get_def_all_args_code()}):",
                1,
            )
            code.add_code(self.to_code(code_input, ctx))

            conversion = function_ctx.gen_conversion(
                converter_name, code.to_string(base_indent_level=0)
            )

        return function_ctx.call_with_all_args(
            conversion
        ).gen_code_and_update_ctx(code_input, ctx)


def set_max_cache_size(cache_size):
    """Initialized converter cache of requested size, dropping existing one"""

    @lru_cache(maxsize=cache_size)
    def type_value_to_converter(
        type_value,
    ):  # pylint: disable=redefined-outer-name
        # with c.OptionsCtx() as options:
        #     options.debug = True
        #     return TypeConversion(type_value).gen_converter()
        return TypeConversion(type_value).gen_converter()

    globals()["type_value_to_converter"] = type_value_to_converter
    return type_value_to_converter


type_value_to_converter = set_max_cache_size(128)


T = TypeVar("T")


def build(model: Type[T], data) -> Union[Tuple[T, None], Tuple[None, dict]]:
    return type_value_to_converter(model)(data)


def build_or_raise(model: Type[T], data) -> T:
    obj, errors = type_value_to_converter(model)(data)
    if obj is None:
        raise ValidationError(errors)
    return obj
