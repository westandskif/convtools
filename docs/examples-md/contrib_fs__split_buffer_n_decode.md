```python
import io
from convtools.contrib.fs import split_buffer_n_decode

buffer = io.BytesIO(b"a,b;;;1,2;;;3,4")
lines = list(
    split_buffer_n_decode(
        buffer, delimiter=b";;;", chunk_size=32768, encoding="utf-8"
    )
)
assert lines == ["a,b", "1,2", "3,4"]

```
