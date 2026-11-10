from convtools import conversion as c

# Option 1: single condition
converter = (
    c.iter(c.if_(c.this < 0, c.this * 2, c.this / 2))
    .as_type(list)
    .gen_converter()
)
assert converter([-1, 0, 1]) == [-2, 0.0, 0.5]

# Omitted branches keep the input unchanged
assert c.iter(c.if_(c.this < 0, -c.this)).as_type(list).execute([-2, 3]) == [
    2,
    3,
]
assert c.if_().execute(42) == 42

# Option 2: multiple conditions
converter = (
    c.iter(
        c.if_multiple(
            (c.this < 0, c.this * 2),
            (c.this == 0, 100),
            (c.this < 10, c.this / 2),
            else_=c.this / 10,
        )
    )
    .as_type(list)
    .gen_converter()
)
assert converter([-1, 0, 1, 20]) == [-2, 100, 0.5, 2]
