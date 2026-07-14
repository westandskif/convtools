from convtools import conversion as c

conversion = c.this + 1
converter = conversion.gen_converter()

assert converter(1) == 2
