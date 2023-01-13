from convtools import conversion as c

converter = (
    c.chunk_by(size=3)
    .aggregate(
        {
            "x": c.ReduceFuncs.First(c.this),
            "y": c.ReduceFuncs.Last(c.this),
            "z": c.ReduceFuncs.Sum(c.this),
        }
    )
    .as_type(list)
    .gen_converter(debug=True)
)
assert converter([0, 1, 2, 3, 4, 5, 6, 7]) == [
    {"x": 0, "y": 2, "z": 3},
    {"x": 3, "y": 5, "z": 12},
    {"x": 6, "y": 7, "z": 13},
]
