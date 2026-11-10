from convtools import conversion as c

# 1. Per-converter debug flag
c.item("orders").pipe(
    c.list_comp({"id": c.item("id"), "total": c.item("qty") * c.item("price")})
).gen_converter(debug=True)

# 2. Scoped debug context
with c.OptionsCtx() as options:
    options.debug = True
    c.item(1).gen_converter()
