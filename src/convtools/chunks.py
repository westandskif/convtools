"""
Provides conversions for slicing iterables into chunks.
"""
import typing as t

from .aggregations import Aggregate
from .base import (
    BaseConversion,
    Code,
    ConversionWrapper,
    EscapedString,
    GeneratorComp,
    NamedConversion,
    This,
)


class BaseChunkBy(BaseConversion):
    def aggregate(self, *args, **kwargs) -> "BaseConversion":
        return self.pipe(GeneratorComp(Aggregate(*args, **kwargs)))


class ChunkBy(BaseChunkBy):
    """Slices iterable into chunks by element values and/or size of chunks.

    >>> # simple #1
    >>> c.chunk_by(size=1000)
    >>>
    >>> # simple #2
    >>> c.chunk_by(c.item("x"))
    >>>
    >>> # with aggregate
    >>> c.chunk_by(
    >>>     c.item("x"),
    >>>     size=1000
    >>> ).aggregate({
    >>>     "x": c.ReduceFuncs.Last(c.item("x")),
    >>>     "y": c.ReduceFuncs.Sum(c.item("y")),
    >>> })

    It also provides a shortcut for running
    :py:obj:`convtools.aggregations.Aggregate` on chunks.
    """

    def __init__(self, *by, size: t.Optional[int] = None):
        """
        Args:
          by: fields/conversions to use for slicing into chunks (elements with
            same values go to the same chunk)
          size: (optional) positive int to limit max size of a chunk
        """
        super().__init__()
        if size is not None:
            if not isinstance(size, int) or size <= 0:
                raise ValueError("size has to be positive int or None")
        if not by and not size:
            raise ValueError("pass at least one of by or size params")

        self.by = (
            (self.ensure_conversion(by if len(by) > 1 else by[0]))
            if by
            else None
        )
        self.size = size

    def _gen_code_and_update_ctx(self, code_input, ctx):
        converter_name = self.gen_name("chunk_by", ctx, self)
        code_args = self.by.get_args_def_code() if self.by else ""
        func_args = self.by.get_args_as_func_args() if self.by else ()

        code = Code()
        code.add_line(f"def {converter_name}(items_{code_args}):", 1)
        code.add_line("items_ = iter(items_)", 0)
        code.add_line("try:", 0)
        code.add_line("    item_ = next(items_)", 0)
        code.add_line("except StopIteration:", 0)
        code.add_line("    return", 0)

        code.add_line("chunk_ = [item_]", 0)

        code_item_to_signature = (
            self.by.gen_code_and_update_ctx("item_", ctx) if self.by else None
        )

        code_before_for = Code()
        code_after_for = Code()
        code_if_condition = None
        code_if_continue_chunk = Code()
        code_if_new_chunk = Code()

        code_if_continue_chunk.add_line("chunk_.append(item_)", 0)
        code_if_new_chunk.add_line("yield chunk_", 0)
        code_if_new_chunk.add_line("chunk_ = [item_]", 0)

        if code_item_to_signature and self.size:
            code_if_condition = (
                "chunk_item_signature == new_item_signature and size_ < "
                f"{self.size}"
            )

        if code_item_to_signature:
            code_before_for.add_line(
                f"chunk_item_signature = {code_item_to_signature}", 0
            )
            code_after_for.add_line(
                f"new_item_signature = {code_item_to_signature}", 0
            )
            code_if_condition = (
                code_if_condition
                or "chunk_item_signature == new_item_signature"
            )
            code_if_new_chunk.add_line(
                "chunk_item_signature = new_item_signature", 0
            )

        if self.size:
            code_before_for.add_line("size_ = 1", 0)
            code_if_condition = code_if_condition or f"size_ < {self.size}"
            code_if_continue_chunk.add_line("size_ = size_ + 1", 0)
            code_if_new_chunk.add_line("size_ = 1", 0)

        if not code_if_condition:
            raise AssertionError("impossible case")

        code.add_code(code_before_for)
        code.add_line("for item_ in items_:", 1)
        code.add_code(code_after_for)
        code.add_line(f"if {code_if_condition}:", 1)
        code.add_code(code_if_continue_chunk)
        code.incr_indent_level(-1)
        code.add_line("else:", 1)
        code.add_code(code_if_new_chunk)
        code.incr_indent_level(-2)
        code.add_line("yield chunk_", -1)

        self._code_to_converter(converter_name, code.to_string(0), ctx)

        return (
            EscapedString(converter_name)
            .call(This(), *func_args)
            .gen_code_and_update_ctx(code_input, ctx)
        )


CHUNK_BY_CONDITION_TEMPLATE = """
def {converter_name}(items_{code_args}):
    items_ = iter(items_)
    try:
        chunk_ = [next(items_)]
    except StopIteration:
        return

    for item_ in items_:
        if {code_condition}:
            chunk_.append(item_)
        else:
            yield chunk_
            chunk_ = [item_]

    yield chunk_
"""


class ChunkByCondition(BaseChunkBy):
    """Slices iterable into chunks based on condition, which is a function of a
    current chunk and a current element.

    >>> # example #1
    >>> c.chunk_by_condition(c.CHUNK.len() < 100)
    >>>
    >>> # example #2
    >>> c.chunk_by_condition(
    >>>     c.and_(
    >>>         c.CHUNK.item(-1) == c.this(),
    >>>         c.CHUNK.item(-1) - c.this() < 100
    >>>     )
    >>> )
    >>> # with aggregate
    >>> c.chunk_by_condition(
    >>>     c.CHUNK.len() < 100
    >>> ).aggregate({
    >>>     "x": c.ReduceFuncs.Last(c.item("x")),
    >>>     "y": c.ReduceFuncs.Sum(c.item("y")),
    >>> })

    It also provides a shortcut for running
    :py:obj:`convtools.aggregations.Aggregate` on chunks.
    """

    CHUNK = NamedConversion("chunk_", This())

    def __init__(self, condition):
        super().__init__()
        self.condition = ConversionWrapper(
            self.ensure_conversion(condition),
            name_to_code_input={self.CHUNK.name: "chunk_"},
        )

    def _gen_code_and_update_ctx(self, code_input, ctx):
        converter_name = self.gen_name("chunk_by_condition", ctx, self)
        code = CHUNK_BY_CONDITION_TEMPLATE.format(
            converter_name=converter_name,
            code_args=self.condition.get_args_def_code(),
            code_condition=self.condition.gen_code_and_update_ctx(
                "item_", ctx
            ),
        )
        self._code_to_converter(converter_name, code, ctx)
        return (
            EscapedString(converter_name)
            .call(
                This(),
                *self.condition.get_args_as_func_args(),
            )
            .gen_code_and_update_ctx(code_input, ctx)
        )
