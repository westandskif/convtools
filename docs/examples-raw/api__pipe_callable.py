from datetime import datetime
from convtools import conversion as c

assert c.this.pipe(int).execute("123") == 123

converter = c.item("dt").pipe(datetime.strptime, "%m/%d/%Y").gen_converter()
assert converter({"dt": "12/25/2000"}) == datetime(2000, 12, 25)
