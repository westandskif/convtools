"""Provides cumulative conversions"""
import typing as t
from uuid import uuid4

from .base import (
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
    """A conversion which resets cumulative values to their initial states. The
    main use case is within nested iterables:

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
    """A conversion which calculates cumulative values. The main use case is
    using it within iterables:

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
        """
        Args:
          parent: conversion which is used as an input
          prepare_first: conversion which gets initial value from the first
            element
          reduce_two: conversion which reduces two values to one
          label_name: custom name of cumulative to be used. It is needed when
            :py:obj:`CumulativeReset`
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
