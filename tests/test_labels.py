from convtools import conversion as c


def test_labels():
    conv1 = c.if_(
        1,
        c.input_arg("y")
        .item("abc")
        .add_label("abc")
        .pipe(
            c.input_arg("x").pipe(
                c.inline_expr("{cde} + 10").pass_args(cde=c.this().item("cde"))
            )
        )
        .pipe(
            c.inline_expr("{this} + {abc}").pass_args(
                this=c.this(), abc=c.label("abc")
            )
        ),
        2,
    ).gen_converter(debug=True)
    assert conv1(data_=1, x={"cde": 2}, y={"abc": 3}) == 15
