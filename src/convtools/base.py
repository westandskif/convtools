"""
Base and basic conversions are defined here.
"""
import re
import string
import sys
import typing as t
from collections import deque
from datetime import datetime
from itertools import chain
from keyword import iskeyword
from random import Random

from .dt import (
    DayOfWeekStep,
    MonthStep,
    TruncModes,
    date_parse,
    date_trunc_to_day,
    date_trunc_to_month,
    datetime_parse,
    datetime_trunc_to_day,
    datetime_trunc_to_microsecond,
    datetime_trunc_to_month,
    to_step,
)
from .heuristics import Weights
from .utils import (
    BaseCtx,
    BaseOptions,
    Code,
    CodeStorage,
    LazyModule,
    iter_windows,
)


convtools_cumulative = LazyModule("convtools.cumulative")
convtools_debug = LazyModule("convtools.debug")
convtools_mutations = LazyModule("convtools.mutations")
convtools_unique = LazyModule("convtools.unique")


black: "t.Optional[t.Any]" = None
try:
    import black as black_  # pragma: no cover

    black = black_  # pragma: no cover
except ImportError:
    pass


class CodeGenerationOptions(BaseOptions):
    pass


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


_none = _None()
_random = Random(1)
choice = _random.choice


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

    _none = _none
    valid_pipe_output = True
    used_in_narrow_context = False
    trackable_dependency = False

    class ContentTypes:
        """Defines types of conversion content for bitmask calculations"""

        REDUCER = 1
        AGGREGATION = 2
        NEW_LABEL = 4
        ARG_USAGE = 8
        LABEL_USAGE = 16
        BREAKPOINT = 32
        FUNCTION_OF_INPUT = 64
        NONE_USAGE = 128

    self_content_type = ContentTypes.FUNCTION_OF_INPUT

    class OutputHints:
        NOT_NONE = 1

    output_hints = 0
    weight = Weights.UNPREDICTABLE

    base_type_to_cast: "t.Union[_None, t.Type]" = _none

    def __init__(self):
        self._depends_on = {}
        self.contents = self.self_content_type
        self.total_weight = self.weight
        self.number_of_input_uses = 1 if self.contents & 64 else 0

    def __hash__(self):
        return id(self)

    def add_hint(self, hint: int):
        self.output_hints |= hint
        return self

    def check_dependency(self, b):
        if (
            b.contents & 1 and self.self_content_type & 1
        ):  # self.ContentTypes.REDUCER
            raise ValueError("nested aggregation", self.__dict__)

    def is_dependency_trackable(self, dependency: "BaseConversion"):
        return dependency.trackable_dependency

    def depends_on(self, *args):
        for arg in args:
            self.check_dependency(arg)

            for dep in arg.get_dependencies():
                if self.is_dependency_trackable(dep):
                    self._depends_on[dep] = dep

            self.number_of_input_uses += arg.number_of_input_uses
            self.total_weight += arg.total_weight
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

    def gen_code_and_update_ctx(self, code_input, ctx) -> str:
        """The main method which generates the code and stores necessary info
        in the context (which will be passed as locals() and globals() on to
        the exec function).  However you should not override this method
        directly, please implement the `_gen_code_and_update_ctx` one.
        """
        return self._gen_code_and_update_ctx(code_input, ctx)

    def _gen_code_and_update_ctx(self, code_input, ctx) -> str:
        raise NotImplementedError

    def to_code(self, code_input, ctx) -> "t.Optional[Code]":
        return self._to_code(code_input, ctx)

    def _to_code(
        self, code_input, ctx  # pylint: disable=unused-argument
    ) -> "t.Optional[Code]":
        return None

    allowed_symbols = string.ascii_lowercase + string.digits

    PREFIXED_HASH_TO_NAME = "_prefixed_hash_to_name"
    GENERATED_NAMES = "_generated_names"

    def gen_random_name(self, prefix, ctx) -> str:
        generated_names = ctx[self.GENERATED_NAMES]
        name = prefix or "_"
        for _ in range(10):
            if _ or iskeyword(name):
                if name == "_":
                    name = f"{name}{choice(self.allowed_symbols)}"
                else:
                    name = f"{name}_{choice(self.allowed_symbols)}"

            if name not in generated_names:
                generated_names.add(name)
                return name

        raise AssertionError("failed to generate unique filename", name)

    def gen_name(self, prefix, ctx, item_to_hash) -> str:
        """Generates name of variable to be used in the generated code. This
        also ensures that same items_to_hash will yield same names."""
        prefixed_hash_to_name = ctx[self.PREFIXED_HASH_TO_NAME]
        prefixed_hash = (prefix, item_to_hash)
        try:
            if prefixed_hash in prefixed_hash_to_name:
                return prefixed_hash_to_name[prefixed_hash]
            name = self.gen_random_name(prefix, ctx)

        except TypeError:
            prefixed_hash = (prefix, id(item_to_hash))
            if prefixed_hash in prefixed_hash_to_name:
                return prefixed_hash_to_name[prefixed_hash]
            name = self.gen_random_name(prefix, ctx)

        prefixed_hash_to_name[prefixed_hash] = name
        return name

    _word_pattern_format = r"((?<=\W)|^){}((?=\W)|$)"

    @classmethod
    def replace_word(cls, where: str, word: str, with_what: str) -> str:
        return re.sub(
            cls._word_pattern_format.format(re.escape(word)),
            with_what,
            where,
        )

    def as_function_ctx(
        self,
        ctx,
        as_kwargs=False,
        args_to_skip=None,
        for_top_level_converter=False,
        optimize_naive=False,
    ) -> "FunctionCtx":
        args_to_skip = args_to_skip or set()
        args = {
            (dep.name, is_lazy): dep
            for dep, is_lazy in (
                (dep, isinstance(dep, LazyEscapedString))
                for dep in self.get_dependencies()
            )
            if (isinstance(dep, InputArg) or is_lazy)
            and dep.name not in args_to_skip
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

        if "_none" not in args_to_skip and (
            self.contents & 128  # self.ContentTypes.NONE_USAGE
        ):
            positional_args_as_def_names.append("_none")
            positional_args_as_conversions.append(EscapedString("_none"))

        if (
            LabelConversion.labels_code_name not in args_to_skip
            and self.contents
            & (
                # self.ContentTypes.LABEL_USAGE | self.ContentTypes.NEW_LABEL
                20
            )
        ):
            positional_args_as_def_names.append(
                LabelConversion.labels_code_name
            )
            positional_args_as_conversions.append(
                EscapedString(LabelConversion.labels_code_name)
            )

        suffix = None
        for key, dep in args.items():
            dep_name, is_named_conversion = key
            if is_named_conversion:
                suffix = suffix or self.gen_random_name("_", ctx)
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

        namespace_ctx = NamespaceCtx(name_to_code, ctx)
        positional_args_as_conversions = [
            namespace_ctx.prevent_rendering_while_active(conv)
            for conv in positional_args_as_conversions
        ]
        keyword_args_as_conversions = {
            key: namespace_ctx.prevent_rendering_while_active(conv)
            for key, conv in keyword_args_as_conversions.items()
        }
        return FunctionCtx(
            self,
            ctx,
            deque(positional_args_as_def_names),
            deque(keyword_args_as_def_names),
            deque(positional_args_as_conversions),
            keyword_args_as_conversions,
            namespace_ctx,
            optimize_naive,
        )

    def compile_converter(
        self, converter_name: str, code: str, ctx: dict
    ) -> t.Callable:
        is_debug = ctx.get(
            "__debug", False
        ) or ConverterOptionsCtx.get_option_value("debug")
        if is_debug and black:
            try:
                code = black.format_str(
                    code, mode=black.FileMode(line_length=160)  # type: ignore
                )
            except black.InvalidInput:
                pass

        abs_path, added = ctx["__convtools__code_storage"].add_sources(
            converter_name, code
        )

        if added:
            if is_debug:
                sys.stdout.write(code)
                sys.stdout.write("\n")
            code_obj = compile(code, abs_path, "exec", optimize=2)
            exec(code_obj, ctx)  # pylint:disable=exec-used
            ctx[converter_name].conv_name = converter_name
        return ctx[converter_name]

    NAMESPACES = "_name_to_code_input"
    CONVERTERS_CACHE = "_converters_cache"
    NAIVE_TO_WARM_UP = "_naive_to_warm_up"

    exceptions_to_dump_sources = (Exception, KeyboardInterrupt)

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
            cls.NAIVE_TO_WARM_UP: None,
            "__convtools__code_storage": CodeStorage(),
            "__exceptions_to_dump_sources": cls.exceptions_to_dump_sources,
            # SetUpCumulative.__cumulative_names__
        }
        return ctx

    def gen_converter(
        self,
        method=False,
        class_method=False,
        signature=None,
        debug=None,
        converter_name="converter",
    ):
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
        # self.ContentTypes.NEW_LABEL | self.ContentTypes.LABEL_USAGE
        has_labels = self.contents & 20
        has_none = self.contents & 128  # self.ContentTypes.NONE_USAGE
        ctx = self._init_ctx(debug=debug)

        args_to_skip = (
            "self",
            "cls",
            "_none",
            "_naive",
            LabelConversion.labels_code_name,
        )
        if signature is not None:
            function_ctx = self.as_function_ctx(
                ctx, args_to_skip=args_to_skip, for_top_level_converter=True
            )
            missing_args = set(function_ctx.args_as_def_names).union(
                function_ctx.kwargs_as_def_names
            ) - set(_pattern_word.findall(signature))
            if missing_args:
                raise ConversionException(
                    "bad signature, missing args", missing_args
                )
        else:
            if method and class_method:
                raise ConversionException(
                    "choose either method or a class_method"
                )
            function_ctx = self.as_function_ctx(
                ctx,
                as_kwargs=True,
                args_to_skip=args_to_skip,
                for_top_level_converter=True,
                optimize_naive=True,
            )
            function_ctx.add_arg(initial_code_input)
            if method:
                function_ctx.add_arg("self", left=True)
            elif class_method:
                function_ctx.add_arg("cls", left=True)

        with function_ctx:
            code = Code()
            converter_name = self.gen_random_name(converter_name, ctx)

            code_ = self.to_code(initial_code_input, ctx)
            if code_ is None:
                code_str = f"return {self.gen_code_and_update_ctx(initial_code_input, ctx)}"

            signature = (
                function_ctx.get_def_all_args_code()
                if signature is None
                else signature
            )

            code.add_line(f"def {converter_name}({signature}):", 1)
            if has_none:
                code.add_line("global __none__", 0)
                code.add_line("_none = __none__", 0)
            if has_labels:
                code.add_line(f"{LabelConversion.labels_code_name} = {{}}", 0)

            code.add_line("try:", 1)

            if code_ is not None:
                code.add_code(code_)
            else:
                code.add_line(code_str, 0)

            code.incr_indent_level(-1)
            code.add_line("except __exceptions_to_dump_sources:", 1)
            code.add_line("__convtools__code_storage.dump_sources()", 0)
            code.add_line("raise", -1)

            converter = function_ctx.gen_function(
                converter_name, code.to_string(base_indent_level=0)
            )

        del ctx[self.CONVERTERS_CACHE]
        del ctx[self.GENERATED_NAMES]
        del ctx[self.NAMESPACES]
        del ctx[self.PREFIXED_HASH_TO_NAME]
        del ctx[self.NAIVE_TO_WARM_UP]

        if debug:
            ctx["__convtools__code_storage"].dump_sources()

        if class_method:
            return classmethod(converter)

        return converter

    def execute(self, *args, debug=None, **kwargs) -> t.Any:
        """Shortcut for generating converter and running it"""
        return self.gen_converter(
            debug=debug or ConverterOptionsCtx.get_option_value("debug")
        )(*args, **kwargs)

    def to_iter(self):
        return GeneratorComp(This, _none, self)

    def iter(self, element_conv, *, where=None) -> "BaseConversion":
        """Shortcut for
        ``self.pipe(c.generator_comp(element_conv, where=condition))``

        Args:
          element_conv (object): conversion to be run on each element
          where (object): condition inside the comprehension

        """
        return GeneratorComp(element_conv, where=where, self_conv=self)

    def iter_unique(self, element_conv=None, by_=None) -> "BaseConversion":
        """
        Creates a conversion which iterates over the input and yields unique
        ones (supports custom uniqueness conditions)

        Args:
          element_conv: defines a conversion to be applied to each element to
            be returned; if it is None, it means `c.this`
          by_: defines a conversion to be applied to each element to check for
            uniqueness; if it is None, it means to use `element_conv` for
            uniqueness
        """
        element_conv = This if element_conv is None else element_conv
        return convtools_unique.IterUnique(
            self, element_conv, element_conv if by_ is None else by_
        )

    def filter(self, condition_conv, cast=None) -> "BaseConversion":
        """Generates the code to iterate the input, taking items for which the
        provided conversion resolves to a truth value.

        Args:
          condition_conv (object): to be wrapped with
            :py:obj:`ensure_conversion` and used on each item of a collection
            to filter it
          cast (callable): to wrap the generator of filtered items
        Returns:
          BaseConversion: the generator of filtered items, wrapped with `cast`
          if provided
        """
        cast = _none if cast is None else cast
        result = self.to_iter().iter(This, where=condition_conv)

        if cast is _none and self.base_type_to_cast is not _none:
            cast = self.base_type_to_cast

        if cast is not _none:
            result = result.as_type(cast)

        return result

    def iter_mut(self, *mutations: "BaseMutation") -> "BaseConversion":
        """Conversion which results in a generator of mutated elements

        Args:
          mutations (BaseMutation): conversion to be run on each element

        """
        return convtools_mutations.IterMutConversion(self, *mutations)

    def iter_windows(self, width, step=1):
        """Iterates through an iterable and yields tuples, which are obtained
        by sliding a windows of a given width, moving it by specified step
        size"""
        return CallFunc(iter_windows, self, width, step)

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

    def ignores_input(self) -> t.Optional[bool]:
        return self.contents & 64 == 0  # self.ContentTypes.FUNCTION_OF_INPUT

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
        resulting_args = []
        for arg in chain((self,), args):
            if isinstance(arg, Or):
                resulting_args.extend(arg.args)
            else:
                resulting_args.append(arg)

        return Or(*resulting_args, **kwargs)

    def __or__(self, b) -> "Or":
        return self.or_(b)

    def and_(self, *args, **kwargs) -> "And":
        resulting_args = []

        for arg in chain((self,), args):
            if isinstance(arg, And):
                resulting_args.extend(arg.args)
            else:
                resulting_args.append(arg)

        return And(*resulting_args, **kwargs)

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

    def eq(self, b, *args) -> "Eq":
        return Eq(self, b, *args)

    def __eq__(self, b) -> "Eq":  # type: ignore
        return Eq(self, b)

    def not_eq(self, b) -> "InlineExpr":
        return self != b

    def __ne__(self, b) -> "InlineExpr":  # type: ignore
        return InlineExpr("{0} != {1}", Weights.LOGICAL).pass_args(self, b)

    def gt(self, b) -> "InlineExpr":
        return self > b

    def __gt__(self, b) -> "InlineExpr":
        return InlineExpr("{0} > {1}", Weights.LOGICAL).pass_args(self, b)

    def gte(self, b) -> "InlineExpr":
        return self >= b

    def __ge__(self, b) -> "InlineExpr":
        return InlineExpr("{0} >= {1}", Weights.LOGICAL).pass_args(self, b)

    def lt(self, b) -> "InlineExpr":
        return self < b

    def __lt__(self, b) -> "InlineExpr":
        return InlineExpr("{0} < {1}", Weights.LOGICAL).pass_args(self, b)

    def lte(self, b) -> "InlineExpr":
        return self <= b

    def __le__(self, b) -> "InlineExpr":
        return InlineExpr("{0} <= {1}", Weights.LOGICAL).pass_args(self, b)

    def neg(self) -> "InlineExpr":
        return -self

    def __neg__(self) -> "InlineExpr":
        return (
            InlineExpr("-{0}", Weights.MATH_SIMPLE)
            .pass_args(self)
            .add_hint(self.OutputHints.NOT_NONE)
        )

    def add(self, b) -> "InlineExpr":
        return self + b

    def __add__(self, b) -> "InlineExpr":
        return (
            InlineExpr("{0} + {1}", Weights.MATH_SIMPLE)
            .pass_args(self, b)
            .add_hint(self.OutputHints.NOT_NONE)
        )

    def mul(self, b) -> "InlineExpr":
        return self * b

    def __mul__(self, b) -> "InlineExpr":
        return (
            InlineExpr("{0} * {1}", Weights.MATH_SIMPLE)
            .pass_args(self, b)
            .add_hint(self.OutputHints.NOT_NONE)
        )

    def sub(self, b) -> "InlineExpr":
        return self - b

    def __sub__(self, b) -> "InlineExpr":
        return (
            InlineExpr("{0} - {1}", Weights.MATH_SIMPLE)
            .pass_args(self, b)
            .add_hint(self.OutputHints.NOT_NONE)
        )

    def div(self, b) -> "InlineExpr":
        return self / b

    def __truediv__(self, b) -> "InlineExpr":
        return (
            InlineExpr("{0} / {1}", Weights.MATH_SIMPLE)
            .pass_args(self, b)
            .add_hint(self.OutputHints.NOT_NONE)
        )

    def mod(self, b) -> "InlineExpr":
        return self % b

    def __mod__(self, b) -> "InlineExpr":
        return (
            InlineExpr("{0} % {1}", Weights.MATH_SIMPLE)
            .pass_args(self, b)
            .add_hint(self.OutputHints.NOT_NONE)
        )

    def floor_div(self, b) -> "InlineExpr":
        return self // b

    def __floordiv__(self, b) -> "InlineExpr":
        return (
            InlineExpr("{0} // {1}", Weights.MATH_SIMPLE)
            .pass_args(self, b)
            .add_hint(self.OutputHints.NOT_NONE)
        )

    def len(self) -> "BaseConversion":
        """Shortcut for CallFunc(len, self)"""
        return CallFunc(len, self)

    def sort(self, key=None, reverse=False) -> "BaseConversion":
        """Shortcut for calling :py:obj:`convtools.base.SortConversion` on
        self"""
        return self.pipe(SortConversion(key=key, reverse=reverse))

    def add_label(self, label_name: t.Union[str, dict]) -> "BaseConversion":
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

        Args:
          label_name: a name of the label to be applied or a dict with labels
            to conversions
        Returns:
          LabelConversion: the labeled conversion
        """
        return self.pipe(This, label_input=label_name)

    def tap(self, *mutations: "BaseMutation") -> "BaseConversion":
        """Allows to tap into the processing of a conversion and mutate it
        in place. Accepts multiple mutations, order matters.

        Args:
          mutations (iterable of BaseMutation): mutations to process the
            conversion
        """
        return convtools_mutations.TapConversion(self, *mutations)

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
        return convtools_debug.Breakpoint(self)

    def and_then(self, conversion, condition=bool) -> "BaseConversion":
        """Applies conversion if condition is true, otherwise leaves untouched.
        Condition is :py:obj:`bool` by default"""
        if condition is bool:
            return self.pipe(And(This(), conversion))

        return self.pipe(
            If(
                CallFunc(condition, This())
                if callable(condition)
                else condition,
                conversion,
            )
        )

    def cumulative(self, prepare_first, reduce_two, label_name=None):
        """Shortcut for :py:obj:`Cumulative`"""
        return convtools_cumulative.Cumulative(
            self, prepare_first, reduce_two, label_name
        )

    def cumulative_reset(self, label_name):
        """Shortcut for :py:obj:`CumulativeReset`"""
        return convtools_cumulative.CumulativeReset(self, label_name)

    def date_parse(self, main_format, *other_formats):
        if other_formats:
            return CallFunc(
                date_parse, self, main_format, NaiveConversion(other_formats)
            )
        return CallFunc(datetime.strptime, self, main_format).call_method(
            "date"
        )

    def datetime_parse(self, main_format, *other_formats):
        if other_formats:
            return CallFunc(
                datetime_parse,
                self,
                main_format,
                NaiveConversion(other_formats),
            )
        return CallFunc(datetime.strptime, self, main_format)

    def date_trunc(self, step, offset=None, mode="start"):
        """Truncates a date to periods of certain length, specified by step and
        offset, passed as either a STEP-STRING (see below) or a
        `datetime.timedelta`.
        It also supports multiple modes of truncating dates.

        >>> conversion.date_trunc("1mo")
        >>> conversion.date_trunc("3mo", "1mo")
        >>> conversion.date_trunc("3mo", "1mo", mode="end_inclusive")

        STEP-STRING is a string which is comprised of numbers and suffixes:
         - y: year
         - mo: month
         - sun/mon/tue/wed/thu/fri/sat: days of week
         - d: day
         - h: hour
         - m: minute
         - s: second
         - ms: millisecond
         - us: microsecond

        so -2d8h10us means minus 2 days 8 hours and 10 microseconds.

        WARNING:
         * y/mo support only y/mo as offsets
         * days of week don't support offsets
         * as this method truncates dates, not datetimes, it accepts only whole
           number of days as steps and offsets

        Args:
          step: defines period length. If it's a year, month or a day of week,
            it defines beginnings of periods too.
          offset (optional): defines the shift of the expected date grid
            relative to 0-point. Positive offset shifts a grid to the right.
          mode (Literal["start", "end", "end_inclusive"]): defines truncating
            mode: "start" returns period start; "end" returns a start of the
            next period, complies with default interval definition where start
            is inclusive and end is not; "end_inclusive" returns the end of the
            current interval

        """
        step = to_step(step)
        mode = TruncModes.to_internal(mode)
        if offset is not None:
            offset = to_step(offset)
        if isinstance(step, MonthStep):
            return CallFunc(
                date_trunc_to_month,
                self,
                step.to_months(),
                0 if offset is None else offset.to_months(),
                mode,
            )
        elif isinstance(step, DayOfWeekStep):
            if offset is not None:
                raise ValueError(
                    "offsets are not applicable to day-of-week steps"
                )
            return CallFunc(
                date_trunc_to_day,
                self,
                step.to_days(),
                step.day_of_week_offset,
                mode,
            )
        return CallFunc(
            date_trunc_to_day,
            self,
            step.to_days(),
            0 if offset is None else offset.to_days(),
            mode,
        )

    def datetime_trunc(self, step, offset=None, mode="start"):
        """Truncates a date to periods of certain length, specified by step and
        offset, passed as either a STEP-STRING (see below) or a
        :py:obj:`datetime.timedelta`.
        It also supports multiple modes of truncating dates.

        >>> conversion.datetime_trunc("1mo")
        >>> conversion.datetime_trunc("3mo", "1mo")
        >>> conversion.datetime_trunc("3mo", "1mo", mode="end_inclusive")

        STEP-STRING is a string which is comprised of numbers and suffixes:
         - y: year
         - mo: month
         - sun/mon/tue/wed/thu/fri/sat: days of week
         - d: day
         - h: hour
         - m: minute
         - s: second
         - ms: millisecond
         - us: microsecond

        so "-2d8h10us" means minus 2 days 8 hours and 10 microseconds.

        WARNING:
         * y/mo support only y/mo as offsets
         * days of week don't support offsets
         * any steps defined as deterministic units (d, h, m, s, ms, us) can
           only be used with offsets defined by deterministic units too

        Args:
          step: defines period length. If it's a year, month or a day of week,
            it defines beginnings of periods too.
          offset (optional): defines the shift of the expected date grid
            relative to 0-point. Positive offset shifts a grid to the right.
          mode (Literal["start", "end", "end_inclusive"]): defines truncating
            mode: "start" returns period start; "end" returns a start of the
            next period, complies with default interval definition where start
            is inclusive and end is not; "end_inclusive" returns the end of the
            current interval
        """
        step = to_step(step)
        mode = TruncModes.to_internal(mode)
        if offset is not None:
            offset = to_step(offset)

        if isinstance(step, MonthStep):
            return CallFunc(
                datetime_trunc_to_month,
                self,
                step.to_months(),
                0 if offset is None else offset.to_months(),
                mode,
            )

        elif isinstance(step, DayOfWeekStep):
            if offset is not None:
                raise ValueError(
                    "offsets are not applicable to day-of-week steps"
                )
            return CallFunc(
                datetime_trunc_to_day,
                self,
                step.to_days(),
                step.day_of_week_offset,
                mode,
            )

        if step.can_be_cast_to_days() and (
            offset is None or offset.can_be_cast_to_days()
        ):
            return CallFunc(
                datetime_trunc_to_day,
                self,
                step.to_days(),
                0 if offset is None else offset.to_days(),
                mode,
            )

        return CallFunc(
            datetime_trunc_to_microsecond,
            self,
            step.to_us(),
            0 if offset is None else offset.to_us(),
            mode,
        )


class BaseMutation(BaseConversion):
    used_in_narrow_context = True
    weight = Weights.FUNCTION_CALL


class BaseMethodConversion(BaseConversion):
    """This conversion is required to take into account method calls.  We need
    to preserve the instance we are calling a method on.

    e.g. like obj['key'] OR obj.func() OR obj.attr1"""

    def __init__(self, self_conv):
        super().__init__()
        self.self_conv = (
            self_conv
            if self_conv is self._none
            else self.ensure_conversion(self_conv)
        )

    def get_self_and_input_code(
        self, code_input: str, ctx: dict
    ) -> t.Tuple[str, str]:
        if self.self_conv is self._none:
            return (code_input, code_input)
        return (
            self.self_conv.gen_code_and_update_ctx(code_input, ctx),
            code_input,
        )


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
        & ~BaseConversion.ContentTypes.FUNCTION_OF_INPUT
    )

    types_to_repr = {type(None), bool, int}
    weight = Weights.STEP

    def __init__(self, value: t.Any, name_prefix="v"):
        """
        Args:
          value (object): any object

        """
        super().__init__()
        self.value = value
        self.name_prefix = name_prefix
        self.code_str = None

        value_name = getattr(value, "__name__", "")
        if (
            value_name in self._builtin_dict
            and self.value is self._builtin_dict[value_name]
        ):
            self.code_str = value_name

        elif callable(value):
            if name_prefix == "v":
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

        if not self.code_str:
            self.total_weight = Weights.DICT_LOOKUP

    def _gen_code_and_update_ctx(self, code_input, ctx):
        if self.code_str:
            return self.code_str

        naive_to_warm_up = ctx[self.NAIVE_TO_WARM_UP]
        if naive_to_warm_up is not None:
            value_name = self.gen_name(
                f"__{self.name_prefix}", ctx, self.value
            )
            ctx["__naive_values__"][value_name] = self.value
            naive_to_warm_up.add(value_name)
            return value_name

        value_name = self.gen_name(self.name_prefix, ctx, self.value)
        ctx["__naive_values__"][value_name] = self.value
        return f'__naive_values__["{value_name}"]'

    def is_itself_callable_like(self) -> t.Optional[bool]:
        return callable(self.value)

    def is_itself_callable(self) -> t.Optional[bool]:
        return callable(self.value)

    @staticmethod
    def get_value(conversion) -> bool:
        return (
            conversion.value
            if isinstance(conversion, NaiveConversion)
            else conversion
        )


class EscapedString(BaseConversion):
    """Defines the conversion which returns the result of running the
    python code, passed to init"""

    self_content_type = (
        BaseConversion.self_content_type
        & ~BaseConversion.ContentTypes.FUNCTION_OF_INPUT
    )
    weight = Weights.STEP

    def __init__(self, s: str):
        super().__init__()
        self.s = s

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return self.s


class ThisConversion(BaseConversion):
    """Defines the conversion which just returns the input.

    Also, provided that you use this inside comprehension conversions,
    it references an item from an iterator."""

    weight = 0

    def __call__(self) -> "ThisConversion":
        """To allow using it as singleton"""
        return self

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return code_input


This = ThisConversion()


class InputArg(BaseConversion):
    """Allows to use arguments passed into the compiled converter.

    Unless the `signature` argument is passed to `gen_converter` function, all
    input arguments used in the conversion definition will be expected as
    keyword-only arguments (affecting the resulting converter signature)."""

    self_content_type = (
        BaseConversion.self_content_type
        | BaseConversion.ContentTypes.ARG_USAGE
    ) & ~BaseConversion.ContentTypes.FUNCTION_OF_INPUT
    trackable_dependency = True
    weight = Weights.STEP

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
    ) & ~BaseConversion.ContentTypes.FUNCTION_OF_INPUT
    weight = Weights.DICT_LOOKUP

    labels_code_name = "_labels"

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
        return f"{self.labels_code_name}[{repr(self.label_name)}]"


class Namespace(BaseConversion):
    """Wrapping conversion which isolates :py:obj:`LazyEscapedString` (parent
    conversions won't detect them as dependencies) and defines code inputs for
    them"""

    weight = 0
    self_content_type = (
        BaseConversion.self_content_type
        & ~BaseConversion.ContentTypes.FUNCTION_OF_INPUT
    )

    def __init__(
        self,
        conversion: "t.Any",
        name_to_code: "t.Dict[str, t.Optional[t.Union[bool, str]]]",
    ):
        super().__init__()
        self.name_to_code = name_to_code
        self.conversion = self.ensure_conversion(conversion)

    def _gen_code_and_update_ctx(self, code_input, ctx):
        with NamespaceCtx(self.name_to_code, ctx):
            return self.conversion.gen_code_and_update_ctx(code_input, ctx)

    def is_dependency_trackable(self, dependency: "BaseConversion"):
        if (
            isinstance(dependency, LazyEscapedString)
            and dependency.name in self.name_to_code
        ):
            return False
        return super().is_dependency_trackable(dependency)


class FunctionCtx:
    """Defines a code generation context for a conversion, which is to help
    with wrapping a conversion code in a function so that all required
    arguments are both defines as parameters and passed properly. It also helps
    with adding additional parameters.

    Another important thing is that some parameters like LazyEscapedString are
    renamed and replaced with arguments of the new function. So it ensures (see
    prevent_rendering_while_active) that those lazy strings are not generating
    code while we are building inner function code (they just won't be
    available there).
    """

    def __init__(
        self,
        conversion,
        ctx,
        args_as_def_names,
        kwargs_as_def_names,
        args_to_pass,
        kwargs_to_pass,
        namespace_ctx,
        optimize_naive,
    ):
        self.conversion = conversion
        self.ctx = ctx
        self.args_as_def_names = args_as_def_names
        self.kwargs_as_def_names = kwargs_as_def_names
        self.args_to_pass = args_to_pass
        self.kwargs_to_pass = kwargs_to_pass
        self.namespace_ctx = namespace_ctx
        self.prev_names_to_warm_up = None
        self.optimize_naive = optimize_naive
        self.naive_to_optimize = None

    def gen_function(self, name, code):
        return self.conversion.compile_converter(
            converter_name=name,
            code=code,
            ctx=self.ctx,
        )

    def gen_conversion(self, name, code):
        self.gen_function(name, code)
        return EscapedString(name)

    def call_with_all_args(self, conversion):
        return conversion.call(*self.args_to_pass, **self.kwargs_to_pass)

    def add_arg(self, def_name, arg_to_pass=None, left=False):
        if left:
            self.args_as_def_names.appendleft(def_name)
            self.args_to_pass.appendleft(arg_to_pass)
        else:
            self.args_as_def_names.append(def_name)
            self.args_to_pass.append(arg_to_pass)

    def add_kwarg(self, def_name, arg_to_pass=None, left=False):
        if left:
            self.kwargs_as_def_names.appendleft(def_name)
        else:
            self.kwargs_as_def_names.append(def_name)
        self.kwargs_to_pass[def_name] = arg_to_pass

    def get_def_all_args_code(self):
        if self.optimize_naive and self.naive_to_optimize:
            kwargs_as_def_names = chain(
                self.kwargs_as_def_names,
                [
                    f"{name}=__naive_values__[{repr(name)}]"
                    for name in self.naive_to_optimize
                ],
            )
        else:
            kwargs_as_def_names = self.kwargs_as_def_names
        if kwargs_as_def_names:
            return ", ".join(
                chain(
                    self.args_as_def_names,
                    ("*",),
                    kwargs_as_def_names,
                )
            )
        return ", ".join(self.args_as_def_names)

    def __enter__(self):
        self.prev_names_to_warm_up = self.ctx[BaseConversion.NAIVE_TO_WARM_UP]
        if self.optimize_naive:
            self.naive_to_optimize = self.ctx[
                BaseConversion.NAIVE_TO_WARM_UP
            ] = set()
        else:
            self.ctx[BaseConversion.NAIVE_TO_WARM_UP] = None
        self.namespace_ctx.__enter__()

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.ctx[BaseConversion.NAIVE_TO_WARM_UP] = self.prev_names_to_warm_up
        return self.namespace_ctx.__exit__(exc_type, exc_value, exc_traceback)


class NamespaceCtx:
    """Context manager which defines code inputs for
    :py:obj:`LazyEscapedString`"""

    _name_to_code = None
    ctx = None
    active = False

    NAMESPACES = BaseConversion.NAMESPACES

    def __init__(self, name_to_code: "t.Dict[str, str]", ctx):
        name_to_code = {
            name: code for name, code in name_to_code.items() if code
        }
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
    weight = 0

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
        & ~BaseConversion.ContentTypes.FUNCTION_OF_INPUT
    )
    trackable_dependency = True
    weight = Weights.STEP

    def __init__(self, name):
        super().__init__()
        self.name = name

    def _gen_code_and_update_ctx(self, code_input, ctx):
        name_to_code = NamespaceCtx.name_to_code(ctx)
        if self.name in name_to_code:
            code = name_to_code[self.name]
            if code is True:
                return code_input
            if code:
                return code
            raise AssertionError("it's a bug")

        raise ValueError("LazyEscapedString is left uninitialized", self.name)


class OrAndEqBaseConversion(BaseConversion):
    """Base class of Or/And/Eq operator conversions"""

    self_content_type = (
        BaseConversion.self_content_type
        & ~BaseConversion.ContentTypes.FUNCTION_OF_INPUT
    )

    op = ""
    weight = Weights.LOGICAL

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


class Or(OrAndEqBaseConversion):
    """Takes any number of objects, each is to be wrapped with
    :py:obj:`ensure_conversion` and generates the code
    joining every argument with python ``or`` expression

    ``default`` defines behavior when args is empty
      * if None is empty will raise ValueError
      * false values - results in False
      * true values - results in True

    """

    op = " or "


class And(OrAndEqBaseConversion):
    """Takes any number of objects, each is to be wrapped with
    :py:obj:`ensure_conversion` and generates the code
    joining every argument with python ``and`` expression.

    ``default`` defines behavior when args is empty
      * if None is empty will raise ValueError
      * false values - results in False
      * true values - results in True

    """

    op = " and "


class Eq(OrAndEqBaseConversion):
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

    self_content_type = (
        BaseConversion.self_content_type
        & ~BaseConversion.ContentTypes.FUNCTION_OF_INPUT
    )
    weight = Weights.STEP

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

        this = This()

        if_cond = this if condition is True else ensure_conversion(condition)
        if_true = this if if_true is self._none else ensure_conversion(if_true)
        if_false = (
            this if if_false is self._none else ensure_conversion(if_false)
        )
        conversion = InlineExpr(
            "({if_true} if {if_cond} else {if_false})"
        ).pass_args(
            if_cond=if_cond,
            if_true=if_true,
            if_false=if_false,
        )
        conversion.number_of_input_uses = if_cond.number_of_input_uses + max(
            if_true.number_of_input_uses,
            if_false.number_of_input_uses,
        )
        conversion.total_weight = if_cond.total_weight + max(
            if_true.total_weight,
            if_false.total_weight,
        )

        if not no_input_caching:
            conversion = PipeConversion(this, conversion)

        self.conversion = self.ensure_conversion(conversion)

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return self.conversion.gen_code_and_update_ctx(code_input, ctx)


class IfMultiple(BaseConversion):
    """Builds a short-circuit conversion, which evaluates multiple conversions
    and stops at first true one:

    >>> converter = c.if_multiple(
    >>>     (c.this < 10, c.this / 2),
    >>>     (c.this == 10, None),
    >>>     else_=c.this * 2
    >>> ).gen_converter()

    is equivalent of:

    >>> def converter(data_):
    >>>     if data_ < 10:
    >>>         return data_ / 2
    >>>     if data_ == 10:
    >>>         return None
    >>>     return data_ * 2
    """

    self_content_type = (
        BaseConversion.self_content_type
        & ~BaseConversion.ContentTypes.FUNCTION_OF_INPUT
    )

    def __init__(self, *condition_to_value_pairs, else_):
        super().__init__()
        self.condition_to_value_pairs = [
            (self.ensure_conversion(condition), self.ensure_conversion(value))
            for condition, value in condition_to_value_pairs
        ]
        self.else_ = self.ensure_conversion(else_)

    def _gen_code_and_update_ctx(self, code_input, ctx):
        code = Code()
        suffix = self.gen_random_name("_", ctx)
        converter_name = f"if_multiple{suffix}"
        function_ctx = self.as_function_ctx(ctx, optimize_naive=True)
        function_ctx.add_arg("data_", This())
        with function_ctx:
            code.add_line("def placeholder", 1)
            for condition, value in self.condition_to_value_pairs:
                condition_code = condition.gen_code_and_update_ctx(
                    "data_", ctx
                )
                value_code = value.gen_code_and_update_ctx("data_", ctx)
                code.add_line(f"if {condition_code}:", 1)
                code.add_line(f"return {value_code}", -1)
            else_code = self.else_.gen_code_and_update_ctx("data_", ctx)
            code.add_line(f"return {else_code}", -1)

            code.lines_info[0] = (
                0,
                f"def {converter_name}({function_ctx.get_def_all_args_code()}):",
            )
            conversion = function_ctx.gen_conversion(
                converter_name, code.to_string(0)
            )
        return function_ctx.call_with_all_args(
            conversion
        ).gen_code_and_update_ctx(code_input, ctx)


class Not(BaseConversion):
    """Conversion which applies not operator to its input"""

    self_content_type = (
        BaseConversion.self_content_type
        & ~BaseConversion.ContentTypes.FUNCTION_OF_INPUT
    )
    weight = Weights.LOGICAL

    def __init__(self, arg):
        super().__init__()
        self.arg = self.ensure_conversion(arg)

    def _gen_code_and_update_ctx(self, code_input, ctx):
        code = self.arg.gen_code_and_update_ctx(code_input, ctx)
        return f"(not {code})"


class InlineExpr(BaseConversion):
    """This conversion allows to avoid function call overhead.  It inlines a
    raw python code expression into the code of resulting conversion."""

    self_content_type = (
        BaseConversion.self_content_type
        & ~BaseConversion.ContentTypes.FUNCTION_OF_INPUT
    )

    def __init__(
        self, code_str, weight=Weights.UNPREDICTABLE, args=None, kwargs=None
    ):
        """
        Args:
          code_str (str): python code string. Supports `{}` expressions of
            :py:obj:`str.format`, both positional and names ones.
            To pass arguments, use :py:obj:`InlineExpr.pass_args`
        """
        self.weight = weight
        super().__init__()
        self.code_str = code_str
        self.args = (
            [self.ensure_conversion(arg) for arg in args] if args else []
        )
        self.kwargs = (
            {k: self.ensure_conversion(v) for k, v in kwargs.items()}
            if kwargs
            else {}
        )

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
        return InlineExpr(self.code_str, self.weight, args, kwargs)

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


get_exceptions = (TypeError, KeyError, IndexError)


def get_1_or_default(data_, key_, default_):
    try:
        return data_[key_]
    except get_exceptions:
        return default_


def get_2_or_default(data_, key_1, key_2, default_):
    try:
        return data_[key_1][key_2]
    except get_exceptions:
        return default_


def get_3_or_default(data_, key_1, key_2, key_3, default_):
    try:
        return data_[key_1][key_2][key_3]
    except get_exceptions:
        return default_


GET_ITEM_OR_DEFAULT_TEMPLATE = """
def {converter_name}({code_args}):
    try:
        return {get_or_default_code}
    except (TypeError, KeyError, IndexError):
        return {default_code}
"""
GET_ATTR_OR_DEFAULT_TEMPLATE = """
def {converter_name}({code_args}):
    try:
        return {get_or_default_code}
    except AttributeError:
        return {default_code}
"""


class GetItem(BaseMethodConversion):
    """``GetItem`` gets compiled into the code which does
    dictionary/index lookups.

    If called without params, just returns the input.

    If an index is a conversion itself, then it is being calculated
    against an input."""

    prefix = "item_or_default"
    weight = Weights.DICT_LOOKUP
    caching_is_possible = True
    template = GET_ITEM_OR_DEFAULT_TEMPLATE

    get_or_default_functions = [
        get_1_or_default,
        get_2_or_default,
        get_3_or_default,
    ]
    naive_or_unsafe_conversions = (NaiveConversion, EscapedString, InlineExpr)

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
        self.total_weight += (len(self.indexes) - 1) * self.weight + (
            0 if self.default is None else Weights.FUNCTION_CALL
        )

        self.indexes_are_simple = not any(
            # self.ContentTypes.FUNCTION_OF_INPUT
            index.contents & 64
            for index in self.indexes
        )
        # self.ContentTypes.FUNCTION_OF_INPUT
        self.default_is_simple = (
            self.default is None or self.default.contents & 64 == 0
        )
        self.default_is_naive_or_unsafe = isinstance(
            self.default, self.naive_or_unsafe_conversions
        )

        self.hardcoded_version = self.get_hardcoded_version()
        if self.hardcoded_version:
            self.total_weight = self.hardcoded_version.total_weight
            self.contents = self.hardcoded_version.contents

    def get_hardcoded_version(self):
        indexes_length = len(self.indexes)
        if indexes_length == 0:
            return This()

        if self.default is None:
            return

        if (
            indexes_length < 4
            and self.indexes_are_simple
            and self.default_is_naive_or_unsafe
        ):
            return CallFunc(
                self.get_or_default_functions[indexes_length - 1],
                (This() if self.self_conv is self._none else self.self_conv),
                *self.indexes,
                self.default,
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

        if self.hardcoded_version is not None:
            return self.hardcoded_version.gen_code_and_update_ctx(
                code_input, ctx
            )

        function_ctx = self.as_function_ctx(ctx, optimize_naive=True)
        with function_ctx:
            do_caching = self.caching_is_possible

            # default
            if self.default_is_simple:
                if self.default_is_naive_or_unsafe:
                    default_code = "default_"
                    function_ctx.add_arg(default_code, self.default)
                else:
                    default_code = self.default.gen_code_and_update_ctx(
                        "not needed", ctx
                    )

            else:
                do_caching = False
                default_code = self.default.gen_code_and_update_ctx(
                    "data_", ctx
                )

            # data_
            if (
                code_self == code_input
                or not self.indexes_are_simple
                or not self.default_is_simple
            ):
                function_ctx.add_arg("data_", This())

            # self_
            if code_self != code_input:
                code_output = "self_"
                function_ctx.add_arg(code_output, EscapedString(code_self))
            else:
                code_output = "data_"

            # indexes
            if self.indexes_are_simple and self.caching_is_possible:
                for i, index in enumerate(self.indexes):
                    var_index = f"index_{i}"
                    function_ctx.add_arg(var_index, index)
                    code_output = self.wrap_path_item(code_output, var_index)

            else:
                do_caching = False
                for i, index in enumerate(self.indexes):
                    code_output = self.wrap_path_item(
                        code_output,
                        index.gen_code_and_update_ctx("data_", ctx),
                    )

            key = (
                (
                    self.prefix,
                    tuple(function_ctx.args_as_def_names),
                    default_code,
                )
                if do_caching
                else None
            )

            if do_caching and key in ctx[self.CONVERTERS_CACHE]:
                converter_name = ctx[self.CONVERTERS_CACHE][key]
            else:
                converter_name = self.gen_random_name(self.prefix, ctx)
                converter_code = self.template.format(
                    code_args=function_ctx.get_def_all_args_code(),
                    converter_name=converter_name,
                    get_or_default_code=code_output,
                    default_code=default_code,
                )
                function_ctx.gen_function(converter_name, converter_code)
                if do_caching:
                    ctx[self.CONVERTERS_CACHE][key] = converter_name

        return function_ctx.call_with_all_args(
            EscapedString(converter_name)
        ).gen_code_and_update_ctx(code_input, ctx)


class GetAttr(GetItem):
    """``GetAttr`` gets compiled into the code which runs getattr.
    If called without params, just returns the input.

    If an index is a conversion itself, then it is being calculated
    against an input."""

    valid_attr = re.compile(r"^'[A-Za-z_][a-zA-Z0-9_]*'$")
    prefix = "attr_or_default"
    weight = Weights.ATTR_LOOKUP
    caching_is_possible = False
    template = GET_ATTR_OR_DEFAULT_TEMPLATE

    def wrap_path_item(self, code_input, path_item):
        if self.valid_attr.match(path_item):
            return f"{code_input}.{path_item[1:-1]}"
        return f"getattr({code_input}, {path_item})"

    def get_hardcoded_version(self):
        return


class Call(BaseMethodConversion):
    """This conversion writes the code which takes the input code and calls it
    as a function.
    It takes both positional and keyword arguments to be passed.
    """

    self_content_type = (
        BaseConversion.self_content_type
        & ~BaseConversion.ContentTypes.FUNCTION_OF_INPUT
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


class GeneratorItem:
    """Internal use only - defines a conversion of each element of a
    comprehension"""

    __slots__ = ["item", "custom_for_params"]

    def __init__(self, item, *custom_for_params):
        self.item = ensure_conversion(item)
        self.custom_for_params = tuple(
            ensure_conversion(param) for param in custom_for_params
        )

    @classmethod
    def ensure_type(cls, item):
        if isinstance(item, GeneratorItem):
            return item
        return cls(item)

    def _replace(self, item):
        return GeneratorItem(item, *self.custom_for_params)


class BaseComp(BaseMethodConversion):
    """Base conversion of non-dict comprehension"""

    def __init__(
        self,
        generator_item,
        where,
        self_conv,
    ):
        """
        Args:
          item (object): to be wrapped with :py:obj:`ensure_conversion`
            and used as a conversion on each item of a collection.
          where: conversion to be used in ``if`` clause of a comprehension

            e.g. for ``[i * 2 for i in l if i > 0]`` an item would be
            ``c.generator_comp(c.this * 2, where=c.this > 0)``
        """
        super().__init__(self_conv)

        self.generator_item = GeneratorItem.ensure_type(generator_item)
        self.depends_on(self.generator_item.item)

        for param in self.generator_item.custom_for_params:
            self.depends_on(param)

        self.where = (
            _none
            if (where is None or where is _none)
            else self.ensure_conversion(where)
        )
        self.number_of_input_uses = 1

    def get_item_n_param_codes(self, ctx):
        if self.generator_item.custom_for_params:
            param_code = ", ".join(
                param.gen_code_and_update_ctx(None, ctx)
                for param in self.generator_item.custom_for_params
            )
            item_code = self.generator_item.item.gen_code_and_update_ctx(
                None, ctx
            )
        else:
            param_code = self.gen_random_name("i", ctx)
            item_code = self.generator_item.item.gen_code_and_update_ctx(
                param_code, ctx
            )
        return item_code, param_code

    def get_iterable_code(self, code_input, ctx):
        code_self, _ = self.get_self_and_input_code(code_input, ctx)
        return code_self


class GeneratorComp(BaseComp):
    """Generates python generator comprehension code."""

    def _gen_code_and_update_ctx(self, code_input, ctx):
        item_code, param_code = self.get_item_n_param_codes(ctx)
        code_iterable = self.get_iterable_code(code_input, ctx)

        if self.where is _none:
            return f"({item_code} for {param_code} in {code_iterable})"

        condition_code = self.where.gen_code_and_update_ctx(param_code, ctx)
        return f"({item_code} for {param_code} in {code_iterable} if {condition_code})"

    def to_iter(self):
        return self

    def iter(self, element_conv, *, where=None) -> "BaseConversion":
        where = _none if (where is None or where is _none) else where

        cannot_consume = self.generator_item.item is not This and (
            where is not _none
            or ensure_conversion(element_conv).number_of_input_uses >= 2
        )
        if cannot_consume:
            return super().iter(element_conv, where=where)

        where_conditions = []
        if self.where is not _none:
            where_conditions.append(self.where)
        if where is not _none:
            where_conditions.append(where)

        return GeneratorComp(
            (
                self.generator_item
                if element_conv is This
                else self.generator_item._replace(
                    self.generator_item.item.pipe(element_conv)
                )
            ),
            And(*where_conditions) if where_conditions else _none,
            self.self_conv,
        )

    def as_type(self, callable_):
        value = NaiveConversion.get_value(callable_)
        if value is list:
            return ListComp(
                self.generator_item, where=self.where, self_conv=self.self_conv
            )
        elif value is tuple:
            return TupleComp(
                self.generator_item, where=self.where, self_conv=self.self_conv
            )
        elif value is set:
            return SetComp(
                self.generator_item, where=self.where, self_conv=self.self_conv
            )
        return super().as_type(callable_)


class SetComp(BaseComp):
    """Generates python set comprehension code (obviously non-sortable)"""

    base_type_to_cast = set

    def _gen_code_and_update_ctx(self, code_input, ctx):
        item_code, param_code = self.get_item_n_param_codes(ctx)
        code_iterable = self.get_iterable_code(code_input, ctx)

        if self.where is _none:
            return f"{{{item_code} for {param_code} in {code_iterable}}}"

        condition_code = self.where.gen_code_and_update_ctx(param_code, ctx)
        return f"{{{item_code} for {param_code} in {code_iterable} if {condition_code}}}"

    def as_type(self, callable_):
        if NaiveConversion.get_value(callable_) is set:
            return self
        return super().as_type(callable_)


class ListComp(BaseComp):
    """Generates python list comprehension code."""

    base_type_to_cast = list

    def _gen_code_and_update_ctx(self, code_input, ctx):
        item_code, param_code = self.get_item_n_param_codes(ctx)
        code_iterable = self.get_iterable_code(code_input, ctx)

        if self.where is _none:
            return f"[{item_code} for {param_code} in {code_iterable}]"

        condition_code = self.where.gen_code_and_update_ctx(param_code, ctx)
        return f"[{item_code} for {param_code} in {code_iterable} if {condition_code}]"

    def to_iter(self):
        return GeneratorComp(self.generator_item, self.where, self.self_conv)

    def iter(self, element_conv, *, where=None) -> "BaseConversion":
        return self.to_iter().iter(element_conv, where=where)

    def as_type(self, callable_):
        if NaiveConversion.get_value(callable_) is list:
            return self
        return self.to_iter().as_type(callable_)

    def sort(self, key=None, reverse=False) -> "BaseConversion":
        return self.to_iter().sort(key, reverse)


class TupleComp(BaseComp):
    """Generates python tuple comprehension code."""

    base_type_to_cast = tuple

    def _gen_code_and_update_ctx(self, code_input, ctx):
        item_code, param_code = self.get_item_n_param_codes(ctx)
        code_iterable = self.get_iterable_code(code_input, ctx)

        if self.where is _none:
            return f"tuple({item_code} for {param_code} in {code_iterable})"

        condition_code = self.where.gen_code_and_update_ctx(param_code, ctx)
        return f"tuple({item_code} for {param_code} in {code_iterable} if {condition_code})"

    def to_iter(self):
        return GeneratorComp(self.generator_item, self.where, self.self_conv)

    def iter(self, element_conv, *, where=None) -> "BaseConversion":
        return self.to_iter().iter(element_conv, where=where)

    def as_type(self, callable_):
        if NaiveConversion.get_value(callable_) is tuple:
            return self
        return self.to_iter().as_type(callable_)

    def sort(self, key=None, reverse=False) -> "BaseConversion":
        return self.to_iter().sort(key, reverse).as_type(tuple)


class DictComp(BaseMethodConversion):
    """Generates python dict comprehension code."""

    def __init__(self, key, value, where, self_conv):
        """
        Args:
          key (object): to be wrapped with :py:obj:`ensure_conversion` and
            used on each item of a collection to form keys
          value (object): to be wrapped with :py:obj:`ensure_conversion` and
            used on each item of a collection to form values
        """
        super().__init__(self_conv)
        self.key = self.ensure_conversion(key)
        self.value = self.ensure_conversion(value)
        self.where = (
            _none
            if (where is None or where is _none)
            else self.ensure_conversion(where)
        )
        self.number_of_input_uses = 1

    def _gen_code_and_update_ctx(self, code_input, ctx):
        param_code = self.gen_random_name("i", ctx)
        key_code = self.key.gen_code_and_update_ctx(param_code, ctx)
        value_code = self.value.gen_code_and_update_ctx(param_code, ctx)
        code_iterable = BaseComp.get_iterable_code(self, code_input, ctx)
        if self.where is _none:
            return f"{{{key_code}: {value_code} for {param_code} in {code_iterable}}}"

        condition_code = self.where.gen_code_and_update_ctx(param_code, ctx)
        return f"{{{key_code}: {value_code} for {param_code} in {code_iterable} if {condition_code}}}"

    def filter(self, condition_conv, cast=BaseConversion._none):
        if cast is self._none:
            cast = dict
        return self.call_method("items").filter(condition_conv, cast=dict)

    def sort(self, key=None, reverse=False) -> "BaseConversion":
        return self.call_method("items").sort(key, reverse).as_type(dict)


class BaseCollectionConversion(BaseConversion):
    """This is a base conversion of every collection"""

    self_content_type = (
        BaseConversion.self_content_type
        & ~BaseConversion.ContentTypes.FUNCTION_OF_INPUT
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
        converter_name = self.gen_random_name("optional_items_generator", ctx)
        function_ctx = self.as_function_ctx(ctx, optimize_naive=True)
        function_ctx.add_arg("data_", This())
        with function_ctx:
            code.add_line("def placeholder", 1)

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

    def gen_joined_items_code(self, code_input, ctx):
        return ("," if len(self.items) < 3 else ",\n").join(
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

    weight = Weights.TUPLE_INIT

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

    weight = Weights.LIST_INIT

    def gen_collection_from_items_code(
        self, joined_items_code, code_input, ctx
    ):
        return f"[{joined_items_code}]"

    def gen_collection_from_generator(self, generator_code, code_input, ctx):
        return f"list({generator_code})"


class Set(BaseCollectionConversion):
    """Gets compiled into the code which generates a set"""

    weight = Weights.SET_INIT

    def gen_collection_from_items_code(
        self, joined_items_code, code_input, ctx
    ):
        return f"{{{joined_items_code}}}"

    def gen_collection_from_generator(self, generator_code, code_input, ctx):
        return f"set({generator_code})"


class Dict(BaseCollectionConversion):
    """Gets compiled into the code which generates a dict"""

    weight = Weights.DICT_INIT

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
        return ("," if len(self.key_value_pairs) < 3 else ",\n").join(
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
        suffix = self.gen_random_name("_", ctx)
        converter_name = f"take_while{suffix}"
        var_it = f"it{suffix}"
        var_item = f"item{suffix}"

        function_ctx = self.as_function_ctx(ctx, optimize_naive=True)
        function_ctx.add_arg(var_it, This())
        with function_ctx:
            condition_code = self.condition.gen_code_and_update_ctx(
                var_item, ctx
            )

            code = Code()
            code.add_line("def placeholder", 1)
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

            code.lines_info[0] = (
                0,
                f"def {converter_name}({function_ctx.get_def_all_args_code()}):",
            )
            conversion = function_ctx.gen_conversion(
                converter_name, code.to_string(0)
            )

        conversion = function_ctx.call_with_all_args(conversion)
        if self.cast is not self._none:
            conversion = conversion.as_type(self.cast)
        return conversion.gen_code_and_update_ctx(code_input, ctx)


class DropWhile(BaseConversion):
    """convtools implementation of :py:obj:`itertools.dropwhile`"""

    def __init__(self, condition):
        super().__init__()
        self.condition = self.ensure_conversion(condition)
        self.filter_results_conditions = None
        self.cast = self._none

    def _gen_code_and_update_ctx(self, code_input, ctx):
        suffix = self.gen_random_name("_", ctx)
        converter_name = f"drop_while{suffix}"
        var_it = f"it{suffix}"
        var_item = f"item{suffix}"

        function_ctx = self.as_function_ctx(ctx, optimize_naive=True)
        function_ctx.add_arg(var_it, This())
        with function_ctx:
            condition_code = self.condition.gen_code_and_update_ctx(
                var_item, ctx
            )

            code = Code()
            code.add_line("def placeholder", 1)
            code.add_line(f"{var_it} = iter({var_it})", 0)
            code.add_line(f"for {var_item} in {var_it}:", 1)
            code.add_line(f"if not ({condition_code}):", 1)
            code.add_line("break", -2)
            code.add_line("else:", 1)
            code.add_line("return ()", -1)
            var_chain = NaiveConversion(chain).gen_code_and_update_ctx(
                "not needed", ctx
            )
            code.add_line(f"return {var_chain}(({var_item},), {var_it})", -1)

            code.lines_info[0] = (
                0,
                f"def {converter_name}({function_ctx.get_def_all_args_code()}):",
            )
            conversion = function_ctx.gen_conversion(
                converter_name, code.to_string(0)
            )

        return function_ctx.call_with_all_args(
            conversion
        ).gen_code_and_update_ctx(code_input, ctx)


def delegate_simple_0_args(name):
    def method(self):
        if self.label_output is None:
            return self._replace(getattr(self.where, name)())
        return getattr(super(self.__class__, self), name)()

    return method


def delegate_simple_1_arg(name):
    def method(self, arg):
        if self.label_output is None and (
            self.what is This
            or ensure_conversion(arg).number_of_input_uses == 0
        ):
            return self._replace(getattr(self.where, name)(arg))
        return getattr(super(self.__class__, self), name)(arg)

    return method


def delegate_input_switching_method(name):
    def method(self, *args, **kwargs):
        if self.label_output is None:
            return self._replace(getattr(self.where, name)(*args, **kwargs))
        return getattr(super(self.__class__, self), name)(*args, **kwargs)

    return method


class PipeConversion(BaseConversion):
    """Passes the result of one conversion as an input to another.  If
    `next_conversion` is callable, it gets called with the previous result
    passed as the first param.

    Supports predicate/sorting/type casting push down (each is directly applied
    to the ``where`` conversion.

    Supports labeling both pipe input and output data (allows to apply
    conversions before labeling)."""

    weight = 0
    function_call_threshold = Weights.FUNCTION_CALL * 1.33
    self_content_type = (
        BaseConversion.self_content_type
    ) & ~BaseConversion.ContentTypes.FUNCTION_OF_INPUT

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
        what = ensure_conversion(what)
        where = ensure_conversion(where)

        if where.is_itself_callable():
            where = where.call(This(), *args, **kwargs)

        elif args or kwargs:
            raise AssertionError(
                "args or kwargs won't be used when 'where' is not callable"
            )

        if (
            where.contents & 1 and what.contents & 1
        ):  # self.ContentTypes.REDUCER
            raise ValueError("nested aggregation", self.__dict__)

        if not where.valid_pipe_output:
            raise ValueError("invalid output, check where conversion")

        if (
            # self.ContentTypes.NEW_LABEL
            (what.contents & 4)
            or label_input
        ) and (
            where.contents & 1  # self.ContentTypes.REDUCER
        ):
            raise ValueError("labeling of reducer inputs is not supported")

        self.input_args_container = EscapedString("None")
        self.label_input = (
            None
            if label_input is None
            else self._prepare_labels(self.input_args_container, label_input)
        )
        self.label_output = (
            None
            if label_output is None
            else self._prepare_labels(self.input_args_container, label_output)
        )
        input_has_no_side_effects = (
            what.contents & 4 == 0  # self.ContentTypes.NEW_LABEL
            and self.label_input is None
        )
        self.to_be_inlined = (
            # can be inlined
            (
                (
                    # if "where" uses an input multiple times, we should weigh
                    # wrapping it into a function and so the input is calculated
                    # only once (of course taking into account function call
                    # overhead)
                    what.total_weight * (where.number_of_input_uses - 1)
                    < self.function_call_threshold
                )
                and self.label_output is None
                and input_has_no_side_effects
            )
            # must be inlined - self.ContentTypes.REDUCER
            or where.contents & 1
        )

        if not self.to_be_inlined:
            if where.ignores_input() and input_has_no_side_effects:
                what, where = where, This()

            self.input_args_container.ensure_conversion(where)
            self.total_weight += Weights.FUNCTION_CALL
            self.number_of_input_uses = 1

        self.what = self.ensure_conversion(what)
        self.where = self.ensure_conversion(where)
        self.ensure_conversion(self.input_args_container)

        if self.label_input or self.label_output:
            self.input_args_container.contents |= (
                4  # self.ContentTypes.NEW_LABEL
            )
            self.contents |= 4  # self.ContentTypes.NEW_LABEL

    def _replace(self, where):
        if self.label_output:
            raise AssertionError("it's a bug")
        return PipeConversion(
            self.what,
            where,
            label_input=self.label_input,
            label_output=self.label_output,
        )

    def __hash__(self):
        return id(self)

    __add__ = delegate_simple_1_arg("__add__")
    add = delegate_simple_1_arg("add")
    __and__ = delegate_simple_1_arg("__and__")
    __eq__ = delegate_simple_1_arg("__eq__")
    __floordiv__ = delegate_simple_1_arg("__floordiv__")
    floor_div = delegate_simple_1_arg("floor_div")
    __ge__ = delegate_simple_1_arg("__ge__")
    gte = delegate_simple_1_arg("gte")
    __gt__ = delegate_simple_1_arg("__gt__")
    gt = delegate_simple_1_arg("gt")
    __le__ = delegate_simple_1_arg("__le__")
    lte = delegate_simple_1_arg("lte")
    __lt__ = delegate_simple_1_arg("__lt__")
    lt = delegate_simple_1_arg("lt")
    __mod__ = delegate_simple_1_arg("__mod__")
    mod = delegate_simple_1_arg("mod")
    __mul__ = delegate_simple_1_arg("__mul__")
    mul = delegate_simple_1_arg("mul")
    __ne__ = delegate_simple_1_arg("__ne__")
    not_eq = delegate_simple_1_arg("not_eq")
    __or__ = delegate_simple_1_arg("__or__")
    __sub__ = delegate_simple_1_arg("__sub__")
    sub = delegate_simple_1_arg("sub")
    __truediv__ = delegate_simple_1_arg("__truediv__")
    div = delegate_simple_1_arg("div")
    as_type = delegate_simple_1_arg("as_type")
    in_ = delegate_simple_1_arg("in_")
    not_in = delegate_simple_1_arg("not_in")
    is_ = delegate_simple_1_arg("is_")
    is_not = delegate_simple_1_arg("is_not")

    __neg__ = delegate_simple_0_args("__neg__")
    neg = delegate_simple_0_args("neg")
    __invert__ = delegate_simple_0_args("__invert__")
    not_ = delegate_simple_0_args("not_")
    flatten = delegate_simple_0_args("flatten")
    len = delegate_simple_0_args("len")

    iter = delegate_input_switching_method("iter")
    iter_mut = delegate_input_switching_method("iter_mut")
    iter_windows = delegate_input_switching_method("iter_windows")
    filter = delegate_input_switching_method("filter")
    pipe = delegate_input_switching_method("pipe")
    drop_while = delegate_input_switching_method("drop_while")
    take_while = delegate_input_switching_method("take_while")
    tap = delegate_input_switching_method("tap")

    @staticmethod
    def _prepare_labels(
        conversion: "BaseConversion",
        label_arg: "t.Union[str, dict]",
    ):
        if isinstance(label_arg, str):
            return {label_arg: This()}

        elif isinstance(label_arg, dict):
            return {
                label_name: conversion.ensure_conversion(conv)
                for label_name, conv in label_arg.items()
            }

        raise ConversionException(
            "unexpected label_input type", type(label_arg), label_arg
        )

    def _gen_code_and_update_ctx(self, code_input, ctx):
        if self.to_be_inlined:
            return self.where.gen_code_and_update_ctx(
                self.what.gen_code_and_update_ctx(code_input, ctx), ctx
            )

        suffix = self.gen_random_name("_", ctx)
        converter_name = f"pipe{suffix}"
        var_result = f"result{suffix}"
        var_input = f"input{suffix}"

        function_ctx = self.input_args_container.as_function_ctx(
            ctx, optimize_naive=True
        )

        what_code = self.what.gen_code_and_update_ctx(code_input, ctx)
        with function_ctx:
            where_code = self.where.gen_code_and_update_ctx(var_input, ctx)
            function_ctx.add_arg(var_input, EscapedString(what_code))
            code = Code()
            code.add_line("def placeholder", 1)

            if self.label_input:
                for label_name, label_c in self.label_input.items():
                    code.add_line(
                        f"{LabelConversion.labels_code_name}['{label_name}'] = "
                        f"{label_c.gen_code_and_update_ctx(var_input, ctx)}",
                        0,
                    )
            if self.label_output:
                code.add_line(f"{var_result} = {where_code}", 0)
                for label_name, label_c in self.label_output.items():
                    code.add_line(
                        f"{LabelConversion.labels_code_name}['{label_name}'] = "
                        f"{label_c.gen_code_and_update_ctx(var_result, ctx)}",
                        0,
                    )
                code.add_line(f"return {var_result}", 0)
            else:
                code.add_line(f"return {where_code}", 0)

            code.lines_info[0] = (
                0,
                f"def {converter_name}({function_ctx.get_def_all_args_code()}):",
            )

            conversion = function_ctx.gen_conversion(
                converter_name, code.to_string(0)
            )

        return function_ctx.call_with_all_args(
            conversion
        ).gen_code_and_update_ctx(None, ctx)
