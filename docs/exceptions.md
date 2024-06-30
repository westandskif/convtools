# Exception handling

**Avoid exception handling in conversions as long as possible, because it
reduces clarity and can hide issues in the code.**

## c.try_

/// admonition | Experimental feature
    type: warning
It was added on Feb 21, 2024 and may be stabilized ~ in half a year.
///

`c.try_(conv).except_(exc_def, value, re_raise_if=None)` conversion
wrapper allows to handle exceptions:

* `conv`: a conversion, which is expected to raise an exception
* `exc_def`: exception class or tuple of exception classes to be caught
* `re_raise_if` (optional): if it evaluates to true, the caught exception is
  re-raised

{!examples-md/api__try.md!}
