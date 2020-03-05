from threading import local


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
