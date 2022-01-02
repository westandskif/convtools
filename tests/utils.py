from reprlib import Repr


_repr = Repr()
_repr.maxdict = 1000
repr = _repr.repr
