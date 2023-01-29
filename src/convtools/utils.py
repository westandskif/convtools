"""Helpers live here: like:
 - recently used cache
 - options ctx manager
"""
import os
import sys
import tempfile
import threading
import typing as t
from collections import deque
from importlib import import_module
from typing import TYPE_CHECKING
from weakref import finalize


if TYPE_CHECKING:
    from typing import Optional

PY_VERSION = sys.version_info[:2]
if PY_VERSION == (3, 6):

    class BaseCtxMeta(t.GenericMeta):  # type: ignore
        def __init__(
            cls, name, bases, kwargs
        ):  # pylint: disable=no-self-argument
            super().__init__(name, bases, kwargs)
            cls._ctx = threading.local()

else:

    class BaseCtxMeta(type):  # type: ignore
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


OT = t.TypeVar("OT", bound=BaseOptions)


class BaseCtx(
    t.Generic[OT], metaclass=BaseCtxMeta
):  # pylint:disable=invalid-metaclass
    """Context manager to manage option objects"""

    options_cls: t.Type[OT]
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
        self.expression_line = None

    def add_line(
        self,
        line: str,
        next_line_indent_incr: int,
        expression_line: "Optional[str]" = None,
    ):
        self.lines_info.append((self.indent_level, line))
        self.indent_level += next_line_indent_incr
        self.expression_line = expression_line
        if self.indent_level < 0:
            raise AssertionError("negative indentation level")

    def as_expression(self) -> "Optional[str]":
        if len(self.lines_info) == 1 and self.expression_line:
            return self.expression_line
        return None

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


class LazyDebugDir:
    """Lazy instance to hold and initialize debug directory for generated code
    sources"""

    def __init__(self):
        self.debug_dir = None
        self.dir_initialized = False

    def get(self):
        if self.debug_dir is None:
            self.debug_dir = os.environ.get(
                "PY_CONVTOOLS_DEBUG_DIR", None
            ) or os.path.join(tempfile.gettempdir(), "py_convtools_debug")
        return self.debug_dir

    def ensure_initialized(self):
        if not self.dir_initialized:
            os.makedirs(self.debug_dir, exist_ok=True)
            self.dir_initialized = True


debug_dir = LazyDebugDir()


class CodePiece:
    __slots__ = ("code_str", "abs_path", "is_dumped")

    def __init__(self, code_str, abs_path, is_dumped):
        self.code_str = code_str
        self.abs_path = abs_path
        self.is_dumped = is_dumped


class CodeStorage:
    """Container which stores a map of converter names to generated code
    pieces. It allows to dump code sources on disk into a debug directory."""

    def __init__(self):
        self.name_to_code_piece = {}
        finalize(self, drop_dumped_code, self.name_to_code_piece)

    def add_sources(self, converter_name, code_str):
        if converter_name in self.name_to_code_piece:
            code_piece = self.name_to_code_piece[converter_name]
            if code_piece.code_str == code_str:
                return code_piece.abs_path, False

            raise Exception(
                "converter with a different code already exists",
                converter_name,
            )

        abs_path = os.path.join(
            debug_dir.get(), f"_{id(self)}_{converter_name}.py"
        )
        self.name_to_code_piece[converter_name] = CodePiece(
            code_str, abs_path, False
        )
        return abs_path, True

    def dump_sources(self):
        debug_dir.ensure_initialized()
        for code_piece in self.name_to_code_piece.values():
            if not code_piece.is_dumped:
                with open(code_piece.abs_path, "w", encoding="utf-8") as f:
                    f.write(code_piece.code_str)
                code_piece.is_dumped = True


def drop_dumped_code(name_to_code_piece):
    for code_piece in name_to_code_piece.values():
        if code_piece.is_dumped:
            try:
                os.remove(code_piece.abs_path)
            except FileNotFoundError:  # pragma: no cover
                pass


def iter_windows(collection, width, step):
    window = deque(maxlen=width)
    window_append = window.append

    index = 0
    for index, obj in enumerate(collection):
        window_append(obj)
        if index % step == 0:
            yield tuple(window)

    if window:
        index += 1
        window.popleft()
        while window:
            if index % step == 0:
                yield tuple(window)
            index += 1
            window.popleft()


obj_getattribute = object.__getattribute__


class LazyModule:
    """Lazy import helper, which caches results of importlib.import_module"""

    __slots__ = ["name", "package", "_module"]

    def __init__(self, name, package=None):
        self.name = name
        self.package = package
        self._module = None

    def __getattribute__(self, name):
        module = obj_getattribute(self, "_module")
        if module is None:
            module = self._module = import_module(
                obj_getattribute(self, "name"),
                obj_getattribute(self, "package"),
            )
        return getattr(module, name)
