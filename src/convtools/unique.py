"""Provides conversions for working with unique values"""
from .base import BaseConversion, EscapedString
from .utils import Code


class IterUnique(BaseConversion):
    """
    Defines a conversion which iterates over the input and yields unique ones
    (supports custom uniqueness conditions)
    """

    def __init__(self, self_conv, element, by_):
        super().__init__()
        self.self_conv = self.ensure_conversion(self_conv)
        self.element = self.ensure_conversion(element)
        self.by_ = self.ensure_conversion(by_)

        self.input_arg_container = EscapedString("")
        self.input_arg_container.depends_on(self.element)
        self.input_arg_container.depends_on(self.by_)

    def _gen_code_and_update_ctx(self, code_input, ctx):
        converter_name = self.gen_random_name("iter_unique", ctx)
        function_ctx = self.input_arg_container.as_function_ctx(
            ctx, optimize_naive=True
        )
        function_ctx.add_arg("data_", self.self_conv)

        code = Code()
        code.add_line("def placeholder", 1)

        with function_ctx:
            code.add_line("s_ = set()", 0)
            code.add_line("s_add = s_.add", 0)
            code.add_line("for item_ in data_:", 1)

            item_code = self.element.gen_code_and_update_ctx("item_", ctx)
            by_code = self.by_.gen_code_and_update_ctx("item_", ctx)
            if by_code != "item_":
                code.add_line(f"by_ = {by_code}", 0)
                code.add_line("if by_ not in s_:", 1)
                code.add_line("s_add(by_)", 0)
                if by_code == item_code:
                    code.add_line("yield by_", 0)
                else:
                    code.add_line(f"yield {item_code}", 0)
            else:
                code.add_line("if item_ not in s_:", 1)
                code.add_line("s_add(item_)", 0)
                code.add_line(f"yield {item_code}", 0)

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
