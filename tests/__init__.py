from types import GeneratorType

from convtools.base import (
    CodeGenerationOptionsCtx,
    _ConverterCallable,
    clean_line_cache,
)
from convtools.utils import RUCache

from .utils import total_size


class MemoryProfilingConverterCallable(_ConverterCallable):
    linecache_keys = RUCache(10, clean_line_cache)

    def __call__(self, *args, **kwargs):
        size_before = total_size(self.__dict__)
        result = super().__call__(*args, **kwargs)
        if isinstance(result, GeneratorType):
            return self.wrap_generator(result, size_before)

        size_after = total_size(self.__dict__)
        assert size_after <= size_before
        return result

    def wrap_generator(self, generator_, size_before):
        yield from generator_
        size_after = total_size(self.__dict__)
        assert size_after <= size_before


CodeGenerationOptionsCtx.options_cls.converter_callable_cls = (
    MemoryProfilingConverterCallable
)
