from convtools import conversion as c

converter = c.this.sort(key=lambda x: x, reverse=True).gen_converter(
    debug=True
)
assert list(converter(range(3))) == [2, 1, 0]
