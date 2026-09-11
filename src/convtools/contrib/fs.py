"""File system helpers.

Python's native open() doesn't support custom newlines in the text mode and
doesn't support "newlines" (delimiters) in binary mode. The following methods
should close the gap. The caller owns and closes the buffer.
"""


def split_buffer(buffer, delimiter, chunk_size=32768):
    """Reads text or binary buffer and splits it by delimiter.

    Args:
      buffer: buffer to be read; the caller owns and closes it
      delimiter: delimiter to use for splitting
      chunk_size: chunk size to read at every iteration
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    return _iter_split_buffer(buffer, delimiter, chunk_size)


def _iter_split_pending(buffer, delimiter, chunk_size, chunk, leftover_box):
    overlap = len(delimiter) - 1
    empty = delimiter[:0]
    pending = [chunk]
    tail = chunk[-overlap:] if overlap > 0 else empty
    while True:
        new_chunk = buffer.read(chunk_size)
        search = new_chunk if overlap <= 0 else tail + new_chunk
        if search.find(delimiter) != -1:
            pending.append(new_chunk)
            chunks = empty.join(pending).split(delimiter)
            for i in range(len(chunks) - 1):
                yield chunks[i]
            leftover_box.append(chunks[-1])
            return
        pending.append(new_chunk)
        if overlap > 0:
            tail = (tail + new_chunk)[-overlap:]
        if not new_chunk:
            yield empty.join(pending)
            return


def _iter_split_buffer(buffer, delimiter, chunk_size):
    delimiter_length = len(delimiter)
    chunk = buffer.read(chunk_size)
    if not chunk:
        yield chunk
        return
    checked_length = 0
    while True:
        new_chunk = buffer.read(chunk_size)
        chunk = chunk + new_chunk

        if chunk.find(delimiter, checked_length) != -1:
            chunks = chunk.split(delimiter)
            for i in range(len(chunks) - 1):
                yield chunks[i]
            chunk = chunks[-1]
            del chunks
        elif new_chunk:
            leftover_box = []
            yield from _iter_split_pending(
                buffer, delimiter, chunk_size, chunk, leftover_box
            )
            if not leftover_box:
                return
            chunk = leftover_box[0]
            checked_length = 0
            continue

        chunk_length = len(chunk)
        checked_length = (
            (chunk_length - delimiter_length)
            if chunk_length > delimiter_length
            else 0
        )

        if not new_chunk:
            yield chunk
            break


def split_buffer_n_decode(
    buffer, delimiter, chunk_size=32768, encoding="utf-8"
):
    """Read binary buffer, yield decoded chunks, splitting by binary delimiter.

    Args:
      buffer: buffer to be read; the caller owns and closes it
      delimiter: delimiter to use for splitting
      chunk_size: chunk size to read at every iteration
      encoding: encoding to use when decoding a chunk
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    return _iter_split_buffer_n_decode(buffer, delimiter, chunk_size, encoding)


def _iter_split_buffer_n_decode(buffer, delimiter, chunk_size, encoding):
    delimiter_length = len(delimiter)
    chunk = buffer.read(chunk_size)
    if not chunk:
        yield chunk.decode(encoding)
        return
    checked_length = 0
    while True:
        new_chunk = buffer.read(chunk_size)
        chunk = chunk + new_chunk

        if chunk.find(delimiter, checked_length) != -1:
            chunks = chunk.split(delimiter)
            for i in range(len(chunks) - 1):
                yield chunks[i].decode(encoding)
            chunk = chunks[-1]
            del chunks
        elif new_chunk:
            leftover_box = []
            yield from (
                piece.decode(encoding)
                for piece in _iter_split_pending(
                    buffer, delimiter, chunk_size, chunk, leftover_box
                )
            )
            if not leftover_box:
                return
            chunk = leftover_box[0]
            checked_length = 0
            continue

        chunk_length = len(chunk)
        checked_length = (
            (chunk_length - delimiter_length)
            if chunk_length > delimiter_length
            else 0
        )

        if not new_chunk:
            yield chunk.decode(encoding)
            break
