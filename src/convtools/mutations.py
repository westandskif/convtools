"""This module brings in-place mutations"""
from .base import BaseConversion, BaseMutation
from .heuristics import Weights
from .utils import Code


class BaseNameValueMutation(BaseMutation):
    """A base in-place mutation where name and value are needed to define it"""

    def __init__(self, name, value):
        """
        Args:
          name: to be wrapped with :py:obj:`ensure_conversion` and used as
            a key/attr/index for a mutation
          value: to be wrapped with :py:obj:`ensure_conversion` and used as
            a value for a mutation
        """
        super().__init__()
        self.name = self.ensure_conversion(name)
        self.value = self.ensure_conversion(value)


class BaseIndexMutation(BaseMutation):
    def __init__(self, index):
        super().__init__()
        self.index = self.ensure_conversion(index)


class SetItem(BaseNameValueMutation):
    def _gen_code_and_update_ctx(self, code_input, ctx):
        name_code = self.name.gen_code_and_update_ctx(code_input, ctx)
        value_code = self.value.gen_code_and_update_ctx(code_input, ctx)
        return f"{code_input}[{name_code}] = {value_code}"


class SetAttr(BaseNameValueMutation):
    def _gen_code_and_update_ctx(self, code_input, ctx):
        name_code = self.name.gen_code_and_update_ctx(code_input, ctx)
        value_code = self.value.gen_code_and_update_ctx(code_input, ctx)
        return f"setattr({code_input}, {name_code}, {value_code})"


class DelItem(BaseIndexMutation):
    def _gen_code_and_update_ctx(self, code_input, ctx):
        index_code = self.index.gen_code_and_update_ctx(code_input, ctx)
        return f"{code_input}.pop({index_code})"


class DelAttr(BaseIndexMutation):
    def _gen_code_and_update_ctx(self, code_input, ctx):
        index_code = self.index.gen_code_and_update_ctx(code_input, ctx)
        return f"delattr({code_input}, {index_code})"


class Custom(BaseMutation):
    """Mutation to be used in conjunction with `tap` method.
    Runs the code, defined by the conversion argument and returns the input
    as is."""

    def __init__(self, conversion):
        """
        Arg:
          conversion: to be wrapped with :py:obj:`ensure_conversion` and used
            as a mutation code
        """
        super().__init__()
        self.conversion = self.ensure_conversion(conversion)

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return self.conversion.gen_code_and_update_ctx(code_input, ctx)


class Mutations:
    """Mutations to be used in conjunction with the conversion `tap` method."""

    #: Sets a value by key.
    set_item = SetItem
    #: Sets a value of an attribute.
    set_attr = SetAttr
    #: Pops a key from a dict.
    del_item = DelItem
    #: Deletes an attribute from an object.
    del_attr = DelAttr
    #: Runs the code, defined by the conversion argument and returns the input
    #: as is.
    custom = Custom


class TapConversion(BaseConversion):
    """This conversion generates the code which mutates the input data
    in-place.  TapConversion takes any number of mutations"""

    weight = Weights.FUNCTION_CALL

    def __init__(self, obj, *mutations: BaseMutation):
        super().__init__()
        self.obj = self.ensure_conversion(obj)
        self.mutations = [
            self.ensure_conversion(mut, explicitly_allowed_cls=BaseMutation)
            for mut in mutations
        ]
        self.number_of_input_uses = 1

    def _gen_code_and_update_ctx(self, code_input, ctx):
        suffix = self.gen_random_name("", ctx)
        converter_name = f"tap_{suffix}"
        function_ctx = self.as_function_ctx(ctx, optimize_naive=True)
        function_ctx.add_arg("data_", self.obj)
        with function_ctx:
            code = Code()
            code.add_line("def placeholder", 1)
            for mut in self.mutations:
                code.add_line(mut.gen_code_and_update_ctx("data_", ctx), 0)
            code.add_line("return data_", 0)

            code.lines_info[0] = (
                0,
                f"def {converter_name}({function_ctx.get_def_all_args_code()}):",
            )
            conversion = function_ctx.gen_conversion(
                converter_name, code.to_string(base_indent_level=0)
            )
        return function_ctx.call_with_all_args(
            conversion
        ).gen_code_and_update_ctx(code_input, ctx)


class IterMutConversion(TapConversion):
    """This conversion generates the code which iterates and mutates the
    elements in-place. The result is a generator.
    IterMutConversion takes any number of mutations"""

    def _gen_code_and_update_ctx(self, code_input, ctx):
        suffix = self.gen_random_name("", ctx)
        converter_name = f"iter_mut_{suffix}"
        code_item = f"item_{suffix}"
        function_ctx = self.as_function_ctx(ctx, optimize_naive=True)
        function_ctx.add_arg("data_", self.obj)

        with function_ctx:
            code = Code()
            code.add_line("def placeholder", 1)
            code.add_line(f"for {code_item} in data_:", 1)
            for mut in self.mutations:
                code.add_line(
                    mut.gen_code_and_update_ctx(f"{code_item}", ctx), 0
                )

            code.add_line(f"yield {code_item}", 0)

            code.lines_info[0] = (
                0,
                f"def {converter_name}({function_ctx.get_def_all_args_code()}):",
            )
            conversion = function_ctx.gen_conversion(
                converter_name, code.to_string(base_indent_level=0)
            )
        return function_ctx.call_with_all_args(
            conversion
        ).gen_code_and_update_ctx(code_input, ctx)
