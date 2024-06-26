"""Implements streaming operations on table-like data and csv files.

Conversions are defined in realtime based on table headers and called methods:
 - update
 - take
 - drop
 - join

"""

import csv
from collections.abc import Callable, Sized
from itertools import chain, zip_longest
from typing import (
    Any,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    TextIO,
    Tuple,
    Union,
    cast,
)

from .._aggregations import Aggregate, GroupBy, ReduceFuncs
from .._base import (
    And,
    BaseConversion,
    CallFunc,
    ConverterOptionsCtx,
    EscapedString,
    GeneratorComp,
    GetItem,
    If,
    InlineExpr,
    InputArg,
    NaiveConversion,
    This,
    Tuple_,
    ensure_conversion,
)
from .._columns import ColumnChanges, ColumnRef, MetaColumns
from .._joins import JoinConversion, LeftJoinCondition, RightJoinCondition


_none = BaseConversion._none


class CloseFileIterator:
    """Iterator wrapper, which closes file in the end."""

    def __init__(self, file_to_close):
        """Init instance.

        Args:
          file_to_close: file descriptor to be closed the first time __next__
            is called on this wrapper
        """
        self.file_to_close = file_to_close

    def __iter__(self):
        """Returns empty iterator."""
        return self

    def __next__(self):
        """Stops iteration and closes the underlying file descriptor."""
        self.file_to_close.close()
        self.file_to_close = None
        raise StopIteration

    def __del__(self):
        """Closes the file descriptor on garbage collection."""
        # Consider rewriting with: weakref.finalize
        if self.file_to_close:
            self.file_to_close.close()
            self.file_to_close = None


class CustomCsvDialect(csv.Dialect):
    """Create custom csv dialects without defining classes."""

    def __init__(
        self,
        delimiter=csv.excel.delimiter,
        quotechar=csv.excel.quotechar,
        escapechar=csv.excel.escapechar,
        doublequote=csv.excel.doublequote,
        skipinitialspace=csv.excel.skipinitialspace,
        lineterminator=csv.excel.lineterminator,
        quoting=csv.excel.quoting,
    ):
        """Init self."""
        self.delimiter = delimiter
        self.quotechar = quotechar
        self.escapechar = escapechar
        self.doublequote = doublequote
        self.skipinitialspace = skipinitialspace
        self.lineterminator = lineterminator
        self.quoting = quoting
        super().__init__()


class Table:
    """Streaming operations on table-like data and csv files.

    >>> Table.from_csv("input.csv", header=True).update(
    >>>     c=c.item("a") + c.item("b")
    >>> ).into_csv("output.csv")

    >>> list(
    >>>     Table.from_rows(
    >>>         [
    >>>             ("a", "b"),
    >>>             (1, 2),
    >>>             (3, 4),
    >>>         ],
    >>>         header=True,
    >>>     )
    >>>     .update(c=c.col("a") + c.col("b"))
    >>>     .into_iter_rows()
    >>> )
    [("a", "b", "c"), (1, 2, 3), (3, 4, 7)]

    """

    def __init__(
        self,
        row_type: "Optional[type]",
        rows_objects: "List[Iterable]",
        meta_columns: "MetaColumns",
        pending_changes: int,
        pipeline: "Optional[BaseConversion]" = None,
        file_to_close=None,
    ):
        """For internal use only. Use from_rows and from_csv methods."""
        self.row_type = row_type
        self.rows_objects: "Optional[List[Iterable]]" = rows_objects
        self.meta_columns = meta_columns
        self.pending_changes = pending_changes
        self.pipeline = pipeline
        self.file_to_close = file_to_close
        self.row_type = row_type

    def get_columns(self) -> "List[str]":
        """Return list of column names."""
        return [column.name for column in self.meta_columns.columns]

    columns = property(get_columns)

    @classmethod
    def from_rows(
        cls,
        rows: "Iterable[Union[dict, tuple, list, Any]]",
        header: """Optional[
            Union[
                bool, List[str], Tuple[str, ...], Mapping[str, Union[str, int]]
            ]
        ]""" = None,
        # Literal["raise", "keep", "drop", "mangle"]
        duplicate_columns: str = "raise",
        skip_rows: int = 0,
        file_to_close=None,
    ) -> "Table":
        """Initialize a table from an iterable of rows.

        Args:
          rows: can be either an iterable of any objects if no header inference
            is required OR an iterable of dicts, tuples or lists
          header: specifies header inference mode:

             * True: takes either the first tuple/list or keys of the first
               dict as a header
             * False: there's no header in input data, use numbered columns
               instead: COLUMN_0, COLUMN_1, etc.
             * list/tuple of str: there's no header in input data, so this is
               the header to be used (raises ValueError if numbers of columns
               don't match)
             * dict: its keys form the header, values are str/int indices to
               take values of columns from input rows (raises ValueError if
               numbers of columns don't match)
             * None: inspects the first row and if it's a dict, then takes its
               keys as a header

          duplicate_columns: either of following ("raise" by default):

            * "raise": ValueError is raise if a duplicate column is detected
            * "keep": duplicate columns are left as is, but when referenced the
              first one is used
            * "drop": duplicate columns are skipped
            * "mangle": names of duplicate columns are mangled like: "name",
              "name_1", "name_2", etc.

          skip_rows: number of rows to skip at the beginning. Useful when input
            data contains a header, but you provide your own - in this case
            it's convenient to skip the heading row from the input

          file_to_close: for internal use

        """
        columns = MetaColumns(duplicate_columns=duplicate_columns)

        rows = iter(rows)

        if skip_rows:
            for _ in range(skip_rows):
                next(rows)

        first_row = next(rows, _none)
        first_row_is_sized = isinstance(first_row, Sized)
        row_type = tuple if first_row is _none else type(first_row)
        pending_changes = 0

        index: "Union[str, int]"
        if isinstance(header, (tuple, list)):
            if first_row is _none:
                for index, name in enumerate(header):
                    pending_changes |= columns.add(name, index, None)[1]

            elif first_row_is_sized:
                first_row = cast(Sized, first_row)
                if len(header) != len(first_row):
                    raise ValueError("non-matching number of columns")
                for index, column in enumerate(header):
                    pending_changes |= columns.add(column, index, None)[1]
            else:
                if len(header) != 1:
                    raise ValueError("non-matching number of columns")
                pending_changes |= columns.add(header[0], None, This())[1]

        elif isinstance(header, dict):
            if first_row is _none:
                for name, index in header.items():
                    pending_changes |= columns.add(name, index, None)[1]

            elif first_row_is_sized:
                first_row = cast(Sized, first_row)
                if len(header) != len(first_row):
                    raise ValueError("non-matching number of columns")
                for name, index in header.items():
                    pending_changes |= columns.add(name, index, None)[1]
            else:
                raise ValueError(
                    "first row is not sized to apply header as dict"
                )

        # inferring a header
        elif isinstance(first_row, dict):
            if header is False:
                for key in first_row:
                    pending_changes |= columns.add(None, key, None)[1]
                pending_changes |= ColumnChanges.MUTATE
            else:
                for key in first_row:
                    pending_changes |= columns.add(key, key, None)[1]

        elif isinstance(first_row, (tuple, list)):
            if header is True:
                for index, column_name in enumerate(first_row):
                    pending_changes |= columns.add(column_name, index, None)[1]
                first_row = None

            else:
                for index in range(len(first_row)):
                    pending_changes |= columns.add(None, index, None)[1]

        else:
            if header is True:
                if first_row is _none:
                    raise ValueError(
                        "impossible to infer header of an empty sequence"
                    )
                else:
                    pending_changes |= columns.add(first_row, None, This())[1]
                    first_row = None
            else:
                pending_changes |= columns.add(None, None, This())[1]

            pending_changes |= ColumnChanges.MUTATE

        rows_objects: "List[Iterable]" = [rows]
        if first_row is not None and first_row is not _none:
            rows_objects.insert(0, (first_row,))

        return cls(
            row_type=row_type,
            rows_objects=rows_objects,
            meta_columns=columns,
            pending_changes=pending_changes,
            file_to_close=file_to_close,
        )

    csv_dialect = CustomCsvDialect

    @classmethod
    def from_csv(
        cls,
        filepath_or_buffer: "Union[str, TextIO]",
        header: """Optional[
            Union[
                bool, List[str], Tuple[str], Mapping[str, Union[str, int]]
            ]
        ]""" = None,
        duplicate_columns: str = "mangle",
        skip_rows: int = 0,
        dialect: "Union[str, CustomCsvDialect]" = "excel",
        encoding: str = "utf-8",
    ) -> "Table":
        """Initialize a table conversion from a csv-like object.

        Args:
          filepath_or_buffer: a filepath or something :py:obj:`csv.reader` can
            read

          header: specifies header inference mode:
             * True: takes either the first tuple/list or keys of the first
               dict as a header
             * False: there's no header in input data, use numbered columns
               instead: COLUMN_0, COLUMN_1, etc.
             * list/tuple of str: there's no header in input data, so this is
               the header to be used (raises ValueError if numbers of columns
               don't match)
             * dict: its keys form the header, values are str/int indices to
               take values of columns from input rows (raises ValueError if
               numbers of columns don't match)
             * None: inspects the first row and if it's a dict, then takes its
               keys as a header

          duplicate_columns: either of following ("mangle" by default):
            * "raise": ValueError is raise if a duplicate column is detected
            * "keep": duplicate columns are left as is, but when referenced the
              first one is used
            * "drop": duplicate columns are skipped
            * "mangle": names of duplicate columns are mangled like: "name",
              "name_1", "name_2", etc.

          skip_rows: number of rows to skip at the beginning. Useful when input
            data contains a header, but you provide your own - in this case
            it's convenient to skip the heading row from the input

          dialect: a dialect acceptable by :py:obj:`csv.reader` There's a
            helper method:
            :py:obj:`convtools.contrib.tables.Table.csv_dialect` to create
            dialects without defining classes

          encoding: encoding to pass to :py:obj:`open`
        """
        file_to_close: "Optional[TextIO]"
        buffer: "TextIO"
        if isinstance(filepath_or_buffer, str):
            buffer = file_to_close = (
                open(  # pylint: disable=consider-using-with # noqa: SIM115
                    filepath_or_buffer,
                    "r",
                    encoding=encoding,
                )
            )
        else:
            buffer = filepath_or_buffer
            file_to_close = None

        rows = map(
            tuple,  # type: ignore
            csv.reader(buffer, dialect=dialect),
        )

        return cls.from_rows(
            rows,
            header,
            duplicate_columns,
            skip_rows=skip_rows,
            file_to_close=file_to_close,
        )

    def embed_conversions(self) -> "Table":
        """For internal use only.

        There's no need in calling this directly, it's done automatically
        when you use :py:obj:`convtools.contrib.tables.Table.update` or
        :py:obj:`convtools.contrib.tables.Table.join` See the explanation
        below:

        Since each column is either:
          * simply taken by index (cheap)
          * or obtained by performing arbitrary convtools conversion (may be
            expensive)

        it's important to have multiple layers of processing when something
        depends on something which may be expensive to calculate.

        This method adds a new processing stage to a pipeline and exposes all
        "cheap" columns to further conversions.
        """
        if any(column.conversion for column in self.meta_columns.columns):
            column_conversions = []
            for index, column in enumerate(self.meta_columns.columns):
                if column.index is None:
                    column_conversions.append(column.conversion)
                    column.conversion = None
                else:
                    column_conversions.append(GetItem(column.index))
                column.index = index

            conversion = GeneratorComp(tuple(column_conversions), _none, _none)

            self.pipeline = (
                conversion
                if self.pipeline is None
                else self.pipeline.pipe(conversion)
            )
            self.pending_changes = 0
            self.row_type = tuple

        return self

    def _set_col_indexes(self, name_to_column, conversion):
        conversion = ensure_conversion(conversion)

        for ref in conversion.get_dependencies(types=ColumnRef):
            column = name_to_column[ref.name]
            if column.conversion is not None:
                self.embed_conversions()
            ref.set_index(column.index)

        return conversion

    def filter(self, condition: "BaseConversion") -> "Table":
        """Keep rows where ``condition`` resolves to `True`."""
        condition = self._set_col_indexes(
            self.meta_columns.get_name_to_column(), condition
        )
        self.pipeline = (self.pipeline or This()).filter(condition)
        return self

    def update(self, **column_to_conversion) -> "Table":
        """The main method to mutate table-like data.

        Args:
          column_to_conversion: dict where keys are new or existing columns and
            values are conversions to be applied row-wise
        """
        column_name_to_column = self.meta_columns.get_name_to_column()

        for column_name in list(column_to_conversion):
            conversion = self._set_col_indexes(
                column_name_to_column, column_to_conversion[column_name]
            )

            if column_name in column_name_to_column:
                column = column_name_to_column[column_name]
                column.conversion = conversion
                column.index = None
            else:
                column, state = self.meta_columns.add(
                    column_name, None, conversion
                )
                self.pending_changes |= state
                column_name_to_column[column.name] = column

            self.pending_changes |= ColumnChanges.MUTATE

        return self

    def update_all(self, *conversions) -> "Table":
        """Table-wide mutations, applied to each value of each column.

        Args:
          conversions: conversion to apply to each value of each column
        """
        conversion: "BaseConversion" = This()
        for conversion_ in conversions:
            conversion = conversion.pipe(conversion_)
        column_to_conversion = {
            column.name: ColumnRef(column.name).pipe(conversion)
            for column in self.meta_columns.columns
        }
        return self.update(**column_to_conversion)

    def rename(
        self, columns: "Union[Tuple[str], List[str], Mapping[str, str]]"
    ) -> "Table":
        """Rename columns.

        The behavior depends on type of columns argument.

        Args:
          columns:
            * tuple/list: then it defines new column names (length of
              passed columns should match number of columns inside).
            * dict: defines a mapping from old column names to new ones.
        """
        renamed = False
        if isinstance(columns, dict):
            for column_ in self.meta_columns.columns:
                if column_.name in columns:
                    column_.name = columns[column_.name]
                    renamed = True

        elif isinstance(columns, (tuple, list)):
            if len(columns) != len(self.meta_columns.columns):
                raise ValueError("non-matching number of columns")
            for column_, new_column_name in zip(
                self.meta_columns.columns, columns
            ):
                column_.name = new_column_name
            renamed = True

        else:
            raise TypeError("unsupported columns type")

        if renamed and self.row_type is dict:
            self.pending_changes |= ColumnChanges.MUTATE

        return self

    def take(self, *column_names: "Union[str, Any]") -> "Table":
        """Leave only specified columns, omitting the rest.

        ``...`` references non-mentioned columns, so it's easy to both take a
        few columns:

        >>> table.take("a", "b")

        and rearrange them:

        >>> table.take("c", "d", ...)

        Args:
          column_names: columns to keep
        """
        self.meta_columns = self.meta_columns.take(*column_names)
        self.pending_changes |= ColumnChanges.REARRANGE
        return self

    def drop(self, *column_names: str) -> "Table":
        """Drops specified columns, keeping the rest.

        Args:
          column_names: columns to drop
        """
        self.meta_columns = self.meta_columns.drop(*column_names)
        if column_names:
            self.pending_changes |= ColumnChanges.REARRANGE
        return self

    def zip(self, table: "Table", fill_value=None) -> "Table":
        """Zip tables one to another.

        Before using this method, make sure you are not looking for
        `convtools.contrib.tables.Table.join`

        Let's assume fill_value is set to " ":

        >>> Table 1      Table 2
        >>> | a | b |    | b | c |
        >>> | 1 | 2 |    | 3 | 4 |
        >>>              | 5 | 6 |
        >>>
        >>> table1.zip(table2, fill_value=" ")
        >>>
        >>> Result:
        >>> | a | b | b | c |
        >>> | 1 | 2 | 3 | 4 |
        >>> |   |   | 5 | 6 |

        Args:
          table: table to be chained
          fill_value: value to use for filling gaps
        """
        new_columns = MetaColumns(duplicate_columns="keep")
        left_columns = self.meta_columns.get_name_to_column()
        right_columns = table.meta_columns.get_name_to_column()

        left_fill_value = tuple(fill_value for _ in range(len(left_columns)))
        right_fill_value = tuple(fill_value for _ in range(len(right_columns)))

        for index, name in enumerate(left_columns):
            new_columns.add(name, None, GetItem(0, index))
        for index, name in enumerate(right_columns):
            new_columns.add(name, None, GetItem(1, index))

        new_rows = (
            (
                (left_fill_value, t[1])
                if t[0] is None
                else ((t[0], right_fill_value) if t[1] is None else t)
            )
            for t in zip_longest(
                self.into_iter_rows(tuple), table.into_iter_rows(tuple)
            )
        )
        return Table(
            row_type=tuple,
            rows_objects=[new_rows],
            meta_columns=new_columns,
            pending_changes=ColumnChanges.MUTATE,
        )

    def chain(
        self,
        table: "Table",
        fill_value=None,
    ) -> "Table":
        """Chain tables, putting them one after another.

        Let's assume fill_value is set to " ":

        >>> Table 1      Table 2
        >>> | a | b |    | b | c |
        >>> | 1 | 2 |    | 3 | 4 |
        >>>
        >>> table1.chain(table2, fill_value=" ")
        >>>
        >>> Result:
        >>> | a | b | c |
        >>> | 1 | 2 |   |
        >>> |   | 3 | 4 |

        Args:
          table: table to be chained
          fill_value: value to use for filling gaps
        """
        if self.rows_objects is None:
            raise AssertionError("move_rows called the 2nd time")
        if (
            self.meta_columns.is_same_as(table.meta_columns)
            and not self.pending_changes
            and not self.pipeline
            and not table.pending_changes
            and not table.pipeline
        ):
            self.rows_objects.extend(table.move_rows_objects())
            return self

        first_name_to_columns = self.meta_columns.get_name_to_column()
        second_name_to_columns = table.meta_columns.get_name_to_column()

        new_columns = MetaColumns(duplicate_columns="raise")
        first_columns = MetaColumns(
            duplicate_columns=self.meta_columns.duplicate_columns,
        )
        second_columns = MetaColumns(
            duplicate_columns=table.meta_columns.duplicate_columns,
        )
        fill_value_conversion = NaiveConversion(fill_value)

        index = 0
        for name, first_column in first_name_to_columns.items():
            new_columns.add(name, index, None)
            first_columns.add(*first_column.as_tuple())
            if name in second_name_to_columns:
                second_columns.add(*second_name_to_columns[name].as_tuple())
            else:
                second_columns.add(name, None, fill_value_conversion)
            index += 1

        for name, second_column in second_name_to_columns.items():
            if name in first_name_to_columns:
                continue
            new_columns.add(name, index, None)
            first_columns.add(name, None, fill_value_conversion)
            second_columns.add(*second_column.as_tuple())
            index += 1

        if not self.meta_columns.is_same_as(first_columns):
            self.pending_changes |= ColumnChanges.MUTATE
        self.meta_columns = first_columns

        if not table.meta_columns.is_same_as(second_columns):
            table.pending_changes |= ColumnChanges.MUTATE
        table.meta_columns = second_columns

        row_type = self.row_type or tuple
        rows_objects = (
            self.into_list_of_iterables() + table.into_list_of_iterables()
        )
        return Table(
            row_type=row_type,
            rows_objects=rows_objects,
            meta_columns=new_columns,
            pending_changes=0,
        )

    def join(
        self,
        table: "Table",
        on: "Union[BaseConversion, str, Iterable[str]]",
        how: str,
        suffixes=("_LEFT", "_RIGHT"),
    ) -> "Table":
        """Classic table join.

        Args:
          table: another table conversion to join to self
          on:
            * either a join conversion like
              ``c.LEFT.col("a") == c.RIGHT.col("A")``
            * or iterable of column names to join on

          how: either of these: "inner", "left", "right", "outer" (same as
            "full")
          suffixes: tuple of two strings: the first one is the suffix to be
            added to left columns, having conflicting names with right columns;
            the second one is added to conflicting right ones. When ``on`` is
            an iterable of strings, these columns are excluded from suffixing.
        """
        how = JoinConversion.validate_how(how)
        left = self.embed_conversions()
        right = table.embed_conversions()

        for table_ in (left, right):
            # after embedding there are no conversions, only indexes.
            # indexes can be used as is except for dict-based data after
            # renamings, but if we skip rebuilding it from scratch by
            # into_list_of_iterables we can continue using indexes
            if table_.row_type is dict and table_.pending_changes:
                table_.pending_changes = 0

        left_join_conversion = LeftJoinCondition()
        right_join_conversion = RightJoinCondition()
        left_column_name_to_column = left.meta_columns.get_name_to_column()
        right_column_name_to_column = right.meta_columns.get_name_to_column()

        after_join_conversions: "List[BaseConversion]" = []
        after_join_column_names: "List[str]" = []

        if isinstance(on, BaseConversion):
            # intentionally left blank to force suffixing
            join_columns = set()
            join_condition = on
            for ref in join_condition.get_dependencies(types=ColumnRef):
                if ref.id_ == left_join_conversion.NAME:
                    column = left_column_name_to_column[ref.name]
                elif ref.id_ == right_join_conversion.NAME:
                    column = right_column_name_to_column[ref.name]
                else:
                    raise ValueError("ambiguous column", ref.name)
                ref.set_index(column.index)
        else:
            on = [on] if isinstance(on, str) else list(on)
            join_columns = set(on)
            join_condition = And(
                *(
                    left_join_conversion.item(
                        left_column_name_to_column[column_name].index
                    )
                    == right_join_conversion.item(
                        right_column_name_to_column[column_name].index
                    )
                    for column_name in on
                )
            )
        del on

        only_left_values_matter = how in ("left", "inner")
        left_is_optional = how in ("right", "outer")
        right_is_optional = how in ("left", "outer")
        for column in left.meta_columns.columns:
            index = column.index
            column_name = column.name
            if column_name in right_column_name_to_column:
                if column_name in join_columns:
                    after_join_column_names.append(column_name)
                    if only_left_values_matter:
                        after_join_conversions.append(GetItem(0, index))
                    elif how == "right":
                        after_join_conversions.append(GetItem(1, index))
                    else:  # outer
                        after_join_conversions.append(
                            If(
                                GetItem(0).is_(None),
                                GetItem(1, index),
                                GetItem(0, index),
                            )
                        )
                else:
                    after_join_column_names.append(
                        f"{column_name}{suffixes[0]}"
                    )
                    after_join_conversions.append(
                        If(GetItem(0).is_(None), None, GetItem(0, index))
                        if left_is_optional
                        else GetItem(0, index)
                    )
            else:
                after_join_column_names.append(column_name)
                after_join_conversions.append(
                    If(GetItem(0).is_(None), None, GetItem(0, index))
                    if left_is_optional
                    else GetItem(0, index)
                )

        for column in right.meta_columns.columns:
            index = column.index
            column_name = column.name
            if column_name in left_column_name_to_column:
                if column_name in join_columns:
                    # handled above
                    pass
                else:
                    after_join_column_names.append(
                        f"{column_name}{suffixes[1]}"
                    )
                    after_join_conversions.append(
                        If(GetItem(1).is_(None), None, GetItem(1, index))
                        if right_is_optional
                        else GetItem(1, index)
                    )
            else:
                after_join_column_names.append(column_name)
                after_join_conversions.append(
                    If(GetItem(1).is_(None), None, GetItem(1, index))
                    if right_is_optional
                    else GetItem(1, index)
                )

        new_rows = JoinConversion(
            This(),
            InputArg("right"),
            join_condition,
            how,
        ).execute(
            left.into_iter_rows(left.row_type),
            right=right.into_iter_rows(right.row_type),
            debug=ConverterOptionsCtx.get_option_value("debug"),
        )
        new_columns = MetaColumns(
            duplicate_columns="raise",
        )
        for column_name, conversion in zip(
            after_join_column_names, after_join_conversions
        ):
            new_columns.add(column_name, None, conversion)

        return Table(
            row_type=tuple,
            rows_objects=[new_rows],
            meta_columns=new_columns,
            pending_changes=ColumnChanges.MUTATE,
        )

    def explode(self, column_name: str):
        """Explode a table by unnesting a column with iterables.

        >>> | a |   b    |
        >>> | 1 | [2, 3] |
        >>> | 4 | [5, 6] |
        >>>
        >>> table.explode("b")
        >>>
        >>> | a | b |
        >>> | 1 | 2 |
        >>> | 1 | 3 |
        >>> | 2 | 5 |
        >>> | 2 | 6 |

        Args:
          column_name: column with iterables to be exploded
        """
        columns = self.columns
        try:
            index = columns.index(column_name)
        except ValueError as e:
            raise ValueError("unknown column", column_name) from e

        c_row = EscapedString("row_")
        c_value = EscapedString("value_")
        c_values = c_row.item(index)

        new_rows = (
            InlineExpr(
                """({new_row} for {row} in {rows} for {value} in {values})"""
            )
            .pass_args(
                new_row=Tuple_(
                    *(
                        c_value if i == index else c_row.item(i)
                        for i in range(len(columns))
                    )
                ),
                row=c_row,
                rows=This,
                value=c_value,
                values=c_values,
            )
            .execute(self.into_iter_rows(tuple, include_header=False))
        )

        return Table.from_rows(new_rows, header=columns)

    def wide_to_long(
        self,
        col_for_names: str = "name",
        col_for_values: str = "value",
        prepare_name: "Optional[Callable[[str], str]]" = None,
        prepare_value: "Optional[Callable[[str], str]]" = None,
        keep_cols: "Sequence[str]" = (),
    ):
        """Turn wide table into a long form.

        It was added on Mar 6, 2024 and may be stabilized ~ in half a year.
        This is an operation, which is opposite to pivot operation:
        >>> assert list(
        >>>     Table.from_rows(
        >>>         [{"name": "John", "height": 200, "age": 30, "mood": "good"}]
        >>>     )
        >>>     .wide_to_long(
        >>>         col_for_names="metric",
        >>>         col_for_values="value",
        >>>         keep_cols=("name",)
        >>>     )
        >>>     .into_iter_rows(dict)
        >>> ) == [
        >>>     {"name": "John", "metric": "height", "value": 200},
        >>>     {"name": "John", "metric": "age", "value": 30},
        >>>     {"name": "John", "metric": "mood", "value": "good"},
        >>> ]

        Args:
          col_for_names: name of the column with names of processed columns
          col_for_values: name of the column with values of processed columns
          prepare_name (optional): callable or conversion to prepare a name
          prepare_value (optional): callable or conversion to prepare a value
          keep_cols: column names to keep as is
        Returns: a new Table.
        """
        columns = self.columns
        keep_cols_set = set(keep_cols)
        collapse_cols = tuple(
            col for col in columns if col not in keep_cols_set
        )
        resulting_cols = tuple(keep_cols) + (col_for_names, col_for_values)

        new_rows = (
            InlineExpr(
                """(new_row for row_ in {rows} for new_row in {new_rows})"""
            )
            .pass_args(
                rows=This,
                new_rows=Tuple_(
                    *(
                        (
                            *(
                                EscapedString("row_").item(
                                    columns.index(keep_col)
                                )
                                for keep_col in keep_cols
                            ),
                            (
                                collapse_col
                                if prepare_name is None
                                else This.pipe(prepare_name).execute(
                                    collapse_col
                                )
                            ),
                            EscapedString("row_")
                            .item(columns.index(collapse_col))
                            .pipe(
                                This
                                if prepare_value is None
                                else prepare_value
                            ),
                        )
                        for collapse_col in collapse_cols
                    )
                ),
            )
            .execute(self.into_iter_rows(tuple, include_header=False))
        )
        return Table.from_rows(new_rows, header=resulting_cols)

    def pivot(
        self,
        rows: "Sequence[str]",
        columns: "Sequence[str]",
        values: "Mapping[str, BaseConversion]",
        prepare_column_names: "Callable[[Sequence[str]], str]" = " - ".join,
    ) -> "Table":
        """Create a pivot table.

        It was added on Jun 5, 2024 and may be stabilized ~ in half a year.
        >>> assert list(
        >>>     Table.from_rows([
        >>>        {"dept": 1, "year": 2023, "currency": "USD", "revenue": 100},
        >>>        {"dept": 1, "year": 2024, "currency": "USD", "revenue": 300},
        >>>        {"dept": 1, "year": 2024, "currency": "CNY", "revenue": 200},
        >>>        {"dept": 1, "year": 2024, "currency": "CNY", "revenue": 111},
        >>>     ])
        >>>     .pivot(
        >>>         rows=["year", "dept"],
        >>>         columns=["currency"],
        >>>         values={
        >>>             "sum": c.ReduceFuncs.Sum(c.col("revenue")),
        >>>             "min": c.ReduceFuncs.Min(c.col("revenue")),
        >>>         },
        >>>     )
        >>>     .into_iter_rows(dict)
        >>> ) == [
        >>>     {
        >>>         "CNY - min": None,
        >>>         "CNY - sum": None,
        >>>         "USD - min": 100,
        >>>         "USD - sum": 100,
        >>>         "dept": 1,
        >>>         "year": 2023,
        >>>     },
        >>>     {
        >>>         "CNY - min": 111,
        >>>         "CNY - sum": 311,
        >>>         "USD - min": 300,
        >>>         "USD - sum": 300,
        >>>         "dept": 1,
        >>>         "year": 2024,
        >>>     },
        >>> ]

        Args:
          rows: columns to group by
          columns: columns to take names of new columns from
          values: mapping of name to reducer of column value/values
          prepare_column_names: callable to create column names from column
            names and reducer name

        """
        name_to_column = self.meta_columns.get_name_to_column()
        name_to_index_cols = {
            col_name: self._set_col_indexes(
                name_to_column, ColumnRef(col_name)
            )
            for col_name in rows
        }
        columns = [
            self._set_col_indexes(name_to_column, ColumnRef(col_name))
            for col_name in columns
        ]
        value_name_to_aggregator = {
            key: Aggregate(
                self._set_col_indexes(name_to_column, value)
            ).gen_converter()
            for key, value in values.items()
        }

        aggregated_data = (
            GroupBy(*name_to_index_cols.values())
            .aggregate(
                (
                    *name_to_index_cols.values(),
                    ReduceFuncs.DictArray(tuple(columns), This()),
                )
            )
            .execute(self.into_iter_rows(self.row_type))
        )
        index_ = len(name_to_index_cols)
        new_col_keys = list(
            {key: 0 for row in aggregated_data for key in row[index_]}
        )

        agg_data_col = "7b51817c-c2d2-4f9c-a708-65d776ed2ddd"
        return (
            Table.from_rows(
                aggregated_data,
                header=tuple(name_to_index_cols) + (agg_data_col,),
            )
            .update(
                **{
                    prepare_column_names(
                        new_col_key + (value_name,)
                    ): ColumnRef(agg_data_col)
                    .call_method("get", NaiveConversion(new_col_key))
                    .and_then(CallFunc(aggregator, This()))
                    for new_col_key in new_col_keys
                    for value_name, aggregator in value_name_to_aggregator.items()
                }
            )
            .drop(agg_data_col)
        )

    def move_rows_objects(self) -> "List[Iterable]":
        """For internal use.

        Moves out rows objects including files to be closed later.
        """
        if self.rows_objects is None:
            raise AssertionError("move_rows called the 2nd time")

        rows_objects = self.rows_objects
        self.rows_objects = None

        if self.file_to_close:
            rows_objects.append(CloseFileIterator(self.file_to_close))
            self.file_to_close = None
        return rows_objects

    supported_types = (tuple, list, dict)

    def into_list_of_iterables(
        self, type_=tuple, include_header=None
    ) -> "List[Iterable]":
        """For internal use."""
        if type_ not in self.supported_types:
            raise TypeError("unsupported type_", type_)

        no_pending_changes = (
            type_ is self.row_type and not self.pending_changes
        )

        if no_pending_changes:
            conversion = None if self.pipeline is None else self.pipeline
        else:
            row_conversion: "Union[dict, tuple, list]"
            if type_ is dict:
                row_conversion = {
                    column.name: (
                        column.conversion
                        if column.index is None
                        else GetItem(column.index)
                    )
                    for column in self.meta_columns.columns
                }
                include_header = False
            else:
                row_conversion = type_(
                    (
                        column.conversion
                        if column.index is None
                        else GetItem(column.index)
                    )
                    for column in self.meta_columns.columns
                )
            conversion = (self.pipeline or This()).iter(row_conversion)

        if conversion:
            converter = conversion.gen_converter()
            rows_objects = [
                converter(chunk) for chunk in self.move_rows_objects()
            ]
        else:
            rows_objects = self.move_rows_objects()

        if type_ is not dict and include_header:
            header = type_(self.get_columns())
            rows_objects.insert(0, (header,))

        return rows_objects

    def into_iter_rows(
        self, type_=tuple, include_header=None
    ) -> "Iterable[Any]":
        """Return iterable of processed rows.

        Args:
          type_: casts output rows to the type. Accepts the following values:

            * :py:obj:`dict`
            * :py:obj:`tuple`
            * :py:obj:`list`
          include_header: whether to include header row in the result or not

        """
        return chain.from_iterable(
            self.into_list_of_iterables(
                type_=type_, include_header=include_header
            )
        )

    def into_csv(
        self,
        filepath_or_buffer: "Union[str, TextIO]",
        include_header: bool = True,
        dialect: "Union[str, CustomCsvDialect]" = "excel",
        encoding="utf-8",
    ):
        """Writes rows to a file.

        Args:
          filepath_or_buffer: a filepath or something :py:obj:`csv.writer` can
            write to
          include_header: self-explanatory bool
          dialect: a dialect acceptable by :py:obj:`csv.writer` There's a
            helper method:
            :py:obj:`convtools.contrib.tables.Table.csv_dialect` to create
            dialects without defining classes
          encoding: encoding to pass to :py:obj:`open`
        """
        row_type = list if self.row_type is list else tuple

        f_to_close = None
        f: "TextIO"
        if isinstance(filepath_or_buffer, str):
            f = f_to_close = (
                open(  # pylint:disable=consider-using-with  # noqa: SIM115
                    filepath_or_buffer, "w", encoding=encoding
                )
            )
        else:
            f = filepath_or_buffer

        try:
            writer = csv.writer(f, dialect=dialect)
            if include_header:
                writer.writerow(self.get_columns())
            for chunk in self.into_list_of_iterables(
                row_type, include_header=False
            ):
                writer.writerows(chunk)
        finally:
            if f_to_close is not None:
                f_to_close.close()
