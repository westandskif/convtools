"""
This module is to contain helpers, which collect info about python code
execution
"""
import os
import sys
from time import sleep
from timeit import Timer


def print_new_weights(sleep_time=0.2):  # pragma: no cover

    config = {
        "LOGICAL": Timer("x or y", "x=0; y=1"),
        "DICT_LOOKUP": Timer("d['abc']", "d = {'abc': 1}"),
        "MATH_SIMPLE": Timer("x / y", "x=1;y=2"),
        "ATTR_LOOKUP": Timer("A.b", "class A: b = 1"),
        "TUPLE_INIT": Timer("(x,2,3,4,5)", "x=1"),
        "LIST_INIT": Timer("[1,2,3,4,5]"),
        "SET_INIT": Timer("{1,2,3,4,5}"),
        "DICT_INIT": Timer("{'a': 1, 'b': 2, 'c': 3, 'd': 4, 'e': 5}"),
        "FUNCTION_CALL": Timer("f(1,2,3)", "def f(x,y,z): return z"),
    }
    total_time = 0
    total_iterations = 0
    for _ in range(10):
        iterations, time_ = Timer("'abc'").autorange()
        total_time += time_
        total_iterations += iterations
        sleep(sleep_time)

    base_time = total_time / total_iterations / 100
    print(
        "class Weights:  #type: ignore # pragma: no cover # pylint: disable=missing-class-docstring"
    )
    print(f"    # base_time: {base_time}")
    print("    STEP = 100")

    max_it = 0
    for name, timer in config.items():
        total_time = 0
        total_iterations = 0
        for _ in range(3):
            iterations, time_ = timer.autorange()
            total_time += time_
            total_iterations += iterations
            sleep(sleep_time)
        it = int(total_time / total_iterations / base_time)
        print(f"    {name} = {it}")
        max_it = max(max_it, it)

    print(f"    UNPREDICTABLE = {max_it * 100}")


if os.environ.get("BUILD_HEURISTICS"):
    print_new_weights()
