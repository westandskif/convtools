# Benefits of convtools


## Fewer bugs & readability

* it forces you to split the definition of data conversion from the data
  itself
* functional approach (_pipes, "everything is an expression"_) lifts the
  obligation to name variables at each step, lowering the chance of confusing
  them
* `convtools` test coverage is 100% and it's development is test-driven, so
  whenever a bug is found, we'll do our best to make sure it never occurs
  again.

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

Since `convtools` is a code-generating layer, it provides you with an extra
functionality like group_by, joins, pipes, etc.


## Performance

/// admonition | 'The Art of Computer Programming' book by Donald Knuth:
    type: note

_The real problem is that programmers have spent far too much time worrying
about efficiency in the wrong places and at the wrong times; premature
optimization is the root of all evil (or at least most of it) in programming._
///

`convtools` worries about code efficiency, so you can put more effort into
other parts of your code. The below table provides the speed-up of
convtools-based solutions over the naive ones. 

/// tab | Speedups by python version
{! performance-md/perf-benchmarks.md !}
///

In cases where there are multiple speed test results, the worst is
taken. See [benchmarks on Github](https://github.com/westandskif/convtools/blob/master/run_benchmarks.py) for source code.
