from convtools import conversion as c

input_data = [{"StoreID": " 123", "Quantity": "123"}]

# define a conversion (sometimes you may want to do this dynamically)
#  takes iterable and returns iterable of dicts, stopping before the first
#  one with quantity >= 1000, splitting into chunks of size = 1000
conversion = (
    c.iter(
        {
            "id": c.item("StoreID").call_method("strip"),
            "quantity": c.item("Quantity").as_type(int),
        }
    )
    .take_while(c.item("quantity") < 1000)
    .pipe(c.chunk_by(c.item("id"), size=1000))
    .as_type(list)
)

# compile the conversion into an ad hoc function and run it
converter = conversion.gen_converter(debug=True)

# run it as any function
assert converter(input_data) == [[{"id": "123", "quantity": 123}]]

# OR in case of a one-shot use, skip the gen_converter part
conversion.execute(input_data)
