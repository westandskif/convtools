from convtools import conversion as c

converter = (
    c.iter(
        c.try_multiple(
            (c.this.as_type(int), (ValueError, TypeError)),
            (c.this.as_type(float), (ValueError, TypeError)),
            default=None,
        )
    )
    .as_type(list)
    .gen_converter()
)

assert converter(["10", "2.5", "bad", None]) == [10, 2.5, None, None]
