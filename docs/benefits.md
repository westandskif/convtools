# Benefits of convtools


## Fewer bugs & readability

* it forces you to split the definition of data conversion from the data
  itself
* functional approach (_pipes, "everything is an expression"_) lifts the
  obligation to name variables at each step, lowering the chance of confusing
  them
* `convtools` test coverage is 100% (enforced in CI across both the pure-Python
  and C-extension paths) and its development is test-driven, so whenever a bug
  is found, we'll do our best to make sure it never occurs again.

## DRY

In some cases, to keep the code DRY (_complying with "Don't Repeat Yourself"
principle_) or just readable you need to pay with code performance:

* intensive code reuse (_function call overhead_)
* configs known at compile time (_loops, which can be unrolled_)

`convtools` encapsulates non-dry pieces in the code it generates.

Of course, there's also a cost, but it is completely under your control where
and when to run `gen_converter` to spend a fraction of a second to generate
an ad-hoc converter.

## Functionality

Since `convtools` is a code-generating layer, it provides you with extra
functionality like group_by, joins, pipes, etc.


## Performance

/// admonition | Donald Knuth, "Computer Programming as an Art" (1974):
    type: note

_The real problem is that programmers have spent far too much time worrying
about efficiency in the wrong places and at the wrong times; premature
optimization is the root of all evil (or at least most of it) in programming._
///

`convtools` worries about code efficiency, so you can put more effort into
other parts of your code. The table below reports relative speed vs. a
hand-written Python baseline (`(baseline_time / convtools_time - 1) * 100%`):
positive numbers mean `convtools` is faster, while negative numbers mean the
generated converter was slightly slower than a specialized hand-written loop on
that Python version.

/// tab | Speedups by python version
--8<-- "docs/performance-md/perf-benchmarks.md"
///

Benchmark families (when multiple runs exist, the worst result is shown; see
[`run_benchmarks.py`](https://github.com/westandskif/convtools/blob/master/run_benchmarks.py)
and
[`benchmarks/benchmarks.py`](https://github.com/westandskif/convtools/blob/master/benchmarks/benchmarks.py)
for full definitions):

* `GetDefaultPositive` / `GetDefaultNegative`: `c.item(..., default=...)` on a
  present vs. missing key compared with `try / except`.
* `Aggregate1`: single-pass `c.aggregate` (`Sum`, `Min`, `Max`) vs. a manual
  `for` loop.
* `GroupBy1 - FEW_GROUPS` / `MANY_GROUPS`: `c.group_by(...).aggregate(...)`
  with few vs. many distinct keys compared with a `defaultdict` loop.
* `IterOfIter1`: chained iterable transforms (`list_comp` + `iter`) vs. chained
  generators.
* `TableDictReader`: `Table.from_csv(..., header=True).into_iter_rows(dict)`
  vs. `csv.DictReader`.
* `DateParse*` / `DatetimeParse*` / `DateFormat*` / `DatetimeFormat*`:
  `c.date_parse`, `c.datetime_parse`, and `c.format_dt` on common date/datetime
  formats vs. `datetime.strptime` and `datetime.strftime`.
