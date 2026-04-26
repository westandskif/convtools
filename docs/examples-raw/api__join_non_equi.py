from convtools import conversion as c


input_data = {
    "people": [
        {"name": "Nick", "age": 17},
        {"name": "Ann", "age": 22},
    ],
    "age_bands": [
        {"band": "junior", "min_age": 0, "max_age": 17},
        {"band": "adult", "min_age": 18, "max_age": 64},
    ],
}

conv = (
    c.join(
        c.item("people"),
        c.item("age_bands"),
        c.and_(
            c.LEFT.item("age") >= c.RIGHT.item("min_age"),
            c.LEFT.item("age") <= c.RIGHT.item("max_age"),
        ),
    )
    .pipe(
        c.list_comp(
            {
                "name": c.item(0, "name"),
                "age": c.item(0, "age"),
                "band": c.item(1, "band"),
            }
        )
    )
    .gen_converter()
)

assert conv(input_data) == [
    {"name": "Nick", "age": 17, "band": "junior"},
    {"name": "Ann", "age": 22, "band": "adult"},
]
