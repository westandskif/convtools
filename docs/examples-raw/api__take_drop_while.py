from itertools import count
from convtools import conversion as c

converter = c.take_while(c.this < 3).as_type(list).gen_converter(debug=True)
assert converter(count()) == [0, 1, 2]


converter = c.drop_while(c.this < 3).as_type(list).gen_converter(debug=True)
assert converter(range(5)) == [3, 4]
