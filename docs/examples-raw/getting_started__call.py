from datetime import datetime
from convtools import conversion as c

# Option 1
converter = c.call_func(datetime.strptime, c.this, "%m/%d/%Y").gen_converter(
    debug=True
)

assert converter("12/31/2000") == datetime(2000, 12, 31)

# Option 2
converter = (
    c.naive(datetime)
    .call_method("strptime", c.this, "%m/%d/%Y")
    .gen_converter(debug=True)
)

assert converter("12/31/2000") == datetime(2000, 12, 31)

# Option 3
assert (
    c.naive(datetime.strptime)
    .call(c.this, "%m/%d/%Y")
    .execute("12/31/2000", debug=True)
) == datetime(2000, 12, 31)
