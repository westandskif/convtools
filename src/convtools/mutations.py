"""This module brings in-place mutations"""
from .base import BaseMutation


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
        return (f"{code_input}[{name_code}] = {value_code}",)


class SetAttr(BaseNameValueMutation):
    def _gen_code_and_update_ctx(self, code_input, ctx):
        name_code = self.name.gen_code_and_update_ctx(code_input, ctx)
        value_code = self.value.gen_code_and_update_ctx(code_input, ctx)
        return (f"setattr({code_input}, {name_code}, {value_code})",)


class DelItem(BaseIndexMutation):
    def _gen_code_and_update_ctx(self, code_input, ctx):
        index_code = self.index.gen_code_and_update_ctx(code_input, ctx)
        return (f"{code_input}.pop({index_code})",)


class DelAttr(BaseIndexMutation):
    def _gen_code_and_update_ctx(self, code_input, ctx):
        index_code = self.index.gen_code_and_update_ctx(code_input, ctx)
        return (f"delattr({code_input}, {index_code})",)


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
