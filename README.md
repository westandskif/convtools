# convtools — write transformations as expressions, run them as Python

**convtools** lets you declare data transformations in plain Python, then
compiles them into tiny, optimized Python functions at runtime. You keep your
data in native iterables (lists, dicts, generators, CSV streams)—no heavy
container required.

[![License](https://img.shields.io/github/license/westandskif/convtools.svg)](https://github.com/westandskif/convtools/blob/master/LICENSE.txt)
[![codecov](https://codecov.io/gh/westandskif/convtools/branch/master/graph/badge.svg)]( https://codecov.io/gh/westandskif/convtools)
[![Tests status](https://github.com/westandskif/convtools/workflows/tests/badge.svg)](https://github.com/westandskif/convtools/actions/workflows/pytest.yml)
[![Docs status](https://readthedocs.org/projects/convtools/badge/?version=latest)](https://convtools.readthedocs.io/en/latest/?badge=latest)
[![PyPI](https://badge.fury.io/py/convtools.svg)](https://pypi.org/project/convtools/)
[![Twitter](https://img.shields.io/twitter/url?label=convtools&style=social&url=https%3A%2F%2Ftwitter.com%2Fconvtools)](https://twitter.com/convtools)
[![Downloads](https://static.pepy.tech/badge/convtools)](https://pepy.tech/project/convtools)
[![Python versions](https://img.shields.io/pypi/pyversions/convtools.svg)](https://pypi.org/project/convtools/)

### Why pick convtools?

  * **Stay in Python.** Compose transformations as expressions: pipes, filters,
  joins, group‑bys, reducers, window functions, and more. Then call
  `.gen_converter()` to get a real Python function.
  * **Stream‑friendly.** Works directly on iterators and files; the Table
  helper processes CSV‑like data without loading everything into memory.
  * **Powerful aggregations.** Rich reducers (Sum, CountDistinct, MaxRow,
  ArraySorted, Dict*, TopK…) with per‑reducer `where` filters and defaults.
  Nested aggregations are first‑class.
  * **Debuggable & inspectable.** Print the generated code with `debug=True` or
  set global options via `c.OptionsCtx`. Works with `pdb`/`pydevd`.
  * **Plays nicely with Pandas/Polars.** It’s not a DataFrame; it’s a
  code‑generation layer. Use it when you want lean, composable transforms over
  native Python data.

____

### Installation

```
pip install convtools
```

## Documentation

**[convtools.readthedocs.io](https://convtools.readthedocs.io/en/latest/)**


## Group by example

```python
from convtools import conversion as c

input_data = [
    {"a": 5, "b": "foo"},
    {"a": 10, "b": "foo"},
    {"a": 10, "b": "bar"},
    {"a": 10, "b": "bar"},
    {"a": 20, "b": "bar"},
]

conv = (
    c.group_by(c.item("b"))
    .aggregate(
        {
            "b": c.item("b"),
            "a_first": c.ReduceFuncs.First(c.item("a")),
            "a_max": c.ReduceFuncs.Max(c.item("a")),
        }
    )
    .pipe(
        c.aggregate({
            "b_values": c.ReduceFuncs.Array(c.item("b")),
            "mode_a_first": c.ReduceFuncs.Mode(c.item("a_first")),
            "median_a_max": c.ReduceFuncs.Median(c.item("a_max")),
        })
    )
    .gen_converter()
)

assert conv(input_data) == {
    'b_values': ['foo', 'bar'],
    'mode_a_first': 10,
    'median_a_max': 15.0
}

```

##### Built-in reducers like `c.ReduceFuncs.First`
    * Sum
    * SumOrNone
    * Max
    * MaxRow
    * Min
    * MinRow
    * Count
    * CountDistinct
    * First
    * Last
    * Average
    * Median
    * Percentile
    * Mode
    * TopK
    * Array
    * ArrayDistinct
    * ArraySorted

    DICT REDUCERS ARE IN FACT AGGREGATIONS THEMSELVES, BECAUSE VALUES GET REDUCED.
    * Dict
    * DictArray
    * DictSum
    * DictSumOrNone
    * DictMax
    * DictMin
    * DictCount
    * DictCountDistinct
    * DictFirst
    * DictLast

    AND LASTLY YOU CAN DEFINE YOUR OWN REDUCER BY PASSING ANY REDUCE FUNCTION
    OF TWO ARGUMENTS TO ``c.reduce``.

---


### When should I reach for convtools?

* You need **composable transforms** over native Python data
(lists/dicts/generators/CSV), not a DataFrame.
* You want to **express business rules declaratively** and generate fast,
readable Python functions.
* You need **aggregations/joins/pipes** that you can **reuse** across scripts
and services.

---

### Contributing

* Star the repo and share use‑cases in Discussions -- it really helps.

* To report a bug or suggest enhancements, please open [an
issue](https://github.com/westandskif/convtools/issues) and/or submit [a pull
request](https://github.com/westandskif/convtools/pulls).

* **Reporting a Security Vulnerability**: see the [security
policy](https://github.com/westandskif/convtools/security/policy).
