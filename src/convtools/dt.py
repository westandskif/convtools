"""
Defines datetime utility functions
"""
from datetime import date, datetime, timedelta
from typing import Dict, Iterator, List, Type, Union


date_from_ordinal = date.fromordinal
datetime_from_ordinal = datetime.fromordinal
MICROSECOND = timedelta(microseconds=1)
DAY = timedelta(days=1)


__all__ = ["DateGrid", "DateTimeGrid"]


class TruncModes:
    """Defines truncate modes: START obviously means period start, END means
    the non-inclusive end of current interval (start of the next one),
    END_INCLUSIVE means inclusive end of the current interval"""

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
    """Base definition of a time-related step"""

    types: "Dict[str, int]"

    def to_months(self):
        raise TypeError("cannot be interpreted as months")

    def to_days(self):
        raise TypeError("cannot be interpreted as days")

    def to_us(self):
        raise TypeError("cannot be interpreted as us")


class MonthStep(BaseStep):
    """Defines steps as number of months"""

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
    """Defines steps as weeks, starting on certain day of week"""

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
    """Defines steps as deterministic time units (days, hours, minutes,
    seconds, milliseconds, microseconds)"""

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

            if first_digit == i:
                number = 1
            else:
                number = int(in_[first_digit:i])

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
    """Defines a grid of dates with a particular step and offset (e.g. every
    other Tuesday).

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


    WARNING:
     * y/mo support only y/mo as offsets
     * days of week don't support offsets
     * as this method truncates dates, not datetimes, it accepts only whole
       number of days as steps and offsets

    Args:
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
    """Defines a grid of dates with a particular step and offset (e.g. every
    other Tuesday).

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

    WARNING:
     * y/mo support only y/mo as offsets
     * days of week don't support offsets
     * any steps defined as deterministic units (d, h, m, s, ms, us) can
       only be used with offsets defined by deterministic units too

    Args:
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


def date_parse(
    s,
    main_format,
    other_formats,
    strptime__=datetime.strptime,
    exc__=(ValueError, TypeError),
):
    try:
        return strptime__(s, main_format).date()
    except exc__:
        pass

    for fmt in other_formats:
        try:
            return strptime__(s, fmt).date()
        except exc__:
            pass

    raise ValueError("string doesn't match any format", s)


def datetime_parse(
    s,
    main_format,
    other_formats,
    strptime__=datetime.strptime,
    exc__=(ValueError, TypeError),
):
    try:
        return strptime__(s, main_format)
    except exc__:
        pass

    for fmt in other_formats:
        try:
            return strptime__(s, fmt)
        except exc__:
            pass

    raise ValueError("data doesn't match any format", s)
