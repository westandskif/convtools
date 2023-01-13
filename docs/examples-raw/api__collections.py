from convtools import conversion as c

converter = c(
    {
        "a": c.item(0),
        "b": c.item(1),
        "c": c.item(0) + c.item(1),
        # keys are dynamic too
        c.call_func("d{}".format, c.item(0)): "key is dynamic",
    }
).gen_converter(debug=True)

assert converter((1, 2)) == {"a": 1, "b": 2, "c": 3, "d1": "key is dynamic"}


assert c([1, c.this, 2]).execute(None, debug=True) == [1, None, 2]
