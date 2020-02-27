import dis
import re
import sys
from collections import OrderedDict
from itertools import chain, count


__all__ = [
    "ensure_conversion",
    "ConversionException",
    "BaseConversion",
    "BaseCollectionConversion",
    "GeneratorComp",
    "NaiveConversion",
    "EscapedString",
    "InputArg",
    "InlineExpr",
    "GetAttr",
    "GetItem",
    "Call",
    "CallFunc",
    "Filter",
    "And",
    "Or",
    "If",
    "Not",
    "Dict",
    "DictComp",
    "List",
    "ListComp",
    "Set",
    "SetComp",
    "Tuple",
    "TupleComp",
]

converter_template = """
def {converter_name}({code_signature}):
    try:
{code}
    except Exception:
        import linecache
        linecache.cache[{converter_name}._fake_filename] = (
            len({converter_name}._code_str),
            None,
            {converter_name}._code_str.splitlines(),
            {converter_name}._fake_filename,
        )
        raise
"""
get_or_default_template = """
def {converter_name}({code_args}):
    try:
        return {get_or_default_code}
    except (TypeError, KeyError, IndexError, AttributeError):
        return default_
    except Exception:
        import linecache
        linecache.cache[{converter_name}._fake_filename] = (
            len({converter_name}._code_str),
            None,
            {converter_name}._code_str.splitlines(),
            {converter_name}._fake_filename,
        )
        raise
"""


def ensure_conversion(conversion: object):
    r"""Helps to define conversions based on its type:
        * any conversion is returned untouched
        * list/dict/set/tuple collections are wrapped with ``c.list``,
          ``c.dict``, ``c.set``, ``c.tuple`` (see below).
          If it's not desired, use ``c.naive`` instead
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

        self._number = next(self.counter)
        if self._number > self.max_counter:
            BaseConversion.counter = count()
        self.debug = options.pop("debug", False)
        self._predefined_input = None

        if "_predefined_input" in options:
            self.set_predefined_input(options.pop("_predefined_input"))

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
        if self._predefined_input is not None:
            code_input = self._predefined_input.gen_code_and_update_ctx(
                code_input, ctx
            )
        return self._gen_code_and_update_ctx(code_input, ctx)

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

    def clone(self):
        clone = self.__class__.__new__(self.__class__)
        clone.__dict__.update(self.__dict__)
        return clone

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

    def _get_args(self):
        return sorted(
            {
                dep.arg_name: dep
                for dep in chain(self.depends_on, (self,))
                if isinstance(dep, InputArg)
            }.values(),
            key=lambda k: k.arg_name,
        )

    def _get_args_def_code(self, ctx, as_kwargs=False, exclude_cls_self=False):
        args = self._get_args()
        if exclude_cls_self:
            args = [arg for arg in args if arg.arg_name not in ("self", "cls")]
        if not args:
            return ""
        _code = ", ".join(arg.gen_code_and_update_ctx("", ctx) for arg in args)
        if as_kwargs:
            return ", *, {}".format(_code)
        return ", {}".format(_code)

    def _get_args_as_func_args(self):
        args = self._get_args()
        return tuple(EscapedString(arg.arg_name) for arg in args)

    def _init_tmp_ctx(self, root_ctx):
        return {"sys": sys, "__debug": root_ctx.get("__debug")}

    def _code_to_converter(self, converter_name, code, ctx, fake_filename):
        if ctx.get("__debug", False):
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
        exec(code_obj, ctx, ctx)
        converter = ctx[converter_name]
        converter._code_str = code
        converter._fake_filename = fake_filename
        return converter

    def gen_converter(
        self, method=False, class_method=False, signature=None, debug=None
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

        Returns:
          The compiled function
        """
        # signature should contain "data_" argument
        initial_code_input = "data_"
        ctx = {"sys": sys, "__debug": debug}
        if signature:
            missing_args = set(
                _pattern_word.findall(self._get_args_def_code({}))
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
            signature = (
                ("self, " if method else "")
                + ("cls, " if class_method else "")
                + (initial_code_input)
                + (
                    self._get_args_def_code(
                        ctx, as_kwargs=True, exclude_cls_self=True
                    )
                )
            )

        if debug is not None:
            self.debug = debug
        converter_name = self.gen_name("converter", ctx)

        conv = self
        pipes = [conv]
        while conv._predefined_input is not None:
            conv = conv._predefined_input
            pipes.append(conv)

        last_index = len(pipes) - 1
        code_input = initial_code_input
        code_lines = []
        indent = " " * 4 * 2
        for index, conv in enumerate(reversed(pipes)):
            _predefined_input = conv._predefined_input
            conv._predefined_input = None
            code_conv = conv.gen_code_and_update_ctx(code_input, ctx)
            conv._predefined_input = _predefined_input

            code_input = self.gen_name("pipe", ctx, code_input)
            if index != last_index:
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

    def eq(self, arg):
        return InlineExpr("{0} == {1}").pass_args(self, arg)

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

    def filter(self, condition_conv, cast=None):
        """Shortcut for calling :py:obj:`convtools.base.Filter` on self"""
        return Filter(condition_conv, cast=cast, _predefined_input=self)

    def set_predefined_input(self, input_conversion):
        if self._predefined_input is not None:
            raise ConversionException(
                "attempt to overwrite _predefined_input",
                self,
                input_conversion,
            )
        self._predefined_input = self.ensure_conversion(input_conversion)
        return self

    def pipe(self, next_conversion, *args, **kwargs):
        """Passes the result of current conversion as an input to the
        `next_conversion`.
        If `next_conversion` is callable, it gets called with self as the
        first param.
        If piping is done at the top level of a resulting conversion (not nested),
        then it's going to be represented as several statements.

        Args:
          next_conversion (object): to be wrapped with :py:obj:`ensure_conversion`
            and called if callable is passed
          args (tuple): to be wrapped with :py:obj:`ensure_conversion` and
            passed to `next_conversion` if it's callable
          kwargs (dict): to be wrapped with :py:obj:`ensure_conversion` and
            passed to `next_conversion` if it's callable
        """
        if callable(next_conversion):
            return (
                ensure_conversion(next_conversion)
                .clone()
                .call(self, *args, **kwargs)
            )

        return (
            ensure_conversion(next_conversion)
            .clone()
            .set_predefined_input(self)
        )


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

    def __init__(self, value: object, name_prefix="v", **kwargs):
        """
        Args:
          value (object): any object

        """
        super(NaiveConversion, self).__init__(kwargs)
        self.value = value
        self.name_prefix = name_prefix
        if callable(value):
            f_name = var_name_from_string(getattr(value, "__name__", ""))
            self.name_prefix = f"{self.name_prefix}{f_name}"

    def _gen_code_and_update_ctx(self, code_input, ctx):
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


class If(BaseConversion):
    """Generates the if expression code.

    Checks the code of the input, if it
    doesn't seem to be complex, then just proceeds with it as is.
    If it's not simple (some index/attribute lookups or function calls are
    in there), then it caches the input for further reuse in if_true and if_false
    clauses."""

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

    def input_is_simple(self, code_input):
        if (
            next(self.symbols_making_expr_complex.finditer(code_input), None)
            is None
        ):
            return True
        return False

    def _gen_code_and_update_ctx(self, code_input, ctx):
        _none = self._none

        if self.no_input_caching or self.input_is_simple(code_input):
            if_conv = if_true = if_false = EscapedString(code_input)

        else:

            def value_cache(value_to_cache=_none):
                if value_to_cache is _none:
                    return value_cache.cached_value
                value_cache.cached_value = value_to_cache
                return value_to_cache

            caching_conv = NaiveConversion(value_cache)
            if_conv = caching_conv.call(EscapedString(code_input))
            if_true = if_false = caching_conv.call()

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

        exec_ctx = self._init_tmp_ctx(ctx)
        self_is_overwritten = code_self != code_input
        code_output = "self_" if self_is_overwritten else "obj_"
        for index in self.indexes:
            code_index = index.gen_code_and_update_ctx("obj_", exec_ctx)
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
            ctx=exec_ctx,
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
                "{}={}".format(k, v.gen_code_and_update_ctx(code_input, ctx),)
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
          key_value_pairs (:obj:`list` of :obj:`tuple`): each tuple is a key-value
            pair to form a dict from.
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
