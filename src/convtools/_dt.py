"""Defines datetime utility functions."""
import re
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Dict, Iterator, List, Type, Union

from ._base import BaseConversion, CallFunc, NaiveConversion, This
from ._utils import Code, CodeParams


date_from_ordinal = date.fromordinal
datetime_from_ordinal = datetime.fromordinal
MICROSECOND = timedelta(microseconds=1)
DAY = timedelta(days=1)


__all__ = ["DateGrid", "DateTimeGrid"]


class TruncModes:
    """Defines truncate modes.

    START obviously means period start, END means
    the non-inclusive end of current interval (start of the next one),
    END_INCLUSIVE means inclusive end of the current interval
    """

    START = 1
    END = 2
    END_INCLUSIVE = 3

    _verbose_to_value = {
        "start": START,
        "end": END,
        "end_inclusive": END_INCLUSIVE,
    }

    @classmethod
    def to_internal(cls, value):
        try:
            return cls._verbose_to_value[value]
        except KeyError:
            raise ValueError(  # pylint: disable=raise-missing-from
                "unsupported mode"
            )


class BaseStep:
    """Base definition of a time-related step."""

    types: "Dict[str, int]"

    def to_months(self):
        raise TypeError("cannot be interpreted as months")

    def to_days(self):
        raise TypeError("cannot be interpreted as days")

    def to_us(self):
        raise TypeError("cannot be interpreted as us")


class MonthStep(BaseStep):
    """Defines steps as number of months."""

    types = {"y": 12, "mo": 1}

    def __init__(self, params, negative=False):
        self.months = 0
        for type_, number in params.items():
            self.months += number * self.types[type_]
        if negative:
            self.months *= -1

    def to_months(self):
        return self.months


class DayOfWeekStep(BaseStep):
    """Defines steps as weeks, starting on certain day of week."""

    types = {
        "sun": 0,
        "mon": 1,
        "tue": 2,
        "wed": 3,
        "thu": 4,
        "fri": 5,
        "sat": 6,
    }

    def __init__(self, params):
        if len(params) != 1:
            raise AssertionError
        self.days = 7
        self.day_of_week_offset = 0
        for type_, number in params.items():
            self.days *= number
            self.day_of_week_offset += self.types[type_]

    def to_days(self):
        return self.days


class MicroSecondStep(BaseStep):
    """Defines steps as deterministic time units.

    Deterministic ones can be represented as days, hours, minutes, seconds,
    milliseconds, microseconds.
    """

    types = {
        "d": 86400000000,
        "h": 3600000000,
        "m": 60000000,
        "s": 1000000,
        "ms": 1000,
        "us": 1,
    }

    def __init__(self, params, negative=False):
        self.us = 0
        for type_, number in params.items():
            self.us += number * self.types[type_]
        if negative:
            self.us *= -1

    def can_be_cast_to_days(self):
        return self.us % 86400000000 == 0

    def to_days(self):
        if not self.can_be_cast_to_days():
            raise TypeError("cannot be interpreted as whole days")
        return self.us // 86400000000

    def to_us(self):
        return self.us


def date_trunc_to_month(dt, to_months, offset_months, mode):
    total_months = dt.year * 12 + dt.month - 1
    total_months -= (total_months - offset_months) % to_months
    if mode == 1:
        return date(total_months // 12, total_months % 12 + 1, 1)

    elif mode == 2:
        total_months += to_months
        return date(total_months // 12, total_months % 12 + 1, 1)

    total_months += to_months
    return date(total_months // 12, total_months % 12 + 1, 1) - DAY


def date_trunc_to_day(dt, to_days, offset_days, mode):
    days = dt.toordinal()
    days -= (days - offset_days) % to_days
    if mode == 1:
        return date_from_ordinal(days)

    elif mode == 2:
        return date_from_ordinal(days + to_days)

    return date_from_ordinal(days + to_days - 1)


def datetime_trunc_to_month(dt, to_months, offset_months, mode):
    total_months = dt.year * 12 + dt.month - 1
    total_months -= (total_months - offset_months) % to_months
    if mode == 1:
        return datetime(
            total_months // 12, total_months % 12 + 1, 1, tzinfo=dt.tzinfo
        )

    elif mode == 2:
        total_months += to_months
        return datetime(
            total_months // 12, total_months % 12 + 1, 1, tzinfo=dt.tzinfo
        )

    total_months += to_months
    return (
        datetime(
            total_months // 12, total_months % 12 + 1, 1, tzinfo=dt.tzinfo
        )
        - MICROSECOND
    )


def datetime_trunc_to_day(dt, to_days, offset_days, mode):
    days = dt.toordinal()
    days -= (days - offset_days) % to_days
    if mode == 1:
        return datetime_from_ordinal(days).replace(tzinfo=dt.tzinfo)

    elif mode == 2:
        return datetime_from_ordinal(days + to_days).replace(tzinfo=dt.tzinfo)

    return (
        datetime_from_ordinal(days + to_days).replace(tzinfo=dt.tzinfo)
        - MICROSECOND
    )


def datetime_trunc_to_microsecond(dt, to_us, offset_us, mode):
    us = (
        (dt.toordinal() - 1) * 86400000000
        + dt.hour * 3600000000
        + dt.minute * 60000000
        + dt.second * 1000000
        + dt.microsecond
    )
    us -= (us - offset_us) % to_us

    if mode == 1:
        pass
    elif mode == 2:
        us += to_us
    else:
        us += to_us - 1

    new_dt = datetime_from_ordinal(us // 86400000000 + 1)
    left_microseconds = us % 86400000000
    return new_dt.replace(
        hour=left_microseconds // 3600000000,
        minute=left_microseconds % 3600000000 // 60000000,
        second=left_microseconds % 60000000 // 1000000,
        microsecond=left_microseconds % 1000000,
        tzinfo=dt.tzinfo,
    )


STEP_CLASSES: "List[Union[Type[MonthStep], Type[DayOfWeekStep], Type[MicroSecondStep]]]" = [
    MonthStep,
    DayOfWeekStep,
    MicroSecondStep,
]
type_to_cls = {type_: cls_ for cls_ in STEP_CLASSES for type_ in cls_.types}


def to_step(in_) -> "Union[MonthStep, DayOfWeekStep, MicroSecondStep]":
    if isinstance(in_, str):
        if not in_:
            raise ValueError("empty definition")

        length = len(in_)
        step_cls = None
        params = {}

        i = 0
        if in_.startswith("-"):
            negative = True
            i = 1
        else:
            negative = False

        while i < length:
            first_digit = i
            while i < length and in_[i].isdigit():
                i += 1

            number = 1 if first_digit == i else int(in_[first_digit:i])

            first_symbol = i
            while i < length and not in_[i].isdigit():
                i += 1
            type_ = in_[first_symbol:i]

            if type_ in type_to_cls:
                if step_cls is None:
                    step_cls = type_to_cls[type_]
                elif type_to_cls[type_] is not step_cls:
                    raise ValueError(
                        "do not mix parameters of different steps",
                        step_cls.__name__,
                        type_to_cls[type_].__name__,
                    )

                if type_ in params:
                    raise ValueError(
                        f"step type is encountered twice: {type_}"
                    )

                params[type_] = number
            else:
                raise ValueError("unknown type", type_)

        if step_cls is None:
            raise AssertionError

        if negative:
            if issubclass(step_cls, DayOfWeekStep):
                raise ValueError("day-of-week steps cannot be negative")
            return step_cls(params, negative=True)

        return step_cls(params)

    elif isinstance(in_, timedelta):
        return MicroSecondStep({"us": round(in_.total_seconds() * 1000000)})

    raise ValueError("unsupported definition of grid")


def gen_dates__month(dt_start, dt_end, to_months, offset_months, mode):
    start_months = dt_start.year * 12 + dt_start.month - 1
    end_months = dt_end.year * 12 + dt_end.month - 1

    months = start_months - (start_months - offset_months) % to_months

    if mode == 1:
        while months <= end_months:
            yield date(months // 12, months % 12 + 1, 1)
            months += to_months

    elif mode == 2:
        while months <= end_months:
            months += to_months
            yield date(months // 12, months % 12 + 1, 1)

    else:
        while months <= end_months:
            months += to_months
            yield date(months // 12, months % 12 + 1, 1) - DAY


def gen_datetimes__month(dt_start, dt_end, to_months, offset_months, mode):
    start_months = dt_start.year * 12 + dt_start.month - 1
    end_months = dt_end.year * 12 + dt_end.month - 1
    tzinfo = dt_start.tzinfo

    months = start_months - (start_months - offset_months) % to_months

    if mode == 1:
        while months <= end_months:
            yield datetime(months // 12, months % 12 + 1, 1, tzinfo=tzinfo)
            months += to_months

    elif mode == 2:
        while months <= end_months:
            months += to_months
            yield datetime(months // 12, months % 12 + 1, 1, tzinfo=tzinfo)

    else:
        while months <= end_months:
            months += to_months
            yield datetime(
                months // 12, months % 12 + 1, 1, tzinfo=tzinfo
            ) - MICROSECOND


def gen_dates__day(dt_start, dt_end, to_days, offset_days, mode):
    start_days = dt_start.toordinal()
    end_days = dt_end.toordinal()

    days = start_days - (start_days - offset_days) % to_days

    if mode == 1:
        while days <= end_days:
            yield date_from_ordinal(days)
            days += to_days

    elif mode == 2:
        while days <= end_days:
            days += to_days
            yield date_from_ordinal(days)

    else:
        while days <= end_days:
            days += to_days
            yield date_from_ordinal(days - 1)


def gen_datetimes__day(dt_start, dt_end, to_days, offset_days, mode):
    start_days = dt_start.toordinal()
    end_days = dt_end.toordinal()
    tzinfo = dt_start.tzinfo

    days = start_days - (start_days - offset_days) % to_days

    if mode == 1:
        while days <= end_days:
            yield datetime_from_ordinal(days).replace(tzinfo=tzinfo)
            days += to_days

    elif mode == 2:
        while days <= end_days:
            days += to_days
            yield datetime_from_ordinal(days).replace(tzinfo=tzinfo)

    else:
        while days <= end_days:
            days += to_days
            yield datetime_from_ordinal(days).replace(
                tzinfo=tzinfo
            ) - MICROSECOND


def gen_datetimes__microsecond(dt_start, dt_end, to_us, offset_us, mode):
    tzinfo = dt_start.tzinfo
    start_us = (
        (dt_start.toordinal() - 1) * 86400000000
        + dt_start.hour * 3600000000
        + dt_start.minute * 60000000
        + dt_start.second * 1000000
        + dt_start.microsecond
    )
    end_us = (
        (dt_end.toordinal() - 1) * 86400000000
        + dt_end.hour * 3600000000
        + dt_end.minute * 60000000
        + dt_end.second * 1000000
        + dt_end.microsecond
    )

    us = start_us - (start_us - offset_us) % to_us

    if mode == 1:
        while us <= end_us:
            new_dt = datetime_from_ordinal(us // 86400000000 + 1)
            left_microseconds = us % 86400000000
            yield new_dt.replace(
                hour=left_microseconds // 3600000000,
                minute=left_microseconds % 3600000000 // 60000000,
                second=left_microseconds % 60000000 // 1000000,
                microsecond=left_microseconds % 1000000,
                tzinfo=tzinfo,
            )
            us += to_us

    elif mode == 2:
        while us <= end_us:
            us += to_us

            new_dt = datetime_from_ordinal(us // 86400000000 + 1)
            left_microseconds = us % 86400000000
            yield new_dt.replace(
                hour=left_microseconds // 3600000000,
                minute=left_microseconds % 3600000000 // 60000000,
                second=left_microseconds % 60000000 // 1000000,
                microsecond=left_microseconds % 1000000,
                tzinfo=tzinfo,
            )

    else:
        while us <= end_us:
            us += to_us

            new_dt = datetime_from_ordinal((us - 1) // 86400000000 + 1)
            left_microseconds = (us - 1) % 86400000000
            yield new_dt.replace(
                hour=left_microseconds // 3600000000,
                minute=left_microseconds % 3600000000 // 60000000,
                second=left_microseconds % 60000000 // 1000000,
                microsecond=left_microseconds % 1000000,
                tzinfo=tzinfo,
            )


class DateGrid:
    """Date grid with a particular step and offset (e.g. every other Tuesday).

    Iterator of month grid, which contains the defined period:
    >>> it = DateGrid("mo").around(date(2020, 12, 31), date(2021, 1, 15))
    >>> assert list(it) == [date(2020, 12, 1), date(2021, 1, 1)]

    Same as above, but returns inclusive ends of periods
    >>> it = DateGrid("mo", mode="end_inclusive").around(
    >>>     date(2020, 12, 31), date(2021, 1, 15)
    >>> )
    >>> assert list(it) == [date(2020, 12, 31), date(2021, 1, 31)]

    Quarters:
    >>> DateGrid("3mo")

    Every other Tuesday:
    >>> DateGrid("2tue")

    Every 10 days grid, shifted 1 day forward:
    >>> DateGrid("10d", "1d")

    Both step and offset can be defined as a string which is comprised of
    numbers and suffixes:
     - y: year
     - mo: month
     - sun/mon/tue/wed/thu/fri/sat: days of week
     - d: day
     - h: hour
     - m: minute
     - s: second
     - ms: millisecond
     - us: microsecond

    so -2d8h10us means minus 2 days 8 hours and 10 microseconds.


    Warning:
    -------
     * y/mo support only y/mo as offsets
     * days of week don't support offsets
     * as this method truncates dates, not datetimes, it accepts only whole
       number of days as steps and offsets

    Args:
    ----
      step: defines period length. If it's a year, month or a day of week,
        it defines beginnings of periods too.
      offset (optional): defines the shift of the expected date grid
        relative to 0-point. Positive offset shifts a grid to the right.
      mode (Literal["start", "end", "end_inclusive"]): defines truncating
        mode: "start" returns period start; "end" returns a start of the
        next period, complies with default interval definition where start
        is inclusive and end is not; "end_inclusive" returns the end of the
        current interval

    """

    __slots__ = ["f", "step", "offset", "mode"]

    def __init__(self, step, offset=None, mode="start"):
        self.mode = TruncModes.to_internal(mode)

        step = to_step(step)
        offset = None if offset is None else to_step(offset)

        if isinstance(step, MonthStep):
            self.f = gen_dates__month
            self.step = step.to_months()
            self.offset = 0 if offset is None else offset.to_months()

        elif isinstance(step, DayOfWeekStep):
            if offset is not None:
                raise ValueError(
                    "offsets are not applicable to day-of-week steps"
                )
            self.f = gen_dates__day
            self.step = step.to_days()
            self.offset = step.day_of_week_offset

        else:
            self.f = gen_dates__day
            self.step = step.to_days()
            self.offset = 0 if offset is None else offset.to_days()

    def around(
        self,
        dt_start: "Union[date, datetime]",
        dt_end: "Union[date, datetime]",
    ) -> "Iterator[date]":
        return self.f(dt_start, dt_end, self.step, self.offset, self.mode)


class DateTimeGrid:
    """Grid of datetimes with a particular step and offset.

    Iterator of month grid, which contains the defined period:
    >>> it = DateTimeGrid("mo").around(
    >>>     datetime(2020, 12, 31),
    >>>     datetime(2021, 1, 15)
    >>> )
    >>> assert list(it) == [datetime(2020, 12, 1, 0, 0), datetime(2021, 1, 1, 0, 0)]

    Same as above, but returns inclusive ends of periods
    >>> it = DateTimeGrid("mo", mode="end_inclusive").around(
    >>>     datetime(2020, 12, 31), datetime(2021, 1, 15)
    >>> )
    >>> assert list(it) == [
    >>>     datetime(2020, 12, 31, 23, 59, 59, 999999),
    >>>     datetime(2021, 1, 31, 23, 59, 59, 999999)
    >>> ]

    Quarters:
    >>> DateTimeGrid("3mo")

    Every other Tuesday:
    >>> DateTimeGrid("2tue")

    Every 8 hours grid, shifted 6 hours forward:
    >>> DateTimeGrid("8h", "6h")

    STEP-STRING is a string which is comprised of numbers and suffixes:
     - y: year
     - mo: month
     - sun/mon/tue/wed/thu/fri/sat: days of week
     - d: day
     - h: hour
     - m: minute
     - s: second
     - ms: millisecond
     - us: microsecond

    so "-2d8h10us" means minus 2 days 8 hours and 10 microseconds.

    Warning:
    -------
     * y/mo support only y/mo as offsets
     * days of week don't support offsets
     * any steps defined as deterministic units (d, h, m, s, ms, us) can
       only be used with offsets defined by deterministic units too

    Args:
    ----
      step: defines period length. If it's a year, month or a day of week,
        it defines beginnings of periods too.
      offset (optional): defines the shift of the expected date grid
        relative to 0-point. Positive offset shifts a grid to the right.
      mode (Literal["start", "end", "end_inclusive"]): defines truncating
        mode: "start" returns period start; "end" returns a start of the
        next period, complies with default interval definition where start
        is inclusive and end is not; "end_inclusive" returns the end of the
        current interval
    """

    __slots__ = ["f", "step", "offset", "mode"]

    def __init__(self, step, offset=None, mode="start"):
        self.mode = TruncModes.to_internal(mode)

        step = to_step(step)
        offset = None if offset is None else to_step(offset)

        if isinstance(step, MonthStep):
            self.f = gen_datetimes__month
            self.step = step.to_months()
            self.offset = 0 if offset is None else offset.to_months()

        elif isinstance(step, DayOfWeekStep):
            if offset is not None:
                raise ValueError(
                    "offsets are not applicable to day-of-week steps"
                )
            self.f = gen_datetimes__day
            self.step = step.to_days()
            self.offset = step.day_of_week_offset

        elif step.can_be_cast_to_days() and (
            offset is None or offset.can_be_cast_to_days()
        ):
            self.f = gen_datetimes__day
            self.step = step.to_days()
            self.offset = 0 if offset is None else offset.to_days()

        else:
            self.f = gen_datetimes__microsecond
            self.step = step.to_us()
            self.offset = 0 if offset is None else offset.to_us()

    def around(
        self, dt_start: datetime, dt_end: datetime
    ) -> "Iterator[datetime]":
        return self.f(dt_start, dt_end, self.step, self.offset, self.mode)


class _LocaleBasedMaps:
    """Lazily initialized locale-based date names."""

    weekday_to_pct_lower_a: List[str]
    weekday_to_pct_upper_a: List[str]
    month_to_pct_lower_b: List[str]
    month_to_pct_upper_b: List[str]
    hour_to_pct_lower_p: List[str]
    upper_y_strftime_fix_needed: bool
    upper_y_format_is_supported: bool
    late_initialized = False

    def late_init(self):
        self.late_initialized = True

        self.weekday_to_pct_lower_a = [
            (datetime(2019, 12, 30) + timedelta(days=i)).strftime("%a")
            for i in range(7)
        ]
        self.weekday_to_pct_upper_a = [
            (datetime(2019, 12, 30) + timedelta(days=i)).strftime("%A")
            for i in range(7)
        ]
        self.month_to_pct_lower_b = [
            datetime(2020, 1, 1).replace(month=i).strftime("%b")
            for i in range(1, 13)
        ]
        self.month_to_pct_upper_b = [
            datetime(2020, 1, 1).replace(month=i).strftime("%B")
            for i in range(1, 13)
        ]
        self.hour_to_pct_lower_p = [
            datetime(2020, 1, 1, i).strftime("%p") for i in (0, 12)
        ]

        # https://github.com/python/cpython/issues/57514
        dt = date(1, 1, 1)
        self.upper_y_strftime_fix_needed = False
        try:
            if (
                dt.strftime("%Y") == "1" and dt.strftime("%4Y") == "0001"
            ):  # pragma: no cover
                self.upper_y_strftime_fix_needed = True
        except (  # pragma: no cover # pylint: disable=broad-exception-caught
            Exception
        ):
            pass  # pragma: no cover
        self.upper_y_format_is_supported = (
            dt.strftime("%Y") == "0001" or self.upper_y_strftime_fix_needed
        )

    def __getattr__(self, attr):
        if not self.late_initialized:
            self.late_init()
        return object.__getattribute__(self, attr)

    def fix_strftime_format(self, fmt):
        if self.upper_y_strftime_fix_needed:
            fmt = fmt.replace("%Y", "%4Y")  # pragma: no cover
        return fmt  # pragma: no cover


LOCALE_BASED_MAPS = _LocaleBasedMaps()


class UnsupportedFormatCode(Exception):
    pass


class DatetimeFormat(BaseConversion):
    """datetime.strftime with certain cases optimized for speed."""

    def __init__(self, fmt):
        if not isinstance(fmt, str):
            raise ValueError
        super().__init__()
        self.fmt = fmt

    def _to_code(self, code_input, ctx):
        result = []

        code_params = CodeParams()
        code_params.create(
            f"isinstance({code_input}, {code_params.naive_code(datetime, ctx)})",
            "is_datetime",
        )
        code_params.create(
            f"({code_input}.hour if is_datetime else 0)",
            "hour",
            used_names=("is_datetime",),
        )
        code_params.create(
            f"({code_input}.minute if is_datetime else 0)",
            "minute",
            used_names=("is_datetime",),
        )
        code_params.create(
            f"({code_input}.second if is_datetime else 0)",
            "second",
            used_names=("is_datetime",),
        )
        code_params.create(
            f"({code_input}.microsecond if is_datetime else 0)",
            "microsecond",
            used_names=("is_datetime",),
        )
        code_params.create(f"{code_input}.weekday()", "weekday")
        code_params.create(f"{code_input}.year", "year")
        code_params.create(f"{code_input}.month", "month")
        code_params.create(f"{code_input}.day", "day")

        match = False
        for ch in self.fmt:
            if match:
                if ch == "%":
                    result.append("%%")
                elif ch == "a":
                    result.append(
                        "{%s[%%s]}"
                        % code_params.naive_code(
                            LOCALE_BASED_MAPS.weekday_to_pct_lower_a, ctx
                        )
                    )
                    code_params.use_param("weekday")
                elif ch == "A":
                    result.append(
                        "{%s[%%s]}"
                        % code_params.naive_code(
                            LOCALE_BASED_MAPS.weekday_to_pct_upper_a, ctx
                        )
                    )
                    code_params.use_param("weekday")
                elif ch == "b":
                    result.append(
                        "{%s[%%s - 1]}"
                        % code_params.naive_code(
                            LOCALE_BASED_MAPS.month_to_pct_lower_b, ctx
                        )
                    )
                    code_params.use_param("month")
                elif ch == "B":
                    result.append(
                        "{%s[%%s - 1]}"
                        % code_params.naive_code(
                            LOCALE_BASED_MAPS.month_to_pct_upper_b, ctx
                        )
                    )
                    code_params.use_param("month")
                elif ch == "p":
                    result.append(
                        "{%s[%%s // 12]}"
                        % code_params.naive_code(
                            LOCALE_BASED_MAPS.hour_to_pct_lower_p, ctx
                        )
                    )
                    code_params.use_param("hour")
                elif ch == "Y":
                    if not LOCALE_BASED_MAPS.upper_y_format_is_supported:
                        return None  # pragma: no cover
                    result.append("{%s:04}")
                    code_params.use_param("year")
                elif ch == "m":
                    result.append("{%s:02}")
                    code_params.use_param("month")
                elif ch == "d":
                    result.append("{%s:02}")
                    code_params.use_param("day")
                elif ch == "u":
                    result.append("{%s + 1}")
                    code_params.use_param("weekday")
                elif ch == "H":
                    result.append("{%s:02}")
                    code_params.use_param("hour")
                elif ch == "I":
                    result.append("{(%s - 1) %% 12 + 1:02}")
                    code_params.use_param("hour")
                elif ch == "M":
                    result.append("{%s:02}")
                    code_params.use_param("minute")
                elif ch == "S":
                    result.append("{%s:02}")
                    code_params.use_param("second")
                elif ch == "f":
                    result.append("{%s:06}")
                    code_params.use_param("microsecond")
                elif ch == "w":
                    result.append("{(%s + 1) %% 7}")
                    code_params.use_param("weekday")
                elif ch == "y":
                    result.append("{%s %% 100:02}")
                    code_params.use_param("year")
                else:
                    return None

                match = False
            elif ch == "%":
                match = True
            elif ch == "{":
                result.append("{{")
            elif ch == "}":
                result.append("}}")
            elif ch == '"':
                result.append(r"\"")
            else:
                result.append(ch)

        if match:
            return None

        code = Code()
        for assignment_code in code_params.iter_assignments():
            code.add_line(assignment_code, 0)

        f_string_code = "".join(result) % code_params.get_format_args()
        code.add_line(f'return f"{f_string_code}"', 0)
        return code

    def _gen_code_and_update_ctx(self, code_input, ctx):
        try:
            converter_name = self.gen_random_name("datetime_format", ctx)
            function_ctx = self.as_function_ctx(ctx, optimize_naive=True)
            function_ctx.add_arg("data_", This())
            with function_ctx:
                code = Code()
                code.add_line("def placeholder", 1)
                code_ = self._to_code("data_", ctx)
                if code_ is None:
                    raise UnsupportedFormatCode
                code.add_code(code_)
                code.lines_info[0] = (
                    0,
                    f"def {converter_name}({function_ctx.get_def_all_args_code()}):",
                )
                conversion = function_ctx.gen_conversion(
                    converter_name, code.to_string(0)
                )

            return function_ctx.call_with_all_args(
                conversion
            ).gen_code_and_update_ctx(code_input, ctx)

        except UnsupportedFormatCode:
            return CallFunc(
                datetime.strftime,
                This,
                LOCALE_BASED_MAPS.fix_strftime_format(self.fmt),
            ).gen_code_and_update_ctx(code_input, ctx)


class DatetimeParse(BaseConversion):
    """Code generation based subset of datetime.strptime."""

    def __init__(self, fmt):
        if not isinstance(fmt, str):
            raise ValueError
        super().__init__()
        self.fmt = fmt
        try:
            (
                self.re_pattern,
                self.assignment_code_lines,
                self.format_args,
            ) = self._parse_fmt(fmt)
        except UnsupportedFormatCode:
            self.re_pattern = (
                self.assignment_code_lines
            ) = self.format_args = None

    @staticmethod
    def _seq_to_re_group_str(seq):
        return "(%s)" % "|".join(
            [re.escape(x.lower()) for x in sorted(seq, key=len, reverse=True)]
        )

    @staticmethod
    @lru_cache(32)
    def _parse_fmt(fmt):
        re_pieces = []
        code_params = CodeParams()
        group_index = 0

        code_params.create("1", "month")
        code_params.create("1", "day")
        code_params.create("0", "hour")
        code_params.create("0", "minute")
        code_params.create("0", "second")
        code_params.create("0", "microsecond")

        match = False
        for ch in fmt:
            if match:
                if ch == "%":
                    re_pieces.append("%")
                elif ch == "Y":
                    re_pieces.append(r"(\d{4})")
                    code_params.create(f"int(groups_[{group_index}])", "year")
                    group_index += 1
                elif ch == "m":
                    re_pieces.append(r"(1[0-2]|0[1-9]|[1-9])")
                    code_params.create(f"int(groups_[{group_index}])", "month")
                    group_index += 1
                elif ch == "d":
                    re_pieces.append(r"(3[0-1]|[1-2]\d|0[1-9]|[1-9]| [1-9])")
                    code_params.create(f"int(groups_[{group_index}])", "day")
                    group_index += 1
                elif ch == "H":
                    re_pieces.append(r"(2[0-3]|[0-1]\d|\d)")
                    code_params.create(f"int(groups_[{group_index}])", "hour")
                    group_index += 1
                elif ch == "I":
                    re_pieces.append(r"(1[0-2]|0[1-9]|[1-9])")
                    code_params.create(
                        f"int(groups_[{group_index}])", "i_hour"
                    )
                    group_index += 1
                elif ch == "p":
                    re_pieces.append(
                        DatetimeParse._seq_to_re_group_str(
                            LOCALE_BASED_MAPS.hour_to_pct_lower_p
                        )
                    )
                    code_params.create(
                        f"12 if groups_[{group_index}].lower() == '''{LOCALE_BASED_MAPS.hour_to_pct_lower_p[1].lower()}''' else 0",
                        "ampm_h_delay",
                    )
                    group_index += 1
                elif ch == "M":
                    re_pieces.append(r"([0-5]\d|\d)")
                    code_params.create(
                        f"int(groups_[{group_index}])", "minute"
                    )
                    group_index += 1
                elif ch == "S":
                    re_pieces.append(r"(6[0-1]|[0-5]\d|\d)")
                    code_params.create(
                        f"int(groups_[{group_index}])", "second"
                    )
                    group_index += 1
                elif ch == "f":
                    re_pieces.append(r"([0-9]{1,6})")
                    code_params.create(
                        f"int(groups_[{group_index}] + '0' * (6 - len(groups_[{group_index}])))",
                        "microsecond",
                    )
                    group_index += 1
                else:
                    raise UnsupportedFormatCode(ch)
                match = False
            elif ch == "%":
                match = True
            else:
                re_pieces.append(re.escape(ch))

        if match:
            raise UnsupportedFormatCode("trailing %")

        if "year" not in code_params.name_to_code:
            raise UnsupportedFormatCode("year is missing")

        if "i_hour" in code_params.name_to_code:
            if "ampm_h_delay" in code_params.name_to_code:
                code_params.create(
                    "i_hour % 12 + ampm_h_delay",
                    "hour",
                    ("i_hour", "ampm_h_delay"),
                )
            else:
                raise UnsupportedFormatCode("%p is missing, when %I is used")
        elif "ampm_h_delay" in code_params.name_to_code:
            raise UnsupportedFormatCode("%I is missing, when %p is used")

        code_params.use_param("year")
        code_params.use_param("month")
        code_params.use_param("day")
        code_params.use_param("hour")
        code_params.use_param("minute")
        code_params.use_param("second")
        code_params.use_param("microsecond")
        re_pattern = re.compile("".join(re_pieces), re.IGNORECASE)
        assignment_code_lines = list(code_params.iter_assignments())
        format_args = code_params.get_format_args()
        return re_pattern, assignment_code_lines, format_args

    def _to_code(self, code_input, ctx):
        if self.re_pattern is None:
            return None

        code = Code()

        pattern_code = NaiveConversion(
            self.re_pattern
        ).gen_code_and_update_ctx(None, ctx)
        code.add_line(
            f"match = {pattern_code}.match({code_input})",
            0,
        )
        code.add_line("if not match:", 1)
        code.add_line(
            f"raise ValueError('time data %r does not match format %r' % ({code_input}, '''{self.fmt}'''))",
            -1,
        )
        code.add_line(f"if len({code_input}) != match.end():", 1)
        code.add_line(
            "raise ValueError('unconverted data remains: %s' % data_string[match.end():])",
            -1,
        )
        code.add_line("groups_ = match.groups()", 0)
        for assignment_code in self.assignment_code_lines:
            code.add_line(assignment_code, 0)

        datetime_code = NaiveConversion(datetime).gen_code_and_update_ctx(
            None, ctx
        )
        code.add_line(
            f"return {datetime_code}(%s, %s, %s, %s, %s, %s, %s)"
            % self.format_args,
            0,
        )
        return code

    def _gen_code_and_update_ctx(self, code_input, ctx):
        if self.re_pattern is None:
            return CallFunc(
                datetime.strptime, This, self.fmt
            ).gen_code_and_update_ctx(code_input, ctx)

        converter_name = self.gen_random_name("datetime_parse", ctx)
        function_ctx = self.as_function_ctx(ctx, optimize_naive=True)
        function_ctx.add_arg("data_", This())
        with function_ctx:
            code = Code()
            code.add_line("def placeholder", 1)
            code.add_code(self._to_code("data_", ctx))
            code.lines_info[0] = (
                0,
                f"def {converter_name}({function_ctx.get_def_all_args_code()}):",
            )
            conversion = function_ctx.gen_conversion(
                converter_name, code.to_string(0)
            )

        return function_ctx.call_with_all_args(
            conversion
        ).gen_code_and_update_ctx(code_input, ctx)
