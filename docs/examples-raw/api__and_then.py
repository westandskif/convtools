from convtools import conversion as c

# DEFAULT CONDITION
converter = (
    c.iter(c.this.and_then(c.this.as_type(int)))
    .as_type(list)
    .gen_converter(debug=True)
)
assert converter(["1", None, 2.0]) == [1, None, 2]

# CUSTOM CONDITION
converter = (
    c.iter(c.this.and_then(c.this + 10, condition=c.this != 1))
    .as_type(list)
    .gen_converter(debug=True)
)
assert converter(range(3)) == [10, 1, 12]
