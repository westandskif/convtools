from convtools import conversion as c

converter = c.item(1).gen_converter(debug=True)

assert converter([10, 20]) == 20
