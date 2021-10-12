**convtools** is a python library to declaratively define pipelines for
processing collections, doing complex aggregations and joins. It also provides
a helper for stream processing of table-like data (e.g. CSV).

Conversions foster extensive code reuse. Once defined, these generate ad hoc
code with as much inlining as possible and return compiled ad hoc functions
`(with superfluous loops and conditions removed)`.
