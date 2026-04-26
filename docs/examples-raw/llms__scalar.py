from convtools import conversion as c


get_total = (c.item("price") * c.item("qty")).gen_converter()
assert get_total({"price": 5, "qty": 3}) == 15
