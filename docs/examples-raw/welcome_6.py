from convtools import conversion as c

with c.OptionsCtx() as options:
    options.debug = True
    converter = c.list_comp(
        {"id": c.item("id"), "total": c.item("qty") * c.item("price")}
    ).gen_converter()
