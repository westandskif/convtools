"""Code generation helpers.

e.g.
 - recently used cache
 - options ctx manager
"""

import os
import sys
import tempfile
import threading
from ast import AST
from collections import defaultdict, deque
from importlib import import_module
from io import StringIO
from weakref import finalize


PY_VERSION = sys.version_info[:2]
if PY_VERSION == (3, 6):

    from typing import (  # type: ignore
        Any,
        Callable,
        Dict,
        Generator,
        Generic,
        GenericMeta,
        Iterator,
        Optional,
        Tuple,
        Type,
        TypeVar,
        cast,
    )

    class BaseCtxMeta(GenericMeta):
        def __init__(
            cls, name, bases, kwargs
        ):  # pylint: disable=no-self-argument
            super().__init__(name, bases, kwargs)
            cls._ctx = threading.local()

else:
    from typing import (
        Any,
        Callable,
        Dict,
        Generator,
        Generic,
        Iterator,
        Optional,
        Tuple,
        Type,
        TypeVar,
        cast,
    )

    class BaseCtxMeta(type):  # type: ignore
        def __init__(cls, name, bases, kwargs):
            super().__init__(name, bases, kwargs)
            cls._ctx = threading.local()


black: "Optional[Any]" = None
try:
    import black as black_  # pragma: no cover

    black = black_  # pragma: no cover
except ImportError:
    pass


class BaseOptionsMeta(type):
    def __init__(cls, name, bases, kwargs):
        super().__init__(name, bases, kwargs)
        cls._option_attrs = {
            k: v
            for k, v in kwargs.items()
            if not k.startswith("_") and k not in {"clone", "to_defaults"}
        }


class BaseOptions(object, metaclass=BaseOptionsMeta):
    """Container object, which carries current code-gen options."""

    _option_attrs: dict

    def clone(self):
        clone = self.__class__()
        for option_attr in self._option_attrs:
            setattr(clone, option_attr, getattr(self, option_attr))
        return clone

    def to_defaults(self, option_name=None):
        if option_name:
            setattr(self, option_name, self._option_attrs[option_name])
        else:
            for option_attr, value in self._option_attrs.items():
                setattr(self, option_attr, value)


OT = TypeVar("OT", bound=BaseOptions)


class BaseCtx(
    Generic[OT], metaclass=BaseCtxMeta
):  # pylint:disable=invalid-metaclass
    """Context manager to manage option objects."""

    options_cls: Type[OT]
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


def format_code(s):  # pragma: no cover
    if black is None:
        return s
    try:
        s = black.format_str(
            s, mode=black.FileMode(line_length=160)  # type: ignore
        )
    except black.InvalidInput:
        pass
    return s


CODE_FORMATTING_AVAILABLE = black is not None


class Code:
    """Code builder for multi-statement code pieces."""

    __slots__ = ["lines_info", "indent_level"]

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

    def to_string(self, base_indent_level: int, single_indent: str = "    "):
        stream = StringIO()
        write_ = stream.write
        for indent_level, line in self.lines_info:
            required_indent = base_indent_level + indent_level
            _ = 0
            while _ < required_indent:
                write_(single_indent)
                _ += 1
            write_(line)
            write_("\n")
        return stream.getvalue()

    def clone(self):
        copy = Code()
        copy.lines_info = self.lines_info[:]
        copy.indent_level = self.indent_level
        return copy


class CodeParams:
    """Code-gen tree-like helper to generate assignments when needed."""

    def __init__(self):
        self.name_to_uses = defaultdict(int)
        self.name_to_code = {}
        self.name_to_deps = defaultdict(list)
        self.id_to_naive_code = {}
        self.params = []

    def naive_code(self, value, ctx):
        key = id(value)
        if key not in self.id_to_naive_code:
            self.id_to_naive_code[key] = convtools_base.NaiveConversion(
                value
            ).gen_code_and_update_ctx(None, ctx)
        return self.id_to_naive_code[key]

    def create(self, code, name, used_names=()):
        self.name_to_code[name] = code
        for used_name in used_names:
            self.name_to_deps[name].append(used_name)

    def use_param(self, name):
        self.name_to_uses[name] += 1
        self.params.append(name)

        names_to_check_deps = [name]
        visited_deps = set()
        while names_to_check_deps:
            name_ = names_to_check_deps.pop()
            visited_deps.add(name_)
            for dep_ in self.name_to_deps[name_]:
                self.name_to_uses[dep_] += 2
                if dep_ in visited_deps:
                    raise ValueError("cyclic dependency detected", name, dep_)
                names_to_check_deps.insert(0, dep_)

    def create_and_use_param(self, code, name):
        self.create(code, name)
        self.use_param(name)

    def iter_assignments(self):
        for name, code in self.name_to_code.items():
            if self.name_to_uses[name] > 1:
                yield f"{name} = {code}"

    def get_format_args(self):
        return tuple(
            self.name_to_code[name] if self.name_to_uses[name] == 1 else name
            for name in self.params
        )


class LazyDebugDir:
    """Lazy debug directory to store generated code sources."""

    def __init__(self):
        self.debug_dir = None
        self.dir_initialized = False

    def get(self) -> str:
        if self.debug_dir is None:
            self.debug_dir = os.environ.get(
                "PY_CONVTOOLS_DEBUG_DIR", None
            ) or os.path.join(tempfile.gettempdir(), "py_convtools_debug")
        return self.debug_dir

    def ensure_initialized(self):
        if not self.dir_initialized:
            os.makedirs(self.get(), exist_ok=True)
            self.dir_initialized = True


debug_dir = LazyDebugDir()


class CodePiece:
    """Piece of generated code."""

    __slots__ = (
        "converter_name",
        "code_parts",
        "abs_path",
        "is_dumped",
    )

    def __init__(self, converter_name, code_parts, abs_path, is_dumped):
        self.converter_name = converter_name
        self.code_parts = code_parts
        self.abs_path = abs_path
        self.is_dumped = is_dumped


class CodeStorage:
    """Container which stores generated code pieces.

    It allows to dump code sources on disk into a debug directory.
    """

    __slots__ = ["key_to_code_piece", "converter_names", "__weakref__"]

    def __init__(self):
        self.key_to_code_piece: "Dict[str, CodePiece]" = {}
        self.converter_names = set()
        finalize(self, drop_dumped_code, self.key_to_code_piece)

    def add_sources(self, converter_name, code_str):
        def_name = f"def {converter_name}("
        code_parts = (def_name, code_str.replace(def_name, ""))

        code_piece = self.key_to_code_piece.get(code_parts[1])
        if code_piece is not None:
            return code_piece, False

        if converter_name in self.converter_names:
            raise ValueError(
                "converter with a different code already exists",
                converter_name,
            )
        self.converter_names.add(converter_name)

        abs_path = os.path.join(
            debug_dir.get(), f"_{id(self)}_{converter_name}.py"
        )
        code_piece = self.key_to_code_piece[code_parts[1]] = CodePiece(
            converter_name, code_parts, abs_path, False
        )
        return code_piece, True

    def dump_sources(self):
        debug_dir.ensure_initialized()
        for code_piece in self.key_to_code_piece.values():
            if not code_piece.is_dumped:
                with open(code_piece.abs_path, "w", encoding="utf-8") as f:
                    f.write("".join(code_piece.code_parts))
                code_piece.is_dumped = True


def drop_dumped_code(key_to_code_piece):
    for code_piece in key_to_code_piece.values():
        if code_piece.is_dumped:
            try:
                os.remove(code_piece.abs_path)
            except FileNotFoundError:  # pragma: no cover
                pass


T = TypeVar("T")


def iter_windows(
    collection: Iterator[T], width, step
) -> Generator[Tuple[T, ...], None, None]:
    window: "deque[T]" = deque(maxlen=width)
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
    """Lazy import helper."""

    __slots__ = ["name", "package", "_module"]

    def __init__(self, name, package=None):
        """Init self."""
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


class _None:
    """Custom None type.

    For the sake of typing AND ability to tell None from "undefined" optional
    parameters.
    """


_none = _None()


def get_builtins_dict():
    builtins = globals()["__builtins__"]
    if isinstance(builtins, dict):
        return builtins
    # for pypy
    return {
        name: getattr(builtins, name) for name in dir(builtins)
    }  # pragma: no cover


convtools_base = LazyModule("convtools._base")


if PY_VERSION < (3, 9):
    from astunparse import unparse as _ast_unparse  # type: ignore

    backported_ast_unparse = cast(Callable[[AST], str], _ast_unparse)

    def ast_unparse(tree):
        return backported_ast_unparse(tree).strip()

else:
    # pylint: disable-next=unused-import,ungrouped-imports
    from ast import unparse as ast_unparse  # type: ignore  # noqa: F401
