# Dates

!!! warning
	**Please, make sure you've covered [Reference / Basics](./basics.md)
	first.**

## Formatting dates

!!! tip "Performance"

    Many format codes are optimized for speed: `%% %A %a %B %H %I %M %S %Y %b %d %f %m %p %u %w %y`

`c.format_dt(fmt)` accepts same format codes as
[datetime.strftime](https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes) does.

{!examples-md/api__dates_format.md!}

## Parsing dates

!!! tip "Performance"

    Many format codes are optimized for speed: `%% %A %a %B %H %I %M %S %Y %b %d %f %m %p %u %w %y`

1. `c.date_parse(main_format, *other_formats, default=_none)` and `date_parse`
   method parse dates
1. `c.datetime_parse(main_format, *other_formats, default=_none)` and
   `datetime_parse` method parse datetimes


Both accept one or more formats, supported by [datetime.strptime](https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes).

{!examples-md/api__dates_parse.md!}

Let's use `default`, so it is returned in cases where neither of provided
formats fit:

{!examples-md/api__dates_parse__default.md!}


## Date/Time Step

For the sake of convenience (kudos to
[Polars](https://github.com/pola-rs/polars) for the idea), let's introduce a
definition of date/time step, to be used below. It's a concatenated string,
which may contain an optional negative sign and then numbers and suffixes:

* `y`: year
* `mo`: month
* `sun`/`mon`/`tue`/`wed`/`thu`/`fri`/`sat`: days of week
* `d`: day
* `h`: hour
* `m`: minute
* `s`: second
* `ms`: millisecond
* `us`: microsecond

Step examples:

* `-2d8h10us` means minus 2 days 8 hours and 10 microseconds
* `2tue` every other Tuesday
* `3mo` every quarter

It also accepts `datetime.timedelta`.


## Truncating dates

Dates and datetimes can be truncated by applying a date/datetime grid, which is
defined by `step` and `offset`.

1. `c.date_trunc` and `date_trunc` truncate dates
1. `c.datetime_trunc` and `datetime_trunc` truncate datetimes, preserving
   timezone of the passed datetime

The methods above have the parameters:

* `step` (step) defines the period of date/datetime grid to be used when
  truncating
* `offset` (optional step) defines the offset of the date/datetime grid to be
  applied
* `mode` (default is `"start"`) defines which part of a date/datetime grid
  period is to be returned
    * `"start"` returns the beginning of a grid period
	* `"end_inclusive"` returns the inclusive end of a grid period (_e.g. for a
	  monthly grid for Jan: it's Jan 31st_)
	* `"end"` return the exclusive end of a grid period (_e.g. for a monthly
	  grid for Jan: it's Feb 1st_)

!!! warning
      * y/mo steps support only y/mo offsets
	  * days of week don't support offsets (_otherwise we would get undesired
	    days of week_)
	  * when truncating dates, not datetimes, it is possible for whole number
	    of days only
      * any steps defined as deterministic units (d, h, m, s, ms, us) can
        only be used with offsets defined by deterministic units too

{!examples-md/api__dates_trunc.md!}


## Date grids

Date grids are not conversions, these are just helper functions which generate
gap free series of dates/datetimes.

e.g. `DateGrid("mo").around(dt_start, dt_end)` returns an iterator of dates of
the monthly grid, which contains the provided period.

!!! note
	It is intentionally different from Postgres' `generate_series(start, end,
	interval)` because it is not convenient in some cases, where you need to
	truncate `start` and `end` to a required precision first, otherwise you
	risk missing the very first period.

1. `DateGrid` generates `date` grids
1. `DateTimeGrid` generates `datetime` grids

Arguments are:

* `step` (step) defines grid period length (see how STEP-STRING is defined above)
* `offset` (optional step) defined the offset of the date/datetime grid
* `mode` (default is `"start"`) defines which part of a date/datetime grid
  period is to be returned
    * `"start"` returns the beginning of a grid period
	* `"end_inclusive"` returns the inclusive end of a grid period (_e.g. for a
	  monthly grid for Jan: it's Jan 31st_)
	* `"end"` return the exclusive end of a grid period (_e.g. for a monthly
	  grid for Jan: it's Feb 1st_)

{!examples-md/api__dates_grid.md!}
