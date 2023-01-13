from convtools import conversion as c

assert (
    c.iter(
        c.cumulative_reset("abc")
        .iter(c.cumulative(c.this, c.this + c.PREV, label_name="abc"))
        .as_type(list)
    )
    .as_type(list)
    .execute([[0, 1, 2], [3, 4]], debug=True)
) == [[0, 1, 3], [3, 7]]
