# Welcome to convtools

**convtools** is a Python library that simplifies data transformation by
allowing you to define them in a declarative way. It then generates the
necessary Python code in the background, saving you time and effort.

[![License](https://img.shields.io/github/license/westandskif/convtools.svg)](https://github.com/westandskif/convtools/blob/master/LICENSE.txt)
[![codecov](https://codecov.io/gh/westandskif/convtools/branch/master/graph/badge.svg)]( https://codecov.io/gh/westandskif/convtools)
[![Tests status](https://github.com/westandskif/convtools/workflows/tests/badge.svg)](https://github.com/westandskif/convtools/actions/workflows/pytest.yml)
[![Docs status](https://readthedocs.org/projects/convtools/badge/?version=latest)](https://convtools.readthedocs.io/en/latest/?badge=latest)
[![PyPI](https://badge.fury.io/py/convtools.svg)](https://pypi.org/project/convtools/)
[![Twitter](https://img.shields.io/twitter/url?label=convtools&style=social&url=https%3A%2F%2Ftwitter.com%2Fconvtools)](https://twitter.com/convtools)
[![Downloads](https://static.pepy.tech/badge/convtools)](https://pepy.tech/project/convtools)
[![Python versions](https://img.shields.io/pypi/pyversions/convtools.svg)](https://pypi.org/project/convtools/)

### Installation
```
pip install convtools
```

### Structure

1. `#!py from convtools import conversion as c` exposes the main interface to
   build pipelines for processing data, doing complex aggregations and joins.

1. `#!py from convtools.contrib.tables import Table` - stream processing of
   table-like data (e.g. CSV)

1. `#!py from convtools.contrib import fs` - tiny utils to handle splitting
   buffers with custom newlines


### Sneak peak on what's inside

#### Pipes

{!examples-md/welcome__pipes.md!}

#### Aggregations & Group By

{!examples-md/welcome__aggregations.md!}

{!examples-md/welcome__group_by.md!}

##### Built-in reducers like `c.ReduceFuncs.Sum`
    * Sum - auto-replaces False values with 0; default=0
    * SumOrNone - sum or None if at least one None is encountered; default=None
    * Max - max not None
    * MaxRow - row with max not None
    * Min - min not None
    * MinRow - row with min not None
    * Count - count of everything
    * CountDistinct - len of resulting set of values
    * First - first encountered value
    * Last - last encountered value
    * Average(value, weight=1) - pass custom weight conversion for weighted average
    * Median
    * Percentile(percentile, value, interpolation="linear")
        c.ReduceFuncs.Percentile(95.0, c.item("x"))
        interpolation is one of:
          - "linear"
          - "lower"
          - "higher"
          - "midpoint"
          - "nearest"
    * Mode
    * TopK - c.ReduceFuncs.TopK(3, c.item("x"))
    * Array
    * ArrayDistinct
    * ArraySorted
        c.ReduceFuncs.ArraySorted(c.item("x"), key=lambda v: v, reverse=True)

    DICT REDUCERS ARE IN FACT AGGREGATIONS THEMSELVES, BECAUSE VALUES GET REDUCED.
    * Dict
        c.ReduceFuncs.Dict(c.item("key"), c.item("x"))
    * DictArray - dict values are lists of encountered values
    * DictSum - values are sums
    * DictSumOrNone
    * DictMax
    * DictMin
    * DictCount
    * DictCountDistinct
    * DictFirst
    * DictLast

    AND LASTLY YOU CAN DEFINE YOUR OWN REDUCER BY PASSING ANY REDUCE FUNCTION
    OF TWO ARGUMENTS TO ``c.reduce``.

#### Joins

{!examples-md/welcome__join.md!}

#### Tables

{!examples-md/welcome__tables.md!}


**And of course you can mix all this together!**

### What's the point if there are tools like Pandas / Polars?

* convtools doesn't need to wrap data in a container to provide functionality,
  it simply runs the python code it generates on **any input**
* convtools is lightweight (_though optional `black` is highly recommended for
  pretty-printing generated code out of curiosity_)
* convtools fosters building pipelines on top of iterators, allowing for stream
  processing
* convtools supports nested aggregations
* convtools is a set of primitives for code generation, so it's just different.

### Is it debuggable?
Despite being compiled at runtime, it is (_by both `pdb` and `pydevd`_).

## Contributing

The best way to support the development of convtools is to spread the word!

Also, if you already are a convtools user, we would love to hear about your use
cases and challenges in the [Discussions
section](https://github.com/westandskif/convtools/discussions).

To report a bug or suggest enhancements, please open [an
issue](https://github.com/westandskif/convtools/issues) and/or submit [a pull
request](https://github.com/westandskif/convtools/pulls).


**Reporting a Security Vulnerability**: see the [security policy](https://github.com/westandskif/convtools/security/policy).
