from convtools import conversion as c


class Obj:
    def __init__(self, a):
        self.a = a


class Container:
    def __init__(self, obj):
        self.obj = obj


assert c.attr("obj", "a").execute(Container(Obj(1))) == 1
assert c.attr("b", default=None).execute(Obj(1)) is None
