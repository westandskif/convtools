"""
Defines type handlers which generate the code which checks types and populates
errors.
"""
import inspect
import sys
from typing import (  # type: ignore
    TYPE_CHECKING,
    Any,
    TypeVar,
    _eval_type,
    get_type_hints,
)

from convtools import conversion as c
from convtools.utils import Code

from .base import (
    BaseModel,
    DictModel,
    ProxyObject,
    TypeValueCodeGenArgs,
    _none,
)
from .casters.casters import BaseCaster, CasterToFinalType
from .field import FieldProcessingPipeline, ensure_caster, field
from .utils import (
    ensure_generic_alias_has_args,
    is_generic_alias,
    is_generic_dict_alias,
    is_generic_list_alias,
    is_generic_union_alias,
)
from .validators.validators import BaseValidator
from .validators.validators import Type as TypeValidator


if TYPE_CHECKING:
    from convtools.base import BaseConversion  # pragma: no cover


def prepare_model_type(model, type_var_to_type_value):
    if type_var_to_type_value:
        model = ensure_generic_alias_has_args(model, type_var_to_type_value)

    if hasattr(model, "__parameters__") and model.__parameters__:
        raise ValueError(
            f"initialize typevars like {model.__name__}[str]",
            model.__parameters__,
        )
    globals_ = sys.modules[model.__module__].__dict__
    locals_ = locals()
    resolved_model = _eval_type(model, globals_, locals_)
    if hasattr(resolved_model, "__origin__"):
        original_model = resolved_model.__origin__
        type_var_to_type_value.update(
            dict(zip(model.__origin__.__parameters__, model.__args__))
        )
    else:
        original_model = resolved_model

    type_hints = get_type_hints(original_model, globals_, locals_)
    return (
        resolved_model,
        original_model,
        type_hints,
        type_var_to_type_value,
    )


def to_dict(data):
    if isinstance(data, BaseModel):
        return data.to_dict()
    if isinstance(data, list):
        return [to_dict(item) for item in data]
    if isinstance(data, dict):
        return {to_dict(key): to_dict(value) for key, value in data.items()}
    return data


def gen_model_cls_code(
    base_conversion,
    original_model,
    code_suffix,
    names,
    field_names_with_mutation,
    ctx,
):
    ctx["to_dict__"] = to_dict

    model_name = f"{original_model.__name__}{code_suffix}"
    base_model_name = f"_{original_model.__name__}{code_suffix}"
    ctx[base_model_name] = original_model

    names = tuple(names)
    code = Code()
    code.add_line(f"class {model_name}({base_model_name}):", 1)
    code.add_line(f"__slots__ = ({', '.join(map(repr, names))},)", 0)
    code.add_line(f"def __init__(self, {', '.join(names)}):", 1)
    for name in names:
        code.add_line(f"self.{name} = {name}", 0)
    code.indent_level -= 1
    code.add_line("def __repr__(self):", 1)

    names_code = ", ".join(f"{name}={{repr(self.{name})}}" for name in names)
    code.add_line(f"return f'{model_name}({names_code})'", -1)

    code.add_line("def to_dict(self):", 1)
    dict_code = c(
        {
            name: (
                c.escaped_string("to_dict__").call(
                    c.escaped_string("self").attr(name)
                )
                if name in field_names_with_mutation
                else c.escaped_string("self").attr(name)
            )
            for name in names
        }
    ).gen_code_and_update_ctx("not needed", ctx)
    code.add_line(f"return {dict_code}", -1)

    base_conversion.compile_converter(model_name, code.to_string(0), ctx)
    return model_name


chunk_pipeline_steps = c.chunk_by(c.attr("STEP_TYPE")).gen_converter()


class ModelMeta:
    __slots__ = ("converter_name", "number_of_usages")

    def __init__(self, converter_name):
        self.converter_name = converter_name
        self.number_of_usages = 1


def model_type_to_code(outer_args: TypeValueCodeGenArgs):
    (
        resolved_model,
        original_model,
        type_hints,
        type_var_to_type_value,
    ) = prepare_model_type(
        outer_args.type_value, outer_args.type_var_to_type_value
    )

    meta_cls = getattr(original_model, "Meta", None)
    private_fields = (
        getattr(meta_cls, "private_fields", None)
        if isinstance(meta_cls, type)
        else None
    ) or ()

    if outer_args.type_value in outer_args.type_to_model_meta:
        model_meta = outer_args.type_to_model_meta[outer_args.type_value]
        model_meta.number_of_usages += 1
    else:
        model_meta = ModelMeta(
            outer_args.base_conversion.gen_name(
                f"try_to_create_{original_model.__name__}",
                outer_args.ctx,
                outer_args.type_value,
            )
        )

    function_ctx = outer_args.base_conversion.as_function_ctx(outer_args.ctx)
    function_ctx.add_arg("name_", c.escaped_string(outer_args.name_code))
    function_ctx.add_arg("data_", c.escaped_string(outer_args.data_code))

    if outer_args.level > 0:
        model_errors_code = f"errors{outer_args.level}"
        function_ctx.add_arg("errors_", c.escaped_string(model_errors_code))
    else:
        function_ctx.add_arg(
            "errors_", c.escaped_string(outer_args.errors_code)
        )

    process_model_code = function_ctx.call_with_all_args(
        c.escaped_string(model_meta.converter_name)
    ).gen_code_and_update_ctx("not needed", outer_args.ctx)

    args = None
    if outer_args.type_value not in outer_args.type_to_model_meta:
        model_code = Code()
        args = outer_args._replace(
            code=model_code,
            name_code="name_",
            data_code="data_",
            errors_code="errors_",
            level=outer_args.level + 1,
        )
        args.type_to_model_meta[args.type_value] = model_meta

        is_dict_model = issubclass(original_model, DictModel)

        with function_ctx:
            model_code.add_line(
                f"def {model_meta.converter_name}({function_ctx.get_def_all_args_code()}):",
                1,
            )

            for method_name in ("prepare", "prepare__"):
                method = getattr(original_model, method_name, None)
                if method and callable(method):
                    if not inspect.ismethod(method):
                        raise AssertionError(
                            f"{original_model.__name__}.{method} should be a classmethod"
                        )
                    break
                method = None

            if method:
                method_code = args.base_conversion.gen_name(
                    method_name, args.ctx, method
                )
                args.ctx[method_code] = method
                model_code.add_line(
                    f"{args.data_code}, errors{args.level} = {method_code}({args.data_code})",
                    0,
                )
                model_code.add_line(f"if errors{args.level}:", 1)
                model_code.add_line(
                    f"{args.errors_code}[{repr(method_name)}] = errors{args.level}",
                    0,
                )
                model_code.add_line("return", -1)

            field_names = []
            field_names_with_mutation = set()
            field_codes = []
            current_indent_level = model_code.indent_level
            for field_name, field_type_value in type_hints.items():
                if field_name in private_fields:
                    continue

                model_code.indent_level = current_indent_level
                field_code = f"{field_name}_{args.level}"
                field_names.append(field_name)
                field_codes.append(field_code)

                if isinstance(field_type_value, TypeVar):
                    field_type_value = type_var_to_type_value[field_type_value]

                pipeline = getattr(resolved_model, field_name, _none)
                if not isinstance(pipeline, FieldProcessingPipeline):
                    # then pipeline is just the default value
                    pipeline = field(field_name, default=pipeline)

                pipeline_path = pipeline.path or (field_name,)

                if pipeline.cls_method:
                    method = getattr(args.type_value, pipeline.cls_method)
                    fetcher: "BaseConversion" = c.naive(
                        method,
                        name_prefix=pipeline.cls_method,
                    )
                    if getattr(method, "cached_model_method", False):
                        args.base_conversion.requires_versions = True
                        fetcher = fetcher.call(
                            c.this, c.escaped_string("run_ctx_.version")
                        )
                    else:
                        fetcher = fetcher.call(c.this)

                    fetch_field_code = fetcher.gen_code_and_update_ctx(
                        args.data_code, args.ctx
                    )
                    model_code.add_line(
                        f"{field_code}, field_errors = {fetch_field_code}",
                        0,
                    )
                    model_code.add_line("if field_errors:", 1)
                    model_code.add_line(
                        f"{args.errors_code}[{repr(field_name)}] = field_errors",
                        -1,
                    )
                    model_code.add_line("else:", 1)
                else:
                    default = (
                        c.call_func(pipeline.default_factory)
                        if pipeline.default_factory is not _none
                        else pipeline.default
                    )
                    if is_dict_model:
                        conversion_: "BaseConversion" = c.item(
                            *pipeline_path, default=default
                        )
                    else:
                        conversion_ = c.this
                        for path_ in pipeline_path:
                            if not isinstance(path_, int):
                                conversion_ = conversion_.attr(
                                    path_, default=default
                                )
                            else:
                                conversion_ = conversion_.item(
                                    path_, default=default
                                )

                    fetch_field_code = conversion_.gen_code_and_update_ctx(
                        args.data_code, args.ctx
                    )
                    model_code.add_line(
                        f"{field_code} = {fetch_field_code}", 0
                    )

                step_chunks = list(chunk_pipeline_steps(pipeline.steps))

                output_type_is_ensured = field_type_value is Any

                last_step_chunk_index = len(step_chunks) - 1

                step_condition = step_condition_has_side_effects = None

                for step_chunk_index, steps in enumerate(step_chunks):
                    if step_condition:
                        model_code.add_line(f"if {step_condition}:", 1)
                        step_condition = step_condition_has_side_effects = None

                    if isinstance(steps[0], BaseValidator):
                        validate_input_conditions_code = c.and_(
                            *[
                                c.naive(
                                    validator.validate,
                                    name_prefix=validator.name,
                                ).call(
                                    field_name,
                                    c.this,
                                    c.escaped_string(args.errors_code),
                                )
                                for validator in steps
                            ]
                        ).gen_code_and_update_ctx(field_code, args.ctx)
                        step_condition = validate_input_conditions_code
                        step_condition_has_side_effects = True

                    elif isinstance(steps[0], BaseCaster):
                        last_caster_index = len(steps) - 1
                        for caster_index, caster in enumerate(steps):
                            if isinstance(caster, CasterToFinalType):
                                caster = ensure_caster(field_type_value)
                                if (
                                    step_chunk_index == last_step_chunk_index
                                    and caster_index == last_caster_index
                                ):
                                    output_type_is_ensured = True

                            caster_code = caster.as_conversion(
                                args.code_suffix,
                                repr(field_name),
                                field_code,
                                args.errors_code,
                                args.base_conversion,
                                args.ctx,
                                args.level,
                            ).gen_code_and_update_ctx(field_code, args.ctx)
                            model_code.add_line(
                                f"{field_code} = {caster_code}", 0
                            )
                            if caster_index == last_caster_index:
                                step_condition = f"{repr(field_name)} not in {args.errors_code}"
                                step_condition_has_side_effects = False
                            else:
                                model_code.add_line(
                                    f"if {repr(field_name)} not in {args.errors_code}:",
                                    1,
                                )

                    else:
                        raise AssertionError(
                            "it's a bug: unsupported pipeline step"
                        )
                if output_type_is_ensured:
                    if step_condition and step_condition_has_side_effects:
                        model_code.add_line(step_condition, 0)
                else:
                    if step_condition:
                        model_code.add_line(f"if {step_condition}:", 1)
                    field_with_mutation = type_value_to_code(
                        args._replace(
                            code=model_code,
                            type_value=field_type_value,
                            name_code=repr(field_name),
                            data_code=field_code,
                        )
                    )
                    if field_with_mutation:
                        field_names_with_mutation.add(field_name)

            model_code.indent_level = current_indent_level

            model_code.add_line(f"if not {args.errors_code}:", 1)

            model_cls_code = gen_model_cls_code(
                args.base_conversion,
                original_model,
                args.code_suffix,
                field_names,
                field_names_with_mutation,
                args.ctx,
            )

            for method_name in ("validate", "validate__"):
                method = getattr(original_model, method_name, None)
                if method and callable(method):
                    if not inspect.ismethod(method):
                        raise AssertionError(
                            f"{original_model.__name__}.{method} should be a classmethod"
                        )
                    break
                method = None

            if method:
                method_code = args.base_conversion.gen_name(
                    "validate", args.ctx, method
                )
                args.ctx[method_code] = method
                model_code.add_line(
                    f"validated_data{args.level}, validate_errors{args.level} = {method_code}({model_cls_code}({', '.join(field_codes)}))",
                    0,
                )
                model_code.add_line(f"if validate_errors{args.level}:", 1)
                model_code.add_line(
                    f"{args.errors_code}[{repr(method_name)}] = validate_errors{args.level}",
                    -1,
                )
                model_code.add_line("else:", 1)
                model_code.add_line(f"return validated_data{args.level}", -2)

            else:

                model_code.add_line(
                    f"return {model_cls_code}({', '.join(field_codes)})",
                    -1,
                )

            function_ctx.gen_function(
                model_meta.converter_name, model_code.to_string(0)
            )
    del args

    code = outer_args.code
    if model_meta.number_of_usages > 1:
        outer_args.base_conversion.tracks_visited = True

        code_suffix = outer_args.code_suffix

        proxy_cls_name = outer_args.base_conversion.gen_name(
            f"Proxy{original_model.__name__}", outer_args.ctx, original_model
        )
        outer_args.ctx[proxy_cls_name] = type(
            proxy_cls_name, (ProxyObject, original_model), {}
        )

        code.add_line(f"_id{code_suffix} = id({outer_args.data_code})", 0)
        code.add_line(
            f"if _id{code_suffix} in run_ctx_.visited_model_data:",
            1,
        )
        code.add_line(
            f"{outer_args.data_code} = run_ctx_.visited_model_data[_id{code_suffix}][1]",
            -1,
        )
        code.add_line("else:", 1)
        code.add_line(
            f"run_ctx_.visited_model_data[_id{code_suffix}] = ({outer_args.data_code}, {proxy_cls_name}())",
            0,
        )

        if outer_args.level > 0:
            code.add_line(f"{model_errors_code} = defaultdict(dict)", 0)

        code.add_line(f"{outer_args.data_code} = {process_model_code}", 0)

        if outer_args.level > 0:
            code.add_line(f"if {model_errors_code}:", 1)
            code.add_line(
                f"{outer_args.errors_code}[{outer_args.name_code}] = {model_errors_code}",
                -1,
            )
        code.add_line(
            f"run_ctx_.visited_model_data[_id{code_suffix}][1].wrapped_object__ = {outer_args.data_code}",
            -1,
        )
    else:
        if outer_args.level > 0:
            code.add_line(f"{model_errors_code} = defaultdict(dict)", 0)

        code.add_line(f"{outer_args.data_code} = {process_model_code}", 0)

        if outer_args.level > 0:
            code.add_line(f"if {model_errors_code}:", 1)
            code.add_line(
                f"{outer_args.errors_code}[{outer_args.name_code}] = {model_errors_code}",
                -1,
            )


def simple_type_to_code(args: TypeValueCodeGenArgs):
    has_none, simple_types, _ = TypeValidator.split_types(args.type_value)
    bad_type_condition_code, set_error_code = TypeValidator.to_code(
        has_none,
        simple_types,
        args,
    )
    args.code.add_line(f"if {bad_type_condition_code}:", 1)
    args.code.add_line(set_error_code, -1)


def union_type_to_code(args: TypeValueCodeGenArgs):
    code = args.code
    current_indent = code.indent_level
    has_none, simple_types, other_types = TypeValidator.split_types(
        *args.type_value.__args__
    )
    if has_none or simple_types:
        bad_type_condition_code, set_error_code = TypeValidator.to_code(
            has_none, simple_types, args
        )
        code.add_line(f"if {bad_type_condition_code}:", 1)
        if not other_types:
            code.add_line(set_error_code, -1)

    if other_types:
        last_index = len(other_types) - 1
        for index, arg in enumerate(other_types):
            type_value_to_code(
                args._replace(
                    type_value=arg,
                    level=args.level + 1,
                )
            )
            if index == last_index:
                pass
            else:
                code.add_line(f"if {args.name_code} in {args.errors_code}:", 1)
                code.add_line(f"del {args.errors_code}[{args.name_code}]", 0)

    code.indent_level = current_indent


def dict_type_to_code(outer_args: TypeValueCodeGenArgs):
    bad_type_condition_code, set_error_code = TypeValidator.to_code(
        False, (dict,), outer_args
    )
    code = outer_args.code
    code.add_line(f"if {bad_type_condition_code}:", 1)
    code.add_line(set_error_code, -1)
    code.add_line("else:", 1)
    current_indent_level = code.indent_level

    level = outer_args.level + 1
    iteration_code = Code()

    key_code = f"key_{level}"
    value_code = f"value_{level}"
    dict_errors_key_code = f"errors_key_{level}"
    dict_errors_value_code = f"errors_value_{level}"
    dict_result_code = f"result_{level}"

    has_mutations = any(
        (
            type_value_to_code(
                outer_args._replace(
                    code=iteration_code,
                    type_value=outer_args.type_value.__args__[0],
                    name_code=key_code,
                    data_code=key_code,
                    errors_code=dict_errors_key_code,
                    level=level,
                ),
            ),
            type_value_to_code(
                outer_args._replace(
                    code=iteration_code,
                    type_value=outer_args.type_value.__args__[1],
                    name_code=key_code,
                    data_code=value_code,
                    errors_code=dict_errors_value_code,
                    level=level,
                ),
            ),
        )
    )

    if has_mutations:
        code.add_line(f"{dict_errors_key_code} = defaultdict(dict)", 0)
        code.add_line(f"{dict_errors_value_code} = defaultdict(dict)", 0)
        code.add_line(f"{dict_result_code} = {{}}", 0)
        code.add_line(
            f"for {key_code}, {value_code} in {outer_args.data_code}.items():",
            1,
        )
        code.add_code(iteration_code)
        code.add_line(f"{dict_result_code}[{key_code}] = {value_code}", -1)

        code.indent_level = current_indent_level
        code.add_line(
            f"if {dict_errors_key_code} or {dict_errors_value_code}:", 1
        )
        code.add_line(f"if {dict_errors_key_code}:", 1)
        code.add_line(
            f'{outer_args.errors_code}[{outer_args.name_code}]["keys"] = {dict_errors_key_code}',
            -1,
        )
        code.add_line(f"if {dict_errors_value_code}:", 1)
        code.add_line(
            f'{outer_args.errors_code}[{outer_args.name_code}]["values"] = {dict_errors_value_code}',
            -2,
        )

        code.add_line("else:", 1)
        code.add_line(f"{outer_args.data_code} = {dict_result_code}", -1)

    else:
        code.add_line(f"{dict_errors_key_code} = defaultdict(dict)", 0)
        code.add_line(f"{dict_errors_value_code} = defaultdict(dict)", 0)
        code.add_line(
            f"for {key_code}, {value_code} in {outer_args.data_code}.items():",
            1,
        )
        code.add_code(iteration_code)

        code.indent_level = current_indent_level
        code.add_line(
            f"if {dict_errors_key_code} or {dict_errors_value_code}:", 1
        )
        code.add_line(f"if {dict_errors_key_code}:", 1)
        code.add_line(
            f'{outer_args.errors_code}[{outer_args.name_code}]["keys"] = {dict_errors_key_code}',
            -1,
        )
        code.add_line(f"if {dict_errors_value_code}:", 1)
        code.add_line(
            f'{outer_args.errors_code}[{outer_args.name_code}]["values"] = {dict_errors_value_code}',
            -2,
        )

    return has_mutations


def list_type_to_code(outer_args: TypeValueCodeGenArgs):
    bad_type_condition_code, set_error_code = TypeValidator.to_code(
        False,
        (list,),
        outer_args,
    )
    code = outer_args.code
    code.add_line(f"if {bad_type_condition_code}:", 1)
    code.add_line(set_error_code, -1)
    code.add_line("else:", 1)
    current_indent_level = code.indent_level

    level = outer_args.level + 1
    list_result_code = f"result_{level}"
    iteration_code = Code()
    args = outer_args._replace(
        code=iteration_code,
        type_value=outer_args.type_value.__args__[0],
        name_code=f"index_{level}",
        data_code=f"item_{level}",
        errors_code=f"errors_{level}",
        level=outer_args.level + 1,
    )
    has_mutations = type_value_to_code(args)

    if has_mutations:
        code.add_line(f"{args.errors_code} = defaultdict(dict)", 0)
        code.add_line(f"{list_result_code} = []", 0)
        code.add_line(
            f"for {args.name_code}, {args.data_code} in enumerate({outer_args.data_code}):",
            1,
        )
        code.add_code(iteration_code)
        code.add_line(f"{list_result_code}.append({args.data_code})", 0)

        code.indent_level = current_indent_level
        code.add_line(f"if {args.errors_code}:", 1)
        code.add_line(
            f"{outer_args.errors_code}[{outer_args.name_code}] = {args.errors_code}",
            -1,
        )
        code.add_line("else:", 1)
        code.add_line(f"{outer_args.data_code} = {list_result_code}", -2)
    else:
        code.add_line(f"{args.errors_code} = defaultdict(dict)", 0)
        code.add_line(
            f"for {args.name_code}, {args.data_code} in enumerate({outer_args.data_code}):",
            1,
        )
        code.add_code(iteration_code)

        code.indent_level = current_indent_level
        code.add_line(f"if {args.errors_code}:", 1)
        code.add_line(
            f"{outer_args.errors_code}[{outer_args.name_code}] = {args.errors_code}",
            -1,
        )

    return has_mutations


def is_model(type_value):
    return (
        is_generic_alias(type_value)
        and isinstance(type_value.__origin__, type)
        and issubclass(type_value.__origin__, BaseModel)
        or isinstance(type_value, type)
        and issubclass(type_value, BaseModel)
    )


def type_value_to_code(args: TypeValueCodeGenArgs):
    """Returns True if it added mutation code"""
    type_value = args.type_value
    code = args.code

    if is_model(type_value):
        model_type_to_code(args)
        return True

    elif type_value is Any:
        code.add_line("pass", 0)
        return False

    elif isinstance(type_value, TypeVar):
        if type_value not in args.type_var_to_type_value:
            raise AssertionError("uninitialized TypeVar", type_value)
        return type_value_to_code(
            args._replace(type_value=args.type_var_to_type_value[type_value])
        )

    elif not is_generic_alias(type_value):
        if not isinstance(type_value, type):
            raise Exception(f"type is expected, got {type_value}")
        simple_type_to_code(args)
        return False

    if is_generic_union_alias(type_value):
        return union_type_to_code(args)

    elif is_generic_list_alias(type_value):
        return list_type_to_code(args)

    elif is_generic_dict_alias(type_value):
        return dict_type_to_code(args)

    else:
        raise Exception(f"{type_value} is not supported yet")
