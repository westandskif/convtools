# convtools

**convtools** is a niche python library created to dynamically define data
transforms using a declarative approach, while under the hood it generates
ad-hoc python code.

[![License](https://img.shields.io/github/license/westandskif/convtools.svg)](https://github.com/westandskif/convtools/blob/master/LICENSE.txt)
[![codecov](https://codecov.io/gh/westandskif/convtools/branch/master/graph/badge.svg)]( https://codecov.io/gh/westandskif/convtools)
[![Tests status](https://github.com/westandskif/convtools/workflows/tests/badge.svg)](https://github.com/westandskif/convtools/actions/workflows/pytest.yml)
[![Docs status](https://readthedocs.org/projects/convtools/badge/?version=latest)](https://convtools.readthedocs.io/en/latest/?badge=latest)
[![PyPI](https://badge.fury.io/py/convtools.svg)](https://pypi.org/project/convtools/)
[![Twitter](https://img.shields.io/twitter/url?label=convtools&style=social&url=https%3A%2F%2Ftwitter.com%2Fconvtools)](https://twitter.com/convtools)
[![Downloads](https://static.pepy.tech/badge/convtools)](https://pepy.tech/project/convtools)
[![Python versions](https://img.shields.io/pypi/pyversions/convtools.svg)](https://pypi.org/project/convtools/)

____

## Installation

`pip install convtools`

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


## What's the point if there are tools like Pandas / Polars?

* convtools doesn't need to wrap data in a container to provide functionality,
  it simply runs the python code it generates on **any input**
* convtools is lightweight (_though optional `black` is highly recommended for
  pretty-printing generated code out of curiosity_)
* convtools fosters building pipelines on top of iterators, allowing for stream
  processing
* convtools supports nested aggregations
* convtools is a set of primitives for code generation, so it's just different.

## Reporting a Security Vulnerability

See the [security policy](https://github.com/westandskif/convtools/security/policy).
