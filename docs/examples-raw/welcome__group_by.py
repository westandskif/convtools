from convtools import conversion as c

input_data = [
    {"a": 5, "b": "foo"},
    {"a": 10, "b": "foo"},
    {"a": 10, "b": "bar"},
    {"a": 10, "b": "bar"},
    {"a": 20, "b": "bar"},
]

conv = (
    c.group_by(c.item("b"))
    .aggregate(
        {
            "b": c.item("b"),
            "a_first": c.ReduceFuncs.First(c.item("a"), where=c.item("a") > 5),
            "a_max": c.ReduceFuncs.Max(c.item("a")),
        }
    )
    .gen_converter(debug=True)
)

assert conv(input_data) == [
    {"b": "foo", "a_first": 10, "a_max": 10},
    {"b": "bar", "a_first": 10, "a_max": 20},
]
