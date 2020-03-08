from collections import deque
from threading import local


class RUCache:
    def __init__(self, max_size, on_evict=None):
        self.max_size = max_size
        self._on_evict = on_evict
        if not (self._on_evict is None or callable(on_evict)):
            raise Exception("neither None nor callable")
        self._keys = deque()
        self._keys_to_be_put_back = set()
        self._data = {}

    def get(self, key, default=None):
        if key in self._data:
            self._keys_to_be_put_back.add(key)
            return self._data[key]
        return default

    def set(self, key, value):
        if key in self._data:
            self._data[key] = value
            self._keys_to_be_put_back.add(key)
        else:
            self._data[key] = value
            if len(self._keys) > self.max_size - 1:
                self._evict(self.max_size - 1)
            self._keys.appendleft(key)

    def has(self, key, bump_up=False):
        if key in self._data:
            if bump_up:
                self._keys_to_be_put_back.add(key)
            return True
        return False

    def _evict(self, expected_size):
        for i in range(self.max_size + 1):
            if len(self._keys) > expected_size:
                key = self._keys.pop()
                if key in self._keys_to_be_put_back:
                    self._keys.appendleft(key)
                    self._keys_to_be_put_back.remove(key)
                else:
                    value = self._data.pop(key)
                    if self._on_evict:
                        self._on_evict(key, value)
            else:
                break


class BaseCtxMeta(type):
    def __init__(cls, name, bases, kwargs):
        super(BaseCtxMeta, cls).__init__(name, bases, kwargs)
        cls._ctx = local()


class BaseOptionsMeta(type):
    def __init__(cls, name, bases, kwargs):
        super(BaseOptionsMeta, cls).__init__(name, bases, kwargs)
        cls._option_attrs = {
            k: v
            for k, v in kwargs.items()
            if not k.startswith("_") and k not in {"clone", "to_defaults"}
        }


class BaseOptions(object, metaclass=BaseOptionsMeta):
    def clone(self):
        clone = self.__class__()
        for option_attr in self._option_attrs.keys():
            setattr(clone, option_attr, getattr(self, option_attr))
        return clone

    def to_defaults(self, option_name=None):
        if option_name:
            setattr(self, option_name, self._option_attrs[option_name])
        else:
            for option_attr, value in self._option_attrs.items():
                setattr(self, option_attr, value)


class BaseCtx(object, metaclass=BaseCtxMeta):
    options_cls = None

    def __enter__(self) -> BaseOptions:
        self._ctx.prev_options = getattr(self._ctx, "options", None)
        if self._ctx.prev_options:
            self._ctx.options = self._ctx.prev_options.clone()
        else:
            self._ctx.options = self.options_cls()
        return self._ctx.options

    def __exit__(self, exc_type, exc_value, tb):
        self._ctx.options = self._ctx.prev_options
        self._ctx.prev_options = None

    @classmethod
    def get_option_value(cls, option_name):
        options = getattr(cls._ctx, "options", None)
        if not options:
            options = cls.options_cls
        return getattr(options, option_name)
