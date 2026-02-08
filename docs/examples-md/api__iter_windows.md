```python
from convtools import conversion as c

converter = c.iter_windows(3, step=1).as_type(list).gen_converter(debug=True)

assert converter(range(5)) == [
    (0,),
    (0, 1),
    (0, 1, 2),
    (1, 2, 3),
    (2, 3, 4),
    (3, 4),
    (4,),
]

```
