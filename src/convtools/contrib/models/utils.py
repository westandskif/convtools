"""Defines methods which should close the gap in typing functionality between
python 3.6 and 3.7+ """
# flake8: noqa
import sys


PY_VERSION = sys.version_info[0:2]

if PY_VERSION <= (3, 6):

    from typing import Dict, List, Union

    GenericAlias = type(List[int])
    UnionCls = Union.__class__

    def is_generic_alias(obj):
        return isinstance(obj, GenericAlias) or is_generic_union_alias(obj)

    def is_generic_union_alias(obj):
        return obj.__class__ is UnionCls

    def is_generic_list_alias(alias):
        return alias.__origin__ is List

    def is_generic_dict_alias(alias):
        return alias.__origin__ is Dict

else:  # if PY_VERSION > (3, 6): -- comment for .coveragerc
    from typing import Dict, List, Union, _GenericAlias  # type: ignore

    def is_generic_alias(obj):
        return isinstance(obj, _GenericAlias)

    def is_generic_union_alias(obj):
        return obj.__origin__ is Union

    def is_generic_list_alias(alias):
        return alias.__origin__ is list

    def is_generic_dict_alias(alias):
        return alias.__origin__ is dict


def ensure_generic_alias_has_args(alias, type_var_to_type_value):
    if is_generic_alias(alias):
        if alias.__parameters__:
            return type(alias).__getitem__(
                alias,
                *tuple(
                    type_var_to_type_value[p] for p in alias.__parameters__
                ),
            )
    return alias
