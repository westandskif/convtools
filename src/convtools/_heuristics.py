"""Helpers to collect info about environment."""

import sys


# generated by "python benchmarks/build_heuristics.py"

PY_VERSION = sys.version_info[0:2]
if PY_VERSION <= (3, 6):
    # 3.6.15
    class Weights:  # type: ignore # pragma: no cover # pylint: disable=missing-class-docstring # noqa: F811
        # base_time: 9.4819895579955e-11
        STEP = 100
        LOGICAL = 106
        DICT_LOOKUP = 138
        MATH_SIMPLE = 160
        ATTR_LOOKUP = 146
        TUPLE_INIT = 230
        LIST_INIT = 288
        SET_INIT = 729
        DICT_INIT = 713
        FUNCTION_CALL = 396
        UNPREDICTABLE = 72900

elif PY_VERSION <= (3, 7):  # pragma: no cover
    # 3.7.16
    class Weights:  # type: ignore # pragma: no cover # pylint: disable=missing-class-docstring # noqa: F811
        # base_time: 9.374689258333346e-11
        STEP = 100
        LOGICAL = 102
        DICT_LOOKUP = 147
        MATH_SIMPLE = 159
        ATTR_LOOKUP = 139
        TUPLE_INIT = 229
        LIST_INIT = 285
        SET_INIT = 714
        DICT_INIT = 778
        FUNCTION_CALL = 355
        UNPREDICTABLE = 77800

elif PY_VERSION == (3, 8):  # pragma: no cover
    # 3.8.16
    class Weights:  # type: ignore # pragma: no cover # pylint: disable=missing-class-docstring # noqa: F811
        # base_time: 9.947647891666672e-11
        STEP = 100
        LOGICAL = 94
        DICT_LOOKUP = 132
        MATH_SIMPLE = 153
        ATTR_LOOKUP = 129
        TUPLE_INIT = 228
        LIST_INIT = 281
        SET_INIT = 679
        DICT_INIT = 725
        FUNCTION_CALL = 355
        UNPREDICTABLE = 72500

elif PY_VERSION == (3, 9):  # pragma: no cover
    # 3.9.12
    class Weights:  # type: ignore # pragma: no cover # pylint: disable=missing-class-docstring # noqa: F811
        # base_time: 9.950430541666667e-11
        STEP = 100
        LOGICAL = 97
        DICT_LOOKUP = 139
        MATH_SIMPLE = 165
        ATTR_LOOKUP = 132
        TUPLE_INIT = 246
        LIST_INIT = 310
        SET_INIT = 573
        DICT_INIT = 742
        FUNCTION_CALL = 358
        UNPREDICTABLE = 74200

elif PY_VERSION == (3, 10):  # pragma: no cover
    # 3.10.9
    class Weights:  # type: ignore # pragma: no cover # pylint: disable=missing-class-docstring # noqa: F811
        # base_time: 9.785650500089106e-11
        STEP = 100
        LOGICAL = 86
        DICT_LOOKUP = 129
        MATH_SIMPLE = 154
        ATTR_LOOKUP = 126
        TUPLE_INIT = 238
        LIST_INIT = 283
        SET_INIT = 602
        DICT_INIT = 800
        FUNCTION_CALL = 461
        UNPREDICTABLE = 80000

elif PY_VERSION == (3, 11):  # pragma: no cover
    # 3.11.1
    class Weights:  # type: ignore # pragma: no cover # pylint: disable=missing-class-docstring # noqa: F811
        # base_time: 9.514307286917756e-11
        STEP = 100
        LOGICAL = 80
        DICT_LOOKUP = 140
        MATH_SIMPLE = 153
        ATTR_LOOKUP = 128
        TUPLE_INIT = 239
        LIST_INIT = 293
        SET_INIT = 623
        DICT_INIT = 888
        FUNCTION_CALL = 247
        UNPREDICTABLE = 88800

elif PY_VERSION == (3, 12):  # pragma: no cover
    # 3.12.1
    class Weights:  # type: ignore # pragma: no cover # pylint: disable=missing-class-docstring # noqa: F811
        # base_time: 1.1845866186558851e-10
        STEP = 100
        LOGICAL = 76
        DICT_LOOKUP = 108
        MATH_SIMPLE = 146
        ATTR_LOOKUP = 50
        TUPLE_INIT = 198
        LIST_INIT = 262
        SET_INIT = 554
        DICT_INIT = 852
        FUNCTION_CALL = 186
        UNPREDICTABLE = 85200

else:  # pragma: no cover
    # 3.13.0
    class Weights:  # type: ignore # pragma: no cover # pylint: disable=missing-class-docstring # noqa: F811
        # base_time: 1.064610156154231e-10
        STEP = 100
        LOGICAL = 90
        DICT_LOOKUP = 122
        MATH_SIMPLE = 143
        ATTR_LOOKUP = 52
        TUPLE_INIT = 195
        LIST_INIT = 263
        SET_INIT = 602
        DICT_INIT = 993
        FUNCTION_CALL = 169
        UNPREDICTABLE = 99300
