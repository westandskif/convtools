"""
Implements base conversions to reference and define columns in table
conversions
"""
import typing as t
from collections import defaultdict

from .base import BaseConversion, ConversionException, GetItem


class ColumnRef(BaseConversion):
    """Helper conversion, which allows to reference a column of a table
    conversion"""

    trackable_dependency = True

    def __init__(self, name: str, id_=None):
        if not isinstance(name, str):
            raise ValueError("name should be str")
        super().__init__()
        self.name = name
        self.index: "t.Optional[t.Union[str, int]]" = None
        self.id_ = id_

    def set_index(self, index: t.Union[str, int]):
        if not isinstance(index, (str, int)):
            raise AssertionError("bad index")
        self.index = index
        return self

    def _gen_code_and_update_ctx(self, code_input, ctx):
        if self.index is None:
            raise ConversionException(
                "column index is not initialized, "
                "possible use outside of Table"
            )
        return GetItem(
            self.index if self.index is not None else -1
        ).gen_code_and_update_ctx(code_input, ctx)


class ColumnDef:
    """
    Defines a column within a table conversion. It holds the following:

     * name of the column in the output
     * index of the column in the input in simple cases, otherwise None
     * conversion to obtain the value from the input, None in simple cases

    """

    __slots__ = ["name", "index", "conversion"]

    def __init__(
        self,
        name: str,
        index: t.Optional[t.Any],
        conversion: t.Optional[BaseConversion],
    ):
        if not bool(index is not None) ^ bool(conversion is not None):
            raise ValueError("provide either index or conversion")
        self.name = name
        self.index = index
        self.conversion = conversion

    def as_tuple(self):
        return self.name, self.index, self.conversion

    def is_same_as(self, other: "ColumnDef") -> bool:
        return (
            self.name == other.name
            and self.index == other.index
            and self.conversion is None
            and other.conversion is None
        )


class ColumnChanges:
    RENAME = 1
    REARRANGE = 2
    MUTATE = 4


class MetaColumns:
    """A helper container for naming & keeping column definitions"""

    def __init__(
        self,
        # t.Literal["raise", "keep", "drop", "mangle"]
        duplicate_columns="raise",
    ):
        self.columns: "t.List[ColumnDef]" = []
        self.column_to_number = defaultdict(int)
        if duplicate_columns not in ("raise", "keep", "drop", "mangle"):
            raise ValueError("invalid duplicate_columns value")
        self.duplicate_columns = duplicate_columns

    def is_same_as(self, other: "MetaColumns"):
        left_columns = self.columns
        right_columns = other.columns
        if len(left_columns) != len(right_columns):
            return False

        for index in range(len(left_columns)):
            if not left_columns[index].is_same_as(right_columns[index]):
                return False

        return True

    def add(self, name, index, conversion):
        if name is not None:
            name = str(name)
        column_number = self.column_to_number[name]
        self.column_to_number[name] += 1
        state = 0

        if name is None:
            name = f"COLUMN_{column_number}"
        elif column_number:
            if self.duplicate_columns == "raise":
                raise ValueError("such column already exists", name)
            if self.duplicate_columns == "mangle":
                name = f"{name}_{column_number}"
                state = ColumnChanges.RENAME
            elif self.duplicate_columns == "drop":
                return None, ColumnChanges.REARRANGE

        column = ColumnDef(name, index, conversion)
        self.columns.append(column)
        return column, state

    def take(self, *column_names) -> "MetaColumns":
        column_names_set = set(column_names)
        name_to_column = self.get_name_to_column()
        missing_columns = column_names_set.difference(name_to_column)

        ellipsis_ = ...

        if ellipsis_ in missing_columns:
            missing_columns.remove(...)
        if missing_columns:
            raise ValueError("missing columns", missing_columns)

        new_columns = MetaColumns(self.duplicate_columns)

        for column_name in column_names:
            if column_name is ellipsis_:
                for name_, column_ in name_to_column.items():
                    if name_ not in column_names_set:
                        new_columns.add(
                            column_.name, column_.index, column_.conversion
                        )
            else:
                column = name_to_column[column_name]
                new_columns.add(column.name, column.index, column.conversion)

        return new_columns

    def drop(self, *column_names: str) -> "MetaColumns":
        unique_column_names = set(column_names)
        missing_columns = unique_column_names.difference(
            {column.name for column in self.columns}
        )
        if missing_columns:
            raise ValueError("missing columns", missing_columns)

        new_columns = MetaColumns(self.duplicate_columns)
        for column in self.columns:
            if column.name in unique_column_names:
                continue
            new_columns.add(column.name, column.index, column.conversion)

        return new_columns

    def get_name_to_column(self) -> "t.Dict[str, ColumnDef]":
        return {column.name: column for column in self.columns}
