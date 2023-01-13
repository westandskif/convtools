# Contrib / Fs

## `split_buffer`

Python's `open` function doesn't support custom newlines in the text mode and
doesn't support "newlines" (delimiters) in binary mode, so it is convenient to
have `split_buffer` helper for this:

{!examples-md/contrib_fs__split_buffer.md!}

## `split_buffer_n_decode`

There's also a sibling method, which works with bytes and runs decode on each
element - `split_buffer_n_decode`:

{!examples-md/contrib_fs__split_buffer_n_decode.md!}

