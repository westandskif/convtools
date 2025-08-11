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

### Installation
```
pip install convtools
```


### 60-second tour

#### 1) Build & run a converter

{!examples-md/welcome_1.md!}

Under the hood `gen_converter()` compiles your expression into an ad‑hoc Python
function. Want a one‑off call? Use `.execute(data)` instead.

#### 2) Transform a collection

{!examples-md/welcome_2.md!}

Uses `c.iter` to express a per‑row transform and `.as_type(list)` to collect. 

#### 3) Group & aggregate

{!examples-md/welcome_3.md!}

Reducers support `where` filters and sensible defaults.
`c.group_by(...).aggregate(...)` returns a list you can sort, filter, or map
further.

#### 4) Join two sequences

{!examples-md/welcome_4.md!}

`c.join` returns `(left, right)` tuples; `c.LEFT`/`c.RIGHT` let you express join
conditions. Hash‑join optimization kicks in on equi‑joins.

---

### Streaming CSVs with `Table`

{!examples-md/welcome_5.md!}

`Table` is optimized for streaming transformations: rename/take/drop/update
columns, joins, explode, pivot, and more. Note: `Table` consumes its input once
(it’s an iterator).

---

### Debugging & generated code

Pass `debug=True` to `.gen_converter(...)` or `.execute(...)` to print the
compiled function for inspection. You can also set global debug options with
`c.OptionsCtx()`. Installing `black` prettifies the printed code automatically.

{!examples-md/welcome_6.md!}

---

### When should I reach for convtools?

* You need **composable transforms** over native Python data
(lists/dicts/generators/CSV), not a DataFrame.
* You want to **express business rules declaratively** and generate fast,
readable Python functions.
* You need **aggregations/joins/pipes** that you can **reuse** across scripts
and services.

/// admonition
    type: info

Looking for benchmarks and deeper rationale? See [Benefits](./benefits.md) in
the docs and the linked benchmark sources.
///

---

### Install & use in 3 steps

1. `pip install convtools`

1. `from convtools import conversion as c`

1. Build an expression → `gen_converter()` → call it wherever you need. 

---

### Links

* 📚 Docs: [https://convtools.readthedocs.io/](https://convtools.readthedocs.io/) *<-- You are here*
* 📦 PyPI: [https://pypi.org/project/convtools/](https://pypi.org/project/convtools/)
* 🧪 Examples: see ["Basics"](./basics.md), ["Collections"](./collections.md),
["Aggregations"](./aggregations.md), ["Joins"](./joins.md) and ["Contrib /
Tables"](./contrib_tables.md) in the docs.


### Contributing

* Star the repo and share use‑cases in Discussions -- it really helps.

* To report a bug or suggest enhancements, please open [an
issue](https://github.com/westandskif/convtools/issues) and/or submit [a pull
request](https://github.com/westandskif/convtools/pulls).

* **Reporting a Security Vulnerability**: see the [security
policy](https://github.com/westandskif/convtools/security/policy).

---

### What’s included in the box?

* `from convtools import conversion as c` — the main interface.

* `from convtools.contrib.tables import Table` — stream processing of CSV‑like/tabular data.

* `from convtools.contrib import fs` — tiny helpers for splitting buffers with custom newlines.

---

### License

MIT License (see `LICENSE.txt`).
