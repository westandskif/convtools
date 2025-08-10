# Joins

**Please, make sure you've covered [Basics](./basics.md) first.**

`c.join(left_conversion, right_conversion, condition, how="inner")` defines
join conversion, which returns an iterator of `(left_element, right_element)`
tuples.

* `left_conversion` defines the left part of a join
* `right_conversion` defines the right part of a join
* `condition` any condition defined as a conversion, where `c.LEFT` and
  `c.RIGHT` reference elements of the left and right sequences.
/// admonition
    type: info

`c.join` builds a hash map of the right side when keys are equi‑joinable
(`and_` / `==` operators only); memory is `O(len(right))`. Non‑equi conditions
can degrade performance.
///

 * `how` is any of `"inner" | "left" | "right" | "outer"`



{!examples-md/welcome__join.md!}
