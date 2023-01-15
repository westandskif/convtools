# Dates

!!! warning
	**Please, make sure you've covered [Reference / Basics](./basics.md)
	first.**

## Parsing dates

1. `c.date_parse` and `date_parse` parse dates
1. `c.datetime_parse` and `datetime_parse` parse datetimes

Both accept one or more formats, supported by `datetime.strptime`.

{!examples-md/api__dates_parse.md!}


## Truncating dates

Dates and datetimes can be truncated by applying a date/datetime grid, which is
defined by `step` and `offset`.

1. `c.date_trunc` and `date_trunc` truncate dates
1. `c.datetime_trunc` and `datetime_trunc` truncate datetimes, preserving
   timezone of the passed datetime

The methods above have the parameters:

* `step` defines the period of date/datetime grid to be applied. It can be
  either `datetime.timedelta` or a simple STEP-STRING,
  which is defined as a concatenated string of an optional negative sign and
  then numbers and suffixes:
    * `y`: year
    * `mo`: month
    * `sun`/`mon`/`tue`/`wed`/`thu`/`fri`/`sat`: days of week
    * `d`: day
    * `h`: hour
    * `m`: minute
    * `s`: second
    * `ms`: millisecond
    * `us`: microsecond

* `offset` (optional) defines the offset of the date/datetime grid to be
  applied. It supports the same values as `step` does.

* `mode` (default is `"start"`) defines which part of a date/datetime grid
  period is to be returned
    * `"start"` returns the beginning of a grid period
	* `"end_inclusive"` returns the inclusive end of a grid period (_e.g. for a
	  monthly grid for Jan: it's Jan 31st_)
	* `"end"` return the exclusive end of a grid period (_e.g. for a monthly
	  grid for Jan: it's Feb 1st_)

Step examples:

* `-2d8h10us` means minus 2 days 8 hours and 10 microseconds
* `2tue` every other Tuesday
* `3mo` every quarter

!!! warning
      * y/mo steps support only y/mo as offsets
      * days of week don't support offsets
	  * truncating to dates, not datetimes, is possible for whole number of
	    days only
      * any steps defined as deterministic units (d, h, m, s, ms, us) can
        only be used with offsets defined by deterministic units too

{!examples-md/api__dates_trunc.md!}


## Date grids

Date grids are used to generate gap free series of dates/datetimes.
`DateGrid("mo").around(dt_start, dt_end)` returns an iterator of dates of the
monthly grid, which contains the provided period.

1. `DateGrid` generates `date` grids
1. `DateTimeGrid` generates `datetime` grids

Arguments are:

* `step` defines grid period length (see how STEP-STRING is defined above)
* `offset` defined the shift of the expected date/datetime grid relative to
  0-point
* `mode` (default is `"start"`) defines which part of a date/datetime grid
  period is to be returned
    * `"start"` returns the beginning of a grid period
	* `"end_inclusive"` returns the inclusive end of a grid period (_e.g. for a
	  monthly grid for Jan: it's Jan 31st_)
	* `"end"` return the exclusive end of a grid period (_e.g. for a monthly
	  grid for Jan: it's Feb 1st_)

{!examples-md/api__dates_grid.md!}
