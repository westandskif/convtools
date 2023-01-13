from convtools import conversion as c

converter = (
    c.iter(
        (c.item("value") + 1).pipe(
            c.if_(c.this < 0, c.this * c.this, c.this * 2)
        )
    )
    .as_type(list)
    .gen_converter(debug=True)
)
assert converter([{"value": -4}, {"value": 2}]) == [9, 6]
