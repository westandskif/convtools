from convtools import conversion as c

input_data = [{"a": 1, "b": 2}]

converter = (
    c.iter_mut(
        c.Mut.set_item("c", c.item("a") + c.item("b")),
        c.Mut.del_item("a"),
        c.Mut.del_item("d", if_exists=True),
        c.Mut.custom(c.this.call_method("update", c.input_arg("extra"))),
    )
    .as_type(list)
    .gen_converter(debug=True)
)

assert converter(input_data, extra={"d": 4}) == [{"b": 2, "c": 3, "d": 4}]
