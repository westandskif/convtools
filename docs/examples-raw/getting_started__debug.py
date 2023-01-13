from convtools import conversion as c

c.item(1).gen_converter(debug=True)

with c.OptionsCtx() as options:
    options.debug = True
    c.item(1).gen_converter()
