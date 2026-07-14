from convtools import conversion as c

converter = (c.this + c.input_arg("increment")).gen_converter()

assert converter(10, increment=5) == 15
