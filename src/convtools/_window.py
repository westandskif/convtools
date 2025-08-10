"""Brings window functions, based on PostgreSQL's ones.

https://www.postgresql.org/docs/current/sql-expressions.html#SYNTAX-WINDOW-FUNCTIONS
"""

from enum import Enum
from itertools import chain, count, islice
from typing import MutableMapping, cast

from ._aggregations import Aggregate, GroupBy, Grouper, ReduceFuncs
from ._base import (
    BaseConversion,
    CallFunc,
    GetItem,
    If,
    InlineExpr,
    LabelConversion,
    LazyEscapedString,
    NaiveConversion,
    Namespace,
    NamespaceCtx,
    This,
)
from ._ordering import SortingKeyConversion
from ._utils import Code


_none = BaseConversion._none


class FrameMode(Enum):
    RANGE = "RANGE"
    ROWS = "ROWS"
    GROUPS = "GROUPS"


class FrameExclusion(Enum):
    CURRENT_ROW = "CURRENT ROW"
    GROUP = "GROUP"
    TIES = "TIES"
    NO_OTHERS = "NO OTHERS"


class Offset:
    """Offset validator."""

    unbounded_preceding = None
    unbounded_following = None
    current_row = None
    offset = None
    offset_sign_as_str = None

    def __init__(self, value):
        if value in ("UNBOUNDED PRECEDING",):
            self.unbounded_preceding = True
        elif value in ("UNBOUNDED FOLLOWING",):
            self.unbounded_following = True
        elif value in ("CURRENT ROW",):
            self.current_row = True
        elif (
            isinstance(value, (tuple, list))
            and len(value) == 2
            and value[1] in ("PRECEDING", "FOLLOWING")
        ):
            self.offset, offset_type = value
            self.offset_sign_as_str = (
                "-" if offset_type == "PRECEDING" else "+"
            )
        else:
            raise ValueError("unsupported window frame offset", value)


SORT_KEY_CODE = """
def {converter_name}({code_args}):
    return {code_result}
"""


class Window(BaseConversion):
    """Partially initialized window functions invocation."""

    def __init__(self, conv, reducer):
        super().__init__()
        self.conv = conv
        self.reducer = reducer

    def over(self, **kwargs):
        return AppliedWindow(self.conv, self.reducer, **kwargs)

    def gen_code_and_update_ctx(self, code_input, ctx):
        raise ValueError("window is not initialized, call over")


class AppliedWindow(BaseConversion):
    """Fully initialized window functions invocation."""

    self_content_type = (
        Grouper.self_content_type | BaseConversion.ContentTypes.NEW_LABEL
    )

    def __init__(
        self,
        conv,
        reducer,
        *,
        partition_by=_none,
        order_by=_none,
        frame_mode=FrameMode.RANGE,
        frame_start="UNBOUNDED PRECEDING",
        frame_end="CURRENT ROW",
        frame_exclusion=FrameExclusion.NO_OTHERS,
    ):
        """Init window funcs.

        Args:
          conv: conversion to apply window funcs to

          # --8<-- [start:over_args_docs]
          reducer: window accepts a conversion, which can contain reducers
            and/or window functions to be applied to window frames

          partition_by (optional): conversion to partition by

          order_by (optional): conversion or tuple with conversions, which
            defines the ordering key to sort rows within partitions; rows with
            the same ordering key form a peer group.

          frame_mode: one of:
            - "ROWS" (default): window frame slides over rows
            - "RANGE": window frames are based on offsets between ordering keys
                of the current row and rows around
            - "GROUPS": window frame slides over peer groups

          frame_start: one of
            - "UNBOUNDED PRECEDING" (default): the first row of a partition
            - "CURRENT ROW":
                * "ROWS" mode: current row
                * "RANGE" / "GROUPS": the first row of the peer group
            - (offset, "PRECEDING") or (offset, "FOLLOWING):
                * "ROWS" mode: offset in rows; must be non-negative int
                * "RANGE" mode: offset is added to / subtracted from an
                  ordering key of the current row and looked for within the
                  sorted partition; the first matching row is used as a frame
                  boundary
                * "GROUPS" mode: offset as a number of peer groups

          frame_end: one of
            - "UNBOUNDED FOLLOWING": the last row of a partition
            - "CURRENT ROW" (default):
                * "ROWS" mode: current row
                * "RANGE" / "GROUPS": the last row of the peer group
            - (offset, "PRECEDING") or (offset, "FOLLOWING):
                * "ROWS" mode: offset in rows; must be non-negative int
                * "RANGE" mode: offset is added to / subtracted from an
                  ordering key of the current row and looked for within the
                  sorted partition; the last matching row is used as a frame
                  boundary
                * "GROUPS" mode: offset as a number of peer groups

          frame_exclusion: one of
            - "NO OTHERS" (default): it says to not exclude anything
            - "CURRENT ROW": excludes the current row in the end
            - "GROUP": excludes peer group of the current row
            - "TIES": excludes peer group of the current row, preserving the
              current row

          # --8<-- [end:over_args_docs]

        """
        super().__init__()
        self.reducer = cast(
            Namespace,
            self.ensure_conversion(
                Namespace(reducer, {name: None for name in FRAME_DATA_NAMES})
            ),
        )
        self.contents = self.contents & ~self.ContentTypes.REDUCER
        self.reducer.contents |= self.ContentTypes.LABEL_USAGE
        self.conv = self.ensure_conversion(conv)

        if isinstance(partition_by, tuple) and len(partition_by) == 1:
            partition_by = partition_by[0]

        self.partition_by = (
            None
            if partition_by is _none
            else self.ensure_conversion(partition_by)
        )
        if order_by is _none:
            self.order_by = None
        else:
            self.order_by = [
                self.ensure_conversion(key)
                for key in (
                    order_by if isinstance(order_by, tuple) else (order_by,)
                )
            ]

        self._label_next = None
        self._label_sorting_key = None

        self.frame_mode = FrameMode(frame_mode)
        self.frame_start = Offset(frame_start)
        self.frame_end = Offset(frame_end)
        self.frame_exclusion = FrameExclusion(frame_exclusion)

        if self.frame_start.unbounded_following:
            raise ValueError("frame start cannot be UNBOUNDED FOLLOWING")
        if self.frame_end.unbounded_preceding:
            raise ValueError("frame end cannot be UNBOUNDED PRECEDING")
        if self.frame_mode == FrameMode.ROWS and not all(
            isinstance(offset, int) and offset >= 0
            for offset in (
                self.frame_start.offset,
                self.frame_end.offset,
            )
            if offset is not None
        ):
            raise ValueError(
                "frame_start/frame_end offsets should be non-negative int"
            )

        if (
            self.frame_mode == FrameMode.RANGE
            and (
                self.frame_start.offset is not None
                or self.frame_end.offset is not None
            )
            and self.order_by is None
        ):
            raise ValueError("RANGE mode offsets require 'order_by' to be set")

    def gen_code_and_update_ctx(self, code_input, ctx):
        labels: "MutableMapping[str, BaseConversion]" = {}
        if self.order_by is not None:
            self._label_sorting_key = self.gen_random_name("sorting_key", ctx)
            labels[self._label_sorting_key] = SortingKeyConversion(
                self.order_by
            )
        self._label_next = self.gen_random_name("next_", ctx)
        labels[self._label_next] = CallFunc(count).attr("__next__")

        if self.frame_mode == FrameMode.RANGE:
            frames_finder, frame_conv, name_to_index = (
                self._gen_range_frames_finder(ctx)
            )
        elif self.frame_mode == FrameMode.ROWS:
            frames_finder, frame_conv, name_to_index = (
                self._gen_rows_frames_finder(ctx)
            )
        elif self.frame_mode == FrameMode.GROUPS:
            frames_finder, frame_conv, name_to_index = (
                self._gen_groups_frames_finder(ctx)
            )
        else:
            raise AssertionError("bug")

        if name_to_index:
            frame_data_label = self.gen_random_name("frame_data", ctx)
            name_to_code = {
                name: (
                    LabelConversion(frame_data_label)
                    .item(index)
                    .gen_code_and_update_ctx(None, ctx)
                )
                for name, index in name_to_index.items()
            }
            c_agg = Aggregate(self.reducer)
            c_agg.contents |= self.ContentTypes.LABEL_USAGE
            c_frame_data_handler = This.pipe(
                frame_conv, label_input={frame_data_label: This}
            ).pipe(c_agg)
        else:
            name_to_code = {}
            c_frame_data_handler = frame_conv.pipe(Aggregate(self.reducer))

        if self.order_by is None:
            if self.partition_by is None:
                ordering_preservation_needed = False
                c_agg = (
                    If(
                        CallFunc(isinstance, This, list),
                        This,
                        CallFunc(list, This),
                    )
                    .pipe(frames_finder)
                    .iter(c_frame_data_handler)
                )
            else:
                ordering_preservation_needed = True
                c_agg = (
                    GroupBy(self.partition_by)
                    .aggregate(
                        CallFunc(
                            zip,
                            ReduceFuncs.Array(
                                LabelConversion(self._label_next).call(),
                                default=NaiveConversion(()),
                            ),
                            ReduceFuncs.Array(
                                This, default=NaiveConversion(())
                            )
                            .pipe(frames_finder)
                            .iter(c_frame_data_handler),
                        )
                    )
                    .flatten()
                )
        elif self.partition_by is None:
            ordering_preservation_needed = True
            label_sorting_key = self.gen_random_name("sorting_key", ctx)
            labels[label_sorting_key] = SortingKeyConversion(
                self.order_by, common_conv=GetItem(1)
            )
            c_agg = (
                CallFunc(
                    zip,
                    CallFunc(count),
                    This,
                )
                .as_type(list)
                .pipe(
                    This.call_method(
                        "sort", key=LabelConversion(label_sorting_key)
                    ).or_(This)
                )
                .pipe(
                    CallFunc(
                        zip,
                        This.iter(GetItem(0)),
                        This.iter(GetItem(1))
                        .as_type(list)
                        .pipe(frames_finder)
                        .iter(c_frame_data_handler),
                    )
                )
            )
        else:
            ordering_preservation_needed = True
            label_sorting_key = self.gen_random_name("sorting_key", ctx)
            labels[label_sorting_key] = SortingKeyConversion(
                self.order_by, common_conv=GetItem(1)
            )
            c_agg = (
                GroupBy(self.partition_by)
                .aggregate(
                    ReduceFuncs.Array(
                        (LabelConversion(self._label_next).call(), This),
                        default=list,
                    )
                    .pipe(
                        This.call_method(
                            "sort", key=LabelConversion(label_sorting_key)
                        ).or_(This)
                    )
                    .pipe(
                        CallFunc(
                            zip,
                            This.iter(GetItem(0)),
                            This.iter(GetItem(1))
                            .as_type(list)
                            .pipe(frames_finder)
                            .iter(c_frame_data_handler),
                        )
                    )
                )
                .flatten()
            )

        conv = self.conv.add_label(labels)

        if ordering_preservation_needed:
            conv = conv.pipe(
                c_agg.pipe(dict)
                .pipe(
                    InlineExpr("[{d}[i] for i in range({d_len})]").pass_args(
                        d=This, d_len=This.pipe(len)
                    )
                )
                .as_type(list)
            )
        else:
            conv = conv.pipe(c_agg.as_type(list))

        with NamespaceCtx(name_to_code, ctx):
            return conv.gen_code_and_update_ctx(code_input, ctx)

    def _init_frame_data(self, name_to_code):
        frame_data_names = {
            dep.name
            for dep in self.reducer.conversion.get_dependencies(
                LazyEscapedString
            )
            if dep.name in FRAME_DATA_NAMES
        }
        extra_results_code_pieces = []
        name_to_index = {}
        for name, code in name_to_code.items():
            if name in frame_data_names:
                extra_results_code_pieces.append(code)
                name_to_index[name] = len(extra_results_code_pieces)

        frame_conv: "BaseConversion"
        if extra_results_code_pieces:
            extra_results_code = ", " + ", ".join(extra_results_code_pieces)
            frame_conv = GetItem(0)
        else:
            extra_results_code = ""
            frame_conv = This

        return extra_results_code, frame_conv, name_to_index

    def _init_peer_groups_code(self, ctx):
        code = Code()
        code.add_line("def placeholder", 1)
        code.add_line("data_len_ = len(data_)", 0)

        code.add_line("if data_:", 1)
        code.add_line("data_len_ = len(data_)", 0)
        code.add_line("groups_ = []", 0)
        code.add_line("append_ = groups_.append", 0)
        code.add_line("prev_index = 0", 0)

        if self._label_sorting_key is not None:
            code.add_line(
                "prev_ordering_key = {}".format(
                    LabelConversion(self._label_sorting_key)
                    .call(This)
                    .gen_code_and_update_ctx("data_[0]", ctx)
                ),
                0,
            )
            code.add_line("for index_cur in range(1, data_len_):", 1)
            code.add_line(
                "ordering_key = {}".format(
                    LabelConversion(self._label_sorting_key)
                    .call(This)
                    .gen_code_and_update_ctx("data_[index_cur]", ctx)
                ),
                0,
            )
            code.add_line("if prev_ordering_key != ordering_key:", 1)
            code.add_line("append_((prev_index, index_cur))", 0)
            code.add_line("prev_index = index_cur", 0)
            code.add_line("prev_ordering_key = ordering_key", -2)

        code.add_line("if not groups_ or groups_[-1][1] != data_len_:", 1)
        code.add_line("append_((prev_index, data_len_))", -1)

        code.add_line("frame_start = 0", 0)
        code.add_line("frame_end = 0", 0)
        code.add_line(
            "for index_group, (index_start, index_end) in enumerate(groups_):",
            1,
        )
        return code

    def _init_yield_results_code(
        self, code, _, frame_start_code, frame_end_code, extra_results_code
    ):
        if self.frame_exclusion == FrameExclusion.NO_OTHERS:
            code.add_line(
                "yield itertools_islice(data_, {0}, {1}){2}".format(
                    frame_start_code, frame_end_code, extra_results_code
                ),
                0,
            )
        elif self.frame_exclusion == FrameExclusion.CURRENT_ROW:
            code.add_line(
                (
                    "yield (itertools_chain("
                    " itertools_islice(data_, {0}, index_cur), "
                    " itertools_islice(data_, index_cur + 1, {1})"
                    ") if {0} <= index_cur <= {1} "
                    "else itertools_islice(data_, {0}, {1})){2}".format(
                        frame_start_code, frame_end_code, extra_results_code
                    )
                ),
                0,
            )
        elif self.frame_exclusion == FrameExclusion.GROUP:
            code.add_line(
                "yield itertools_chain("
                "itertools_islice(data_, {0}, min({1}, index_start)),"
                "itertools_islice(data_, max({0}, index_end), {1}),"
                "){2}".format(
                    frame_start_code, frame_end_code, extra_results_code
                ),
                0,
            )
        elif self.frame_exclusion == FrameExclusion.TIES:
            code.add_line(
                "yield itertools_chain("
                "itertools_islice(data_, {0}, min({1}, index_start)),"
                "(data_[index_cur],) if {0} <= index_cur < {1} else (),"
                "itertools_islice(data_, max({0}, index_end), {1}),"
                "){2}".format(
                    frame_start_code, frame_end_code, extra_results_code
                ),
                0,
            )
        else:
            raise AssertionError("bug")

    def _gen_groups_frames_finder(self, ctx):
        ctx["itertools_islice"] = islice
        ctx["itertools_chain"] = chain
        converter_name = self.gen_random_name("iter_groups_frames", ctx)
        function_ctx = self.as_function_ctx(ctx, optimize_naive=True)
        function_ctx.add_arg("data_", This)
        with function_ctx:
            code = self._init_peer_groups_code(ctx)

            if self.frame_start.unbounded_preceding:
                frame_start_code = "0"
            elif self.frame_start.current_row:
                frame_start_code = "index_group"
            else:
                frame_start_code = "index_group {} {}".format(
                    self.frame_start.offset_sign_as_str,
                    NaiveConversion(
                        self.frame_start.offset
                    ).gen_code_and_update_ctx(None, ctx),
                )

            if self.frame_end.unbounded_following:
                frame_end_code = "len(groups_) - 1"
            elif self.frame_end.current_row:
                frame_end_code = "index_group"
            else:
                frame_end_code = "index_group {} {}".format(
                    self.frame_end.offset_sign_as_str,
                    NaiveConversion(
                        self.frame_end.offset
                    ).gen_code_and_update_ctx(None, ctx),
                )

            code.add_line(f"frame_start_group_index = {frame_start_code}", 0)
            code.add_line(f"frame_end_group_index = {frame_end_code}", 0)

            code.add_line(
                "if frame_end_group_index < 0 or frame_start_group_index >= len(groups_):",
                1,
            )
            code.add_line("frame_start = frame_end = data_len_", 0)
            extra_results_code, frame_conv, name_to_index = (
                self._init_frame_data(
                    {
                        FrameData.ROW_INDEX.name: "index_cur",
                        FrameData.PEER_GROUP_FIRST_ROW_INDEX.name: "index_start",
                        FrameData.PEER_GROUP_LAST_ROW_INDEX.name: "index_end - 1",
                        FrameData.PEER_GROUP_INDEX.name: "index_group",
                        FrameData.PARTITION.name: "data_",
                    }
                )
            )

            code.add_line(
                "yield from ({} for index_cur in range(index_start, index_end))".format(
                    f"((){extra_results_code})" if extra_results_code else "()"
                ),
                0,
            )
            code.add_line("continue", -1)

            code.add_line(
                "frame_start = groups_[min(len(groups_) - 1, max(0, frame_start_group_index))][0]",
                0,
            )
            code.add_line(
                "frame_end = groups_[min(len(groups_) - 1, max(0, frame_end_group_index))][1]",
                0,
            )

            code.add_line("for index_cur in range(index_start, index_end):", 1)

            self._init_yield_results_code(
                code, ctx, "frame_start", "frame_end", extra_results_code
            )

            code.lines_info[0] = (
                0,
                f"def {converter_name}({function_ctx.get_def_all_args_code()}):",
            )
            conversion = function_ctx.gen_conversion(
                converter_name, code.to_string(0)
            )
        return (
            function_ctx.call_with_all_args(conversion),
            frame_conv,
            name_to_index,
        )

    def _gen_rows_frames_finder(self, ctx):
        ctx["itertools_islice"] = islice
        ctx["itertools_chain"] = chain
        converter_name = self.gen_random_name("iter_rows_frames", ctx)
        function_ctx = self.as_function_ctx(ctx, optimize_naive=True)
        function_ctx.add_arg("data_", This)
        with function_ctx:
            code = self._init_peer_groups_code(ctx)

            code.add_line("for index_cur in range(index_start, index_end):", 1)

            if self.frame_start.unbounded_preceding:
                frame_start_code = "0"
            elif self.frame_start.current_row:
                frame_start_code = "index_cur"
            else:
                frame_start_code = "index_cur {} {}".format(
                    self.frame_start.offset_sign_as_str,
                    NaiveConversion(
                        self.frame_start.offset
                    ).gen_code_and_update_ctx(None, ctx),
                )
                if self.frame_start.offset_sign_as_str == "-":
                    frame_start_code = f"max(0, {frame_start_code})"

            if self.frame_end.unbounded_following:
                frame_end_code = "data_len_"
            elif self.frame_end.current_row:
                frame_end_code = "index_cur + 1"
            else:
                frame_end_code = "index_cur {} {}".format(
                    self.frame_end.offset_sign_as_str,
                    NaiveConversion(
                        (self.frame_end.offset or 0)
                        + (
                            -1
                            if self.frame_end.offset_sign_as_str == "-"
                            else 1
                        )
                    ).gen_code_and_update_ctx(None, ctx),
                )
                if self.frame_end.offset_sign_as_str == "+":
                    frame_end_code = f"min(data_len_, {frame_end_code})"

            extra_results_code, frame_conv, name_to_index = (
                self._init_frame_data(
                    {
                        FrameData.ROW_INDEX.name: "index_cur",
                        FrameData.PEER_GROUP_FIRST_ROW_INDEX.name: "index_start",
                        FrameData.PEER_GROUP_LAST_ROW_INDEX.name: "index_end - 1",
                        FrameData.PEER_GROUP_INDEX.name: "index_group",
                        FrameData.PARTITION.name: "data_",
                    }
                )
            )

            self._init_yield_results_code(
                code, ctx, frame_start_code, frame_end_code, extra_results_code
            )

            code.lines_info[0] = (
                0,
                f"def {converter_name}({function_ctx.get_def_all_args_code()}):",
            )
            conversion = function_ctx.gen_conversion(
                converter_name, code.to_string(0)
            )
        return (
            function_ctx.call_with_all_args(conversion),
            frame_conv,
            name_to_index,
        )

    def _gen_range_frames_finder(self, ctx):
        ctx["itertools_islice"] = islice
        ctx["itertools_chain"] = chain
        converter_name = self.gen_random_name("iter_range_frames", ctx)
        function_ctx = self.as_function_ctx(ctx, optimize_naive=True)
        function_ctx.add_arg("data_", This)

        with function_ctx:
            code = self._init_peer_groups_code(ctx)

            if self.frame_start.unbounded_preceding:
                code.add_line("frame_start = 0", 0)

            elif self.frame_start.current_row:
                code.add_line("frame_start = index_start", 0)
            else:
                label_sorting_key = cast(str, self._label_sorting_key)
                code.add_line(
                    "stop_value = {} {} {}".format(
                        LabelConversion(label_sorting_key)
                        .call(This)
                        .gen_code_and_update_ctx("data_[index_start]", ctx),
                        self.frame_start.offset_sign_as_str,
                        NaiveConversion(
                            self.frame_start.offset
                        ).gen_code_and_update_ctx(None, ctx),
                    ),
                    0,
                )
                code.add_line("for index in range(frame_start, data_len_):", 1)
                code.add_line(
                    "if {} >= stop_value:".format(
                        LabelConversion(label_sorting_key)
                        .call(This)
                        .gen_code_and_update_ctx("data_[index]", ctx),
                    ),
                    1,
                )
                code.add_line("frame_start = index", 0)
                code.add_line("break", -2)
                code.add_line("else:", 1)
                code.add_line("frame_start = data_len_", -1)

            if self.frame_end.unbounded_following:
                code.add_line("frame_end = data_len_", 0)
            elif self.frame_end.current_row:
                code.add_line("frame_end = index_end", 0)
            else:
                label_sorting_key = cast(str, self._label_sorting_key)
                code.add_line(
                    "stop_value = {} {} {}".format(
                        LabelConversion(label_sorting_key)
                        .call(This)
                        .gen_code_and_update_ctx("data_[index_start]", ctx),
                        self.frame_end.offset_sign_as_str,
                        NaiveConversion(
                            self.frame_end.offset
                        ).gen_code_and_update_ctx(None, ctx),
                    ),
                    0,
                )
                code.add_line("for index in range(frame_end, data_len_):", 1)
                code.add_line(
                    "if {} > stop_value:".format(
                        LabelConversion(label_sorting_key)
                        .call(This)
                        .gen_code_and_update_ctx("data_[index]", ctx),
                    ),
                    1,
                )
                code.add_line("frame_end = index", 0)
                code.add_line("break", -2)
                code.add_line("else:", 1)
                code.add_line("frame_end = data_len_", -1)

            code.add_line("for index_cur in range(index_start, index_end):", 1)

            extra_results_code, frame_conv, name_to_index = (
                self._init_frame_data(
                    {
                        FrameData.ROW_INDEX.name: "index_cur",
                        FrameData.PEER_GROUP_FIRST_ROW_INDEX.name: "index_start",
                        FrameData.PEER_GROUP_LAST_ROW_INDEX.name: "index_end - 1",
                        FrameData.PEER_GROUP_INDEX.name: "index_group",
                        FrameData.PARTITION.name: "data_",
                    }
                )
            )
            self._init_yield_results_code(
                code, ctx, "frame_start", "frame_end", extra_results_code
            )

            code.lines_info[0] = (
                0,
                f"def {converter_name}({function_ctx.get_def_all_args_code()}):",
            )
            conversion = function_ctx.gen_conversion(
                converter_name, code.to_string(0)
            )
        return (
            function_ctx.call_with_all_args(conversion),
            frame_conv,
            name_to_index,
        )


class FrameData:
    PARTITION = LazyEscapedString("partition")
    PEER_GROUP_FIRST_ROW_INDEX = LazyEscapedString(
        "peer_group_first_row_index"
    )
    PEER_GROUP_INDEX = LazyEscapedString("group_index")
    PEER_GROUP_LAST_ROW_INDEX = LazyEscapedString("peer_group_last_row_index")
    ROW_INDEX = LazyEscapedString("row_index")
    # PeerGroupIndex = LazyEscapedString("group_index")
    # PeerGroupLastRowIndex = LazyEscapedString("peer_group_last_row_index")
    # RowIndex = LazyEscapedString("row_index")


FRAME_DATA_NAMES = {
    FrameData.PARTITION.name,
    FrameData.PEER_GROUP_FIRST_ROW_INDEX.name,
    FrameData.PEER_GROUP_INDEX.name,
    FrameData.PEER_GROUP_LAST_ROW_INDEX.name,
    FrameData.ROW_INDEX.name,
}


def row_index():
    """Row index within the partition."""
    return FrameData.ROW_INDEX


def row():
    return FrameData.PARTITION.item(FrameData.ROW_INDEX)


def row_preceding(offset, default=None):
    return If(
        FrameData.ROW_INDEX - offset < 0,
        default,
        FrameData.PARTITION.item(FrameData.ROW_INDEX - offset),
    )


def row_following(offset, default=None):
    return If(
        FrameData.ROW_INDEX + offset >= FrameData.PARTITION.pipe(len),
        default,
        FrameData.PARTITION.item(FrameData.ROW_INDEX + offset),
    )


def peer_group_first_row_index():
    return FrameData.PEER_GROUP_FIRST_ROW_INDEX


def peer_group_first_row():
    return FrameData.PARTITION.item(FrameData.PEER_GROUP_FIRST_ROW_INDEX)


def peer_group_last_row_index():
    return FrameData.PEER_GROUP_LAST_ROW_INDEX


def peer_group_last_row():
    return FrameData.PARTITION.item(FrameData.PEER_GROUP_LAST_ROW_INDEX)


def peer_group_index():
    return FrameData.PEER_GROUP_INDEX


def frame_first_row(default=None):
    return ReduceFuncs.First(This, default=default)


def frame_last_row(default=None):
    return ReduceFuncs.Last(This, default=default)


def frame_nth_row(n, default=None):
    return ReduceFuncs.Array(This).item(n, default=default)


class WindowFuncs:
    """Expose the list of window functions."""

    # pylint: disable=invalid-name

    FrameFirstRow = frame_first_row
    FrameLastRow = frame_last_row
    FrameNthRow = frame_nth_row
    PeerGroupFirstRow = peer_group_first_row
    PeerGroupFirstRowIndex = peer_group_first_row_index
    PeerGroupIndex = peer_group_index
    PeerGroupLastRow = peer_group_last_row
    PeerGroupLastRowIndex = peer_group_last_row_index
    Row = row
    RowFollowing = row_following
    RowIndex = row_index
    RowPreceding = row_preceding
