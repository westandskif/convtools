from convtools import conversion as c


input_data = [
    {"version": "v1", "field1": 10},
    {"version": "v2", "field2": 20},
    {"version": "v3", "field": 30},
]

converter = (
    c.iter(
        c.this.dispatch(
            c.item("version"),
            {
                "v1": c.item("field1"),
                "v2": c.item("field2"),
            },
            default=c.item("field"),
        )
    )
    .as_type(list)
    .gen_converter(debug=True)
)

assert converter(input_data) == [10, 20, 30]
