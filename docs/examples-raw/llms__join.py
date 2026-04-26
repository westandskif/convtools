from convtools import conversion as c


join_users = (
    c.join(
        c.item(0),
        c.item(1),
        c.LEFT.item("user_id") == c.RIGHT.item("id"),
    )
    .gen_converter()
)
rows = ([{"user_id": 1}], [{"id": 1, "name": "Ada"}])
assert list(join_users(rows)) == [
    ({"user_id": 1}, {"id": 1, "name": "Ada"})
]
