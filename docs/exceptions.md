# Exception handling

**Avoid exception handling in conversions as long as possible, because it
reduces clarity and can hide issues in the code.**

## c.try_

`c.try_(conv).except_(exc_def, value, re_raise_if=None)` conversion
wrapper allows to handle exceptions:

* `conv`: a conversion, which is expected to raise an exception
* `exc_def`: exception class or tuple of exception classes to be caught
* `value`: a value or conversion to return when `exc_def` is caught and
  `re_raise_if` is absent or evaluates to false
* `re_raise_if` (optional): if it evaluates to true, the caught exception is
  re-raised

Both `value` and `re_raise_if` can work with the input data as usual, or
reference the caught exception as `c.EXCEPTION`.

{!examples-md/api__try.md!}
