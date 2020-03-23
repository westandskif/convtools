import dis
import linecache
import re
import sys
from collections import OrderedDict
from itertools import chain, count
from types import GeneratorType

from .utils import BaseCtx, BaseOptions, RUCache


def clean_line_cache(key, value):
    try:
        del linecache.cache[key]
    except KeyError:
        pass


class _ConverterCallable:
    linecache_keys = RUCache(100, clean_line_cache)

    def __init__(
        self,
        converter,
        code_str,
        fake_filename,
        ctx,
        _instance=None,
        debug=None,
    ):
        self.converter = converter
        self._code_str = code_str
        self._fake_filename = fake_filename
        self._ctx = ctx
        self._ctx["__depth"] = 0
        self._debug = debug
        self._line_cache_populated = False
        self._instance = _instance
        self.__name__ = getattr(self.converter, "__name__", "")

        if self._debug:
            self.populate_line_cache()

    def __get__(self, instance, cls):
        return self.__class__(
            self.converter,
            code_str=self._code_str,
            fake_filename=self._fake_filename,
            ctx=self._ctx,
            _instance=instance or cls,
        )

    def __call__(self, *args, **kwargs):
        deferred_labels_cleaning = False
        self._ctx["__depth"] += 1
        try:
            if self._instance:
                args = (self._instance,) + args

            result = self.converter(*args, **kwargs)
            if isinstance(result, GeneratorType):
                deferred_labels_cleaning = True
                return self.wrap_generator_clean_labels_on_exit(
                    result, self._ctx["labels_"]
                )
            return result
        except Exception:
            self.populate_line_cache()
            raise
        finally:
            self._ctx["__depth"] -= 1
            if not deferred_labels_cleaning and self._ctx["__depth"] == 0:
                labels_ = self._ctx["labels_"]
                if labels_:
                    for key in list(labels_):
                        del labels_[key]

    def wrap_generator_clean_labels_on_exit(self, generator_, labels_):
        try:
            yield from generator_
        finally:
            labels_ = self._ctx["labels_"]
            if labels_ and self._ctx["__depth"] == 0:
                for key in list(labels_):
                    del labels_[key]

    def populate_line_cache(self):
        if self.linecache_keys.has(self._fake_filename, bump_up=True):
            return

        linecache.cache[self._fake_filename] = (
            len(self._code_str),
            None,
            self._code_str.splitlines(),
            self._fake_filename,
        )
        self.linecache_keys.set(self._fake_filename, True)


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


converter_template = """
def {converter_name}({code_signature}):
    global add_label_, get_by_label_
{code}
"""


get_or_default_template = """
def {converter_name}({code_args}):
    global add_label_, get_by_label_
    try:
        return {get_or_default_code}
    except (TypeError, KeyError, IndexError, AttributeError):
        return default_
"""


def ensure_conversion(conversion: object):
    r"""Helps to define conversions based on its type:
        * any conversion is returned untouched
        * list/dict/set/tuple collections are wrapped with ``c.list``,
          ``c.dict``, ``c.set``, ``c.tuple`` (see below).
          If it's not desired, use ``c.naive`` instead
        * slice gets recreated, each ``slice.start, slice.stop, slice.step`` is wrapped with ``ensure_conversion``
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


class BaseConversion:
    """This is the base class  of every conversion (so you are not going to
    use this directly).

    A conversion is a definition of
    some actions to be done to the input passed as `data_` argument.

    Conversions are nestable (iteration, calling functions) and chainable
    (method calling or piping).

    Every conversion has many important methods like:

     * `gen_converter`
     * `item`, `attr`, `call`, `call_methods`, `as_type`
     * `and_`, `or_`, `not_`, `is_`, `is not`, `in_`, `not_in`
     * `filter`
     * `pipe`
     * overloaded operators"""

    _none = object()
    counter = count()
    max_counter = 32768

    def __init__(self, options):
        self.depends_on = ()

        self._number = self._get_number()
        self.debug = options.pop("debug", False)
        self._predefined_input = None

        if "_predefined_input" in options:
            self.set_predefined_input(options.pop("_predefined_input"))

    def _get_number(self):
        number = next(self.counter)
        if number > self.max_counter:
            BaseConversion.counter = count()
        return number

    @property
    def max_pipe_length(self):
        return ConverterOptionsCtx.get_option_value("max_pipe_length")

    def __hash__(self):
        return id(self)

    def _depends_on(self, *args):
        for arg in args:
            self.depends_on += arg.depends_on + (arg,)
        return self

    def ensure_conversion(self, conversion):
        conversion = ensure_conversion(conversion)
        self._depends_on(conversion)
        return conversion

    def gen_code_and_update_ctx(self, code_input, ctx):
        code_to_be_attached = None
        if self._predefined_input is not None:
            code_input = self._predefined_input.gen_code_and_update_ctx(
                code_input, ctx
            )
            if not If.input_is_simple(code_input):
                code_to_be_attached = code_input
        resulting_code = self._gen_code_and_update_ctx(code_input, ctx)
        if code_to_be_attached and code_to_be_attached not in resulting_code:
            return "({} and None or {})".format(
                code_to_be_attached, resulting_code
            )
        return resulting_code

    def _gen_code_and_update_ctx(self, code_input, ctx):
        raise NotImplementedError

    @classmethod
    def _hash_item(cls, item):
        if callable(item):
            try:
                code_obj_hash = hash(dis.Bytecode(item).codeobj)
            except TypeError:
                pass
            else:
                return f"#{code_obj_hash}"
        try:
            return f"#{hash(item)}"
        except TypeError:
            return f"id{id(item)}"

    def _clone(self):
        clone = self.__class__.__new__(self.__class__)
        clone.__dict__.update(self.__dict__)
        clone._number = clone._get_number()
        return clone

    def clone(self):
        result = self._clone()
        conv = result
        for i in range(self.max_pipe_length):
            if conv._predefined_input:
                conv._predefined_input = conv._predefined_input._clone()
                conv = conv._predefined_input
            else:
                break
        else:
            raise ConversionException("failed to clone, too long pipe")
        return result

    def gen_name(self, prefix, ctx, item_to_hash=None):
        prefixed_hash_to_name = ctx.setdefault("_prefixed_hash_to_name", {})
        prefixed_hash = (
            f"{prefix}"
            f"{type(item_to_hash).__name__}"
            f"{self._hash_item(item_to_hash)}"
        )
        if prefixed_hash in prefixed_hash_to_name:
            return prefixed_hash_to_name[prefixed_hash]

        name = "%s%d_%d" % (prefix, self._number, hash(prefixed_hash) % 1000)
        prefixed_hash_to_name[prefixed_hash] = name
        return name

    @classmethod
    def _indent_statements(cls, statements, indentation_level):
        indentation = "    " * indentation_level
        return "\n".join(
            f"{indentation}{line}" for line in statements.splitlines()
        )

    def _get_dependencies(self, types=None):
        deps = chain(self.depends_on, (self,))
        if types:
            deps = (dep for dep in deps if isinstance(dep, types))
        return deps

    def _get_args(self):
        return sorted(
            {
                dep.arg_name: dep
                for dep in self._get_dependencies(types=InputArg)
            }.values(),
            key=lambda k: k.arg_name,
        )

    def _get_args_def_code(
        self, as_kwargs=False, exclude_cls_self=False, exclude_labels=False,
    ):
        args = self._get_args()
        if exclude_labels:
            args = [
                arg for arg in args if not isinstance(arg, LabelConversion)
            ]

        if exclude_cls_self:
            args = [arg for arg in args if arg.arg_name not in ("self", "cls")]
        if not args:
            return ""

        _code = ", ".join(arg.arg_name for arg in args)
        if as_kwargs:
            return ", *, {}".format(_code)
        return ", {}".format(_code)

    def _get_args_as_func_args(self):
        args = self._get_args()
        _ctx = {}
        return tuple(
            EscapedString(arg.gen_code_and_update_ctx(None, _ctx))
            for arg in args
        )

    def _code_to_converter(self, converter_name, code, ctx, fake_filename):
        is_debug = ctx.get(
            "__debug", False
        ) or ConverterOptionsCtx.get_option_value("debug")
        if is_debug:
            try:
                import black

                code = black.format_str(
                    code, mode=black.FileMode(line_length=79)
                )
            except ImportError:
                pass
            except black.InvalidInput:
                pass
            print("\n", code)

        fake_filename = f"{fake_filename}_{self._number}.py"
        code_obj = compile(code, fake_filename, "exec")
        exec(code_obj, ctx)
        converter = ctx[converter_name]

        converter_callable_cls = CodeGenerationOptionsCtx.get_option_value(
            "converter_callable_cls"
        )
        return converter_callable_cls(
            converter,
            code_str=code,
            fake_filename=fake_filename,
            ctx=ctx,
            debug=is_debug,
        )

    NAME_TO_CODE_INPUT = "_name_to_code_input"

    def gen_converter(
        self,
        method=False,
        class_method=False,
        signature=None,
        debug=None,
        converter_name="converter",
    ):
        """Compiles a function which act according to the conversion definition.

        Args:
          debug (bool): If `True`, prints the generated code (formats with black if
            available). By default: None
          signature (str): Defines the signature of the function to be compiled.
            `data_` argument is what going to be used as the input.
            e.g. ``signature="self, dt, data_, **kwargs"``
          method (bool): `True` is a shortcut for: ``signature="self, data_"``
          class_method (bool): `True` is a shortcut for: ``signature="cls, data_"``
          converter_name (str): prefix of the name of the function to be compiled

        Returns:
          The compiled function
        """
        # signature should contain "data_" argument
        initial_code_input = "data_"

        labels_ = {}

        ctx = {
            "sys": sys,
            "__debug": debug,
            "__name__": "_convtools",
            "add_label_": labels_.__setitem__,
            "get_by_label_": labels_.__getitem__,
            "labels_": labels_,
            self.NAME_TO_CODE_INPUT: [{}],
        }
        if signature:
            signature_words = _pattern_word.findall(signature)
            missing_args = set(
                _pattern_word.findall(
                    self._get_args_def_code(exclude_labels=True)
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
                    self._get_args_def_code(
                        as_kwargs=True,
                        exclude_cls_self=True,
                        exclude_labels=True,
                    )
                )
            )

        if debug is not None:
            self.debug = debug
        converter_name = self.gen_name(converter_name, ctx)

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
            _predefined_input = conv._predefined_input
            conv._predefined_input = None
            if last_index == 0:
                with CodeGenerationOptionsCtx() as options:
                    options.expressions_only = True
                    code_conv = conv.gen_code_and_update_ctx(code_input, ctx)
            else:
                code_conv = conv.gen_code_and_update_ctx(code_input, ctx)
            conv._predefined_input = _predefined_input

            if index != last_index:
                code_input = self.gen_name("pipe", ctx, code_input)
                code_lines.append(f"{indent}{code_input} = {code_conv}")
            else:
                code_lines.append(f"{indent}return {code_conv}")

        converter_code = converter_template.format(
            code="\n".join(code_lines),
            converter_name=converter_name,
            code_signature=signature,
        )
        return self._code_to_converter(
            converter_name=converter_name,
            code=converter_code,
            ctx=ctx,
            fake_filename="_convtools_gen_converter",
        )

    def execute(self, *args, debug=False, **kwargs):
        return self.gen_converter(debug=debug)(*args, **kwargs)

    def item(self, *args, **kwargs):
        return GetItem(*args, _predefined_self=self, **kwargs)

    def attr(self, *attrs, **kwargs):
        return GetAttr(*attrs, _predefined_self=self, **kwargs)

    def call(self, *args, **kwargs):
        """Gets compiled into the code which calls the input with params.
        Each ``*args`` and ``**kwargs`` are wrapped with ``ensure_conversion``.
        """
        return Call(*args, _predefined_self=self, **kwargs)

    def call_method(self, method_name: str, *args, **kwargs):
        """Gets compiled into the code which calls the ``method_name`` method
        of input with params.
        It's a shortcut to ``(...).attr(method_name).call(*args, **kwargs)``
        """
        return self.attr(method_name).call(*args, **kwargs)

    def as_type(self, _callable):
        return ensure_conversion(_callable).call(self)

    def or_(self, *args, **kwargs):
        return Or(self, *args, **kwargs)

    def __or__(self, b):
        return self.or_(b)

    def and_(self, *args, **kwargs):
        return And(self, *args, **kwargs)

    def __and__(self, b):
        return self.and_(b)

    def not_(self):
        return InlineExpr("not {0}").pass_args(self)

    def __invert__(self):
        return self.not_()

    def is_(self, arg):
        return InlineExpr("{0} is {1}").pass_args(self, arg)

    def is_not(self, arg):
        return InlineExpr("{0} is not {1}").pass_args(self, arg)

    def in_(self, arg):
        return InlineExpr("{0} in {1}").pass_args(self, arg)

    def not_in(self, arg):
        return InlineExpr("{0} not in {1}").pass_args(self, arg)

    def eq(self, *args, **kwargs):
        return Eq(self, *args, **kwargs)

    def __eq__(self, b):
        return self.eq(b)

    def not_eq(self, arg):
        return InlineExpr("{0} != {1}").pass_args(self, arg)

    def __ne__(self, b):
        return self.not_eq(b)

    def gt(self, arg):
        return InlineExpr("{0} > {1}").pass_args(self, arg)

    def __gt__(self, b):
        return self.gt(b)

    def gte(self, arg):
        return InlineExpr("{0} >= {1}").pass_args(self, arg)

    def __ge__(self, b):
        return self.gte(b)

    def lt(self, arg):
        return InlineExpr("{0} < {1}").pass_args(self, arg)

    def __lt__(self, b):
        return self.lt(b)

    def lte(self, arg):
        return InlineExpr("{0} <= {1}").pass_args(self, arg)

    def __le__(self, b):
        return self.lte(b)

    def neg(self):
        return InlineExpr("-{0}").pass_args(self)

    def __neg__(self):
        return self.neg()

    def add(self, arg):
        return InlineExpr("{0} + {1}").pass_args(self, arg)

    def __add__(self, b):
        return self.add(b)

    def mul(self, arg):
        return InlineExpr("{0} * {1}").pass_args(self, arg)

    def __mul__(self, b):
        return self.mul(b)

    def sub(self, arg):
        return InlineExpr("{0} - {1}").pass_args(self, arg)

    def __sub__(self, b):
        return self.sub(b)

    def div(self, arg):
        return InlineExpr("{0} / {1}").pass_args(self, arg)

    def __truediv__(self, b):
        return self.div(b)

    def mod(self, arg):
        return InlineExpr("{0} % {1}").pass_args(self, arg)

    def __mod__(self, b):
        return self.mod(b)

    def floor_div(self, arg):
        return InlineExpr("{0} // {1}").pass_args(self, arg)

    def __floordiv__(self, b):
        return self.floor_div(b)

    def __getitem__(self, k):
        return InlineExpr("{}[{}]").pass_args(self, k)

    def filter(self, condition_conv, cast=None):
        """Shortcut for calling :py:obj:`convtools.base.Filter` on self"""
        return Filter(condition_conv, cast=cast, _predefined_input=self)

    def set_predefined_input(self, input_conversion):
        _self = self
        input_conversion = ensure_conversion(input_conversion)
        for i in range(self.max_pipe_length - 1):
            if _self._predefined_input is None:
                _self._predefined_input = _self.ensure_conversion(
                    input_conversion
                )
                break
            else:
                _self._depends_on(input_conversion)

            _self = _self._predefined_input
        else:
            raise ConversionException("failed to set predefined_input", self)
        return self

    def _prepare_labels(self, label_arg):
        if isinstance(label_arg, str):
            return {label_arg: GetItem()}

        elif isinstance(label_arg, dict):
            return label_arg

        raise ConversionException("unexpected label_input type", label_arg)

    def add_label(self, label_name: str):
        """Wraps the conversion into :py:obj:`LabelConversion` to allow further
        reuse.

        Args:
          label_name (str): a name of the label to be applied
        Returns:
          LabelConversion: the labeled conversion
        """
        return self.pipe(GetItem(), label_input=label_name)

    def pipe(
        self,
        next_conversion,
        *args,
        label_input=None,
        label_output=None,
        **kwargs,
    ):
        """Passes the result of current conversion as an input to the
        `next_conversion`.
        If `next_conversion` is callable, it gets called with self as the
        first param.
        If piping is done at the top level of a resulting conversion (not nested),
        then it's going to be represented as several statements.

        Supports labeling both pipe input and output data (allows to apply
        conversions before labeling).

        Args:
          next_conversion (object): to be wrapped with :py:obj:`ensure_conversion`
            and called if callable is passed
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

        cloned_self = self.clone()

        if label_input:
            cloned_self = CachingConversion(cloned_self)
            for label_name, conversion in self._prepare_labels(
                label_input
            ).items():
                cloned_self.add_label(label_name, conversion)

        next_is_callable = callable(next_conversion)
        if next_is_callable:
            result = (
                ensure_conversion(next_conversion)
                .clone()
                .call(cloned_self, *args, **kwargs)
            )
        else:
            result = ensure_conversion(next_conversion).clone()

        if label_output:
            result = CachingConversion(result)
            for label_name, conversion in self._prepare_labels(
                label_output
            ).items():
                result.add_label(label_name, conversion)

        if not next_is_callable:
            result = result.set_predefined_input(cloned_self)

        return result


class BaseMethodConversion(BaseConversion):
    """like obj['key'] OR obj.func() OR obj.attr1"""

    def __init__(self, options):
        super(BaseMethodConversion, self).__init__(options)
        self._predefined_self = None
        if "_predefined_self" in options:
            self._predefined_self = self.ensure_conversion(
                options.pop("_predefined_self")
            )

    def get_self_code(self, code_input, ctx):
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
    """Naive conversion gets compiled into the code, which just returns
    the `value` it's been initialized with.
    Allows to make any object available inside other conversions.
    """

    _builtin_dict = globals()["__builtins__"]

    def __init__(self, value: object, name_prefix="v", **kwargs):
        """
        Args:
          value (object): any object

        """
        super(NaiveConversion, self).__init__(kwargs)
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
        value_name = self.gen_name(self.name_prefix, ctx, self.value)
        ctx[value_name] = self.value
        return value_name


class CachingConversion(BaseConversion):
    """Caches the result of the passed conversion globally, so it is possible
    to use the result twice without double evaluation.

    Provides the API to add labels to the result, supports result
    post-processing."""

    def __init__(self, conversion, name=None, **kwargs):
        """Takes a conversion to cache its result.

        Args:
          conversion (BaseConversion or object): to be wrapped with
            :py:obj:`ensure_conversion` and then its result is cached
          name (str): optional - it's possible to overwrite internally
            generated name, which also can be references as a label
        """
        super(CachingConversion, self).__init__(kwargs)
        self.conversion = self.ensure_conversion(conversion)
        self.labels = {}
        self._name = name

    @property
    def name(self):
        if self._name is None:
            self._name = f"cached_val_{self._number}"
        return self._name

    def add_label(self, label_name: str, conversion):
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
        conversion = self.ensure_conversion(conversion)
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
    def __init__(self, s, **kwargs):
        super(EscapedString, self).__init__(kwargs)
        self.s = s

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return self.s


class InputArg(BaseConversion):
    """Allows to use arguments passed into the compiled converter.

    Unless the `signature` argument is passed to `gen_converter` function,
    all input arguments used in the conversion definition will be expected
    as keyword-only arguments (affecting the resulting converter signature)."""

    def __init__(self, arg_name, **kwargs):
        """
        Args:
          arg_name (string): argument name of the converter to be used
        """
        super(InputArg, self).__init__(kwargs)
        self.arg_name = arg_name

    def __hash__(self):
        return hash(self.arg_name)

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return self.arg_name


class LabelConversion(InputArg):
    """Allows to reference a conversion result by label, after it was cached by
    :py:obj:`CachingConversion`."""

    def __init__(self, label_name, **kwargs):
        """
        Args:
          label_name (string): label name to be referenced
        """
        super(LabelConversion, self).__init__(label_name, **kwargs)
        self.caching_conversion = None

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return f"get_by_label_('{self.arg_name}')"


class ConversionWrapper(BaseConversion):
    def __init__(self, conversion, name_to_code_input=None, **kwargs):
        super(ConversionWrapper, self).__init__(kwargs)
        self.conversion = self.ensure_conversion(conversion)
        self._name_to_code_input = name_to_code_input

    @classmethod
    def name_to_code_input(cls, ctx, name_to_code_input=None):
        if name_to_code_input is None:
            return ctx[cls.NAME_TO_CODE_INPUT][-1]
        new_value = {}
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
    def __init__(self, name, conversion, **kwargs):
        super(NamedConversion, self).__init__(kwargs)
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

    def __init__(self, arg1, arg2, *other_args, **kwargs):
        """"""
        super(Or, self).__init__(kwargs)
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
        **kwargs,
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
        super(If, self).__init__(kwargs)
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
    def __init__(self, arg, **kwargs):
        super(Not, self).__init__(kwargs)
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
        self, *indexes, default=BaseConversion._none, **kwargs,
    ):
        """
        Args:
          indexes (:obj:`list` of :obj:`object`): to do lookups with
          default (:obj:`object`, optional): to be returned on fail,
           like ``{}.get`` method, but now applicable to arrays too
        """
        super(GetItem, self).__init__(kwargs)
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

        converter_name = self.gen_name("get_or_default", ctx)
        converter_code = get_or_default_template.format(
            code_args=(
                "self_, obj_, default_"
                if self_is_overwritten
                else "obj_, default_"
            ),
            converter_name=converter_name,
            get_or_default_code=code_output,
        )
        converter = self._code_to_converter(
            converter_name=converter_name,
            code=converter_code,
            ctx=ctx,
            fake_filename="_convtools_gen_get_or_default",
        )
        default_code = self.default.gen_code_and_update_ctx(code_input, ctx)
        result = NaiveConversion(converter)
        if self_is_overwritten:
            result = result.call(
                EscapedString(code_self),
                GetItem(),
                EscapedString(default_code),
            )
        else:
            result = result.call(GetItem(), EscapedString(default_code))
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
    symbols_to_filter_out = re.compile(r"\W")

    def __init__(self, *args, **kwargs):
        super(Call, self).__init__(kwargs)
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


def Filter(condition_conv, cast=None, **kwargs):
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
        return GeneratorComp(GetItem(), **kwargs).filter(condition_conv)
    if cast is list:
        return ListComp(GetItem(), **kwargs).filter(condition_conv)
    if cast is tuple:
        return TupleComp(GetItem(), **kwargs).filter(condition_conv)
    if cast is set:
        return SetComp(GetItem(), **kwargs).filter(condition_conv)
    if callable(cast):
        gen = GeneratorComp(GetItem(), **kwargs).filter(condition_conv)
        return NaiveConversion(cast).call(gen)
    raise AssertionError("cannot cast generator to cast={}".format(cast))


class InlineExpr(BaseConversion):
    """This conversion allows to avoid function call overhead.
    It inlines a raw python code expression into
    the code of resulting conversion."""

    def __init__(self, code_str, **kwargs):
        """
        Args:
          code_str (str): python code string. Supports `{}` expressions of
            :py:obj:`str.format`, both positional and names ones.
            To pass arguments, use :py:obj:`InlineExpr.pass_args`
        """
        super().__init__(kwargs)
        self.code_str = code_str
        self.args = []
        self.kwargs = {}

    def __hash__(self):
        return hash(self.code_str)

    def pass_args(self, *args, **kwargs):
        """The method passes arguments to the code to be inlined.

        Args:
          args (tuple of objects): each is wrapped with :py:obj:`ensure_conversion`
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
    def __init__(self, item, **kwargs):
        """
        Args:
          item (object): to be wrapped with :py:obj:`ensure_conversion` and used
            as a conversion on each item of a collection.

            e.g. for ``[i * 2 for i in l]`` an item would be ``c.this() * 2``
        """
        super(BaseComprehensionConversion, self).__init__(kwargs)
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
        self_clone = self.clone()
        self_clone.condition_conversion = self_clone.ensure_conversion(
            condition_conversion
        )
        return self_clone

    def sort(self, key=None, reverse=False):
        """
        Args:
          key (object): to be wrapped with
            :py:obj:`ensure_conversion` and used as a key to sort the collection
          reverse (bool): if `True`, sorts DESC
        Returns:
          BaseComprehensionConversion: cloned and filtered comprehension
          conversion
        """
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
        return f"sorted({code_input}, key={sort_key_code}, reverse={reverse_code})"


class TupleComp(BaseComprehensionConversion):
    """Generates python tuple comprehension code."""

    def gen_comprehension_pre_sort(self, generator_code, ctx):
        if self.sort_key:
            return f"({generator_code})"
        return f"tuple({generator_code})"

    def gen_sort_code(self, code_input, ctx, sort_key_code, reverse_code):
        return f"tuple(sorted({code_input}, key={sort_key_code}, reverse={reverse_code}))"


class SetComp(BaseComprehensionConversion):
    """Generates python set comprehension code (obviously non-sortable)"""

    def gen_comprehension_pre_sort(self, generator_code, ctx):
        return "{%s}" % generator_code

    def sort(self, key=None, reverse=False):
        raise ConversionException("attempt to build sorted set")


class DictComp(BaseComprehensionConversion):
    """Generates python dict comprehension code."""

    def __init__(self, key, value, **kwargs):
        """
        Args:
          key (object): to be wrapped with :py:obj:`ensure_conversion` and
            used on each item of a collection to form keys
          value (object): to be wrapped with :py:obj:`ensure_conversion` and
            used on each item of a collection to form values
        """
        super(DictComp, self).__init__(item=None, **kwargs)
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
        return f"OrderedDict(sorted({code_input}, key={sort_key_code}, reverse={reverse_code}))"


class BaseCollectionConversion(BaseConversion):
    def __init__(self, *items, **kwargs):
        """
        Args:
          items (objects): items to form a collection from.
            every item gets wrapped with :py:obj:`ensure_conversion`
        """
        super(BaseCollectionConversion, self).__init__(kwargs)
        self.items = [self.ensure_conversion(item) for item in items]

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

    def _gen_code_and_update_ctx(self, code_input, ctx):
        joined_items_code = self.gen_joined_items_code(code_input, ctx)
        return self.gen_collection_from_items_code(
            joined_items_code, code_input, ctx
        )


class Tuple(BaseCollectionConversion):
    """Gets compiled into the code which generates a tuple"""

    def gen_collection_from_items_code(
        self, joined_items_code, code_input, ctx
    ):
        return f"({joined_items_code},)"


class List(BaseCollectionConversion):
    """Gets compiled into the code which generates a list"""

    def gen_collection_from_items_code(
        self, joined_items_code, code_input, ctx
    ):
        return f"[{joined_items_code}]"


class Set(BaseCollectionConversion):
    """Gets compiled into the code which generates a set"""

    def gen_collection_from_items_code(
        self, joined_items_code, code_input, ctx
    ):
        return "{%s}" % joined_items_code


class Dict(BaseCollectionConversion):
    """Gets compiled into the code which generates a dict"""

    def __init__(self, *key_value_pairs, **kwargs):
        """
        Args:
          key_value_pairs (:obj:`list` of :obj:`tuple`): each tuple is a
            key-value pair to form a dict from.
            Every key and value gets wrapped with ``ensure_conversion``
        """
        super(Dict, self).__init__(**kwargs)
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

    def gen_collection_from_items_code(
        self, joined_items_code, code_input, ctx
    ):
        return "{%s}" % joined_items_code
