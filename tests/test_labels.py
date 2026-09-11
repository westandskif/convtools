import pytest

from convtools import conversion as c


def test_labels():
    conv1 = c.if_(
        1,
        c.input_arg("y")
        .item("abc")
        .add_label("abc")
        .pipe(
            c.input_arg("x").pipe(
                c.inline_expr("{cde} + 10").pass_args(cde=c.this.item("cde"))
            )
        )
        .pipe(
            c.inline_expr("{this} + {abc}").pass_args(
                this=c.this, abc=c.label("abc")
            )
        ),
        2,
    ).gen_converter(debug=False)
    assert conv1(data_=1, x={"cde": 2}, y={"abc": 3}) == 15

    list(c.generator_comp(c.this.add_label("a")).execute([1, 2]))
    c.list_comp(c.this.add_label("a")).execute([1, 2])

    with pytest.raises(c.ConversionException):
        c.this.add_label(123)
    with pytest.raises(ValueError):
        c.label(123)

    conversion = (
        c.this.add_label("abc")
        .pipe(c.naive({1: 2, 3: 4, 5: 6}).call_method("items"))
        .pipe(c.generator_comp(c.item(1), where=c.item(0) <= c.label("abc")))
        .pipe(sum)
    )
    assert conversion.execute(4) == 6


def test_label_output_on_pipe_into_reducer():
    with pytest.raises(ValueError):
        c.this.pipe(c.ReduceFuncs.Sum(c.this), label_output="x")
    with pytest.raises(ValueError):
        c.this.pipe(c.ReduceFuncs.Sum(c.this), label_output="")
    with pytest.raises(ValueError):
        c.this.pipe(c.ReduceFuncs.Count(), label_input="")

    assert (
        c.aggregate(
            c.ReduceFuncs.Sum(c.this).pipe(c.this + 1, label_output="s")
        )
        .pipe(c.this + c.label("s"))
        .execute([1, 2])
        == 8
    )
    assert (
        c.aggregate(
            c.this.pipe(c.ReduceFuncs.Sum(c.this)).pipe(
                c.this * 2, label_output="s"
            )
        )
        .pipe(c.label("s"))
        .execute([1, 2])
        == 6
    )


@pytest.mark.parametrize("name", ["a'b", 'a"b', "a\\b", "a\nb"])
def test_label_names_with_quotes_and_escapes(name):
    assert (
        c.this.pipe(c.this + 1, label_output=name)
        .pipe(c.label(name) * 2)
        .execute(1)
        == 4
    )
    assert (
        c.this.pipe(c.this + 1, label_input=name)
        .pipe(c.label(name) + c.this + 1)
        .execute(1)
        == 4
    )
    assert c.this.add_label(name).pipe(c.label(name) * 4).execute(1) == 4
    assert (
        c.this.pipe(c.this + 1, label_output={name: c.this})
        .pipe(c.label(name) * 2)
        .execute(1)
        == 4
    )


def test_sibling_reducer_label_dependencies():
    R = c.ReduceFuncs
    sibling_msg = "sibling reducers of the same aggregate"

    with pytest.raises(c.ConversionException, match=sibling_msg) as exc_info:
        c.aggregate(
            {
                "s": R.Sum(c.item("a").pipe(c.this, label_output="lbl")),
                "m": R.Max(c.label("lbl")),
            }
        ).gen_converter()
    assert "lbl" in str(exc_info.value)

    with pytest.raises(c.ConversionException, match=sibling_msg):
        c.aggregate(
            {
                "s": R.Sum(c.item("a").pipe(c.this, label_input="lbl")),
                "m": R.Max(c.label("lbl")),
            }
        ).gen_converter()

    with pytest.raises(c.ConversionException, match=sibling_msg):
        c.aggregate(
            {
                "s": R.Sum(c.item("a").pipe(c.this, label_output="lbl")),
                "m": R.Max(c.label("lbl") * 2),
            }
        ).gen_converter()

    with pytest.raises(c.ConversionException, match=sibling_msg):
        c.aggregate(
            {
                "s": R.Sum(c.item("a").pipe(c.this, label_output="lbl")),
                "m": R.Max(c.item("b"), where=c.label("lbl") > 0),
            }
        ).gen_converter()

    with pytest.raises(c.ConversionException, match=sibling_msg):
        c.aggregate(
            {
                "a": R.Sum(
                    c.this.cumulative(
                        c.this, c.this + c.PREV, label_name="lbl"
                    )
                ),
                "b": R.Max(c.label("lbl")),
            }
        ).gen_converter()

    with pytest.raises(c.ConversionException, match=sibling_msg):
        c.aggregate(
            {
                "a": R.Sum(c.this.cumulative_reset("lbl")),
                "b": R.Max(c.label("lbl")),
            }
        ).gen_converter()

    with pytest.raises(c.ConversionException, match=sibling_msg):
        c.aggregate(
            {
                "a": R.Array(c.this.pipe(c.this, label_output="x")),
                "b": R.Sum(c.this, initial=c.label("x")),
            }
        ).gen_converter()

    assert (
        c.aggregate(
            R.Sum(
                c.item("a").pipe(c.this, label_output="lbl") + c.label("lbl")
            )
        ).execute([{"a": 1}, {"a": 2}])
        == 6
    )

    nested_write_read = c.aggregate(
        R.Sum(c.this.pipe(c.this, label_output="lbl") + c.label("lbl"))
    )
    assert c.aggregate(
        {
            "a": R.Sum(c.item("xs").pipe(nested_write_read)),
            "b": R.Max(
                c.item("ys").pipe(
                    c.aggregate(
                        R.Sum(
                            c.this.pipe(c.this, label_output="lbl")
                            + c.label("lbl")
                        )
                    )
                )
            ),
        }
    ).execute([{"xs": [1, 2], "ys": [3]}]) == {"a": 6, "b": 6}

    assert (
        c.this.pipe(c.this, label_output={"n": c.call_func(len, c.this)})
        .pipe(c.aggregate(R.Sum(c.this) + c.label("n")))
        .execute([1, 2, 3])
        == 9
    )

    c.this.add_label("g").pipe(
        c.group_by(c.label("g")).aggregate(R.Count())
    ).gen_converter()
    assert c.this.add_label("flag").pipe(
        c.group_by(c.this).aggregate(
            {"k": c.this, "n": R.Count(), "flag": c.label("flag")}
        )
    ).execute([1, 1, 2]) == [
        {"k": 1, "n": 2, "flag": [1, 1, 2]},
        {"k": 2, "n": 1, "flag": [1, 1, 2]},
    ]

    c.aggregate(
        {
            "a": R.Sum(c.item("a").pipe(c.this, label_output="lbl")),
            "b": R.Max(
                c.item("xs").pipe(
                    c.group_by(c.label("lbl")).aggregate(R.Count())
                )
            ),
        }
    ).gen_converter()

    reducer_outside_msg = (
        "reducers are only allowed inside aggregate/group_by reducer "
        "expressions"
    )
    with pytest.raises(c.ConversionException, match=reducer_outside_msg):
        c.group_by(R.Sum(c.this)).aggregate(c.this).gen_converter()
    with pytest.raises(c.ConversionException, match=reducer_outside_msg):
        c.group_by(c.item(0)).aggregate(c.item(0)).filter(
            R.Sum(c.this)
        ).gen_converter()
