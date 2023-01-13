from datetime import datetime
from convtools import conversion as c

converter = (
    c.this.add_label({"a": c.item("a")})
    .item("b")
    .iter({"a": c.label("a"), "b": c.this})
    .as_type(list)
    .gen_converter(debug=True)
)
# SAME
converter_2 = (
    c.this.pipe(c.item("b"), label_input={"a": c.item("a")})
    .iter({"a": c.label("a"), "b": c.this})
    .as_type(list)
    .gen_converter(debug=True)
)
input_data = {
    "a": 1,
    "b": [2, 3, 4],
}
expected_output = [{"a": 1, "b": 2}, {"a": 1, "b": 3}, {"a": 1, "b": 4}]
assert (
    converter(input_data) == expected_output
    and converter_2(input_data) == expected_output
)


# BETTER WITHOUT LABELS (HERE IT'S POSSIBLE)
converter_3 = (
    c.zip(a=c.repeat(c.item("a")), b=c.item("b"))
    .as_type(list)
    .gen_converter(debug=True)
)
assert converter_3(input_data) == expected_output
