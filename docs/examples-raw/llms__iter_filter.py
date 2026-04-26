from convtools import conversion as c


normalize = (
    c.iter({"name": c.item("name"), "age": c.item("age").as_type(int)})
    .filter(c.item("age") >= 18)
    .as_type(list)
    .gen_converter()
)
assert normalize([{"name": "Ada", "age": "36"}]) == [
    {"name": "Ada", "age": 36}
]
