import pytest

from convtools.base import (
    BaseConversion,
    CodeGenerationOptions,
    CodeGenerationOptionsCtx,
)
from convtools.utils import RUCache


def test_code_generation_ctx():
    with CodeGenerationOptionsCtx() as options:
        assert isinstance(options, CodeGenerationOptions)

        assert options.inline_pipes_only is False
        assert (
            CodeGenerationOptionsCtx.get_option_value("inline_pipes_only")
            is False
        )

        options.inline_pipes_only = True
        assert (
            CodeGenerationOptionsCtx.get_option_value("inline_pipes_only")
            is True
        )

        with CodeGenerationOptionsCtx() as options2:
            assert options2.inline_pipes_only is True
            assert (
                CodeGenerationOptionsCtx.get_option_value("inline_pipes_only")
                is True
            )

            options2.to_defaults("inline_pipes_only")
            assert options2.inline_pipes_only is False

            options2.inline_pipes_only = True
            options2.to_defaults()
            assert options2.inline_pipes_only is False
            assert (
                CodeGenerationOptionsCtx.get_option_value("inline_pipes_only")
                is False
            )

            assert options.inline_pipes_only is True

        assert (
            CodeGenerationOptionsCtx.get_option_value("inline_pipes_only")
            is True
        )

    assert (
        CodeGenerationOptionsCtx.get_option_value("inline_pipes_only") is False
    )


def test_ru_cache():
    pairs = []

    def on_evict(key, value):
        try:
            pairs.pop()
        except IndexError:
            pass
        pairs.append((key, value))

    cache = RUCache(3, on_evict)

    cache.set(1, 1)
    cache.set(2, 2)
    cache.set(3, 3)
    assert pairs == []
    cache.set(4, 4)
    assert pairs == [(1, 1)]
    cache.set(5, 5)
    assert pairs == [(2, 2)]
    cache.set(6, 6)
    assert pairs == [(3, 3)]

    assert cache.get(4) == 4 and cache.get(10, default=-1) == -1
    cache.set(7, 7)
    assert pairs == [(5, 5)]
    cache.set(8, 8)
    assert pairs == [(6, 6)]
    cache.set(9, 9)
    assert pairs == [(4, 4)]
    cache.set(10, 10)
    assert pairs == [(7, 7)]

    with pytest.raises(Exception):
        RUCache(1, False)

    cache = RUCache(3)
    for i in range(10):
        cache.set(i, i)
    assert cache.has(7) and cache.has(8) and cache.has(9)
    cache.set(10, 10)
    assert not cache.has(7)
    assert cache.has(8, bump_up=True)
    cache.set(11, 11)
    assert cache.has(8) and cache.has(11) and not cache.has(9)
    cache.set(10, 100)
    cache.set(12, 12)
    assert (
        cache.has(12) and cache.has(10) and cache.has(11) and not cache.has(8)
    )

    cache = RUCache(3)
    for i in range(3):
        cache.set(i, i)
        cache.has(i, bump_up=True)
    cache.set(3, 3)
    assert cache.has(3)


def test_replace_word():
    cases = [
        ("abc", "abc", "cde", "cde"),
        ("aabc", "abc", "cde", "aabc"),
        ("abcc", "abc", "cde", "abcc"),
        ("aabcc", "abc", "cde", "aabcc"),
        ("aabc 1", "abc", "cde", "aabc 1"),
        ("1 abcc", "abc", "cde", "1 abcc"),
        ("abc 1", "abc", "cde", "cde 1"),
        ("1 abc", "abc", "cde", "1 cde"),
        ("1 abccabc _abc abc 2", "abc", "cde", "1 abccabc _abc cde 2"),
        (" aabc ", "abc", "cde", " aabc "),
        (" abcc ", "abc", "cde", " abcc "),
        (" abc ", "abc", "cde", " cde "),
        (" abc abc abc abc  ", "abc", "cde", " cde cde cde cde  "),
    ]
    for (where, word, with_what, expected_result) in cases:
        result = BaseConversion.replace_word(where, word, with_what)
        assert result == expected_result


def test_count_words():
    cases = [(" abc abc abc abc abcc aabc aabcc abc", "abc", 5)]

    for (where, what, expected_result) in cases:
        result = BaseConversion.count_words(where, what)
        assert result == expected_result
