--8<-- "README.md:intro"

## How it works

Convtools separates describing a transformation from running it:

1. Build a **conversion** such as `c.item("name").pipe(str.title)`. This is a
   reusable specification; it does not process data yet.
2. Call `.gen_converter()` once to compile the conversion into a normal Python
   function.
3. Call that function with as many inputs as needed. For a one-off operation,
   `.execute(data)` combines the compile and run steps.

--8<-- "docs/examples-md/welcome_1.md"

The examples below build on this model. Methods such as `c.iter(...)` change
what `c.this` refers to, while terminal operations decide whether a result is a
lazy iterator or a concrete collection.

## 60-second tour

### 1) Transform a collection

--8<-- "docs/examples-md/welcome_2.md"

Uses `c.iter` to express a per‑row transform and `.as_type(list)` to collect.

### 2) Group & aggregate

--8<-- "docs/examples-md/welcome_3.md"

Reducers support `where` filters and sensible defaults.
`c.group_by(...).aggregate(...)` returns a list you can sort, filter, or map
further.

### 3) Join two sequences

--8<-- "docs/examples-md/welcome_4.md"

`c.join` returns `(left, right)` tuples; `c.LEFT`/`c.RIGHT` let you express join
conditions. Hash‑join optimization kicks in on equi‑joins.

---

### 4) Process CSV rows with `Table`

--8<-- "docs/examples-md/welcome_5.md"

`Table` consumes its input once. Row-wise operations such as filtering,
updating, and selecting columns can stream; operations which need global state,
such as joins and pivots, retain data while processing. See
[Contrib / Tables](./contrib_tables.md) for the execution model.

---

## Debugging generated code

Pass `debug=True` to `.gen_converter(...)` or `.execute(...)` to print the
compiled function for inspection. You can also set global debug options with
`c.OptionsCtx()`. Installing `black` prettifies the printed code automatically.

--8<-- "docs/examples-md/welcome_6.md"

---

## Where to go next

| If you want to... | Read... |
| ----------------- | ------- |
| Understand inputs, lookups, calls, and converter reuse | [Basics](./basics.md) |
| Map, filter, sort, chunk, or materialize iterables | [Collections](./collections.md) |
| Compose branches and reusable pipelines | [Conditions and Pipes](./conditions_n_pipes.md) |
| Group rows and calculate reducers | [Aggregations](./aggregations.md) |
| Match two sequences | [Joins](./joins.md) |
| Process CSV, JSONL, or row streams | [Contrib / Tables](./contrib_tables.md) |

--8<-- "README.md:when_to_use"

/// admonition
    type: info

Looking for benchmarks and deeper rationale? See [Benefits](./benefits.md) in
the docs and the linked benchmark sources.
///

---

## Links

* 📚 Docs: [https://convtools.readthedocs.io/](https://convtools.readthedocs.io/) *<-- You are here*
* 📦 PyPI: [https://pypi.org/project/convtools/](https://pypi.org/project/convtools/)
* 🧪 Examples: see ["Basics"](./basics.md), ["Collections"](./collections.md),
["Aggregations"](./aggregations.md), ["Joins"](./joins.md) and ["Contrib /
Tables"](./contrib_tables.md) in the docs.
* 🤖 LLM-friendly docs:
[llms.txt](https://convtools.readthedocs.io/en/latest/llms.txt) — a concise,
machine-readable overview of convtools for AI assistants and code generators

--8<-- "README.md:contributing"

---

## License

MIT License (see `LICENSE.txt`).
