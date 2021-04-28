"""
Base and basic conversions are defined here.
"""
import linecache
import re
import string
import sys
import typing
from collections import OrderedDict
from itertools import chain, count
from random import choice
from types import GeneratorType

from .utils import BaseCtx, BaseOptions, RUCache


try:
    import black
except ImportError:
    pass


def clean_line_cache(key, _):
    try:
        del linecache.cache[key]
    except KeyError:
        pass


class _ConverterCallable:
    """A wrapper which collects all source code, generated every conversion,
    used in the main converter.

    If an exception is raised, it populates the linecache for beautiful
    stacktraces and easy pdb debugging.  If black is installed, it's applied to
    the code.
    """

    linecache_keys = RUCache(1000, clean_line_cache)

    def __init__(self, ctx, debug=None):
        self._fake_filename_to_code_str = {}
        self._ctx = ctx
        self._debug = debug

        self._main_converter = None
        self.__name__ = "not_defined_yet"

    def add_sources(self, fake_filename, code_str):
        code_str_is_new = fake_filename not in self._fake_filename_to_code_str
        if (
            not code_str_is_new
            and self._fake_filename_to_code_str[fake_filename] != code_str
        ):
            raise Exception("fake_filename already exists", fake_filename)
        self._fake_filename_to_code_str[fake_filename] = code_str
        if self._debug and code_str_is_new:
            print("\n", code_str)

    def set_main_converter(self, converter):
        self._main_converter = converter
        self.__name__ = getattr(self._main_converter, "__name__", "")
        if self._debug:
            self.populate_line_cache()

    def __get__(self, instance, cls):
        return _ConverterCallableMethod(self, instance, cls)

    def __call__(self, *args, **kwargs):
        drop_labels_now = True
        try:
            result = self._main_converter(*args, **kwargs)
            if isinstance(result, GeneratorType):
                drop_labels_now = False
                return self.wrap_generator_clean_labels_on_exit(result)
            return result
        except (Exception, KeyboardInterrupt):
            # definitely not generator
            self.populate_line_cache()
            raise
        finally:
            if drop_labels_now:
                labels_ = self._ctx["labels_"]
                if labels_:
                    for key in list(labels_):
                        del labels_[key]

    def wrap_generator_clean_labels_on_exit(self, generator_):
        try:
            yield from generator_
        except Exception:
            self.populate_line_cache()
            raise
        finally:
            labels_ = self._ctx["labels_"]
            if labels_:
                for key in list(labels_):
                    del labels_[key]

    def populate_line_cache(self):
        for fake_filename, code_str in self._fake_filename_to_code_str.items():
            if self.linecache_keys.has(fake_filename, bump_up=True):
                continue

            linecache.cache[fake_filename] = (
                len(code_str),
                None,
                code_str.splitlines(True),
                fake_filename,
            )
            self.linecache_keys.set(fake_filename, True)


class _ConverterCallableMethod:
    __slots__ = ["converter_callable", "instance_or_cls"]

    def __init__(self, converter_callable, instance, cls):
        self.converter_callable = converter_callable
        self.instance_or_cls = instance or cls

    def __call__(self, *args, **kwargs):
        return self.converter_callable(self.instance_or_cls, *args, **kwargs)


class CodeGenerationOptions(BaseOptions):
    labeling = False
    expressions_only = False
    converter_callable_cls = _ConverterCallable


class CodeGenerationOptionsCtx(BaseCtx):
    options_cls = CodeGenerationOptions


class ConverterOptions(BaseOptions):
    """Converter options (+ see default values below):

    * ``debug = False`` - same as ``.gen_converter(debug=...)``
    * ``max_pipe_length = 100``

    """

    debug = False
    max_pipe_length = 100


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
    global add_label_, get_by_label_
{code}
"""


GET_OR_DEFAULT_TEMPLATE = """
def {converter_name}({code_args}):
    global add_label_, get_by_label_
    try:
        return {get_or_default_code}
    except (TypeError, KeyError, IndexError, AttributeError):
        return default_
"""


def ensure_conversion(
    conversion: typing.Any, accept_mutations=False
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
        if not accept_mutations and isinstance(conversion, BaseMutation):
            raise Exception("BaseMutation instances are not allowed")
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


CT = typing.TypeVar("CT", bound="BaseConversion")
MCT = typing.TypeVar("MCT", bound="BaseMethodConversion")


class _None:
    """Custom None type for the sake of typing AND ability to tell None passed
    instead of default value to an optional parameter"""

    pass


class BaseConversion(typing.Generic[CT, MCT]):
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
    counter = count()
    max_counter = 2 ** 30
    valid_pipe_output = True
    method_calls_override_input = False
    multi_step_calculation = False

    def __init__(self):
        self.number = self._gen_number()
        self._depends_on = {}
        self._predefined_input = None

    def __hash__(self):
        return id(self)

    def _gen_number(self):
        number = next(self.counter)
        if number > self.max_counter:
            BaseConversion.counter = count()
        return number

    @property
    def max_pipe_length(self):
        return ConverterOptionsCtx.get_option_value("max_pipe_length")

    def _add_dependency(self, dep):
        self._depends_on[dep.number] = dep

    def _delete_dependency(self, dep):
        del self._depends_on[dep.number]

    def set_dependencies(self, deps):
        self._depends_on = dict(deps.items())

    def depends_on(self, *args):
        for arg in args:
            for dep in arg.get_dependencies():
                self._add_dependency(dep)
        return self

    def get_dependencies(self, types=None, exclude_types=None):
        deps = self._depends_on.values()
        deps = chain(deps, (self,))
        if types:
            deps = (dep for dep in deps if isinstance(dep, types))
        if exclude_types:
            deps = (dep for dep in deps if not isinstance(dep, exclude_types))
        return deps

    def ensure_conversion(self, conversion, **kwargs) -> CT:
        """Runs ensure_conversion on the input object and adds the resulting
        conversion to the list of dependencies"""
        conversion = ensure_conversion(conversion, **kwargs)
        self.depends_on(conversion)
        return conversion

    def clone(self: CT) -> CT:
        clone: CT = self.__class__.__new__(self.__class__)
        clone.__dict__.update(self.__dict__)
        clone.number = self._gen_number()
        clone.set_dependencies(self._depends_on)
        return clone

    def _set_predefined_input(self: CT, input_conversion: CT) -> CT:
        cloned_self = self.clone()
        cloned_self.depends_on(input_conversion)
        cloned_self._predefined_input = input_conversion
        return cloned_self

    def set_predefined_input(self: CT, input_conversion) -> CT:
        conversions_chain = []
        conversion = self
        for _ in range(self.max_pipe_length - 1):
            conversions_chain.append(conversion)
            if conversion._predefined_input is None:
                break
            conversion = conversion._predefined_input
        else:
            raise ConversionException("failed to set predefined_input", self)

        input_conversion = ensure_conversion(input_conversion)
        dependencies_to_be_dropped = []  # type: typing.List[CT]
        for conversion in reversed(conversions_chain):
            # pylint: disable=protected-access
            input_conversion = conversion._set_predefined_input(
                input_conversion
            )
            for dep in dependencies_to_be_dropped:
                input_conversion._delete_dependency(dep)
            dependencies_to_be_dropped.append(conversion)
        return input_conversion

    def gen_code_and_update_ctx(self, code_input, ctx) -> str:
        """The main method which generates the code and stores necessary info
        in the context (which will be passed as locals() and globals() on to
        the exec function).  However you should not override this method
        directly, please implement the `_gen_code_and_update_ctx` one.

        Also there's a tricky thing here: there's a chance every conversion
        down the pipe has the predefined input set, while we do have the code
        input which needs to be run (e.g. it has side effects, like adding
        labels).  Then we attach the code anyway, see below."""
        code_to_be_attached = None
        if self._predefined_input is not None:
            code_input = self._predefined_input.gen_code_and_update_ctx(
                code_input, ctx
            )
            if not If.input_is_simple(code_input):
                code_to_be_attached = code_input
        resulting_code = self._gen_code_and_update_ctx(code_input, ctx)
        if (
            not self.multi_step_calculation
            and code_to_be_attached
            and code_to_be_attached not in resulting_code
        ):
            return "({} and None or {})".format(
                code_to_be_attached, resulting_code
            )
        return resulting_code

    def _gen_code_and_update_ctx(self, code_input, ctx) -> str:
        raise NotImplementedError

    allowed_symbols = string.ascii_lowercase + string.digits

    def gen_name(self, prefix, ctx, item_to_hash) -> str:
        """Generates name of variable to be used in the generated code. This
        also ensures that same items_to_hash will yield same names."""
        if "_prefixed_hash_to_name" not in ctx:
            ctx["_prefixed_hash_to_name"] = {}
            ctx["_generated_names"] = set()
        prefixed_hash_to_name = ctx["_prefixed_hash_to_name"]
        generated_names = ctx["_generated_names"]
        prefixed_hash = "{}_{}".format(prefix, str(id(item_to_hash)))
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

    @classmethod
    def indent_statements(
        cls,
        statements: typing.Union[str, typing.Iterable[str]],
        indentation_level: int,
    ) -> str:
        indentation = "    " * indentation_level
        lines = (
            statements.splitlines()
            if isinstance(statements, str)
            else statements
        )
        return "\n".join(f"{indentation}{line}" for line in lines)

    def get_args(self, exclude_types=None):
        return sorted(
            {
                dep.arg_name: dep
                for dep in self.get_dependencies(
                    types=InputArg, exclude_types=exclude_types
                )
            }.values(),
            key=lambda k: k.arg_name,
        )

    def get_args_def_code(
        self,
        as_kwargs=False,
        exclude_cls_self=False,
        exclude_labels=True,
    ):
        """Generates the code to define a function signature based on InputArgs
        used inside the conversion"""
        args = self.get_args(
            exclude_types=(LabelConversion,) if exclude_labels else None
        )

        if exclude_cls_self:
            args = [arg for arg in args if arg.arg_name not in ("self", "cls")]
        if not args:
            return ""

        code = ", ".join(arg.arg_name for arg in args)
        if as_kwargs:
            return ", *, {}".format(code)
        return ", {}".format(code)

    def get_args_as_func_args(self, exclude_labels=True):
        """Generates the code to pass InputArgs as arguments to the function"""
        args = self.get_args(
            exclude_types=(LabelConversion,) if exclude_labels else None
        )
        ctx = {}
        return tuple(
            EscapedString(arg.gen_code_and_update_ctx(None, ctx))
            for arg in args
        )

    def _code_to_converter(
        self, converter_name: str, code: str, ctx: dict
    ) -> _ConverterCallable:
        is_debug = ctx.get(
            "__debug", False
        ) or ConverterOptionsCtx.get_option_value("debug")
        if is_debug and "black" in globals():
            try:
                code = black.format_str(
                    code, mode=black.FileMode(line_length=79)
                )
            except black.InvalidInput:
                pass

        fake_filename = f"_fake_{converter_name}.py"
        code_obj = compile(code, fake_filename, "exec")
        exec(code_obj, ctx)  # pylint:disable=exec-used
        converter = ctx[converter_name]
        converter.conv_name = converter_name

        main_converter_callable = ctx["__main_converter_callable"]
        main_converter_callable.add_sources(fake_filename, code)
        return converter

    NAME_TO_CODE_INPUT = "_name_to_code_input"

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

        labels_: typing.Dict[str, typing.Any] = {}

        ctx = {
            "sys": sys,
            "__debug": debug,
            "__name__": "_convtools",
            "add_label_": labels_.__setitem__,
            "get_by_label_": labels_.__getitem__,
            "labels_": labels_,
            self.NAME_TO_CODE_INPUT: [{}],
        }

        converter_callable_cls = CodeGenerationOptionsCtx.get_option_value(
            "converter_callable_cls"
        )
        main_converter_callable = converter_callable_cls(debug=debug, ctx=ctx)
        ctx["__main_converter_callable"] = main_converter_callable

        if signature:
            signature_words = _pattern_word.findall(signature)
            missing_args = set(
                _pattern_word.findall(
                    self.get_args_def_code(exclude_labels=True)
                )
            ) - set(signature_words)
            if missing_args:
                raise ConversionException(
                    "bad signature, missing args", missing_args
                )
        else:
            if method and class_method:
                raise ConversionException(
                    "choose either method or a class_method"
                )
            signature = (
                ("self, " if method else "")
                + ("cls, " if class_method else "")
                + (initial_code_input)
                + (
                    self.get_args_def_code(
                        as_kwargs=True,
                        exclude_cls_self=True,
                        exclude_labels=True,
                    )
                )
            )

        converter_name = self.gen_name(converter_name, ctx, None)

        conv = self

        pipes = [conv]
        while conv._predefined_input is not None:
            conv = conv._predefined_input
            pipes.append(conv)

        last_index = len(pipes) - 1
        code_input = initial_code_input
        code_lines = []
        indent = " " * 4
        for index, conv in enumerate(reversed(pipes)):
            predefined_input = conv._predefined_input
            conv._predefined_input = None
            if last_index == 0:
                with CodeGenerationOptionsCtx() as options:
                    options.expressions_only = True
                    code_conv = conv.gen_code_and_update_ctx(code_input, ctx)
            else:
                code_conv = conv.gen_code_and_update_ctx(code_input, ctx)
            conv._predefined_input = predefined_input

            if index != last_index:
                code_input = self.gen_name("pipe", ctx, code_input)
                code_lines.append(f"{indent}{code_input} = {code_conv}")
            else:
                code_lines.append(f"{indent}return {code_conv}")

        converter_code = CONVERTER_TEMPLATE.format(
            code="\n".join(code_lines),
            converter_name=converter_name,
            code_signature=signature,
        )
        main_converter = self._code_to_converter(
            converter_name=converter_name,
            code=converter_code,
            ctx=ctx,
        )
        main_converter_callable.set_main_converter(main_converter)
        return main_converter_callable

    def execute(self, *args, debug=False, **kwargs) -> typing.Any:
        """Shortcut for generating converter and running it"""
        return self.gen_converter(debug=debug)(*args, **kwargs)

    def item(self, *args, **kwargs) -> "GetItem":
        return GetItem(*args, **kwargs).set_predefined_self(self)

    def __getitem__(self, k) -> "GetItem":
        return self.item(k)

    def attr(self, *attrs, **kwargs) -> "GetAttr":
        return GetAttr(*attrs, **kwargs).set_predefined_self(self)

    def call(self, *args, **kwargs) -> "Call":
        """Gets compiled into the code which calls the input with params.
        Each ``*args`` and ``**kwargs`` are wrapped with ``ensure_conversion``.
        """
        return Call(*args, **kwargs).set_predefined_self(self)

    def call_method(self, method_name: str, *args, **kwargs) -> "Call":
        """Gets compiled into the code which calls the ``method_name`` method
        of input with params.
        It's a shortcut to ``(...).attr(method_name).call(*args, **kwargs)``
        """
        return self.attr(method_name).call(*args, **kwargs)

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
        return InlineExpr("-{0}").pass_args(self)

    def __neg__(self) -> "InlineExpr":
        return self.neg()

    def add(self, arg) -> "InlineExpr":
        return InlineExpr("{0} + {1}").pass_args(self, arg)

    def __add__(self, b) -> "InlineExpr":
        return self.add(b)

    def mul(self, arg) -> "InlineExpr":
        return InlineExpr("{0} * {1}").pass_args(self, arg)

    def __mul__(self, b) -> "InlineExpr":
        return self.mul(b)

    def sub(self, arg) -> "InlineExpr":
        return InlineExpr("{0} - {1}").pass_args(self, arg)

    def __sub__(self, b) -> "InlineExpr":
        return self.sub(b)

    def div(self, arg) -> "InlineExpr":
        return InlineExpr("{0} / {1}").pass_args(self, arg)

    def __truediv__(self, b) -> "InlineExpr":
        return self.div(b)

    def mod(self, arg) -> "InlineExpr":
        return InlineExpr("{0} % {1}").pass_args(self, arg)

    def __mod__(self, b) -> "InlineExpr":
        return self.mod(b)

    def floor_div(self, arg) -> "InlineExpr":
        return InlineExpr("{0} // {1}").pass_args(self, arg)

    def __floordiv__(self, b) -> "InlineExpr":
        return self.floor_div(b)

    def filter(self, condition_conv, cast=None) -> "BaseConversion":
        """Shortcut for calling :py:obj:`convtools.base.Filter` on self"""
        conversion = Filter(condition_conv, cast=cast)
        return conversion.set_predefined_input(self)

    def _prepare_labels(self, label_arg):
        if isinstance(label_arg, str):
            return {label_arg: GetItem()}

        elif isinstance(label_arg, dict):
            return label_arg

        raise ConversionException("unexpected label_input type", label_arg)

    def add_label(
        self, label_name: str, conversion: typing.Optional[typing.Any] = None
    ):
        """Wraps the conversion into :py:obj:`LabelConversion` to allow further
        reuse.

        Args:
          label_name (str): a name of the label to be applied
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
        """Passes the result of current conversion as an input to the
        `next_conversion`.
        If `next_conversion` is callable, it gets called with self as the first
        param.
        If piping is done at the top level of a resulting conversion (not
        nested), then it's going to be represented as several statements.

        Supports labeling both pipe input and output data (allows to apply
        conversions before labeling).

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

        if (
            isinstance(next_conversion, BaseConversion)
            and not next_conversion.valid_pipe_output
        ):
            raise Exception("invalid pipe output", next_conversion)

        self_to_pass = self
        next_is_callable = callable(next_conversion)
        next_conversion = ensure_conversion(next_conversion)

        if label_input:
            self_to_pass = CachingConversion(self_to_pass)
            for label_name, conversion in self._prepare_labels(
                label_input
            ).items():
                self_to_pass.add_label(label_name, conversion)

        result = (
            next_conversion.call(self_to_pass, *args, **kwargs)
            if next_is_callable
            else next_conversion.set_predefined_input(self_to_pass)
        )

        if label_output:
            result = CachingConversion(result)
            for label_name, conversion in self._prepare_labels(
                label_output
            ).items():
                result.add_label(label_name, conversion)

        return result


class BaseMutation(BaseConversion):
    pass


class BaseMethodConversion(BaseConversion):
    """This conversion is required to take into account method calls.  We need
    to preserve the instance we are calling a method on.

    e.g. like obj['key'] OR obj.func() OR obj.attr1"""

    def __init__(self):
        super().__init__()
        self._predefined_self = None

    def set_predefined_self(self: MCT, input_conversion) -> MCT:
        if self._predefined_self is not None:
            raise ConversionException("failed to set predefined_input", self)

        input_conversion = ensure_conversion(input_conversion)
        self.depends_on(input_conversion)
        self._predefined_self = input_conversion
        if input_conversion.method_calls_override_input:
            return self.set_predefined_input(input_conversion)
        return self

    def get_self_code(self, code_input: str, ctx: dict) -> str:
        if self._predefined_self is None:
            code_self = code_input
        else:
            code_self = self._predefined_self.gen_code_and_update_ctx(
                code_input, ctx
            )
        return code_self


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

    def __init__(self, value: typing.Any, name_prefix="v"):
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
            if hasattr(value, "conv_name") and isinstance(
                getattr(value, "conv_name"), str
            ):
                self.value_name = getattr(value, "conv_name")
            else:
                f_name = var_name_from_string(value_name)
                if f_name:
                    self.name_prefix = f_name

    def _gen_code_and_update_ctx(self, code_input, ctx):
        if self.code_str:
            return self.code_str
        if self.value is None:
            return "None"
        if self.value is True:
            return "True"
        if self.value is False:
            return "False"
        if isinstance(self.value, (int, str)):
            return repr(self.value)
        value_name = self.value_name or self.gen_name(
            self.name_prefix, ctx, self.value
        )
        ctx[value_name] = self.value
        return value_name


class CachingConversion(BaseConversion):
    """Caches the result of the passed conversion globally, so it is possible
    to use the result twice without double evaluation.

    Provides the API to add labels to the result, supports result
    post-processing."""

    def __init__(self, conversion: typing.Any, name=None):
        """Takes a conversion to cache its result.

        Args:
          conversion (BaseConversion or object): to be wrapped with
            :py:obj:`ensure_conversion` and then its result is cached
          name (str): optional - it's possible to overwrite internally
            generated name, which also can be references as a label
        """
        super().__init__()
        self.conversion = self.ensure_conversion(conversion)
        self.labels: typing.Dict[str, BaseConversion] = {}
        self._name = name

    @property
    def name(self) -> str:
        if self._name is None:
            self._name = f"cached_val_{self.number}"
        return self._name

    def add_label(
        self, label_name: str, conversion: typing.Optional[typing.Any] = None
    ) -> "CachingConversion":
        """Adds a label to a result of the cached conversion,
        received into the ``__init__`` method. The cached result is first
        processed with ``conversion``.

        Args:
          label_name (str): name of a label
          conversion (BaseConversion or object): to be wrapped with
            :py:obj:`ensure_conversion` and applied to the cached result before
            the actual labeling
        Returns:
          CachingConversion: labeled conversion
        """
        if label_name in self.labels or label_name == self._name:
            raise ConversionException("label_name is already used", label_name)
        conversion = self.ensure_conversion(
            GetItem() if conversion is None else conversion
        )
        if (
            self._name is None
            and isinstance(conversion, GetItem)
            and not conversion.indexes
        ):
            self._name = label_name
        else:
            self.labels[label_name] = conversion
        return self

    def _gen_code_and_update_ctx(self, code_input, ctx):
        with CodeGenerationOptionsCtx() as options:
            options.labeling = True
            code = self.conversion.gen_code_and_update_ctx(code_input, ctx)
            cache_lines = [f"add_label_('{self.name}', {code})"]
            output_code = LabelConversion(self.name).gen_code_and_update_ctx(
                None, ctx
            )
            for label_name, label_conversion in self.labels.items():
                conv_code = label_conversion.gen_code_and_update_ctx(
                    output_code, ctx
                )
                cache_lines.append(f"add_label_('{label_name}', {conv_code})")

        cache_lines_code = " or ".join(cache_lines)
        return f"({cache_lines_code} or {output_code})"


class EscapedString(BaseConversion):
    def __init__(self, s):
        super().__init__()
        self.s = s

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return self.s


class InputArg(BaseConversion):
    """Allows to use arguments passed into the compiled converter.

    Unless the `signature` argument is passed to `gen_converter` function, all
    input arguments used in the conversion definition will be expected as
    keyword-only arguments (affecting the resulting converter signature)."""

    def __init__(self, arg_name: str):
        """
        Args:
          arg_name (string): argument name of the converter to be used
        """
        super().__init__()
        self.arg_name = arg_name

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return self.arg_name


class LabelConversion(InputArg):
    """Allows to reference a conversion result by label, after it was cached by
    :py:obj:`CachingConversion`."""

    def __init__(self, label_name: str):
        """
        Args:
          label_name (string): label name to be referenced
        """
        super().__init__(label_name)
        self.caching_conversion = None

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return f"get_by_label_('{self.arg_name}')"


class ConversionWrapper(BaseConversion):
    """This is to be used in conjunction with NamedConversion.

    ConversionWrapper is a map where:
      - key is the name of NamedConversion used somewhere inside what the
        ConversionWrapper wraps
      - value is the piece of code to be used as input for NamedConversion
    """

    def __init__(self, conversion: typing.Any, name_to_code_input=None):
        super().__init__()
        self.conversion = self.ensure_conversion(conversion)
        self._name_to_code_input = name_to_code_input

    @classmethod
    def name_to_code_input(
        cls, ctx, name_to_code_input=None
    ) -> typing.Dict[str, str]:
        if name_to_code_input is None:
            return ctx[cls.NAME_TO_CODE_INPUT][-1]
        new_value: typing.Dict[str, str] = {}
        new_value.update(cls.name_to_code_input(ctx))
        new_value.update(name_to_code_input)
        ctx[cls.NAME_TO_CODE_INPUT].append(new_value)
        return new_value

    def _gen_code_and_update_ctx(self, code_input, ctx):
        pop_name_to_code_input = False
        if self._name_to_code_input is not None:
            pop_name_to_code_input = True
            self.name_to_code_input(ctx, self._name_to_code_input)
        result = self.conversion.gen_code_and_update_ctx(code_input, ctx)
        if pop_name_to_code_input:
            ctx[self.NAME_TO_CODE_INPUT].pop()
        return result


class NamedConversion(BaseConversion):
    """See the ConversionWrapper docstring above"""

    def __init__(self, name, conversion):
        super().__init__()
        self.conversion = self.ensure_conversion(conversion)
        self.name = name

    def _gen_code_and_update_ctx(self, code_input, ctx):
        name_to_code_input = ConversionWrapper.name_to_code_input(ctx)
        if self.name in name_to_code_input:
            code_input = name_to_code_input[self.name]
        return self.conversion.gen_code_and_update_ctx(code_input, ctx)


class Or(BaseConversion):
    """Takes any number of objects, each is to be wrapped with
    :py:obj:`ensure_conversion` and generates the code
    joining every argument with python ``or`` expression"""

    op = " or "

    def __init__(self, arg1, arg2, *other_args):
        """"""
        super().__init__()
        args = [arg1, arg2]
        args.extend(other_args)
        self.args = [self.ensure_conversion(a) for a in args]

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return "({})".format(
            self.op.join(
                [
                    arg.gen_code_and_update_ctx(code_input, ctx)
                    for arg in self.args
                ]
            )
        )


class And(Or):
    """Takes any number of objects, each is to be wrapped with
    :py:obj:`ensure_conversion` and generates the code
    joining every argument with python ``and`` expression"""

    op = " and "


class Eq(Or):
    """Takes any number of objects, each is to be wrapped with
    :py:obj:`ensure_conversion` and generates the code
    joining every argument with python `` == `` operator"""

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
            None if condition is True else self.ensure_conversion(condition)
        )
        self.if_true = (
            None if if_true is self._none else self.ensure_conversion(if_true)
        )
        self.if_false = (
            None
            if if_false is self._none
            else self.ensure_conversion(if_false)
        )
        self.no_input_caching = no_input_caching

    symbols_making_expr_complex = re.compile(r"[^\w\"']")

    @classmethod
    def input_is_simple(cls, code_input):
        if code_input.startswith("(") and code_input.endswith(")"):
            code_input = code_input[1:-1]
        if (
            next(cls.symbols_making_expr_complex.finditer(code_input), None)
            is None
        ):
            return True
        return False

    def _gen_code_and_update_ctx(self, code_input, ctx):
        if self.input_is_simple(code_input) or self.no_input_caching:
            if_conv = if_true = if_false = code_input
        else:
            caching_conv = CachingConversion(GetItem())
            if_conv = caching_conv.gen_code_and_update_ctx(code_input, ctx)
            if_true = LabelConversion(
                caching_conv.name
            ).gen_code_and_update_ctx(None, ctx)
            if_false = if_true

        if_conv = EscapedString(if_conv)
        if_true = EscapedString(if_true)
        if_false = EscapedString(if_false)

        if self.if_conv is not None:
            if_conv = if_conv.pipe(self.if_conv)
        if self.if_true is not None:
            if_true = if_true.pipe(self.if_true)
        if self.if_false is not None:
            if_false = if_false.pipe(self.if_false)

        return "({code_if_true} if {code_if} else {code_if_false})".format(
            code_if_true=(if_true.gen_code_and_update_ctx(code_input, ctx)),
            code_if=(if_conv.gen_code_and_update_ctx(code_input, ctx)),
            code_if_false=(if_false.gen_code_and_update_ctx(code_input, ctx)),
        )


class Not(BaseConversion):
    def __init__(self, arg):
        super().__init__()
        self.arg = self.ensure_conversion(arg)

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return "(not {})".format(
            self.arg.gen_code_and_update_ctx(code_input, ctx)
        )


class GetItem(BaseMethodConversion):
    """``GetItem`` gets compiled into the code which does
    dictionary/index lookups.

    If called without params, just returns the input.

    If an index is a conversion itself, then it is being calculated
    against an input."""

    def __init__(
        self,
        *indexes,
        default=BaseConversion._none,
    ):
        """
        Args:
          indexes (:obj:`list` of :obj:`object`): to do lookups with
          default (:obj:`object`, optional): to be returned on fail,
           like ``{}.get`` method, but now applicable to arrays too
        """
        super().__init__()
        self.indexes = [self.ensure_conversion(index) for index in indexes]
        self.default = (
            self.ensure_conversion(default)
            if default is not self._none
            else None
        )

    def wrap_path_item(self, code_input, path_item):
        return f"{code_input}[{path_item}]"

    def _gen_code_and_update_ctx(self, code_input, ctx):
        code_self = self.get_self_code(code_input, ctx)
        if self.default is None:
            code_output = code_self
            for index in self.indexes:
                code_index = index.gen_code_and_update_ctx(code_input, ctx)
                code_output = self.wrap_path_item(code_output, code_index)
            return code_output

        self_is_overwritten = code_self != code_input
        code_output = "self_" if self_is_overwritten else "obj_"
        for index in self.indexes:
            code_index = index.gen_code_and_update_ctx("obj_", ctx)
            code_output = self.wrap_path_item(code_output, code_index)

        converter_name = self.gen_name("get_or_default", ctx, self)
        converter_code = GET_OR_DEFAULT_TEMPLATE.format(
            code_args=(
                "self_, obj_, default_"
                if self_is_overwritten
                else "obj_, default_"
            )
            + self.get_args_def_code(),
            converter_name=converter_name,
            get_or_default_code=code_output,
        )
        converter = self._code_to_converter(
            converter_name=converter_name,
            code=converter_code,
            ctx=ctx,
        )
        default_code = self.default.gen_code_and_update_ctx(code_input, ctx)
        result = NaiveConversion(converter)
        if self_is_overwritten:
            result = result.call(
                EscapedString(code_self),
                GetItem(),
                EscapedString(default_code),
                *self.get_args_as_func_args(),
            )
        else:
            result = result.call(
                GetItem(),
                EscapedString(default_code),
                *self.get_args_as_func_args(),
            )
        return result.gen_code_and_update_ctx(code_input, ctx)


class GetAttr(GetItem):
    """``GetAttr`` gets compiled into the code which runs getattr.
    If called without params, just returns the input.

    If an index is a conversion itself, then it is being calculated
    against an input."""

    valid_attr = re.compile(r"^'[A-Za-z][a-zA-Z0-9_]*'$")

    def wrap_path_item(self, code_input, path_item):
        if self.valid_attr.match(path_item):
            return f"{code_input}.{path_item[1:-1]}"
        return f"getattr({code_input}, {path_item})"


class Call(BaseMethodConversion):
    """This conversion writes the code which takes the input code and calls it
    as a function.
    It takes both positional and keyword arguments to be passed.
    """

    symbols_to_filter_out = re.compile(r"\W")

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.args = [self.ensure_conversion(arg) for arg in args]
        self.kwargs = {
            k: self.ensure_conversion(v) for k, v in (kwargs or {}).items()
        }

    def _gen_code_and_update_ctx(self, code_input, ctx):
        code_self = self.get_self_code(code_input, ctx)

        params = [
            param.gen_code_and_update_ctx(code_input, ctx)
            for param in self.args
        ]
        for k, v in self.kwargs.items():
            params.append(
                "{}={}".format(k, v.gen_code_and_update_ctx(code_input, ctx))
            )
        return f"{code_self}({','.join(params)})"


def CallFunc(func, *args, **kwargs):
    """Shortcut to ``NaiveConversion(func).call(*args, **kwargs)``"""
    assert callable(func)
    return NaiveConversion(func).call(*args, **kwargs)


def Filter(condition_conv, cast=None) -> BaseConversion:
    """Generates the code to iterate the input, taking items for which the
    provided conversion resolves to a truth value.

    Args:
      condition_conv (object): to be wrapped with :py:obj:`ensure_conversion`
        and used on each item of a collection to filter it
      cast (callable): to wrap the generator of filtered items
    Returns:
      BaseConversion: the generator of filtered items, wrapped with `cast`
      if provided
    """
    if cast is None:
        return GeneratorComp(GetItem()).filter(condition_conv)
    if cast is list:
        return ListComp(GetItem()).filter(condition_conv)
    if cast is tuple:
        return TupleComp(GetItem()).filter(condition_conv)
    if cast is set:
        return SetComp(GetItem()).filter(condition_conv)
    if callable(cast):
        gen = GeneratorComp(GetItem()).filter(condition_conv)
        return NaiveConversion(cast).call(gen)
    raise AssertionError("cannot cast generator to cast={}".format(cast))


class InlineExpr(BaseConversion):
    """This conversion allows to avoid function call overhead.  It inlines a
    raw python code expression into the code of resulting conversion."""

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


class BaseComprehensionConversion(BaseConversion):
    """This is the base conversion to generate a code, which creates a
    collection like: list/dict/etc."""

    def __init__(self, item):
        """
        Args:
          item (object): to be wrapped with :py:obj:`ensure_conversion`
            and used as a conversion on each item of a collection.

            e.g. for ``[i * 2 for i in l]`` an item would be ``c.this() * 2``
        """
        super().__init__()
        self.sort_key = None
        self.sort_key_reverse = None
        self.condition_conversion = None
        self.item = self.ensure_conversion(item)

    def filter(self, condition_conversion):
        """
        Args:
          condition_conversion (object): to be wrapped with
            :py:obj:`ensure_conversion` and used as a condition within the
            comprehension.
        Returns:
          BaseComprehensionConversion: cloned and filtered comprehension
          conversion
        """
        if self.condition_conversion:
            raise AssertionError("condition_conversion is already present")
        self_clone = self.clone()
        self_clone.condition_conversion = self_clone.ensure_conversion(
            condition_conversion
        )
        return self_clone

    def sort(self, key=None, reverse=False):
        """
        Args:
          key (object): to be wrapped with
            :py:obj:`ensure_conversion` and used as a key to sort the
            collection
          reverse (bool): if `True`, sorts DESC
        Returns:
          BaseComprehensionConversion: cloned and filtered comprehension
          conversion
        """
        if self.sort_key:
            raise AssertionError("sort has already been called")
        self_clone = self.clone()
        self_clone.sort_key = True if key is None else key
        self_clone.sort_key_reverse = reverse
        return self_clone

    def _gen_code_and_update_ctx(self, code_input, ctx):
        param_name = self.gen_name("i", ctx, code_input)
        gen_code_str = self.gen_generator_code(code_input, param_name, ctx)
        code_str = self.gen_comprehension_pre_sort(gen_code_str, ctx)
        if self.sort_key:
            code_str = self.gen_sort_code(
                code_str,
                ctx,
                self.ensure_conversion(
                    None if self.sort_key is True else self.sort_key
                ).gen_code_and_update_ctx(None, ctx),
                self.ensure_conversion(
                    self.sort_key_reverse
                ).gen_code_and_update_ctx(None, ctx),
            )
        return code_str

    def gen_item_code(self, code_input, ctx):
        return self.item.gen_code_and_update_ctx(code_input, ctx)

    def gen_generator_code(self, code_input, param_name, ctx):
        item_code = self.gen_item_code(param_name, ctx)
        gen_code = f"{item_code} for {param_name} in {code_input}"
        if self.condition_conversion is not None:
            condition_code = self.condition_conversion.gen_code_and_update_ctx(
                param_name, ctx
            )
            gen_code = f"{gen_code} if {condition_code}"
        return gen_code

    def gen_comprehension_pre_sort(self, generator_code, ctx):
        raise NotImplementedError

    def gen_sort_code(self, code_input, ctx, sort_key_code, reverse_code):
        raise NotImplementedError


class GeneratorComp(BaseComprehensionConversion):
    """Generates python generator comprehension code."""

    def gen_comprehension_pre_sort(self, generator_code, ctx):
        return f"({generator_code})"


class ListComp(BaseComprehensionConversion):
    """Generates python list comprehension code."""

    def gen_comprehension_pre_sort(self, generator_code, ctx):
        return f"[{generator_code}]"

    def gen_sort_code(self, code_input, ctx, sort_key_code, reverse_code):
        return (
            f"sorted({code_input}, key={sort_key_code},"
            f"reverse={reverse_code})"
        )


class TupleComp(BaseComprehensionConversion):
    """Generates python tuple comprehension code."""

    def gen_comprehension_pre_sort(self, generator_code, ctx):
        if self.sort_key:
            return f"({generator_code})"
        return f"tuple({generator_code})"

    def gen_sort_code(self, code_input, ctx, sort_key_code, reverse_code):
        return (
            f"tuple(sorted({code_input}, key={sort_key_code},"
            f"reverse={reverse_code}))"
        )


class SetComp(BaseComprehensionConversion):
    """Generates python set comprehension code (obviously non-sortable)"""

    def gen_comprehension_pre_sort(self, generator_code, ctx):
        return "{%s}" % generator_code

    def sort(self, key=None, reverse=False):
        raise ConversionException("attempt to build sorted set")


class DictComp(BaseComprehensionConversion):
    """Generates python dict comprehension code."""

    def __init__(self, key, value):
        """
        Args:
          key (object): to be wrapped with :py:obj:`ensure_conversion` and
            used on each item of a collection to form keys
          value (object): to be wrapped with :py:obj:`ensure_conversion` and
            used on each item of a collection to form values
        """
        super().__init__(item=None)
        self.key = self.ensure_conversion(key)
        self.value = self.ensure_conversion(value)

    def gen_item_code(self, code_input, ctx):
        key_code = self.key.gen_code_and_update_ctx(code_input, ctx)
        value_code = self.value.gen_code_and_update_ctx(code_input, ctx)
        if self.sort_key:
            return f"({key_code}, {value_code})"
        return f"{key_code}: {value_code}"

    def gen_comprehension_pre_sort(self, generator_code, ctx):
        if self.sort_key:
            return f"({generator_code})"
        return "{%s}" % generator_code

    def gen_sort_code(self, code_input, ctx, sort_key_code, reverse_code):
        ctx["OrderedDict"] = OrderedDict
        return (
            f"OrderedDict(sorted({code_input}, key={sort_key_code},"
            f"reverse={reverse_code}))"
        )


class BaseCollectionConversion(BaseConversion):
    """This is a base conversion of """

    def __init__(self, *items):
        """
        Args:
          items (objects): items to form a collection from.
            every item gets wrapped with :py:obj:`ensure_conversion`
        """
        super().__init__()
        self.items = [self.ensure_conversion(item) for item in items]

    def gen_optional_items_generator_code(
        self, condition_to_item_pairs, code_input, ctx
    ):
        code_lines = []
        inner_code_input = "data_"
        for condition, item in condition_to_item_pairs:
            value_code = item.gen_code_and_update_ctx(inner_code_input, ctx)
            if condition is not None:
                condition_code = condition.gen_code_and_update_ctx(
                    inner_code_input, ctx
                )
                code_lines.append(f"    if {condition_code}:")
                code_lines.append(f"        yield {value_code}")
            else:
                code_lines.append(f"    yield {value_code}")
        code_lines = "\n".join(code_lines)
        converter_name = self.gen_name("optional_items_generator", ctx, self)
        code_args = self.get_args_def_code(as_kwargs=False)
        code = f"""
def {converter_name}(data_{code_args}):
{code_lines}
        """
        generator_converter = self._code_to_converter(
            converter_name=converter_name,
            code=code,
            ctx=ctx,
        )
        return CallFunc(
            generator_converter, GetItem(), *self.get_args_as_func_args()
        ).gen_code_and_update_ctx(code_input, ctx)

    def gen_joined_items_code(self, code_input, ctx):
        params = [
            item.gen_code_and_update_ctx(code_input, ctx)
            for item in self.items
        ]
        return ",".join(params)

    def gen_collection_from_items_code(
        self, joined_items_code, code_input, ctx
    ):
        raise NotImplementedError

    def gen_collection_from_generator(self, generator_code, code_input, ctx):
        raise NotImplementedError

    def prepare_optional_items(self):
        condition_to_item_pairs = []
        for item in self.items:
            if isinstance(item, OptionalCollectionItem):
                condition_to_item_pairs.append(
                    (item.condition, item.conversion)
                )
            else:
                condition_to_item_pairs.append((None, item))
        return condition_to_item_pairs

    def has_optional_items(self):
        return any(
            isinstance(item, OptionalCollectionItem) for item in self.items
        )

    def _gen_code_and_update_ctx(self, code_input, ctx):
        has_optional_items = self.has_optional_items()

        if has_optional_items:
            condition_to_item_pairs = self.prepare_optional_items()
            return self.gen_collection_from_generator(
                self.gen_optional_items_generator_code(
                    condition_to_item_pairs, code_input, ctx
                ),
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
        return "{%s}" % joined_items_code

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
        self.key_value_pairs = [
            (self.ensure_conversion(k), self.ensure_conversion(v))
            for k, v in key_value_pairs
        ]

    def gen_joined_items_code(self, code_input, ctx):
        params = [
            "{}:{}".format(
                key.gen_code_and_update_ctx(code_input, ctx),
                value.gen_code_and_update_ctx(code_input, ctx),
            )
            for key, value in self.key_value_pairs
        ]
        return ",".join(params)

    def gen_collection_from_generator(self, generator_code, code_input, ctx):
        return f"dict({generator_code})"

    def prepare_optional_items(self):
        condition_to_item_pairs = []
        for key_value in self.key_value_pairs:
            conditions = []
            tuple_items = []
            for item in key_value:
                if isinstance(item, OptionalCollectionItem):
                    conditions.append(item.condition)
                    tuple_items.append(item.conversion)
                else:
                    tuple_items.append(item)
            if conditions:
                condition = (
                    And(conditions[0], conditions[1], *conditions[2:])
                    if len(conditions) > 1
                    else conditions[0]
                )
                condition_to_item_pairs.append(
                    (condition, Tuple(*tuple_items))
                )
            else:
                condition_to_item_pairs.append((None, Tuple(*tuple_items)))
        return condition_to_item_pairs

    def has_optional_items(self):
        return any(
            isinstance(item, OptionalCollectionItem)
            for key_value in self.key_value_pairs
            for item in key_value
        )

    def gen_collection_from_items_code(
        self, joined_items_code, code_input, ctx
    ):
        return "{%s}" % joined_items_code


class TapConversion(BaseConversion):
    """This conversion generates the code which mutates the input date in-place.
    TapConversion takes any number of mutations"""

    def __init__(self, obj, *mutations: BaseMutation):
        super().__init__()
        self.obj = self.ensure_conversion(obj)
        self.mutations = [
            self.ensure_conversion(mut, accept_mutations=True)
            for mut in mutations
        ]

    code_template = """
def {f_name}(data_{code_args}):
{mut_stmts}
    return data_
"""

    def _gen_code_and_update_ctx(self, code_input, ctx):
        converter_name = self.gen_name("tap", ctx, self)
        obj_code = self.obj.gen_code_and_update_ctx(code_input, ctx)
        mut_stmts = [
            self.indent_statements(
                mut.gen_code_and_update_ctx("data_", ctx), 1
            )
            for mut in self.mutations
        ]
        code = self.code_template.format(
            f_name=converter_name,
            code_args=self.get_args_def_code(
                as_kwargs=False, exclude_labels=True
            ),
            mut_stmts="\n".join(mut_stmts),
        )
        converter = self._code_to_converter(converter_name, code, ctx)
        return CallFunc(
            converter, EscapedString(obj_code), *self.get_args_as_func_args()
        ).gen_code_and_update_ctx(code_input, ctx)
