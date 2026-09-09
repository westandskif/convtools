"""Base conversions to reference/define columns for tables."""

from collections import defaultdict
from typing import Any, Dict, List, Optional

from ._base import BaseConversion, ConversionException, GetItem


class ColumnRef(BaseConversion):
    """Table column reference."""

    trackable_dependency = True
    SCOPES = "__column_ref_scopes"

    def __init__(self, name: str, id_=None):
        if not isinstance(name, str):
            raise ValueError("name should be str")
        super().__init__()
        self.name = name
        self.id_ = id_

    def gen_code_and_update_ctx(self, code_input, ctx):
        key = (self.id_, self.name)
        for mapping in reversed(ctx.get(self.SCOPES, ())):
            if key in mapping:
                return GetItem(mapping[key]).gen_code_and_update_ctx(
                    code_input, ctx
                )
        raise ConversionException(
            "column index is not initialized, " "possible use outside of Table"
        )


class ColumnScope(BaseConversion):
    """Push column-ref bindings for one conversion's render."""

    weight = 0
    self_content_type = (
        BaseConversion.self_content_type
        & ~BaseConversion.ContentTypes.FUNCTION_OF_INPUT
    )

    def __init__(self, conversion, name_to_index):
        super().__init__()
        self.name_to_index = name_to_index
        self.conversion = self.ensure_conversion(conversion)

    def gen_code_and_update_ctx(self, code_input, ctx):
        scopes = ctx.setdefault(ColumnRef.SCOPES, [])
        scopes.append(self.name_to_index)
        try:
            return self.conversion.gen_code_and_update_ctx(code_input, ctx)
        finally:
            scopes.pop()


class ColumnDef:
    """Table column definition."""

    __slots__ = ["name", "index", "conversion"]

    def __init__(
        self,
        name: str,
        index: Optional[Any],
        conversion: Optional[BaseConversion],
    ):
        """Init self.

        Args:
          name: of the column in the output
          index: of the column in the input in simple cases, otherwise None
          conversion: to obtain the value from the input, None in simple cases
        """
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
    """Helper container many table columns."""

    def __init__(
        self,
        # Literal["raise", "keep", "drop", "mangle"]
        duplicate_columns="raise",
    ):
        self.columns: "List[ColumnDef]" = []
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
        original_name = name
        column_number = self.column_to_number[original_name]
        self.column_to_number[original_name] += 1
        state = 0
        occupied = {column.name for column in self.columns}

        if original_name is None:
            n = column_number
            name = f"COLUMN_{n}"
            while name in occupied:
                n += 1
                name = f"COLUMN_{n}"
            self.column_to_number[None] = n + 1
        elif column_number or (
            self.duplicate_columns == "mangle" and original_name in occupied
        ):
            if self.duplicate_columns == "raise":
                raise ValueError("such column already exists", original_name)
            if self.duplicate_columns == "mangle":
                n = column_number or 1
                name = f"{original_name}_{n}"
                while name in occupied:
                    n += 1
                    name = f"{original_name}_{n}"
                self.column_to_number[original_name] = n + 1
                state = ColumnChanges.RENAME
            elif self.duplicate_columns == "drop":
                return None, ColumnChanges.REARRANGE

        column = ColumnDef(name, index, conversion)
        self.columns.append(column)
        return column, state

    def rename(self, new_names):
        if self.duplicate_columns != "keep":
            seen = set()
            for name in new_names:
                if name in seen:
                    raise ValueError("such column already exists", name)
                seen.add(name)
        none_counter = self.column_to_number[None]
        for column, new_name in zip(self.columns, new_names):
            column.name = new_name
        self.column_to_number = defaultdict(int)
        for column in self.columns:
            self.column_to_number[column.name] += 1
        self.column_to_number[None] = none_counter

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
                for column_ in self.columns:
                    if column_.name not in column_names_set:
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

        to_drop = set(unique_column_names)
        new_columns = MetaColumns(self.duplicate_columns)
        for column in self.columns:
            if column.name in to_drop:
                to_drop.remove(column.name)
                continue
            new_columns.add(column.name, column.index, column.conversion)

        return new_columns

    def get_name_to_column(self) -> "Dict[str, ColumnDef]":
        result: "Dict[str, ColumnDef]" = {}
        for column in self.columns:
            if column.name not in result:
                result[column.name] = column
        return result
