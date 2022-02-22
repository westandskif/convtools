"""
Base and basic conversions are defined here.
"""
import os
import pdb
import re
import string
import sys
import tempfile
import typing as t
from itertools import chain
from random import choice

from .utils import BaseCtx, BaseOptions, Code


try:
    import black
except ImportError:
    pass


class _ConverterCallable:
    """A wrapper which collects all source code, generated every conversion,
    used in the main converter.

    If an exception is raised, it dumps generated code on disk to
    ``PY_CONVTOOLS_DEBUG_DIR`` (*if env variable is defined*) or to
    :py:obj:`tempfile.gettempdir` for beautiful stacktraces and proper
    debugging via pdb & pydevd.  If black is installed, it is applied to the
    code."""

    debug_dir_initialized = False
    debug_dir = os.environ.get("PY_CONVTOOLS_DEBUG_DIR", None) or os.path.join(
        tempfile.gettempdir(), "py_convtools_debug"
    )
    os.makedirs(debug_dir, exist_ok=True)

    def __init__(self, ctx, debug=None):
        self._code_dumped = False
        self._name_to_converter = {}
        self._ctx = ctx
        self._debug = debug

        self._main_converter = None
        self.__name__ = "not_defined_yet"

    def __del__(self):
        if self._code_dumped:
            try:
                for item in self._name_to_converter.values():
                    os.remove(item["abs_path"])
            except FileNotFoundError:  # pragma: no cover
                pass

    def add_sources(self, converter_name, code_str):
        if converter_name in self._name_to_converter:
            if self._name_to_converter[converter_name]["code_str"] == code_str:
                return (
                    self._name_to_converter[converter_name]["abs_path"],
                    False,
                )
            raise Exception(
                "converter with a different code already exists",
                converter_name,
            )

        abs_path = os.path.join(
            self.debug_dir, f"_{id(self)}_{converter_name}.py"
        )
        self._name_to_converter[converter_name] = {
            "code_str": code_str,
            "abs_path": abs_path,
        }
        if self._debug:
            print("\n", code_str)
        return abs_path, True

    def set_main_converter(self, converter):
        self._main_converter = converter
        self.__name__ = getattr(self._main_converter, "__name__", "")
        if self._debug:
            self.dump_code()

    def __get__(self, instance, cls):
        return _ConverterCallableMethod(self, instance, cls)

    def __call__(self, *args, **kwargs):
        try:
            return self._main_converter(*args, **kwargs)
        except (Exception, KeyboardInterrupt):
            self.dump_code()
            raise

    def dump_code(self):
        """Run this method if you are consuming iterator, returned from the
        conversion, and you need proper tracebacks:

            >>> converter = c.iter({...}).gen_converter()
                try:
                    for item in converter(data):
                        ...
                except Exception:
                    converter.dump_code()
                    raise
        """
        if self._code_dumped:
            return
        cls = self.__class__
        if not cls.debug_dir_initialized:
            os.makedirs(cls.debug_dir, exist_ok=True)
            cls.debug_dir_initialized = True
        for item in self._name_to_converter.values():
            with open(item["abs_path"], "w", encoding="utf-8") as f:
                f.write(item["code_str"])

        self._code_dumped = True


class _ConverterCallableMethod:
    __slots__ = ["converter_callable", "instance_or_cls"]

    def __init__(self, converter_callable, instance, cls):
        self.converter_callable = converter_callable
        self.instance_or_cls = instance or cls

    def __call__(self, *args, **kwargs):
        return self.converter_callable(self.instance_or_cls, *args, **kwargs)


class CodeGenerationOptions(BaseOptions):
    converter_callable_cls = _ConverterCallable
    inline_pipes_only = False
    reducers_run_stage = None


class CodeGenerationOptionsCtx(BaseCtx):
    options_cls = CodeGenerationOptions


class ConverterOptions(BaseOptions):
    """Converter options (+ see default values below):

    * ``debug = False`` - same as ``.gen_converter(debug=...)``

    """

    debug = False


class ConverterOptionsCtx(BaseCtx):
    """Thread-safe context to manage options.

    Example:

    .. code-block:: python

       with ConverterOptionsCtx() as options:
           options.debug = True
           # ...

    """

    options_cls = ConverterOptions


CONVERTER_TEMPLATE = """
def {converter_name}({code_signature}):
{code}
"""


GET_OR_DEFAULT_TEMPLATE = """
def {converter_name}({code_args}):
    try:
        return {get_or_default_code}
    except (TypeError, KeyError, IndexError, AttributeError):
        return {default_code}
"""


def ensure_conversion(
    conversion: t.Any, explicitly_allowed_cls=None
) -> "BaseConversion":
    r"""Helps to define conversions based on its type:
        * any conversion is returned untouched
        * list/dict/set/tuple collections are wrapped with ``c.list``,
          ``c.dict``, ``c.set``, ``c.tuple`` (see below).
          If it's not desired, use ``c.naive`` instead
        * slice gets recreated, each ``slice.start, slice.stop, slice.step`` is
          wrapped with ``ensure_conversion``
        * everything else is wrapped with ``c.naive`` (see below)


    Args:
      conversion (object): any object

    Returns:
      BaseConversion: a conversion based on ``conversion`` type:
       * BaseConversion -> :py:class:`BaseConversion`
       * {} -> :py:class:`Dict` (\*conversion.items())
       * [] -> :py:class:`List` (\*conversion)
       * () -> :py:class:`Tuple` (\*conversion)
       * set() -> :py:class:`Set` (\*conversion)
       * slice -> :py:obj:`InlineExpr`
       * object -> :py:class:`NaiveConversion` (conversion)
    """
    if isinstance(conversion, BaseConversion):
        if conversion.used_in_narrow_context and (
            explicitly_allowed_cls is None
            or not isinstance(conversion, explicitly_allowed_cls)
        ):
            raise Exception(
                f"{conversion} cannot be used in this context unless "
                "explicitly allowed"
            )
        return conversion
    if isinstance(conversion, dict):
        return Dict(*conversion.items())
    if isinstance(conversion, list):
        return List(*conversion)
    if isinstance(conversion, tuple):
        return Tuple(*conversion)
    if isinstance(conversion, set):
        return Set(*conversion)
    if isinstance(conversion, slice):
        return InlineExpr("slice({}, {}, {})").pass_args(
            conversion.start, conversion.stop, conversion.step
        )
    return NaiveConversion(conversion)


class ConversionException(Exception):
    pass


CT = t.TypeVar("CT", bound="BaseConversion")


class _None:
    """Custom None type for the sake of typing AND ability to tell None passed
    instead of default value to an optional parameter"""

    pass


class BaseConversion(t.Generic[CT]):
    """This is the base class  of every conversion (so you are not going to use
    this directly).

    A conversion is a definition of some actions to be done to the input passed
    as `data_` argument.

    Conversions are nestable (iteration, calling functions) and chainable
    (method calling or piping).

    Every conversion has many important methods like:
      * `gen_converter`
      * `item`, `attr`, `call`, `call_methods`, `as_type`
      * `and_`, `or_`, `not_`, `is_`, `is not`, `in_`, `not_in`
      * `filter`
      * `pipe`
      * overloaded operators"""

    _none = _None()
    valid_pipe_output = True
    method_calls_replace_input_with_self = False
    used_in_narrow_context = False

    class ContentTypes:
        REDUCER = 1
        AGGREGATION = 2
        NEW_LABEL = 4
        ARG_USAGE = 8
        LABEL_USAGE = 16
        BREAKPOINT = 32
        FUNCTION_OF_INPUT = 64
        NAIVE_USAGE = 128

    self_content_type = ContentTypes.FUNCTION_OF_INPUT

    class OutputHints:
        NOT_NONE = 1

    output_hints = 0

    def __init__(self):
        self._depends_on = {}
        self.contents = self.self_content_type

    def __hash__(self):
        return id(self)

    def add_hint(self, hint: int):
        self.output_hints |= hint
        return self

    def check_dependency(self, b, for_piping=False):
        contents = self.contents if for_piping else self.self_content_type
        if contents & b.contents & self.ContentTypes.REDUCER:
            raise ValueError("nested aggregation", self.__dict__)

    def depends_on(self, *args):
        for arg in args:
            for dep in arg.get_dependencies():
                self._depends_on[dep] = dep
            self.check_dependency(arg)
            self.contents |= arg.contents
        return self

    def get_dependencies(self, types=None):
        deps = self._depends_on.values()
        deps = chain(deps, (self,))
        if types:
            deps = (dep for dep in deps if isinstance(dep, types))
        return deps

    def ensure_conversion(self, conversion, **kwargs) -> "BaseConversion":
        """Runs ensure_conversion on the input object and adds the resulting
        conversion to the list of dependencies"""
        conversion = ensure_conversion(conversion, **kwargs)
        self.depends_on(conversion)
        return conversion

    def clone(self: CT) -> CT:
        clone: CT = self.__class__.__new__(self.__class__)
        clone.__dict__.update(self.__dict__)
        clone._depends_on = dict(  # pylint:disable=protected-access
            self._depends_on.items()
        )
        return clone

    def gen_code_and_update_ctx(self, code_input, ctx) -> str:
        """The main method which generates the code and stores necessary info
        in the context (which will be passed as locals() and globals() on to
        the exec function).  However you should not override this method
        directly, please implement the `_gen_code_and_update_ctx` one.
        """
        return self._gen_code_and_update_ctx(code_input, ctx)

    def _gen_code_and_update_ctx(self, code_input, ctx) -> str:
        raise NotImplementedError

    allowed_symbols = string.ascii_lowercase + string.digits

    PREFIXED_HASH_TO_NAME = "_prefixed_hash_to_name"
    GENERATED_NAMES = "_generated_names"

    def gen_name(self, prefix, ctx, item_to_hash) -> str:
        """Generates name of variable to be used in the generated code. This
        also ensures that same items_to_hash will yield same names."""
        prefixed_hash_to_name = ctx[self.PREFIXED_HASH_TO_NAME]
        generated_names = ctx[self.GENERATED_NAMES]
        try:
            prefixed_hash = (prefix, item_to_hash)
            if prefixed_hash in prefixed_hash_to_name:
                return prefixed_hash_to_name[prefixed_hash]
        except TypeError:
            prefixed_hash = (prefix, id(item_to_hash))
            if prefixed_hash in prefixed_hash_to_name:
                return prefixed_hash_to_name[prefixed_hash]

        name = prefix
        for _ in range(10):
            name += (
                f"_{choice(self.allowed_symbols)}"
                f"{choice(self.allowed_symbols)}"
            )
            if name not in generated_names:
                prefixed_hash_to_name[prefixed_hash] = name
                generated_names.add(name)
                return name
        raise AssertionError("failed to generate unique filename", name)

    _word_pattern_format = r"((?<=\W)|^){}((?=\W)|$)"

    @classmethod
    def count_words(cls, where: str, word: str) -> int:
        return len(
            re.findall(
                cls._word_pattern_format.format(re.escape(word)),
                where,
            )
        )

    @classmethod
    def replace_word(cls, where: str, word: str, with_what: str) -> str:
        return re.sub(
            cls._word_pattern_format.format(re.escape(word)),
            with_what,
            where,
        )

    def get_args_def_info(
        self,
        ctx,
        as_kwargs=False,
        args_to_skip=None,
        for_top_level_converter=False,
    ):
        args_to_skip = args_to_skip or set()
        args = {
            (dep.name, is_lazy): dep
            for dep, is_lazy in (
                (dep, isinstance(dep, LazyEscapedString))
                for dep in self.get_dependencies()
            )
            if isinstance(dep, InputArg)
            and dep.name not in args_to_skip
            or is_lazy
        }
        if for_top_level_converter:
            non_resolved_lazy = [
                dep_name for dep_name, is_lazy in args if is_lazy
            ]
            if non_resolved_lazy:
                raise ValueError(
                    "non-resolved lazy escaped strings", non_resolved_lazy
                )

        if len({dep_name for dep_name, _ in args}) != len(args):
            raise ValueError("duplicate args found", args)

        name_to_code = {}

        positional_args_as_def_names = []
        positional_args_as_conversions = []
        keyword_args_as_def_names = []
        keyword_args_as_conversions = {}

        if "_none" not in args_to_skip:
            positional_args_as_def_names.append("_none")
            positional_args_as_conversions.append(EscapedString("_none"))

        if "_naive" not in args_to_skip and (
            self.contents & self.ContentTypes.NAIVE_USAGE
        ):
            positional_args_as_def_names.append("_naive")
            positional_args_as_conversions.append(EscapedString("_naive"))

        if "_labels" not in args_to_skip and self.contents & (
            self.ContentTypes.LABEL_USAGE | self.ContentTypes.NEW_LABEL
        ):
            positional_args_as_def_names.append("_labels")
            positional_args_as_conversions.append(EscapedString("_labels"))

        suffix = None
        for key, dep in args.items():
            dep_name, is_named_conversion = key
            if is_named_conversion:
                suffix = suffix or self.gen_name("_", ctx, self)
                def_name = f"{dep.name}{suffix}"
                name_to_code[dep.name] = def_name
            else:
                def_name = dep_name

            if as_kwargs:
                keyword_args_as_def_names.append(def_name)
                keyword_args_as_conversions[def_name] = dep
            else:
                positional_args_as_def_names.append(def_name)
                positional_args_as_conversions.append(dep)

        code_args = ", "

        if positional_args_as_def_names:
            code_args = f"{code_args}{', '.join(positional_args_as_def_names)}"

        if keyword_args_as_def_names:
            code_args = (
                f"{code_args} *, {', '.join(keyword_args_as_def_names)}"
            )

        namespace_ctx = NamespaceCtx(name_to_code, ctx)
        positional_args_as_conversions = [
            namespace_ctx.prevent_rendering_while_active(conv)
            for conv in positional_args_as_conversions
        ]
        keyword_args_as_conversions = {
            key: namespace_ctx.prevent_rendering_while_active(conv)
            for key, conv in keyword_args_as_conversions.items()
        }
        return (
            code_args,
            positional_args_as_conversions,
            keyword_args_as_conversions,
            namespace_ctx,
        )

    def _code_to_converter(
        self, converter_name: str, code: str, ctx: dict
    ) -> t.Callable:
        is_debug = ctx.get(
            "__debug", False
        ) or ConverterOptionsCtx.get_option_value("debug")
        if is_debug and "black" in globals():
            try:
                code = black.format_str(
                    code, mode=black.FileMode(line_length=79)  # type: ignore
                )
            except black.InvalidInput:
                pass

        main_converter_callable = ctx["__main_converter_callable"]
        abs_path, added = main_converter_callable.add_sources(
            converter_name, code
        )

        if added:
            code_obj = compile(code, abs_path, "exec", optimize=2)
            exec(code_obj, ctx)  # pylint:disable=exec-used
            ctx[converter_name].conv_name = converter_name
        return ctx[converter_name]

    NAMESPACES = "_name_to_code_input"
    CONVERTERS_CACHE = "_converters_cache"

    @classmethod
    def _init_ctx(cls, debug=None):
        ctx = {
            "sys": sys,
            "__debug": debug,
            "__name__": "_convtools",
            "__naive_values__": {},
            "__none__": cls._none,
            cls.CONVERTERS_CACHE: {},
            cls.GENERATED_NAMES: set(),
            cls.NAMESPACES: [{}],
            cls.PREFIXED_HASH_TO_NAME: {},
        }
        return ctx

    def gen_converter(
        self,
        method=False,
        class_method=False,
        signature=None,
        debug=None,
        converter_name="converter",
    ) -> _ConverterCallable:
        """Compiles a function which act according to the conversion
        definition.

        Args:
          debug (bool): If `True`, prints the generated code (formats with
            black if available). By default: None
          signature (str): Defines the signature of the function to be
            compiled.  `data_` argument is what going to be used as the input.
            e.g. ``signature="self, dt, data_, **kwargs"``
          method (bool): `True` is a shortcut for: ``signature="self, data_"``
          class_method (bool): `True` is a shortcut for:
            ``signature="cls, data_"``
          converter_name (str): prefix of the name of the function to be
            compiled

        Returns:
          The compiled function
        """
        # signature should contain "data_" argument
        initial_code_input = "data_"
        debug = (
            debug
            or (self.contents & self.ContentTypes.BREAKPOINT)
            or ConverterOptionsCtx.get_option_value("debug")
        )
        has_labels = self.contents & self.ContentTypes.NEW_LABEL
        ctx = self._init_ctx(debug=debug)
        ConverterOptionsCtx.get_option_value("debug")

        converter_callable_cls = CodeGenerationOptionsCtx.get_option_value(
            "converter_callable_cls"
        )
        main_converter_callable = converter_callable_cls(debug=debug, ctx=ctx)
        ctx["__main_converter_callable"] = main_converter_callable

        args_to_skip = ("self", "cls", "_none", "_naive", "_labels")
        if signature:
            (code_args, _, _, namespace_ctx,) = self.get_args_def_info(
                ctx, args_to_skip=args_to_skip, for_top_level_converter=True
            )
            signature_words = _pattern_word.findall(signature)
            missing_args = set(_pattern_word.findall(code_args)) - set(
                signature_words
            )
            if missing_args:
                raise ConversionException(
                    "bad signature, missing args", missing_args
                )
        else:
            if method and class_method:
                raise ConversionException(
                    "choose either method or a class_method"
                )
            (code_args, _, _, namespace_ctx,) = self.get_args_def_info(
                ctx,
                as_kwargs=True,
                args_to_skip=args_to_skip,
                for_top_level_converter=True,
            )
            signature = (
                ("self, " if method else "")
                + ("cls, " if class_method else "")
                + (initial_code_input)
                + code_args
            )

        with namespace_ctx:
            code = Code()
            converter_name = self.gen_name(converter_name, ctx, self)
            code.add_line(f"def {converter_name}({signature}):", 1)
            code.add_line("global __naive_values__, __none__", 0)
            code.add_line("_naive = __naive_values__", 0)
            code.add_line("_none = __none__", 0)
            if has_labels:
                code.add_line("_labels = {}", 0)
            else:
                code.add_line("_labels = _none", 0)

            code_str = self.gen_code_and_update_ctx(initial_code_input, ctx)
            code.add_line(f"return {code_str}", 0)

        main_converter = self._code_to_converter(
            converter_name=converter_name,
            code=code.to_string(base_indent_level=0),
            ctx=ctx,
        )
        main_converter_callable.set_main_converter(main_converter)
        del ctx[self.CONVERTERS_CACHE]
        del ctx[self.GENERATED_NAMES]
        del ctx[self.NAMESPACES]
        del ctx[self.PREFIXED_HASH_TO_NAME]
        return main_converter_callable

    def execute(self, *args, debug=None, **kwargs) -> t.Any:
        """Shortcut for generating converter and running it"""
        return self.gen_converter(
            debug=debug or ConverterOptionsCtx.get_option_value("debug")
        )(*args, **kwargs)

    def iter(self, element_conv, *, where=None) -> "BaseConversion":
        """Shortcut for
        ``self.pipe(c.generator_comp(element_conv, where=condition))``

        Args:
          element_conv (object): conversion to be run on each element
          where (object): condition inside the comprehension

        """
        return self.pipe(GeneratorComp(element_conv, where=where))

    def iter_mut(self, *mutations: "BaseMutation") -> "IterMutConversion":
        """Conversion which results in a generator of mutated elements

        Args:
          mutations (BaseMutation): conversion to be run on each element

        """
        return IterMutConversion(self, *mutations)

    def flatten(self) -> "Call":
        """Conversion which calls :py:obj:`itertools.chain.from_iterable` on
        self. Returns iterable"""
        return CallFunc(chain.from_iterable, self)

    def take_while(self, condition) -> "BaseConversion":
        return self.pipe(TakeWhile(condition))

    def drop_while(self, condition) -> "BaseConversion":
        return self.pipe(DropWhile(condition))

    def item(self, *args, **kwargs) -> "GetItem":
        return GetItem(*args, self_conv=self, **kwargs)

    def __getitem__(self, k) -> "GetItem":
        return self.item(k)

    def attr(self, *attrs, **kwargs) -> "GetAttr":
        return GetAttr(*attrs, self_conv=self, **kwargs)

    def is_itself_callable_like(self) -> t.Optional[bool]:
        pass

    def is_itself_callable(self) -> t.Optional[bool]:
        pass

    def is_independent(self) -> t.Optional[bool]:
        return not self.contents & self.ContentTypes.FUNCTION_OF_INPUT

    def call_like(self, *args, **kwargs):
        if self.is_itself_callable_like():
            return self.call(*args, **kwargs)
        raise AssertionError("unexpected callable", self)

    def call(self, *args, **kwargs) -> "Call":
        """Gets compiled into the code which calls the input with params.
        Each ``*args`` and ``**kwargs`` are wrapped with ``ensure_conversion``.
        """
        return Call(*args, self_conv=self, **kwargs)

    def apply(self, args, kwargs):
        """Gets compiled into the code which calls the input with params.
        Both ``args`` and ``kwargs`` are wrapped with ``ensure_conversion``.
        """
        return ApplyFunc(self, args, kwargs)

    def call_method(self, method_name: str, *args, **kwargs) -> "Call":
        """Gets compiled into the code which calls the ``method_name`` method
        of input with params.
        It's a shortcut to ``(...).attr(method_name).call(*args, **kwargs)``
        """
        return self.attr(method_name).call(*args, **kwargs)

    def apply_method(self, method_name: str, args, kwargs) -> "Call":
        """Gets compiled into the code which calls the ``method_name`` method
        of input with params.
        It's a shortcut to ``(...).attr(method_name).apply(args, kwargs)``
        """
        return self.attr(method_name).apply(args, kwargs)

    def as_type(self, callable_) -> "Call":
        return ensure_conversion(callable_).call(self)

    def or_(self, *args, **kwargs) -> "Or":
        return Or(self, *args, **kwargs)

    def __or__(self, b) -> "Or":
        return self.or_(b)

    def and_(self, *args, **kwargs) -> "And":
        return And(self, *args, **kwargs)

    def __and__(self, b) -> "And":
        return self.and_(b)

    def not_(self) -> "InlineExpr":
        return InlineExpr("not {0}").pass_args(self)

    def __invert__(self) -> "InlineExpr":
        return self.not_()

    def is_(self, arg) -> "InlineExpr":
        return InlineExpr("{0} is {1}").pass_args(self, arg)

    def is_not(self, arg) -> "InlineExpr":
        return InlineExpr("{0} is not {1}").pass_args(self, arg)

    def in_(self, arg) -> "InlineExpr":
        return InlineExpr("{0} in {1}").pass_args(self, arg)

    def not_in(self, arg) -> "InlineExpr":
        return InlineExpr("{0} not in {1}").pass_args(self, arg)

    def eq(self, *args, **kwargs) -> "Eq":
        return Eq(self, *args, **kwargs)

    def __eq__(self, b) -> "Eq":  # type: ignore
        return self.eq(b)

    def not_eq(self, arg) -> "InlineExpr":
        return InlineExpr("{0} != {1}").pass_args(self, arg)

    def __ne__(self, b) -> "InlineExpr":  # type: ignore
        return self.not_eq(b)

    def gt(self, arg) -> "InlineExpr":
        return InlineExpr("{0} > {1}").pass_args(self, arg)

    def __gt__(self, b) -> "InlineExpr":
        return self.gt(b)

    def gte(self, arg) -> "InlineExpr":
        return InlineExpr("{0} >= {1}").pass_args(self, arg)

    def __ge__(self, b) -> "InlineExpr":
        return self.gte(b)

    def lt(self, arg) -> "InlineExpr":
        return InlineExpr("{0} < {1}").pass_args(self, arg)

    def __lt__(self, b) -> "InlineExpr":
        return self.lt(b)

    def lte(self, arg) -> "InlineExpr":
        return InlineExpr("{0} <= {1}").pass_args(self, arg)

    def __le__(self, b) -> "InlineExpr":
        return self.lte(b)

    def neg(self) -> "InlineExpr":
        return (
            InlineExpr("-{0}")
            .pass_args(self)
            .add_hint(self.OutputHints.NOT_NONE)
        )

    def __neg__(self) -> "InlineExpr":
        return self.neg()

    def add(self, arg) -> "InlineExpr":
        return (
            InlineExpr("{0} + {1}")
            .pass_args(self, arg)
            .add_hint(self.OutputHints.NOT_NONE)
        )

    def __add__(self, b) -> "InlineExpr":
        return self.add(b)

    def mul(self, arg) -> "InlineExpr":
        return (
            InlineExpr("{0} * {1}")
            .pass_args(self, arg)
            .add_hint(self.OutputHints.NOT_NONE)
        )

    def __mul__(self, b) -> "InlineExpr":
        return self.mul(b)

    def sub(self, arg) -> "InlineExpr":
        return (
            InlineExpr("{0} - {1}")
            .pass_args(self, arg)
            .add_hint(self.OutputHints.NOT_NONE)
        )

    def __sub__(self, b) -> "InlineExpr":
        return self.sub(b)

    def div(self, arg) -> "InlineExpr":
        return (
            InlineExpr("{0} / {1}")
            .pass_args(self, arg)
            .add_hint(self.OutputHints.NOT_NONE)
        )

    def __truediv__(self, b) -> "InlineExpr":
        return self.div(b)

    def mod(self, arg) -> "InlineExpr":
        return (
            InlineExpr("{0} % {1}")
            .pass_args(self, arg)
            .add_hint(self.OutputHints.NOT_NONE)
        )

    def __mod__(self, b) -> "InlineExpr":
        return self.mod(b)

    def floor_div(self, arg) -> "InlineExpr":
        return (
            InlineExpr("{0} // {1}")
            .pass_args(self, arg)
            .add_hint(self.OutputHints.NOT_NONE)
        )

    def __floordiv__(self, b) -> "InlineExpr":
        return self.floor_div(b)

    def len(self) -> "BaseConversion":
        """Shortcut for CallFunc(len, self)"""
        return CallFunc(len, self)

    def filter(self, condition_conv, cast=_none) -> "BaseConversion":
        """Shortcut for calling :py:obj:`convtools.base.FilterConversion` on
        self"""
        return self.pipe(FilterConversion(condition_conv, cast=cast))

    def sort(self, key=None, reverse=False) -> "BaseConversion":
        """Shortcut for calling :py:obj:`convtools.base.SortConversion` on
        self"""
        return self.pipe(SortConversion(key=key, reverse=reverse))

    def add_label(
        self,
        label_name: t.Union[str, dict],
        conversion: t.Optional[t.Any] = None,
    ) -> "BaseConversion":
        """Labels data so it can be reused further:

        Basic:
        >>> c.item("objects", 0).add_label("first")

        Advanced:
        >>> c.item("objects").add_label({
        >>>     "first": c.item(0),
        >>>     "count": c.call_func(len, c.this),
        >>> }).iter_mut(
        >>>     c.Mut.set_attr("_first", c.label("first")),
        >>>     c.Mut.set_attr("_count", c.label("count")),
        >>> )

        Rare:
        >>> c.iter(
        >>>     c.item(0)
        >>> ).add_label(
        >>>     "before_5",
        >>>     c.take_while(c.this < 5).as_type(list)
        >>> ).iter(
        >>>     c.this + c.label("before_5").item(-1)
        >>> )

        Args:
          label_name: a name of the label to be applied or a dict with labels
            to conversions
          conversion: a conversion to be applied before labeling
        Returns:
          LabelConversion: the labeled conversion
        """
        return self.pipe(
            GetItem() if conversion is None else conversion,
            label_input=label_name,
        )

    def tap(self, *mutations: "BaseMutation") -> "TapConversion":
        """Allows to tap into the processing of a conversion and mutate it
        in place. Accepts multiple mutations, order matters.

        Args:
          mutations (iterable of BaseMutation): mutations to process the
            conversion
        """
        return TapConversion(self, *mutations)

    def pipe(
        self,
        next_conversion,
        *args,
        label_input=None,
        label_output=None,
        **kwargs,
    ) -> "BaseConversion":
        """Shortcut for :py:obj:`PipeConversion`"""
        return PipeConversion(
            self,
            next_conversion,
            *args,
            label_input=label_input,
            label_output=label_output,
            **kwargs,
        )

    def breakpoint(self):
        """Shortcut to Breakpoint(self)"""
        return Breakpoint(self)

    def and_then(self, conversion, condition=bool):
        """Applies conversion if condition is true, otherwise leaves untouched.
        Condition is :py:obj:`bool` by default"""
        return self.pipe(
            If(This() if condition is bool else condition, conversion)
        )


class BaseMutation(BaseConversion):
    used_in_narrow_context = True


class BaseMethodConversion(BaseConversion):
    """This conversion is required to take into account method calls.  We need
    to preserve the instance we are calling a method on.

    e.g. like obj['key'] OR obj.func() OR obj.attr1"""

    def __init__(self, self_conv):
        super().__init__()
        if self_conv is self._none:
            self.self_conv = None
        else:
            self.self_conv = self.ensure_conversion(self_conv)

    def get_self_and_input_code(
        self, code_input: str, ctx: dict
    ) -> t.Tuple[str, str]:
        if self.self_conv is None:
            return (code_input, code_input)
        self_code = self.self_conv.gen_code_and_update_ctx(code_input, ctx)
        if self.self_conv.method_calls_replace_input_with_self:
            code_input = self_code
        return (self_code, code_input)


_pattern_illegal_chars = re.compile("[^0-9a-zA-Z_]")
_pattern_illegal_leading_chars = re.compile("^[^a-zA-Z_]+")
_pattern_word = re.compile(r"(\w+)")


def var_name_from_string(s):
    # Remove invalid characters
    s = _pattern_illegal_chars.sub("", s)
    # Remove leading characters until we find a letter or underscore
    s = _pattern_illegal_leading_chars.sub("", s)
    return s


class NaiveConversion(BaseConversion):
    """Naive conversion gets compiled into the code, which just returns the
    `value` it's been initialized with.  Allows to make any object available
    inside other conversions.
    """

    _builtin_dict = globals()["__builtins__"]
    self_content_type = (
        BaseConversion.self_content_type
        ^ BaseConversion.ContentTypes.FUNCTION_OF_INPUT
    ) | BaseConversion.ContentTypes.NAIVE_USAGE

    types_to_repr = {type(None), bool, int}

    def __init__(self, value: t.Any, name_prefix="v"):
        """
        Args:
          value (object): any object

        """
        super().__init__()
        self.value = value
        self.name_prefix = name_prefix
        self.code_str = None
        self.value_name = None

        value_name = getattr(value, "__name__", "")
        if (
            value_name in self._builtin_dict
            and self.value is self._builtin_dict[value_name]
        ):
            self.code_str = value_name

        elif callable(value):
            f_name = var_name_from_string(value_name)
            if f_name:
                self.name_prefix = f_name
        else:
            value_type = type(value)
            if (
                value_type in self.types_to_repr
                or value_type is str
                and len(value) < 128
                and "%" not in value
                and "{" not in value
            ):
                self.code_str = repr(value)

        if self.code_str:
            self.contents = self.contents ^ self.ContentTypes.NAIVE_USAGE

    def _gen_code_and_update_ctx(self, code_input, ctx):
        if self.code_str:
            return self.code_str

        value_name = self.value_name or self.gen_name(
            self.name_prefix, ctx, self.value
        )
        ctx["__naive_values__"][value_name] = self.value
        return f'_naive["{value_name}"]'

    def is_itself_callable_like(self) -> t.Optional[bool]:
        return callable(self.value)

    def is_itself_callable(self) -> t.Optional[bool]:
        return callable(self.value)


class EscapedString(BaseConversion):
    """Defines the conversion which returns the result of running the
    python code, passed to init"""

    self_content_type = (
        BaseConversion.self_content_type
        ^ BaseConversion.ContentTypes.FUNCTION_OF_INPUT
    )

    def __init__(self, s):
        super().__init__()
        self.s = s

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return self.s


class This(BaseConversion):
    """Defines the conversion which just returns the input.

    Also, provided that you use this inside comprehension conversions,
    it references an item from an iterator."""

    def __call__(self) -> "This":
        """To allow using it as singleton"""
        return self

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return code_input


class InputArg(BaseConversion):
    """Allows to use arguments passed into the compiled converter.

    Unless the `signature` argument is passed to `gen_converter` function, all
    input arguments used in the conversion definition will be expected as
    keyword-only arguments (affecting the resulting converter signature)."""

    self_content_type = (
        BaseConversion.self_content_type
        | BaseConversion.ContentTypes.ARG_USAGE
    ) ^ BaseConversion.ContentTypes.FUNCTION_OF_INPUT

    def __init__(self, name: str):
        """
        Args:
          name (string): argument name of the converter to be used
        """
        super().__init__()
        self.name = name

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return self.name


class LabelConversion(BaseConversion):
    """Allows to reference a conversion result by label, after it was cached by
    :py:obj:`PipeConversion` or :py:obj:`BaseConversion.add_label`."""

    self_content_type = (
        BaseConversion.self_content_type
        | BaseConversion.ContentTypes.LABEL_USAGE
    ) ^ BaseConversion.ContentTypes.FUNCTION_OF_INPUT

    def __init__(self, label_name: str):
        """
        Args:
          label_name (string): label name to be referenced
        """
        super().__init__()
        if not isinstance(label_name, str):
            raise ValueError("invalid label_name type")
        self.label_name = label_name

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return f"_labels[{repr(self.label_name)}]"


class Namespace(BaseConversion):
    """Wrapping conversion which isolates :py:obj:`LazyEscapedString` (parent
    conversions won't detect them as dependencies) and defines code inputs for
    them"""

    self_content_type = (
        BaseConversion.self_content_type
        ^ BaseConversion.ContentTypes.FUNCTION_OF_INPUT
    )

    def __init__(
        self,
        conversion: "t.Any",
        name_to_code: "t.Dict[str, t.Optional[t.Union[bool, str]]]",
    ):
        super().__init__()
        self.conversion = self.ensure_conversion(conversion)
        self.name_to_code = name_to_code

    def _gen_code_and_update_ctx(self, code_input, ctx):
        with NamespaceCtx(self.name_to_code, ctx):
            return self.conversion.gen_code_and_update_ctx(code_input, ctx)

    def get_dependencies(self, types=None):
        name_to_code = self.name_to_code
        return (
            dep
            for dep in super().get_dependencies(types=types)
            if not isinstance(dep, LazyEscapedString)
            or dep.name not in name_to_code
        )


class NamespaceCtx:
    """Context manager which defines code inputs for
    :py:obj:`LazyEscapedString`"""

    _name_to_code = None
    ctx = None
    active = False

    NAMESPACES = BaseConversion.NAMESPACES

    def __init__(
        self,
        name_to_code: "t.Dict[str, t.Optional[t.Union[bool, str]]]",
        ctx,
    ):
        if name_to_code:
            self._name_to_code = name_to_code
            self._ctx = ctx

    def __enter__(self):
        if self._name_to_code:
            new_value: "t.Dict[str, str]" = {}
            new_value.update(self.name_to_code(self._ctx))
            new_value.update(self._name_to_code)
            self._ctx[self.NAMESPACES].append(new_value)
        self.active = True
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        if self._name_to_code:
            self._ctx[self.NAMESPACES].pop()
        self.active = False

    @classmethod
    def name_to_code(cls, ctx) -> "t.Dict[str, str]":
        return ctx[cls.NAMESPACES][-1]

    def prevent_rendering_while_active(self, conversion):
        return NamespaceControlledUnit(self, conversion)


class NamespaceControlledUnit(BaseConversion):
    """Wrapping conversion which prevents the inner one from being rendered
    while it is inside the parent NamespaceCtx"""

    __slots__ = ["conversion", "namespace_ctx"]

    def __init__(self, namespace_ctx: "NamespaceCtx", conversion):
        super().__init__()
        self.namespace_ctx = namespace_ctx
        self.conversion = self.ensure_conversion(conversion)

    def _gen_code_and_update_ctx(self, code_input, ctx):
        if self.namespace_ctx.active:
            raise Exception(
                "rendering prevented by parent NamespaceCtx, "
                "move rendering out"
            )
        return self.conversion.gen_code_and_update_ctx(code_input, ctx)


class LazyEscapedString(BaseConversion):
    """A lazy named conversion which allows to build a conversion on the
    outside to then generate some code around it (properly passing required
    args, etc.)"""

    self_content_type = (
        BaseConversion.self_content_type
        ^ BaseConversion.ContentTypes.FUNCTION_OF_INPUT
    )

    def __init__(self, name):
        super().__init__()
        self.name = name

    def _gen_code_and_update_ctx(self, code_input, ctx):
        code = NamespaceCtx.name_to_code(ctx)[self.name]
        if code is True:
            return code_input
        if code:
            return code

        raise ValueError("LazyEscapedString is left uninitialized", self.name)


class Or(BaseConversion):
    """Takes any number of objects, each is to be wrapped with
    :py:obj:`ensure_conversion` and generates the code
    joining every argument with python ``or`` expression

    ``default`` defines behavior when args is empty
      * if None is empty will raise ValueError
      * false values - results in False
      * true values - results in True

    """

    op = " or "

    def __init__(self, *args, default=None):
        """
        Args:
            args: conditions
            default: defines behavior when args is empty
              - if None, empty args will raise ValueError
              - false values - results in False
              - true values - results in True
        """
        super().__init__()

        if not args and default is None:
            raise ValueError("neither args nor default is provided")

        self.args = [self.ensure_conversion(arg) for arg in args]
        self.default = default

    def _gen_code_and_update_ctx(self, code_input, ctx):
        if not self.args:
            return repr(bool(self.default))

        code = self.op.join(
            [arg.gen_code_and_update_ctx(code_input, ctx) for arg in self.args]
        )
        return f"({code})"


class And(Or):
    """Takes any number of objects, each is to be wrapped with
    :py:obj:`ensure_conversion` and generates the code
    joining every argument with python ``and`` expression.

    ``default`` defines behavior when args is empty
      * if None is empty will raise ValueError
      * false values - results in False
      * true values - results in True

    """

    op = " and "


class Eq(Or):
    """Takes any number of objects, each is to be wrapped with
    :py:obj:`ensure_conversion` and generates the code
    joining every argument with python `` == `` operator

    ``default`` defines behavior when args is empty
      * if None is empty will raise ValueError
      * false values - results in False
      * true values - results in True

    """

    op = " == "


class If(BaseConversion):
    """Generates the if expression code.

    Checks the code of the input, if it
    doesn't seem to be complex, then just proceeds with it as is.
    If it's not simple (some index/attribute lookups or function calls are
    in there), then it caches the input for further reuse in if_true and
    if_false clauses."""

    def __init__(
        self,
        condition=True,
        if_true=BaseConversion._none,
        if_false=BaseConversion._none,
        no_input_caching=False,
    ):
        """
        Args:
          condition (object): condition for the IF expression. If it is left as
            True, then the input is used as the condition.
          if_true (object): the result if the condition is true
          if_false (object): the result if the condition is false
          no_input_caching (bool): if True, disables automatic decision making
            on whether result caching is needed
        """
        super().__init__()
        self.if_conv = (
            GetItem()
            if condition is True
            else self.ensure_conversion(condition)
        )
        self.if_true = (
            GetItem()
            if if_true is self._none
            else self.ensure_conversion(if_true)
        )
        self.if_false = (
            GetItem()
            if if_false is self._none
            else self.ensure_conversion(if_false)
        )
        self.no_input_caching = no_input_caching

        if self.no_input_caching:
            self.conversion = InlineExpr(
                "({if_true} if {if_cond} else {if_false})"
            ).pass_args(
                if_cond=self.if_conv,
                if_true=self.if_true,
                if_false=self.if_false,
            )
        else:
            self.conversion = PipeConversion(
                GetItem(),
                InlineExpr(
                    "({if_true} if {if_cond} else {if_false})"
                ).pass_args(
                    if_cond=self.if_conv,
                    if_true=self.if_true,
                    if_false=self.if_false,
                ),
            )

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return self.conversion.gen_code_and_update_ctx(code_input, ctx)


class Not(BaseConversion):
    def __init__(self, arg):
        super().__init__()
        self.arg = self.ensure_conversion(arg)

    def _gen_code_and_update_ctx(self, code_input, ctx):
        code = self.arg.gen_code_and_update_ctx(code_input, ctx)
        return f"(not {code})"


class GetItem(BaseMethodConversion):
    """``GetItem`` gets compiled into the code which does
    dictionary/index lookups.

    If called without params, just returns the input.

    If an index is a conversion itself, then it is being calculated
    against an input."""

    prefix = "item_or_default"

    def __init__(
        self,
        *indexes,
        default=BaseConversion._none,
        self_conv=BaseConversion._none,
    ):
        """
        Args:
          indexes (:obj:`list` of :obj:`object`): to do lookups with
          default (:obj:`object`, optional): to be returned on fail,
           like ``{}.get`` method, but now applicable to arrays too
        """
        super().__init__(self_conv)
        self.indexes = [self.ensure_conversion(index) for index in indexes]
        self.default = (
            self.ensure_conversion(default)
            if default is not self._none
            else None
        )

    def wrap_path_item(self, code_input, path_item):
        return f"{code_input}[{path_item}]"

    def _gen_code_and_update_ctx(self, code_input, ctx):
        code_self, code_input = self.get_self_and_input_code(code_input, ctx)
        if self.default is None:
            code_output = code_self
            for index in self.indexes:
                code_index = index.gen_code_and_update_ctx(code_input, ctx)
                code_output = self.wrap_path_item(code_output, code_index)
            return code_output

        (
            code_args,
            positional_args_as_conversions,
            keyword_args_as_conversions,
            namespace_ctx,
        ) = self.get_args_def_info(ctx)

        with namespace_ctx:
            function_of_input_type = self.ContentTypes.FUNCTION_OF_INPUT
            caching_is_impossible = (
                not isinstance(self.default, NaiveConversion)
                or any(
                    index.contents & function_of_input_type
                    for index in self.indexes
                )
                and not PipeConversion.input_is_simple(code_input)
            )

            args_as_def_names = ["data_"]
            args_as_conversions = [This()]
            code_output = "data_"

            if code_self != code_input:
                args_as_def_names.append("self_")
                args_as_conversions.append(EscapedString(code_self))
                code_output = "self_"

            if caching_is_impossible:
                default_code = self.default.gen_code_and_update_ctx(
                    "data_", ctx
                )
            else:
                args_as_def_names.append("default_")
                args_as_conversions.append(self.default)
                default_code = "default_"

            if caching_is_impossible:
                for index in self.indexes:
                    code_index = index.gen_code_and_update_ctx("data_", ctx)
                    code_output = self.wrap_path_item(code_output, code_index)

                positional_args_as_conversions = chain(
                    args_as_conversions, positional_args_as_conversions
                )
                code_args = f"{', '.join(args_as_def_names)}{code_args}"

                converter_name = self.gen_name(self.prefix, ctx, (self, -1))
                converter_code = GET_OR_DEFAULT_TEMPLATE.format(
                    code_args=code_args,
                    converter_name=converter_name,
                    get_or_default_code=code_output,
                    default_code=default_code,
                )
                self._code_to_converter(
                    converter_name=converter_name,
                    code=converter_code,
                    ctx=ctx,
                )
                resulting_conversion = EscapedString(converter_name).call(
                    *positional_args_as_conversions,
                    **keyword_args_as_conversions,
                )
            else:

                key = (self.prefix, code_args, len(self.indexes))

                if key not in ctx[self.CONVERTERS_CACHE]:
                    for i, index in enumerate(self.indexes):
                        var_index = f"index_{i}"
                        args_as_def_names.append(var_index)
                        code_output = self.wrap_path_item(
                            code_output, var_index
                        )

                    code_args = f"{', '.join(args_as_def_names)}{code_args}"

                    converter_name = self.gen_name(
                        self.prefix, ctx, (self, len(self.indexes))
                    )
                    converter_code = GET_OR_DEFAULT_TEMPLATE.format(
                        code_args=code_args,
                        converter_name=converter_name,
                        get_or_default_code=code_output,
                        default_code=default_code,
                    )
                    self._code_to_converter(
                        converter_name=converter_name,
                        code=converter_code,
                        ctx=ctx,
                    )
                    ctx[self.CONVERTERS_CACHE][key] = converter_name

                else:
                    converter_name = ctx[self.CONVERTERS_CACHE][key]

                resulting_conversion = EscapedString(converter_name).call(
                    *args_as_conversions,
                    *self.indexes,
                    *positional_args_as_conversions,
                    **keyword_args_as_conversions,
                )
        return resulting_conversion.gen_code_and_update_ctx(code_input, ctx)


class GetAttr(GetItem):
    """``GetAttr`` gets compiled into the code which runs getattr.
    If called without params, just returns the input.

    If an index is a conversion itself, then it is being calculated
    against an input."""

    valid_attr = re.compile(r"^'[A-Za-z_][a-zA-Z0-9_]*'$")
    prefix = "attr_or_default"

    def wrap_path_item(self, code_input, path_item):
        if self.valid_attr.match(path_item):
            return f"{code_input}.{path_item[1:-1]}"
        return f"getattr({code_input}, {path_item})"


class Call(BaseMethodConversion):
    """This conversion writes the code which takes the input code and calls it
    as a function.
    It takes both positional and keyword arguments to be passed.
    """

    self_content_type = (
        BaseConversion.self_content_type
        ^ BaseConversion.ContentTypes.FUNCTION_OF_INPUT
    )

    def __init__(self, *args, self_conv=BaseConversion._none, **kwargs):
        super().__init__(self_conv)
        self.args = [self.ensure_conversion(arg) for arg in args]
        self.kwargs = (
            {k: self.ensure_conversion(v) for k, v in kwargs.items()}
            if kwargs
            else {}
        )

    def _gen_code_and_update_ctx(self, code_input, ctx):
        code_self, code_input = self.get_self_and_input_code(code_input, ctx)

        params = chain(
            (
                param.gen_code_and_update_ctx(code_input, ctx)
                for param in self.args
            ),
            (
                f"{k}={v.gen_code_and_update_ctx(code_input, ctx)}"
                for k, v in self.kwargs.items()
            ),
        )
        return f"{code_self}({','.join(params)})"


def CallFunc(func, *args, **kwargs) -> "Call":  # pylint:disable=invalid-name
    """Shortcut to ``NaiveConversion(func).call(*args, **kwargs)``"""
    assert callable(func)
    return NaiveConversion(func).call(*args, **kwargs)


def ApplyFunc(  # pylint:disable=invalid-name
    func, args, kwargs
) -> "InlineExpr":
    """Shortcut to ``NaiveConversion(func).apply(args, kwargs)``"""
    if args:
        if kwargs:
            return InlineExpr("{}(*{}, **{})").pass_args(func, args, kwargs)
        return InlineExpr("{}(*{})").pass_args(func, args)

    if kwargs:
        return InlineExpr("{}(**{})").pass_args(func, kwargs)

    return InlineExpr("{}()").pass_args(func)


class FilterConversion(BaseConversion):
    """Generates the code to iterate the input, taking items for which the
    provided conversion resolves to a truth value."""

    def __init__(self, condition_conv, cast=BaseConversion._none):
        """
        Args:
          condition_conv (object): to be wrapped with
            :py:obj:`ensure_conversion` and used on each item of a collection
            to filter it
          cast (callable): to wrap the generator of filtered items
        Returns:
          BaseConversion: the generator of filtered items, wrapped with `cast`
          if provided
        """
        super().__init__()
        if cast is None or cast is self._none:
            result = GeneratorComp(GetItem(), where=condition_conv)
        elif cast is list:
            result = ListComp(GetItem(), where=condition_conv)
        elif cast is tuple:
            result = TupleComp(GetItem(), where=condition_conv)
        elif cast is set:
            result = SetComp(GetItem(), where=condition_conv)
        elif callable(cast):
            gen = GeneratorComp(GetItem(), where=condition_conv)
            result = NaiveConversion(cast).call(gen)
        else:
            raise AssertionError(f"cannot cast generator to cast={cast}")
        self.conversion = self.ensure_conversion(result)

    def as_type(self, callable_):
        return self.conversion.as_type(callable_)

    def filter(self, condition_conv, cast=BaseConversion._none):
        return self.conversion.filter(condition_conv, cast=cast)

    def sort(self, key=None, reverse=False):
        return self.conversion.sort(key, reverse)

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return self.conversion.gen_code_and_update_ctx(code_input, ctx)


class SortConversion(BaseConversion):
    """Generates the code to sort the input."""

    def __init__(self, key=None, reverse=False):
        """
        Args:
          key (callable): to be passed to :py:obj:`sorted`
          reverse (bool): to be passed to :py:obj:`sorted`
        """
        super().__init__()
        self.sorted_kwargs = {}
        if key is not None:
            self.sorted_kwargs["key"] = self.ensure_conversion(key)
        if reverse:
            self.sorted_kwargs["reverse"] = self.ensure_conversion(reverse)

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return (
            EscapedString("sorted")
            .call(EscapedString(code_input), **self.sorted_kwargs)
            .gen_code_and_update_ctx("NOT_NEEDED_OR_BUG", ctx)
        )


class InlineExpr(BaseConversion):
    """This conversion allows to avoid function call overhead.  It inlines a
    raw python code expression into the code of resulting conversion."""

    self_content_type = (
        BaseConversion.self_content_type
        ^ BaseConversion.ContentTypes.FUNCTION_OF_INPUT
    )

    def __init__(self, code_str):
        """
        Args:
          code_str (str): python code string. Supports `{}` expressions of
            :py:obj:`str.format`, both positional and names ones.
            To pass arguments, use :py:obj:`InlineExpr.pass_args`
        """
        super().__init__()
        self.code_str = code_str
        self.args = []
        self.kwargs = {}

    def pass_args(self, *args, **kwargs):
        """The method passes arguments to the code to be inlined.

        Args:
          args (tuple of objects): each is wrapped with
            :py:obj:`ensure_conversion`
          kwargs (dict of objects): each value is wrapped
            with :py:obj:`ensure_conversion`
        Returns:
          InlineExpr: Clone of the conversion after arguments are passed.
        """
        self_clone = self.clone()
        self_clone.args = [self_clone.ensure_conversion(arg) for arg in args]
        self_clone.kwargs = {
            k: self_clone.ensure_conversion(v) for k, v in kwargs.items()
        }
        return self_clone

    def _gen_code_and_update_ctx(self, code_input, ctx):
        code = self.code_str.format(
            *(
                arg.gen_code_and_update_ctx(code_input, ctx)
                for arg in self.args
            ),
            **{
                k: v.gen_code_and_update_ctx(code_input, ctx)
                for k, v in self.kwargs.items()
            },
        )
        return f"({code})"

    def is_itself_callable_like(self) -> t.Optional[bool]:
        return True

    def call_like(self, *args, **kwargs):
        return self.pass_args(*args, **kwargs)


class BaseComprehensionConversion(BaseConversion):
    """This is the base conversion to generate a code, which creates a
    collection like: list/dict/etc."""

    sorting_requested = None

    def __init__(self, item, *, where=None):
        """
        Args:
          item (object): to be wrapped with :py:obj:`ensure_conversion`
            and used as a conversion on each item of a collection.
          where: conversion to be used in ``if`` clause of a comprehension

            e.g. for ``[i * 2 for i in l if i > 0]`` an item would be
            ``c.generator_comp(c.this * 2, where=c.this > 0)``
        """
        super().__init__()
        self.item = self.ensure_conversion(item)
        self.where = None if where is None else self.ensure_conversion(where)

    def gen_item_code(self, code_input, ctx):
        return self.item.gen_code_and_update_ctx(code_input, ctx)

    def gen_generator_code(self, code_input, ctx):
        suffix = self.gen_name("", ctx, self)
        param_code = f"i_{suffix}"
        for_params_code = param_code

        item_code = self.gen_item_code(param_code, ctx)
        gen_code = f"{item_code} for {for_params_code} in {code_input}"

        if self.where is not None:
            condition_code = self.where.gen_code_and_update_ctx(
                param_code, ctx
            )
            if condition_code == "True":
                pass
            elif condition_code == "False":
                gen_code = ""
            else:
                gen_code = f"{gen_code} if {condition_code}"

        return gen_code


class GeneratorComp(BaseComprehensionConversion):
    """Generates python generator comprehension code."""

    def as_type(self, callable_):
        if callable_ in (list, set, tuple):
            kwargs = dict(item=self.item, where=self.where)
            if callable_ is list:
                comp = ListComp(**kwargs)
            elif callable_ is tuple:
                comp = TupleComp(**kwargs)
            else:
                comp = SetComp(**kwargs)
            return comp
        return super().as_type(callable_)

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return f"({self.gen_generator_code(code_input, ctx)})"


class SetComp(BaseComprehensionConversion):
    """Generates python set comprehension code (obviously non-sortable)"""

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return f"{{{self.gen_generator_code(code_input, ctx)}}}"

    def filter(self, condition_conv, cast=BaseConversion._none):
        if cast is self._none:
            cast = set

        return super().filter(condition_conv, cast=cast)


class ListComp(BaseComprehensionConversion):
    """Generates python list comprehension code."""

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return f"[{self.gen_generator_code(code_input, ctx)}]"

    def filter(self, condition_conv, cast=BaseConversion._none):
        if cast is self._none:
            return GeneratorComp(self.item, where=self.where).filter(
                condition_conv, cast=list
            )
        return super().filter(condition_conv, cast=cast)

    def sort(self, key=None, reverse=False) -> "BaseConversion":
        return GeneratorComp(self.item, where=self.where).sort(key, reverse)


class TupleComp(BaseComprehensionConversion):
    """Generates python tuple comprehension code."""

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return f"tuple({self.gen_generator_code(code_input, ctx)})"

    def filter(self, condition_conv, cast=BaseConversion._none):
        if cast is self._none:
            return GeneratorComp(self.item, where=self.where).filter(
                condition_conv, cast=tuple
            )
        return super().filter(condition_conv, cast=cast)

    def sort(self, key=None, reverse=False) -> "BaseConversion":
        return (
            GeneratorComp(self.item, where=self.where)
            .sort(key, reverse)
            .as_type(tuple)
        )


class DictComp(BaseComprehensionConversion):
    """Generates python dict comprehension code."""

    def __init__(self, key, value, *, where=None):
        """
        Args:
          key (object): to be wrapped with :py:obj:`ensure_conversion` and
            used on each item of a collection to form keys
          value (object): to be wrapped with :py:obj:`ensure_conversion` and
            used on each item of a collection to form values
        """
        super().__init__(item=None, where=where)
        self.key = self.ensure_conversion(key)
        self.value = self.ensure_conversion(value)

    def gen_item_code(self, code_input, ctx):
        key_code = self.key.gen_code_and_update_ctx(code_input, ctx)
        value_code = self.value.gen_code_and_update_ctx(code_input, ctx)
        return f"{key_code}: {value_code}"

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return f"{{{self.gen_generator_code(code_input, ctx)}}}"

    def filter(self, condition_conv, cast=BaseConversion._none):
        if cast is self._none:
            cast = dict
        return GeneratorComp((self.key, self.value), where=self.where).filter(
            condition_conv, cast=dict
        )

    def sort(self, key=None, reverse=False) -> "BaseConversion":
        return (
            GeneratorComp(
                (self.key, self.value),
                where=self.where,
            )
            .sort(key, reverse)
            .as_type(dict)
        )


class BaseCollectionConversion(BaseConversion):
    """This is a base conversion of every collection"""

    self_content_type = (
        BaseConversion.self_content_type
        ^ BaseConversion.ContentTypes.FUNCTION_OF_INPUT
    )

    def __init__(self, *items):
        """
        Args:
          items (objects): items to form a collection from.
            every item gets wrapped with :py:obj:`ensure_conversion`
        """
        super().__init__()
        resulting_items = []
        condition_to_item_pairs = None
        for item in items:
            item = self.ensure_conversion(item)
            if condition_to_item_pairs is None:
                if isinstance(item, OptionalCollectionItem):
                    condition_to_item_pairs = [
                        (None, item_) for item_ in resulting_items
                    ]
                    condition_to_item_pairs.append(
                        (item.condition, item.conversion)
                    )
                    resulting_items = None
                else:
                    resulting_items.append(item)
            else:
                condition_to_item_pairs.append(
                    (item.condition, item.conversion)
                    if isinstance(item, OptionalCollectionItem)
                    else (None, item)
                )
        self.items = resulting_items
        self.condition_to_item_pairs = condition_to_item_pairs

    def gen_optional_items_generator_code(self, code_input, ctx):
        inner_code_input = "data_"
        code = Code()
        converter_name = self.gen_name("optional_items_generator", ctx, self)
        (
            code_args,
            positional_args_as_conversions,
            keyword_args_as_conversions,
            namespace_ctx,
        ) = self.get_args_def_info(ctx)
        with namespace_ctx:
            code.add_line(f"def {converter_name}(data_{code_args}):", 1)

            for condition, item in self.condition_to_item_pairs:
                value_code = ensure_conversion(item).gen_code_and_update_ctx(
                    inner_code_input, ctx
                )
                if condition is not None:
                    condition_code = condition.gen_code_and_update_ctx(
                        inner_code_input, ctx
                    )
                    code.add_line(f"if {condition_code}:", 1)
                    code.add_line(f"yield {value_code}", -1)
                else:
                    code.add_line(f"yield {value_code}", 0)

            self._code_to_converter(
                converter_name=converter_name,
                code=code.to_string(base_indent_level=0),
                ctx=ctx,
            )
        return (
            EscapedString(converter_name)
            .call(
                This(),
                *positional_args_as_conversions,
                **keyword_args_as_conversions,
            )
            .gen_code_and_update_ctx(code_input, ctx)
        )

    def gen_joined_items_code(self, code_input, ctx):
        return ",".join(
            item.gen_code_and_update_ctx(code_input, ctx)
            for item in self.items
        )

    def gen_collection_from_items_code(
        self, joined_items_code, code_input, ctx
    ):
        raise NotImplementedError

    def gen_collection_from_generator(self, generator_code, code_input, ctx):
        raise NotImplementedError

    def _gen_code_and_update_ctx(self, code_input, ctx):
        if self.condition_to_item_pairs is not None:
            return self.gen_collection_from_generator(
                self.gen_optional_items_generator_code(code_input, ctx),
                code_input,
                ctx,
            )

        joined_items_code = self.gen_joined_items_code(code_input, ctx)
        return self.gen_collection_from_items_code(
            joined_items_code, code_input, ctx
        )


class OptionalCollectionItem(BaseConversion):
    """Wrapping conversion which makes key/value/item of a collection
    optional."""

    valid_pipe_output = False

    def __init__(
        self,
        conversion,
        skip_value=None,
        skip_if=BaseConversion._none,
        keep_if=BaseConversion._none,
    ):
        """
        Args:
          conversion (BaseConversion): conversion to be wrapped
          skip_value: value to compare with conversion result and to be
            excluded from the collection
          skip_if: a condition to be checked; if it resolves to True, then the
            item gets excluded from the collection
          keep_if: a condition to be checked; if it resolves to False, then the
            item gets excluded from the collection
        """
        super().__init__()
        condition_is_passed = (
            skip_if is not self._none or keep_if is not self._none
        )
        if condition_is_passed and skip_value is not None:
            raise Exception("both condition and skip_value are passed")
        self.conversion = self.ensure_conversion(conversion)
        if condition_is_passed:
            if skip_if is not self._none:
                self.condition = Not(self.ensure_conversion(skip_if))
            if keep_if is not self._none:
                self.condition = self.ensure_conversion(keep_if)
        else:
            if skip_value is None:
                self.condition = self.conversion.is_not(None)
            else:
                self.condition = self.conversion != self.ensure_conversion(
                    skip_value
                )

    def _gen_code_and_update_ctx(self, code_input, ctx):
        raise Exception(
            "OptionalCollectionItem cannot be used outside of collections"
        )


class Tuple(BaseCollectionConversion):
    """Gets compiled into the code which generates a tuple"""

    def gen_collection_from_items_code(
        self, joined_items_code, code_input, ctx
    ):
        if not joined_items_code:
            return "()"
        return f"({joined_items_code},)"

    def gen_collection_from_generator(self, generator_code, code_input, ctx):
        return f"tuple({generator_code})"


class List(BaseCollectionConversion):
    """Gets compiled into the code which generates a list"""

    def gen_collection_from_items_code(
        self, joined_items_code, code_input, ctx
    ):
        return f"[{joined_items_code}]"

    def gen_collection_from_generator(self, generator_code, code_input, ctx):
        return f"list({generator_code})"


class Set(BaseCollectionConversion):
    """Gets compiled into the code which generates a set"""

    def gen_collection_from_items_code(
        self, joined_items_code, code_input, ctx
    ):
        return f"{{{joined_items_code}}}"

    def gen_collection_from_generator(self, generator_code, code_input, ctx):
        return f"set({generator_code})"


class Dict(BaseCollectionConversion):
    """Gets compiled into the code which generates a dict"""

    def __init__(self, *key_value_pairs):
        """
        Args:
          key_value_pairs (:obj:`list` of :obj:`tuple`): each tuple is a
            key-value pair to form a dict from.
            Every key and value gets wrapped with ``ensure_conversion``
        """
        super().__init__()
        pairs = []
        condition_to_item_pairs = None
        for pair in key_value_pairs:
            pair = tuple(self.ensure_conversion(item_) for item_ in pair)
            conditions = [
                item_.condition
                for item_ in pair
                if isinstance(item_, OptionalCollectionItem)
            ]
            condition = And(*conditions) if conditions else None
            if condition is not None:
                pair = tuple(
                    item_.conversion
                    if isinstance(item_, OptionalCollectionItem)
                    else item_
                    for item_ in pair
                )

            if condition_to_item_pairs is None:
                if condition:
                    condition_to_item_pairs = [
                        (None, pair_) for pair_ in pairs
                    ]
                    pairs = None
                    condition_to_item_pairs.append((condition, pair))
                else:
                    pairs.append(pair)
            else:
                condition_to_item_pairs.append((condition, pair))

        self.key_value_pairs = pairs
        self.condition_to_item_pairs = condition_to_item_pairs

    def gen_joined_items_code(self, code_input, ctx):
        return ",".join(
            f"{key.gen_code_and_update_ctx(code_input, ctx)}:"
            f"{value.gen_code_and_update_ctx(code_input, ctx)}"
            for key, value in self.key_value_pairs
        )

    def gen_collection_from_generator(self, generator_code, code_input, ctx):
        return f"dict({generator_code})"

    def gen_collection_from_items_code(
        self, joined_items_code, code_input, ctx
    ):
        return f"{{{joined_items_code}}}"


class TakeWhile(BaseConversion):
    """convtools implementation of :py:obj:`itertools.takewhile`"""

    def __init__(self, condition):
        super().__init__()
        self.condition = self.ensure_conversion(condition)
        self.filter_results_conditions = None
        self.cast = self._none

    def filter(self, condition_conv, cast=BaseConversion._none):
        conditions = self.filter_results_conditions
        if conditions is None:
            conditions = self.filter_results_conditions = [
                self.ensure_conversion(condition_conv)
            ]
        else:
            conditions.append(self.ensure_conversion(condition_conv))
        self.cast = cast
        return self

    def _gen_code_and_update_ctx(self, code_input, ctx):
        suffix = self.gen_name("_", ctx, ("take_while", self, code_input))
        converter_name = f"take_while{suffix}"
        var_it = f"it{suffix}"
        var_item = f"item{suffix}"

        (
            code_args,
            positional_args_as_conversions,
            keyword_args_as_conversions,
            namespace_ctx,
        ) = self.get_args_def_info(ctx)
        with namespace_ctx:
            condition_code = self.condition.gen_code_and_update_ctx(
                var_item, ctx
            )

            code = Code()
            code.add_line(f"def {converter_name}({var_it}{code_args}):", 1)
            code.add_line(f"for {var_item} in {var_it}:", 1)
            code.add_line(f"if {condition_code}:", 1)
            if self.filter_results_conditions is None:
                code.add_line(f"yield {var_item}", -1)
            else:
                filter_code = And(
                    *self.filter_results_conditions
                ).gen_code_and_update_ctx(var_item, ctx)
                code.add_line(f"if {filter_code}:", 1)
                code.add_line(f"yield {var_item}", -2)

            code.add_line("else:", 1)
            code.add_line("break", -2)

            self._code_to_converter(converter_name, code.to_string(0), ctx)
            result = EscapedString(converter_name).call(
                This(),
                *positional_args_as_conversions,
                **keyword_args_as_conversions,
            )
            if self.cast is not self._none:
                result = result.as_type(self.cast)
        return result.gen_code_and_update_ctx(code_input, ctx)


class DropWhile(BaseConversion):
    """convtools implementation of :py:obj:`itertools.dropwhile`"""

    def __init__(self, condition):
        super().__init__()
        self.condition = self.ensure_conversion(condition)
        self.filter_results_conditions = None
        self.cast = self._none

    def _gen_code_and_update_ctx(self, code_input, ctx):
        suffix = self.gen_name("_", ctx, ("take_while", self, code_input))
        converter_name = f"drop_while{suffix}"
        var_chain = f"chain{suffix}"
        var_it = f"it{suffix}"
        var_item = f"item{suffix}"

        (
            code_args,
            positional_args_as_conversions,
            keyword_args_as_conversions,
            namespace_ctx,
        ) = self.get_args_def_info(ctx)
        with namespace_ctx:
            condition_code = self.condition.gen_code_and_update_ctx(
                var_item, ctx
            )

            code = Code()
            code.add_line(
                f"def {converter_name}({var_it},{var_chain}{code_args}):", 1
            )
            code.add_line(f"{var_it} = iter({var_it})", 0)
            code.add_line(f"for {var_item} in {var_it}:", 1)
            code.add_line(f"if not ({condition_code}):", 1)
            code.add_line("break", -2)
            code.add_line("else:", 1)
            code.add_line("return ()", -1)
            code.add_line(f"return {var_chain}(({var_item},), {var_it})", -1)
            self._code_to_converter(converter_name, code.to_string(0), ctx)
        return (
            EscapedString(converter_name)
            .call(
                This(),
                NaiveConversion(chain),
                *positional_args_as_conversions,
                **keyword_args_as_conversions,
            )
            .gen_code_and_update_ctx(code_input, ctx)
        )


class PipeConversion(BaseConversion):
    """Passes the result of one conversion as an input to another.  If
    `next_conversion` is callable, it gets called with the previous result
    passed as the first param.

    Supports predicate/sorting/type casting push down (each is directly applied
    to the ``where`` conversion.

    Supports labeling both pipe input and output data (allows to apply
    conversions before labeling)."""

    def __init__(
        self,
        what,
        where,
        *args,
        label_input=None,
        label_output=None,
        **kwargs,
    ):
        """

        Args:
          next_conversion (object): to be wrapped with
            :py:obj:`ensure_conversion` and called if callable is passed
          args (tuple): to be wrapped with :py:obj:`ensure_conversion` and
            passed to `next_conversion` if it's callable
          kwargs (dict): to be wrapped with :py:obj:`ensure_conversion` and
            passed to `next_conversion` if it's callable
          label_input (str or dict): Labels to be put on pipe input data.
            If a ``str`` is passed, then it is used as a label name.
            If a ``dict`` is passed, keys are label names, values
            are conversions to be applied before labeling.
          label_output (str or dict): Labels to be put on pipe output data.
            The rest is all the same as with ``label_input``
        """
        super().__init__()
        if (
            CodeGenerationOptionsCtx.get_option_value("inline_pipes_only")
        ) and (label_input or label_output):
            raise AssertionError(
                "inline pipes requested: no labeling is supported"
            )

        self.input_args_container = EscapedString("None")

        self.what = self.ensure_conversion(what, skip_for_input_args=True)
        self.where = self.ensure_conversion(where)
        self.where.check_dependency(self.what, for_piping=True)

        if (
            (self.what.contents & self.ContentTypes.NEW_LABEL) or label_input
        ) and (self.where.contents & self.ContentTypes.REDUCER):
            raise ValueError("labeling of reducer inputs is not supported")

        if not self.where.valid_pipe_output:
            raise ValueError("invalid output, check where conversion")

        if self.where.is_itself_callable():
            self.where = self.where.call(
                GetItem(),
                *tuple(self.ensure_conversion(arg) for arg in args),
                **{k: self.ensure_conversion(v) for k, v in kwargs.items()},
            )
        elif args or kwargs:
            raise AssertionError(
                "args or kwargs won't be used when 'where' is not callable"
            )

        self.label_input = (
            None if label_input is None else self._prepare_labels(label_input)
        )
        self.label_output = (
            None
            if label_output is None
            else self._prepare_labels(label_output)
        )
        if self.label_input or self.label_output:
            self.self_content_type |= self.ContentTypes.NEW_LABEL
            self.contents |= self.self_content_type
            self.input_args_container.contents |= self.ContentTypes.NEW_LABEL

    def replace(self, where):
        return PipeConversion(
            what=self.what,
            where=where,
            label_input=self.label_input,
            label_output=self.label_output,
        )

    def as_type(self, callable_):
        return self.replace(self.where.as_type(callable_))

    def filter(self, condition_conv, cast=BaseConversion._none):
        return self.replace(self.where.filter(condition_conv, cast=cast))

    def sort(self, key=None, reverse=False):
        return self.replace(self.where.sort(key, reverse))

    def _prepare_labels(
        self,
        label_arg: t.Union[str, dict],
    ):
        if isinstance(label_arg, str):
            return {label_arg: GetItem()}

        elif isinstance(label_arg, dict):
            return {
                label_name: self.ensure_conversion(conv)
                for label_name, conv in label_arg.items()
            }

        raise ConversionException(
            "unexpected label_input type", type(label_arg), label_arg
        )

    symbols_making_expr_complex = re.compile(r"[^\w\"'\[\]]")

    @classmethod
    def input_is_simple(cls, code_input):
        while code_input.startswith("(") and code_input.endswith(")"):
            code_input = code_input[1:-1].strip()
        if not code_input or (
            next(cls.symbols_making_expr_complex.finditer(code_input), None)
            is None
        ):
            return code_input.count("][") < 2
        return False

    def ensure_conversion(
        self, conversion, skip_for_input_args=False, **kwargs
    ) -> "BaseConversion":
        if not skip_for_input_args:
            self.input_args_container.ensure_conversion(conversion)
        return super().ensure_conversion(conversion, **kwargs)

    def _gen_code_and_update_ctx(self, code_input, ctx):
        what_code = self.what.gen_code_and_update_ctx(code_input, ctx)
        where = self.where

        where_code = where.gen_code_and_update_ctx(what_code, ctx)
        code_usage_count = self.count_words(where_code, what_code)
        what_code_has_no_side_effects = not (
            (self.what.contents & self.ContentTypes.NEW_LABEL)
            or self.label_input
        )
        can_be_inlined = (
            (code_usage_count < 2 or self.input_is_simple(what_code))
            and what_code_has_no_side_effects
            and self.label_output is None
        )
        if can_be_inlined:
            return where_code

        code_input_is_ignored = (
            code_usage_count == 0 and what_code_has_no_side_effects
        )
        # backing up reducer inputs, collected at the previous step
        reducers_run_stage = CodeGenerationOptionsCtx.get_option_value(
            "reducers_run_stage"
        )
        reducer_inputs_backup_needed = (
            reducers_run_stage == "collecting_reducer_inputs"
        )
        key_to_backup = "_reducer_inputs_info"

        suffix = self.gen_name("_", ctx, ("pipe", self, code_input))
        converter_name = f"pipe{suffix}"
        var_result = f"result{suffix}"
        var_input = f"input{suffix}"

        (
            code_args,
            positional_args_as_conversions,
            keyword_args_as_conversions,
            namespace_ctx,
        ) = self.input_args_container.get_args_def_info(ctx)

        with namespace_ctx:

            if code_input_is_ignored:
                if self.label_output is None:
                    raise AssertionError("what are we doing here? it's a bug")
                what_code, where_code = (where_code, var_input)
            else:
                if reducer_inputs_backup_needed:
                    ctx[key_to_backup].append(False)

                where_code = where.gen_code_and_update_ctx(var_input, ctx)

                if reducer_inputs_backup_needed:
                    ctx[key_to_backup].pop()

            code = Code()
            code.add_line(f"def {converter_name}({var_input}{code_args}):", 1)

            if self.label_input:
                for label_name, label_c in self.label_input.items():
                    code.add_line(
                        f"_labels['{label_name}'] = "
                        f"{label_c.gen_code_and_update_ctx(var_input, ctx)}",
                        0,
                    )
            if self.label_output:
                code.add_line(f"{var_result} = {where_code}", 0)
                for label_name, label_c in self.label_output.items():
                    code.add_line(
                        f"_labels['{label_name}'] = "
                        f"{label_c.gen_code_and_update_ctx(var_result, ctx)}",
                        0,
                    )
                code.add_line(f"return {var_result}", 0)
            else:
                code.add_line(f"return {where_code}", 0)

        # no need in catching the function, we'll just use it by the name
        if reducers_run_stage != "collecting_reducer_inputs":
            self._code_to_converter(
                converter_name=converter_name,
                code=code.to_string(0),
                ctx=ctx,
            )

        return (
            EscapedString(converter_name)
            .call(
                EscapedString(what_code),
                *positional_args_as_conversions,
                **keyword_args_as_conversions,
            )
            .gen_code_and_update_ctx(None, ctx)
        )


class TapConversion(BaseConversion):
    """This conversion generates the code which mutates the input data
    in-place.  TapConversion takes any number of mutations"""

    def __init__(self, obj, *mutations: BaseMutation):
        super().__init__()
        self.obj = self.ensure_conversion(obj)
        self.mutations = [
            self.ensure_conversion(mut, explicitly_allowed_cls=BaseMutation)
            for mut in mutations
        ]

    def _gen_code_and_update_ctx(self, code_input, ctx):
        suffix = self.gen_name("", ctx, self)
        converter_name = f"tap_{suffix}"
        (
            code_args,
            positional_args_as_conversions,
            keyword_args_as_conversions,
            namespace_ctx,
        ) = self.get_args_def_info(ctx)
        with namespace_ctx:
            code = Code()
            code.add_line(f"def {converter_name}(data_{code_args}):", 1)
            for mut in self.mutations:
                code.add_line(mut.gen_code_and_update_ctx("data_", ctx), 0)
            code.add_line("return data_", 0)

            self._code_to_converter(
                converter_name, code.to_string(base_indent_level=0), ctx
            )
        return (
            EscapedString(converter_name)
            .call(
                self.obj,
                *positional_args_as_conversions,
                **keyword_args_as_conversions,
            )
            .gen_code_and_update_ctx(code_input, ctx)
        )


class IterMutConversion(TapConversion):
    """This conversion generates the code which iterates and mutates the
    elements in-place. The result is a generator.
    IterMutConversion takes any number of mutations"""

    def _gen_code_and_update_ctx(self, code_input, ctx):
        suffix = self.gen_name("", ctx, self)
        converter_name = f"iter_mut_{suffix}"
        code_item = f"item_{suffix}"
        (
            code_args,
            positional_args_as_conversions,
            keyword_args_as_conversions,
            namespace_ctx,
        ) = self.get_args_def_info(ctx)

        with namespace_ctx:
            code = Code()
            code.add_line(f"def {converter_name}(data_{code_args}):", 1)
            code.add_line(f"for {code_item} in data_:", 1)
            for mut in self.mutations:
                code.add_line(
                    mut.gen_code_and_update_ctx(f"{code_item}", ctx), 0
                )

            code.add_line(f"yield {code_item}", 0)

            self._code_to_converter(
                converter_name, code.to_string(base_indent_level=0), ctx
            )
        return (
            EscapedString(converter_name)
            .call(
                self.obj,
                *positional_args_as_conversions,
                **keyword_args_as_conversions,
            )
            .gen_code_and_update_ctx(code_input, ctx)
        )


if "pydevd" in sys.modules:  # pragma: no cover

    def debug_func(obj):
        import pydevd  # type: ignore # pylint: disable=import-outside-toplevel

        pydevd.settrace()
        return obj


elif sys.version_info[:2] < (3, 7):  # pragma: no cover

    def debug_func(obj):
        pdb.set_trace()  # pylint: disable=forgotten-debug-statement
        return obj


else:  # pragma: no cover

    def debug_func(obj):
        breakpoint()  # pylint: disable=undefined-variable,forgotten-debug-statement # noqa: F821,E501
        return obj


class Breakpoint(BaseConversion):
    """Defines the conversion which wraps another one and puts a breakpoint
    after it"""

    self_content_type = (
        BaseConversion.self_content_type
        | BaseConversion.ContentTypes.BREAKPOINT
    ) ^ BaseConversion.ContentTypes.FUNCTION_OF_INPUT
    debug_func = staticmethod(debug_func)

    def __init__(self, to_debug):
        super().__init__()
        self.conversion = self.ensure_conversion(to_debug).pipe(
            self.debug_func
        )

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return self.conversion.gen_code_and_update_ctx(code_input, ctx)
