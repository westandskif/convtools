from io import BytesIO, StringIO

import pytest

from convtools.contrib.fs import split_buffer, split_buffer_n_decode


def test_split_buffer():
    tests = [
        ["", "1", 10, [""]],
        ["1", "1", 10, ["", ""]],
        ["12345", "1", 10, ["", "2345"]],
        ["12345", "3", 10, ["12", "45"]],
        ["12345", "5", 10, ["1234", ""]],
        ["123453673", "3", 10, ["12", "45", "67", ""]],
        ["", "34", 10, [""]],
        ["34", "34", 10, ["", ""]],
        ["12345", "34", 10, ["12", "5"]],
        ["12345637348", "34", 4, ["12", "5637", "8"]],
        ["312345637348", "34", 4, ["312", "5637", "8"]],
        ["3312345637348", "34", 4, ["3312", "5637", "8"]],
        ["33312345637348", "34", 4, ["33312", "5637", "8"]],
        ["333312345637348", "34", 4, ["333312", "5637", "8"]],
        ["111111111", "111", 4, ["", "", "", ""]],
        ["010011000111000011100000", "111", 4, ["010011000", "0000", "00000"]],
        [
            "7010011000111000011100000",
            "111",
            4,
            ["7010011000", "0000", "00000"],
        ],
        [
            "77010011000111000011100000",
            "111",
            4,
            ["77010011000", "0000", "00000"],
        ],
        [
            "777010011000111000011100000",
            "111",
            4,
            ["777010011000", "0000", "00000"],
        ],
        [
            "7777010011000111000011100000",
            "111",
            4,
            ["7777010011000", "0000", "00000"],
        ],
        ["123abc456", "abc", 4, ["123", "456"]],
    ]
    for input_str, delimiter, chunk_size, result in tests:
        for chunk_size_ in (1, 2, 3, chunk_size):
            assert (
                list(split_buffer(StringIO(input_str), delimiter, chunk_size_))
                == result
            )
            assert list(
                split_buffer(
                    BytesIO(input_str.encode("utf-8")),
                    delimiter.encode("utf-8"),
                    chunk_size_,
                )
            ) == [s.encode("utf-8") for s in result]
            assert list(
                split_buffer_n_decode(
                    BytesIO(input_str.encode("utf-8")),
                    delimiter.encode("utf-8"),
                    chunk_size_,
                )
            ) == [s for s in result]


def test_split_buffer_leaves_caller_buffer_open():
    buf = StringIO("12345")
    list(split_buffer(buf, "3", 10))
    assert buf.closed is False

    buf = BytesIO(b"12345")
    list(split_buffer(buf, b"3", 10))
    assert buf.closed is False

    buf = BytesIO(b"12345")
    list(split_buffer_n_decode(buf, b"3", 10))
    assert buf.closed is False


def test_split_buffer_rejects_non_positive_chunk_size():
    buf = StringIO("abc")
    with pytest.raises(ValueError):
        split_buffer(buf, "a", 0)
    with pytest.raises(ValueError):
        split_buffer(buf, "a", -1)

    buf = BytesIO(b"abc")
    with pytest.raises(ValueError):
        split_buffer_n_decode(buf, b"a", 0)
    with pytest.raises(ValueError):
        split_buffer_n_decode(buf, b"a", -1)
