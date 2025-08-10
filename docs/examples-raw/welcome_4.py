from convtools import conversion as c

left = [
    {"id": 1, "name": "Nick"},
    {"id": 2, "name": "Joash"},
    {"id": 3, "name": "Bob"},
]
right = [
    {"ID": "3", "age": 17, "country": "GB"},
    {"ID": "2", "age": 21, "country": "US"},
    {"ID": "1", "age": 18, "country": "CA"},
]

join_and_shape = (
    c.join(
        c.naive(left),
        c.naive(right),
        c.and_(
            c.LEFT.item("id") == c.RIGHT.item("ID").as_type(int),
            c.RIGHT.item("age") >= 18,
        ),
        how="left",
    )
    .pipe(
        c.list_comp(
            {
                "id": c.item(0, "id"),
                "name": c.item(0, "name"),
                "age": c.item(1, "age", default=None),
                "country": c.item(1, "country", default=None),
            }
        )
    )
    .gen_converter()
)

assert join_and_shape(None) == [
    {"id": 1, "name": "Nick", "age": 18, "country": "CA"},
    {"id": 2, "name": "Joash", "age": 21, "country": "US"},
    {"id": 3, "name": "Bob", "age": None, "country": None},
]
