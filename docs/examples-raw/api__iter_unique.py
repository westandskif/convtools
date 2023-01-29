from convtools import conversion as c

# SIMPLE UNIQUE
converter = c.iter_unique().as_type(list).gen_converter(debug=True)
assert converter([0, 0, 0, 1, 1, 2]) == [0, 1, 2]

# UNIQUE BY MODULO OF 3
converter = (
    c.iter_unique(by_=c.this % 3).as_type(list).gen_converter(debug=True)
)
assert converter(range(10)) == [0, 1, 2]

# UNIQUE BY ID, YIELD NAMES
converter = (
    c.item("data")
    .iter_unique(c.item("name"), by_=c.item("id"))
    .as_type(list)
    .gen_converter(debug=True)
)
assert converter(
    {
        "data": [
            {"name": "foo", "id": 1},
            {"name": "foo", "id": 1},
            {"name": "bar", "id": 1},
            {"name": "def", "id": 2},
        ]
    }
) == ["foo", "def"]
