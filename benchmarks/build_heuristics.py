import os
import sys

from timer import SimpleTimer


def print_new_weights():  # pragma: no cover

    config = {
        "LOGICAL": SimpleTimer("x or y", "x=0; y=1"),
        "DICT_LOOKUP": SimpleTimer("d['abc']", "d = {'abc': 1}"),
        "MATH_SIMPLE": SimpleTimer("x / y", "x=1;y=2"),
        "ATTR_LOOKUP": SimpleTimer("A.b", "class A: b = 1"),
        "TUPLE_INIT": SimpleTimer("(x,2,3,4,5)", "x=1"),
        "LIST_INIT": SimpleTimer("[1,2,3,4,5]"),
        "SET_INIT": SimpleTimer("{1,2,3,4,5}"),
        "DICT_INIT": SimpleTimer("{'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5}"),
        "FUNCTION_CALL": SimpleTimer("f(v, 1)", "v=1\ndef f(v, x): return x"),
    }
    print("# WARMING UP")
    for i in range(2):
        SimpleTimer.get_base_time()

    print("# CALCULATING BASE TIME")
    base_time = SimpleTimer.get_base_time() / 100.0

    print(f"# {'.'.join(map(str, sys.version_info[:3]))}")
    print(
        "class Weights:  #type: ignore # pragma: no cover "
        "# pylint: disable=missing-class-docstring # noqa: F811"
    )
    print(f"    # base_time: {base_time}")
    print("    STEP = 100")

    max_it = 1
    for name, timer in config.items():
        iterations, time_taken = timer.auto_measure()
        it = int(time_taken / iterations / base_time)
        print(f"    {name} = {it}")
        max_it = max(max_it, it)

    print(f"    UNPREDICTABLE = {max_it * 100}")


if __name__ == "__main__":
    print_new_weights()  # pragma: no cover
