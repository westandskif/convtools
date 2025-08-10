from convtools import conversion as c

with c.OptionsCtx() as opts:
    opts.debug = True
    c.item(1).gen_converter()
