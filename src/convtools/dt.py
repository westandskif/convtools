"""
Defines datetime utility functions
"""
from datetime import date, datetime, timedelta
from typing import Dict, List, Type, Union


date_from_ordinal = date.fromordinal
datetime_from_ordinal = datetime.fromordinal
MICROSECOND = timedelta(microseconds=1)
DAY = timedelta(days=1)


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


def date_to_month(dt, to_months, offset_months, mode):
    total_months = dt.year * 12 + dt.month - 1
    total_months -= (total_months - offset_months) % to_months
    if mode == 1:
        return date(total_months // 12, total_months % 12 + 1, 1)

    elif mode == 2:
        total_months += to_months
        return date(total_months // 12, total_months % 12 + 1, 1)

    total_months += to_months
    return date(total_months // 12, total_months % 12 + 1, 1) - DAY


def datetime_to_month(dt, to_months, offset_months, mode):
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


def date_to_day(dt, to_days, offset_days, mode):
    days = dt.toordinal()
    days -= (days - offset_days) % to_days
    if mode == 1:
        return date_from_ordinal(days)

    elif mode == 2:
        return date_from_ordinal(days + to_days)

    return date_from_ordinal(days + to_days - 1)


def datetime_to_day(dt, to_days, offset_days, mode):
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


def datetime_to_microsecond(dt, to_us, offset_us, mode):
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
