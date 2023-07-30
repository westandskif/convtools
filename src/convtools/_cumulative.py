"""Cumulative conversions."""
import typing as t
from uuid import uuid4

from ._base import (
    BaseConversion,
    EscapedString,
    If,
    LabelConversion,
    LazyEscapedString,
    NaiveConversion,
    Namespace,
    PipeConversion,
)


class CumulativeReset(BaseConversion):
    """Reset cumulative value to its initial state.

    >>> assert (
    >>>     c.iter(
    >>>         c.cumulative_reset("abc")
    >>>         .iter(c.cumulative(c.this, c.this + c.PREV, label_name="abc"))
    >>>         .as_type(list)
    >>>     )
    >>>     .as_type(list)
    >>>     .execute([[0, 1, 2], [3, 4]])
    >>> ) == [[0, 1, 3], [3, 7]]
    """

    def __init__(self, parent: "t.Any", label_name: str):
        super().__init__()
        self.label_name = label_name
        self.parent = self.ensure_conversion(parent)
        self.contents |= BaseConversion.ContentTypes.NEW_LABEL

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return (
            f"(_labels.pop({repr(self.label_name)}, None), "
            f"{self.parent.gen_code_and_update_ctx(code_input, ctx)})[1]"
        )


class Cumulative(BaseConversion):
    """Calculate cumulative values within iterables.

    Example:
    >>> assert (
    >>>     c.iter(c.cumulative(c.this, c.this + c.PREV))
    >>>     .as_type(list)
    >>>     .execute([0, 1, 2, 3, 4])
    >>> ) == [0, 1, 3, 6, 10]
    """

    PREV = LazyEscapedString("prev_value")

    def __init__(
        self,
        parent: "t.Any",
        prepare_first: "t.Any",
        reduce_two: "t.Any",
        label_name: "t.Optional[str]" = None,
    ):
        """Initialize cumulative conversion.

        Args:
          parent: conversion which is used as an input
          prepare_first: conversion to apply to the first element
          reduce_two: conversion to reduce two values to one
          label_name: custom name of cumulative to be used. It is needed when
            `c.cumulative_reset(label_name)`
        """
        super().__init__()
        self.label_name = label_name or uuid4().hex

        self.parent = self.ensure_conversion(parent)

        label_conversion = LabelConversion(self.label_name)

        self.prepare_first = self.ensure_conversion(prepare_first)
        self.reduce_two = self.ensure_conversion(
            Namespace(
                reduce_two,
                name_to_code={
                    self.PREV.name: label_conversion.gen_code_and_update_ctx(
                        None, label_conversion._init_ctx()
                    )
                },
            )
        )
        self.contents |= BaseConversion.ContentTypes.NEW_LABEL

    def _gen_code_and_update_ctx(self, code_input, ctx):
        return PipeConversion(
            self.parent,
            If(
                NaiveConversion(self.label_name).in_(
                    EscapedString(LabelConversion.labels_code_name)
                ),
                self.reduce_two,
                self.prepare_first,
            ),
            label_output=self.label_name,
        ).gen_code_and_update_ctx(code_input, ctx)
