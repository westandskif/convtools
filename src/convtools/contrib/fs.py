"""
Python's native open() doesn't support custom newlines in the text mode and
doesn't support "newlines" (delimiters) in binary mode. The following methods
should close the gap.
"""


def split_buffer(buffer, delimiter, chunk_size=32768):
    """Reads text or binary buffer and splits it by delimiter.

    Args:
      buffer: buffer to be read
      delimiter: delimiter to use for splitting
      chunk_size: chunk size to read at every iteration
    """
    delimiter_length = len(delimiter)
    with buffer:
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
    """Reads binary buffer, splits it by binary delimiter and yields decoded
    chunks.

    Args:
      buffer: buffer to be read
      delimiter: delimiter to use for splitting
      chunk_size: chunk size to read at every iteration
      encoding: encoding to use when decoding a chunk
    """
    delimiter_length = len(delimiter)
    with buffer:
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

            chunk_length = len(chunk)
            checked_length = (
                (chunk_length - delimiter_length)
                if chunk_length > delimiter_length
                else 0
            )

            if not new_chunk:
                yield chunk.decode(encoding)
                break
