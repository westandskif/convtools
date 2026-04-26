# Joins

/// admonition | Prerequisites
    type: info

Start with [Basics](./basics.md) for conversion fundamentals and
[Collections](./collections.md) for shaping or iterating inputs before joining.
///

/// admonition | See also
    type: tip

Join conditions use context-specific references; see
[Placeholders & Special References](./basics.md#placeholders-special-references).
For composing join predicates, see [Conditions and Pipes](./conditions_n_pipes.md).
///

`c.join(left_conversion, right_conversion, condition, how="inner")` defines
join conversion, which returns an iterator of `(left_element, right_element)`
tuples.

* `left_conversion` defines the left part of a join
* `right_conversion` defines the right part of a join
* `condition` defines which left/right row pairs match. Use `c.LEFT` and
  `c.RIGHT` inside the condition to reference elements of the left and right
  sequences. Pass `True` to make a cross join.
* `how` is any of `"inner" | "left" | "right" | "full"`. `"outer"` is accepted
  as an alias for `"full"`.

See [Placeholders & Special References](./basics.md#placeholders-special-references)
for the full list of context-specific references.

/// admonition
    type: info

`c.join` builds a hash map of the right side when keys are equi‑joinable
(`c.and_(...)` / `==` operators only); memory is `O(len(right))`. Non‑equi
conditions use nested-loop matching and can be much slower on large inputs.
///

## Left and right references

`c.LEFT` and `c.RIGHT` point to the current left and right rows being compared.
They behave like normal conversions, so you can use `item`, `attr`,
`call_method`, operators, and type conversions on them.

The example below joins two collections from a tuple input. The right-side IDs
are strings, so the condition casts them with `.as_type(int)` before comparing.
It also keeps only right-side rows where `age >= 18`.


{!examples-md/welcome__join.md!}

## Multi-key joins

Use `c.and_(...)` with multiple equality conditions to join on more than one
key. Equi-joinable conditions are used to build the right-side hash map.

{!examples-md/api__join_multikey.md!}

## Non-equi joins

Conditions do not have to be equality checks. For range matching and other
non-equi joins, write the condition directly with operators on `c.LEFT` and
`c.RIGHT`.

{!examples-md/api__join_non_equi.md!}

## Duplicate matches

`c.join` emits every matching pair. If two left rows and two right rows have the
same join key, the result contains four pairs for that key. This is the same
many-to-many behavior as a relational join.

{!examples-md/api__join_duplicates.md!}

## Memory and performance

When the condition contains equality predicates that compare left expressions to
right expressions, `c.join` uses those predicates as hash keys and stores the
right side in memory. Additional one-sided filters can be pushed to the relevant
side before matching.

For non-equi conditions, or conditions that cannot be split into hash keys,
`c.join` keeps the right side available and checks candidate pairs in a nested
loop. This is flexible, but it is usually more expensive for large inputs.

`left`, `right`, and `full` joins may yield `None` for the missing side. `full`
joins also track which right rows were already matched so they can emit
unmatched right rows at the end.
