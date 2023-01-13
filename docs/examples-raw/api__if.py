from convtools import conversion as c

# No. 1
converter = (
    c.iter(c.if_(c.this < 0, c.this * 2, c.this / 2))
    .as_type(list)
    .gen_converter(debug=True)
)
assert converter([-1, 0, 1]) == [-2, 0, 0.5]

# No. 2
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
    .gen_converter(debug=True)
)
assert converter([-1, 0, 1, 20]) == [-2, 100, 0.5, 2]
