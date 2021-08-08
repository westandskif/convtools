"""Helpers live here: like:
 - recently used cache
 - options ctx manager
"""
import sys
import threading
import typing


if sys.version_info[:2] == (3, 6):
    GenericMeta = typing.GenericMeta
else:

    class GenericMeta(type):
        pass


class BaseCtxMeta(GenericMeta):
    def __init__(cls, name, bases, kwargs):
        super().__init__(name, bases, kwargs)
        cls._ctx = threading.local()


class BaseOptionsMeta(type):
    def __init__(cls, name, bases, kwargs):
        super().__init__(name, bases, kwargs)
        cls._option_attrs = {
            k: v
            for k, v in kwargs.items()
            if not k.startswith("_") and k not in {"clone", "to_defaults"}
        }


class BaseOptions(object, metaclass=BaseOptionsMeta):
    """Container object, which carries current options"""

    def clone(self):
        clone = self.__class__()
        for option_attr in self._option_attrs.keys():
            setattr(clone, option_attr, getattr(self, option_attr))
        return clone

    def to_defaults(self, option_name=None):
        if option_name:
            setattr(self, option_name, self._option_attrs[option_name])
        else:
            for option_attr, value in self._option_attrs.items():
                setattr(self, option_attr, value)


OT = typing.TypeVar("OT", bound=BaseOptions)


class BaseCtx(
    typing.Generic[OT], metaclass=BaseCtxMeta
):  # pylint:disable=invalid-metaclass
    """Context manager to manage option objects"""

    options_cls: typing.Type[OT]
    _ctx: threading.local

    def __enter__(self) -> OT:
        self._ctx.prev_options = getattr(self._ctx, "options", None)
        if self._ctx.prev_options:
            self._ctx.options = self._ctx.prev_options.clone()
        else:
            self._ctx.options = self.options_cls()
        return self._ctx.options

    def __exit__(self, exc_type, exc_value, tb):
        self._ctx.options = self._ctx.prev_options
        self._ctx.prev_options = None

    @classmethod
    def get_option_value(cls, option_name):
        options = getattr(cls._ctx, "options", None)
        if not options:
            options = cls.options_cls
        return getattr(options, option_name)


class Code:
    """A building block for generating code, which is composed of multiple
    statements."""

    def __init__(self):
        self.lines_info = []
        self.indent_level = 0

    def add_line(self, line: str, next_line_indent_incr: int):
        self.lines_info.append((self.indent_level, line))
        self.indent_level += next_line_indent_incr
        if self.indent_level < 0:
            raise AssertionError("negative indentation level")

    def add_code(self, code: "Code"):
        for indent_level, line in code.lines_info:
            self.lines_info.append((indent_level + self.indent_level, line))

    def incr_indent_level(self, incr: int):
        self.indent_level += incr

    def has_lines(self):
        return bool(self.lines_info)

    def to_string(self, base_indent_level: int, single_indent: str = "    "):
        return "\n".join(
            f"{single_indent * (base_indent_level + indent_level)}{line}"
            for indent_level, line in self.lines_info
        )
