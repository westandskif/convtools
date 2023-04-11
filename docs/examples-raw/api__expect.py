from convtools import conversion as c

# expect doesn't change input
converter = (
    c.iter(c.expect(c.this < 3, "too big") ** 10)
    .as_type(list)
    .gen_converter(debug=True)
)
assert converter(range(3)) == [0, 1, 1024]

# error_msg can be conversion itself
converter = (
    c.item("a")
    .expect(
        condition=c.this.len() > 3,
        error_msg=c.call_func("{} is too short".format, c.this),
    )
    .gen_converter(debug=True)
)
try:
    converter({"a": "val"})
except c.ExpectException as e:
    assert str(e) == "val is too short"
