```python
from datetime import date, datetime
from convtools import conversion as c

# SIMPLE DEFAULT
converter = c.date_parse("%m/%d/%Y", default=None).gen_converter(debug=True)
assert converter("some str") is None

# DEFAULT AS CONVERSION
converter = c.date_parse(
    "%m/%d/%Y", default=c.call_func(date.today)
).gen_converter(debug=True)
assert converter("some str") == date.today()

```
