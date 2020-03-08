import pytest

from convtools.base import CodeGenerationOptions, CodeGenerationOptionsCtx
from convtools.utils import RUCache


def test_code_generation_ctx():
    with CodeGenerationOptionsCtx() as options:
        assert isinstance(options, CodeGenerationOptions)

        assert options.labeling is False
        assert CodeGenerationOptionsCtx.get_option_value("labeling") is False

        options.labeling = True
        assert CodeGenerationOptionsCtx.get_option_value("labeling") is True

        with CodeGenerationOptionsCtx() as options2:
            assert options2.labeling is True
            assert (
                CodeGenerationOptionsCtx.get_option_value("labeling") is True
            )

            options2.to_defaults("labeling")
            assert options2.labeling is False

            options2.labeling = True
            options2.to_defaults()
            assert options2.labeling is False
            assert (
                CodeGenerationOptionsCtx.get_option_value("labeling") is False
            )

            assert options.labeling is True

        assert CodeGenerationOptionsCtx.get_option_value("labeling") is True

    assert CodeGenerationOptionsCtx.get_option_value("labeling") is False


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
