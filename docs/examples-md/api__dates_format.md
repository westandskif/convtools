```python
from datetime import date, datetime
from convtools import conversion as c

# optimized
converter = c.format_dt("%m/%d/%Y %H:%M %p").gen_converter(debug=True)
assert converter(datetime(2023, 7, 27, 12, 13)) == "07/27/2023 12:13 PM"

# falls back to even faster standard isoformat()
converter = c.format_dt("%Y-%m-%d").gen_converter(debug=True)
assert converter(date(2020, 12, 31)) == "2020-12-31"

# falls back to standard strftime()
converter = c.format_dt("%c").gen_converter(debug=True)
assert converter(date(2020, 12, 31)) == "Thu Dec 31 00:00:00 2020"

```
