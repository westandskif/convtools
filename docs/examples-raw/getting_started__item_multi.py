from convtools import conversion as c

converter = c.item(1, "value").gen_converter()

assert converter([{"value": 10}, {"value": 20}]) == 20
