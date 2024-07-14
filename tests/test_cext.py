import pytest

from convtools import conversion as c
from convtools._base import (
    get_attr_deep_default_callable,
    get_attr_deep_default_simple,
    get_item_deep_default_callable,
    get_item_deep_default_simple,
)


class Obj:
    def __init__(self, attr, value):
        setattr(self, attr, value)


if get_attr_deep_default_simple:

    def test_cext_get_item():
        d = {1: {}}
        d2 = {1: {"2": {}}}
        assert get_item_deep_default_simple(d, 1, 7) is d[1]
        assert get_item_deep_default_simple(d, 2, 7) == 7

        assert get_item_deep_default_callable(d, 1, int) is d[1]
        assert get_item_deep_default_callable(d, 2, int) == 0

        assert get_item_deep_default_simple(d2, 1, "2", 7) is d2[1]["2"]
        assert get_item_deep_default_simple(d2, 1, "3", 7) == 7

        f = lambda: -1
        assert get_item_deep_default_callable(d2, 1, "2", f) is d2[1]["2"]
        assert get_item_deep_default_callable(d2, 1, "3", f) == -1

        # from benchmarks.timer import SimpleTimer

        # for data_ in (d2, d):
        #     conv = c.item(1, "2", default=7)
        #     conv.hardcoded_version = None
        #     iterations, time_taken = SimpleTimer(
        #         "f(data_)", globals={"f": conv.gen_converter(), "data_": data_}
        #     ).auto_measure()
        #     baseline_time = time_taken / iterations
        #     print(f" raw get_item: {baseline_time:e}")

        #     iterations, time_taken = SimpleTimer(
        #         "f(data_)",
        #         globals={
        #             "f": c.item(1, "2", default=7).gen_converter(),
        #             "data_": data_,
        #         },
        #     ).auto_measure()
        #     cext_time = time_taken / iterations
        #     print(f"CEXT get_item: {cext_time:e}")
        #     print(f"     SPEED-UP: {(baseline_time / cext_time):f}")

    def test_cext_get_attr():
        a_b = Obj("a", Obj("b", 1))
        a_x = Obj("a", Obj("x", 1))
        x_x = Obj("x", Obj("x", 1))

        assert get_attr_deep_default_simple(a_b, "a", "b", 7) == 1
        assert get_attr_deep_default_simple(a_x, "a", "b", 7) == 7
        assert get_attr_deep_default_simple(x_x, "a", "b", 7) == 7

        assert get_attr_deep_default_callable(a_b, "a", "b", int) == 1
        assert get_attr_deep_default_callable(a_x, "a", "b", int) == 0
        assert get_attr_deep_default_callable(x_x, "a", "b", int) == 0
