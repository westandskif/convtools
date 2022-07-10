# fmt: off
# START__PART_0
from decimal import Decimal
from typing import Dict, List, Tuple

from convtools.contrib.models import DictModel, build, cast, casters
from pydantic import BaseModel, StrictInt
# END__PART_0


# PART_01__1
class PydanticModel(BaseModel):
    age: StrictInt

PydanticModel.parse_obj({"age": 25.5})
# >>> ValidationError: 1 validation error for PydanticModel
# >>> age
# >>>   value is not a valid integer (type=type_error.integer)
# PART_01__1



# PART_01__2
class ConvtoolsModel(DictModel):
    age: int

obj, errors = build(ConvtoolsModel, {"age": 25.5})
# >>> In [9]: errors
# >>> Out[9]: {'age': {'__ERRORS': {'type': 'float instead of int'}}}
# PART_01__2




# PART_02__1
class PydanticModel(BaseModel):
    age: int

PydanticModel.parse_obj({"age": 25.5})
# >>> Out[4]: PydanticModel(age=25)
# PART_02__1




# PART_02__2
class ConvtoolsModel(DictModel):
    age: int = cast()

# this is safe as there's no data loss
obj, errors = build(ConvtoolsModel, {"age": 25.0})
# >>> In [83]: obj
# >>> Out[83]: ConvtoolsModel(age=25)

# this is not, hence we get an error
obj, errors = build(ConvtoolsModel, {"age": 25.5})
# >>> In [85]: errors
# >>> Out[85]: {'age': {'__ERRORS': {'int_caster': 'losing fractional part: 25.5; if desired, use casters.IntLossy'}}}

"""
Should you want to cast with data losses, use lossy casters:
"""
class ConvtoolsModel(DictModel):
    age: int = cast(casters.IntLossy())

obj, errors = build(ConvtoolsModel, {"age": 25.5})
# >>> In [88]: obj
# >>> Out[88]: ConvtoolsModel(age=25)
# PART_02__2




# PART_03__1
class PydanticModel(BaseModel):
    age: Decimal


PydanticModel.parse_obj({"age": 0.1 + 0.1 + 0.1})
# >>> Out[65]: PydanticModel(age=Decimal('0.30000000000000004'))
# PART_03__1


# PART_03__2
class ConvtoolsModel(DictModel):
    age: Decimal = cast()

obj, errors = build(ConvtoolsModel, {"age": 0.1 + 0.1 + 0.1})
# >>> In [58]: errors
# >>> Out[58]: {'age': {'__ERRORS': {'decimal_caster': 'imprecise init from float: 0.30000000000000004; if desired, use casters.DecimalLossy'}}}

"""
Should you want to cast with data losses, use lossy casters:
"""

class ConvtoolsModel(DictModel):
    age: Decimal = cast(casters.DecimalLossy())

obj, errors = build(ConvtoolsModel, {"age": 0.1 + 0.1 + 0.1})
# >>> In [70]: obj
# >>> Out[70]: ConvtoolsModel(age=Decimal('0.3000000000000000444089209850062616169452667236328125'))
# PART_03__2

# PART_04
"""
# tested on python 3.9.7
# $ pytest --benchmark-min-time=0.05 -k bench

Under the hood convtools generate python code the first time you run it, e.g.
build/build_or_raise. So its first runs are:
 - 1.8x slower
 - consume 1.6x more RAM (to store converters, not for data processing).

But once the required validator/converter is generated, it is cached in LRU
cache and then it is fast:

- strict validation:                                   33.5x
- type casting when data matches expected types:        7.8x
- type casting when each field requires type casting:   4.1x

see below for details:

-------------------------------------------------------------------------------------------------- benchmark: 6 tests --------------------------------------------------------------------------------------------------
Name (time in us)                                    Min                 Max                Mean            StdDev              Median               IQR            Outliers  OPS (Kops/s)            Rounds  Iterations
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
test_model__benchmark_1_validation               10.3651 (1.0)       10.6473 (1.0)       10.4112 (1.0)      0.0839 (1.38)      10.3840 (1.0)      0.0168 (1.0)           1;1       96.0502 (1.0)          10       10000
test_model__benchmark_1_pydantic_validation     347.4766 (33.52)    350.0541 (32.88)    348.1051 (33.44)    0.5562 (9.18)     348.0870 (33.52)    0.4755 (28.26)         4;1        2.8727 (0.03)         20         144

test_model__benchmark_1_casting                  28.4511 (2.74)      28.6624 (2.69)      28.5209 (2.74)     0.0606 (1.0)       28.5160 (2.75)     0.0769 (4.57)          5;1       35.0621 (0.37)         20        1758
test_model__benchmark_1_pydantic_casting        221.5129 (21.37)    222.6293 (20.91)    222.0416 (21.33)    0.4748 (7.84)     221.8825 (21.37)    0.8057 (47.89)         2;0        4.5037 (0.05)          5        1000

test_model__benchmark_2_casting                  59.4243 (5.73)      61.9716 (5.82)      59.9632 (5.76)     0.7784 (12.85)     59.7646 (5.76)     0.4548 (27.03)         2;2       16.6769 (0.17)         17        1000
test_model__benchmark_2_pydantic_casting        244.2930 (23.57)    246.0899 (23.11)    245.2601 (23.56)    0.7054 (11.64)    245.2778 (23.62)    1.0846 (64.46)         2;0        4.0773 (0.04)          5        1000
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
"""
# PART_04

"""
##################
4. ERRORS FORMAT #
##################
convtools model error format is designed to allow for automated processing.
Error dicts have reserved keys:
 - "__ERRORS" - dict with errors is behind this key
 - "__KEYS" - dict where keys are keys from data and values are error dicts of key
   validation
 - "__VALUES" - dict where keys are keys from data and values are error dicts
   of dict value validation
 - "__SET_ITEMS" - dict where keys are set items and values are error dicts of
   set item validation
"""


# PART_05__1
class PydanticModel(BaseModel):
    objects: Dict[int, int]

PydanticModel.parse_obj({"objects": {1: 2, "2.5": 3}})
# ValidationError: 1 validation error for PydanticModel
# objects -> __key__
#   value is not a valid integer (type=type_error.integer)
# PART_05__1


# PART_05__2
class ConvtoolsModel(DictModel):
    objects: Dict[int, int]

obj, errors = build(ConvtoolsModel, {"objects": {1: "2", "2.5": 3}})
# >>> In [104]: errors
# >>> Out[104]:
# >>> {'objects': {'__VALUES': {1: {'__ERRORS': {'type': 'str instead of int'}}},
# >>>   '__KEYS': {'2.5': {'__ERRORS': {'type': 'str instead of int'}}}}}
# PART_05__2
