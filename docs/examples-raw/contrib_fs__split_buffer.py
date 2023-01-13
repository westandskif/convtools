import io
from convtools.contrib.fs import split_buffer
from convtools.contrib.tables import Table

buffer = io.StringIO("a,b;;;1,2;;;3,4")
lines_generator = split_buffer(buffer, delimiter=";;;", chunk_size=32768)

# e.g. convenient for
assert list(
    Table.from_csv(lines_generator, header=True).into_iter_rows(dict)
) == [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}]
