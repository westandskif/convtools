"""
Implements streaming operations on table-like data and csv files.

Conversions are defined in realtime based on table headers and called methods:
 - update
 - take
 - drop
 - join

"""
import csv
import typing as t  # pylint: disable=unused-import
from itertools import chain, zip_longest

from ..base import (
    And,
    BaseConversion,
    ConverterOptionsCtx,
    GeneratorComp,
    GetItem,
    If,
    InputArg,
    NaiveConversion,
    ensure_conversion,
)
from ..columns import ColumnRef, MetaColumns
from ..joins import JoinConversion, LeftJoinCondition, RightJoinCondition


class CloseFileIterator:
    """
    Utility to close the corresponding file once the iterator is exhausted
    """

    def __init__(self, file_to_close):
        self.file_to_close = file_to_close

    def __iter__(self):
        return self

    def __next__(self):
        raise StopIteration

    def __del__(self):
        self.file_to_close.close()


class CustomCsvDialect(csv.Dialect):
    """A helper to define custom csv dialects without defining classes"""

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
        self.delimiter = delimiter
        self.quotechar = quotechar
        self.escapechar = escapechar
        self.doublequote = doublequote
        self.skipinitialspace = skipinitialspace
        self.lineterminator = lineterminator
        self.quoting = quoting
        super().__init__()


class Table:
    """Table conversion exposes streaming operations on table-like data and csv
    files

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
        rows: "t.Iterable",
        meta_columns: "MetaColumns",
        pipeline: "t.Optional[BaseConversion]" = None,
        first_row=None,
        file_to_close=None,
    ):
        """It is used internally only. Use from_rows and from_csv methods."""
        self.rows = rows
        self.meta_columns = meta_columns
        self.pipeline = pipeline
        self.first_row = first_row
        self.file_to_close = file_to_close

    def get_columns(self) -> "t.List[str]":
        """Exposes list of column names"""
        return [column.name for column in self.meta_columns.columns]

    columns = property(get_columns)

    @classmethod
    def from_rows(
        cls,
        rows: "t.Iterable[t.Union[dict, tuple, list, t.Any]]",
        header: """t.Optional[
            t.Union[
                bool, t.List[str], t.Tuple[str], t.Dict[str, t.Union[str, int]]
            ]
        ]""" = None,
        # t.Literal["raise", "keep", "drop", "mangle"]
        duplicate_columns: str = "raise",
        skip_rows: int = 0,
        file_to_close=None,
    ) -> "Table":
        """A method to initialize a table conversion from an iterable of
        rows.

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

        """
        columns = MetaColumns(duplicate_columns=duplicate_columns)

        rows = iter(rows)

        if skip_rows:
            for _ in range(skip_rows):
                next(rows)

        first_row = next(rows)

        index: "t.Union[str, int]"
        if isinstance(header, (tuple, list)):
            if len(header) != len(first_row):
                raise ValueError("non-matching number of columns")
            for index, column in enumerate(header):
                columns.add(column, index, None)

        elif isinstance(header, dict):
            if len(header) != len(first_row):
                raise ValueError("non-matching number of columns")
            for name, index in header.items():
                columns.add(name, index, None)

        else:
            # inferring a header
            if isinstance(first_row, dict):
                if header is False:
                    for key in first_row:
                        columns.add(None, key, None)
                else:
                    for key in first_row:
                        columns.add(key, key, None)

            elif isinstance(first_row, (tuple, list)):
                if header is True:
                    for index, column_name in enumerate(first_row):
                        columns.add(column_name, index, None)
                    first_row = None

                else:
                    for index in range(len(first_row)):
                        columns.add(None, index, None)

            else:
                raise ValueError(
                    "failed to infer header: unsupported row type",
                    type(first_row),
                )

        return cls(
            rows, columns, first_row=first_row, file_to_close=file_to_close
        )

    csv_dialect = CustomCsvDialect

    @classmethod
    def from_csv(
        cls,
        filepath_or_buffer: "t.Union[str, t.TextIO]",
        header: """t.Optional[
            t.Union[
                bool, t.List[str], t.Tuple[str], t.Dict[str, t.Union[str, int]]
            ]
        ]""" = None,
        duplicate_columns: str = "mangle",
        skip_rows: int = 0,
        dialect: "t.Union[str, CustomCsvDialect]" = "excel",
        encoding: str = "utf-8",
    ) -> "Table":
        """A method to initialize a table conversion from a csv-like file.

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
        file_to_close = None
        if isinstance(filepath_or_buffer, str):
            file_to_close = open(  # pylint: disable=consider-using-with
                filepath_or_buffer,
                encoding=encoding,
            )
            rows = csv.reader(file_to_close, dialect=dialect)
        else:
            rows = csv.reader(filepath_or_buffer, dialect=dialect)

        return cls.from_rows(
            rows,
            header,
            duplicate_columns,
            skip_rows=skip_rows,
            file_to_close=file_to_close,
        )

    def embed_conversions(self) -> "Table":
        """There's no need in calling this directly, it's done automatically
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

            conversion = GeneratorComp(tuple(column_conversions))

            self.pipeline = (
                conversion
                if self.pipeline is None
                else self.pipeline.pipe(conversion)
            )

        return self

    def filter(self, condition: "BaseConversion") -> "Table":
        """Filters table-like data, keeping rows where ``condition`` resolves
        to ``True``"""
        condition = ensure_conversion(condition)
        column_refs = list(condition.get_dependencies(types=ColumnRef))
        name_to_column = self.meta_columns.get_name_to_column()

        depends_on_complex_columns = any(
            name_to_column[ref.name].conversion is not None
            for ref in column_refs
        )
        if depends_on_complex_columns:
            return self.embed_conversions().filter(condition)

        for ref in condition.get_dependencies(types=ColumnRef):
            column = name_to_column[ref.name]
            ref.set_index(column.index)

        self.rows = (
            (self.pipeline or GetItem())
            .filter(condition)
            .execute(
                self.move_rows(),
                debug=ConverterOptionsCtx.get_option_value("debug"),
            )
        )
        self.pipeline = None
        return self

    def update(self, **column_to_conversion) -> "Table":
        """The main method to mutate table-like data.

        Args:
          column_to_conversion: dict where keys are new or existing columns and
            values are conversions to be applied row-wise
        """
        column_name_to_column = self.meta_columns.get_name_to_column()

        for column_name in list(column_to_conversion):
            conversion = ensure_conversion(column_to_conversion[column_name])
            column_refs = list(conversion.get_dependencies(types=ColumnRef))

            depends_on_complex_columns = any(
                column_name_to_column[ref.name].conversion is not None
                for ref in column_refs
            )
            if depends_on_complex_columns:
                return self.embed_conversions().update(**column_to_conversion)

            del column_to_conversion[column_name]

            for ref in column_refs:
                ref.set_index(column_name_to_column[ref.name].index)

            if column_name in column_name_to_column:
                column = column_name_to_column[column_name]
                column.conversion = conversion
                column.index = None
            else:
                column = self.meta_columns.add(column_name, None, conversion)
                column_name_to_column[column.name] = column

        return self

    def update_all(self, *conversions) -> "Table":
        """Table-wide mutations, applied to each value of each column.

        Args:
          conversions: conversion to apply to each value of each column
        """
        conversion: "BaseConversion" = GetItem()
        for conversion_ in conversions:
            conversion = conversion.pipe(conversion_)
        column_to_conversion = {
            column.name: (
                column.conversion.pipe(conversion)
                if column.conversion is not None
                else GetItem(column.index).pipe(conversion)
            )
            for column in self.meta_columns.columns
        }
        return self.update(**column_to_conversion)

    def rename(
        self, columns: "t.Union[t.Tuple[str], t.List[str], t.Dict[str, str]]"
    ) -> "Table":
        """Method to rename columns. The behavior depends on type of columns
        argument.

        Args:
          columns: if tuple/list, then it defines new column names (length of
            passed columns should match number of columns inside).  If dict,
            then it defines a mapping from old column names to new ones.
        """
        if isinstance(columns, dict):
            for column_ in self.meta_columns.columns:
                if column_.name in columns:
                    column_.name = columns[column_.name]
        elif isinstance(columns, (tuple, list)):
            if len(columns) != len(self.meta_columns.columns):
                raise ValueError("non-matching number of columns")
            for column_, new_column_name in zip(
                self.meta_columns.columns, columns
            ):
                column_.name = new_column_name
        else:
            raise TypeError("unsupported columns type")
        return self

    def take(self, *column_names: str) -> "Table":
        """Leaves only specified columns, omitting the rest.

        Args:
          column_names: columns to keep
        """
        self.meta_columns = self.meta_columns.take(*column_names)
        return self

    def drop(self, *column_names: str) -> "Table":
        """Drops specified columns, keeping the rest.

        Args:
          column_names: columns to drop
        """
        self.meta_columns = self.meta_columns.drop(*column_names)
        return self

    def zip(self, table: "Table", fill_value=None) -> "Table":
        """Zip tables one to another. Before using this method, make sure you
        are not looking for :py:obj:`convtools.contrib.tables.Table.join`

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
         - table: table to be chained
         - fill_value: value to use for filling gaps

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
            (left_fill_value, t[1])
            if t[0] is None
            else ((t[0], right_fill_value) if t[1] is None else t)
            for t in zip_longest(
                self.into_iter_rows(tuple), table.into_iter_rows(tuple)
            )
        )
        return Table(new_rows, new_columns)

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
         - table: table to be chained
         - fill_value: value to use for filling gaps

        """
        first_name_to_columns = self.meta_columns.get_name_to_column()
        second_name_to_columns = table.meta_columns.get_name_to_column()

        new_columns = MetaColumns(duplicate_columns="raise")
        first_columns = MetaColumns(
            duplicate_columns=self.meta_columns.duplicate_columns
        )
        second_columns = MetaColumns(
            duplicate_columns=table.meta_columns.duplicate_columns
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

        self.meta_columns = first_columns
        table.meta_columns = second_columns

        return Table(
            chain(
                self.into_iter_rows(tuple),
                table.into_iter_rows(tuple),
            ),
            new_columns,
        )

    def join(
        self,
        table: "Table",
        on: "t.Union[BaseConversion, str, t.Iterable[str]]",
        how: str,
        suffixes=("_LEFT", "_RIGHT"),
    ) -> "Table":
        """Joins the table conversion to another table conversion.

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
        left_join_conversion = LeftJoinCondition()
        right_join_conversion = RightJoinCondition()
        left_column_name_to_column = left.meta_columns.get_name_to_column()
        right_column_name_to_column = right.meta_columns.get_name_to_column()

        after_join_conversions: "t.List[BaseConversion]" = []
        after_join_column_names: "t.List[str]" = []

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
            join_condition = (
                And(
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
                if len(on) > 1
                else left_join_conversion.item(
                    left_column_name_to_column[on[0]].index
                )
                == right_join_conversion.item(
                    right_column_name_to_column[on[0]].index
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
            left.pipeline or GetItem(),
            InputArg("right").pipe(right.pipeline or GetItem()),
            join_condition,
            how,
        ).execute(
            left.move_rows(),
            right=right.move_rows(),
            debug=ConverterOptionsCtx.get_option_value("debug"),
        )
        new_columns = MetaColumns(self.meta_columns.duplicate_columns)
        for column_name, conversion in zip(
            after_join_column_names, after_join_conversions
        ):
            new_columns.add(column_name, None, conversion)

        return Table(
            new_rows,
            new_columns,
        )

    def move_rows(self):
        if self.rows is None:
            raise AssertionError("move_rows called the 2nd time")

        iterables = []

        if self.first_row is not None:
            iterables.append((self.first_row,))
            self.first_row = None

        iterables.append(self.rows)
        self.rows = None

        if self.file_to_close:
            iterables.append(CloseFileIterator(self.file_to_close))
            self.file_to_close = None

        return chain(*iterables)

    def into_iter_rows(
        self, type_=tuple, include_header=None
    ) -> "t.Iterable[t.Any]":
        """Consumes inner rows Iterable and returns Iterable of processed rows.

        Args:
          type_: casts output rows to the type. Accepts the following values:

            * :py:obj:`dict`
            * :py:obj:`tuple`
            * :py:obj:`list`

        """
        if type_ not in (tuple, list, dict):
            raise TypeError("unsupported type_", type_)

        row_conversion: "t.Union[dict, tuple, list]"
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
        resulting_rows = (
            (self.pipeline or GetItem())
            .pipe(GeneratorComp(row_conversion))
            .execute(
                self.move_rows(),
                debug=ConverterOptionsCtx.get_option_value("debug"),
            )
        )
        if include_header:
            header = type_(self.get_columns())
            resulting_rows = chain(
                (header,),
                resulting_rows,
            )
        return resulting_rows

    def into_csv(
        self,
        filepath_or_buffer: "t.Union[str, t.TextIO]",
        include_header: bool = True,
        dialect: "t.Union[str, CustomCsvDialect]" = "excel",
        encoding="utf-8",
    ):
        """Consumes inner rows Iterable and writes processed rows as a csv-like
        file.

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
        if isinstance(filepath_or_buffer, str):
            with open(filepath_or_buffer, "w", encoding=encoding) as f:
                writer = csv.writer(f, dialect=dialect)
                if include_header:
                    writer.writerow(self.get_columns())
                writer.writerows(
                    self.into_iter_rows(tuple, include_header=False)
                )
        else:
            writer = csv.writer(filepath_or_buffer, dialect=dialect)
            if include_header:
                writer.writerow(self.get_columns())
            writer.writerows(self.into_iter_rows(tuple, include_header=False))
