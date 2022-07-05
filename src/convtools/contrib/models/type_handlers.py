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
from .casters.base import BaseCaster, CasterToFinalType
from .field import (
    FieldProcessingPipeline,
    ensure_caster,
    field,
    try_simple_type_to_caster,
)
from .utils import (
    ensure_generic_alias_has_args,
    is_generic_alias,
    is_generic_dict_alias,
    is_generic_list_alias,
    is_generic_literal_alias,
    is_generic_set_alias,
    is_generic_tuple_alias,
    is_model_cls,
    is_union,
)
from .validators.validators import BaseValidator
from .validators.validators import Type as TypeValidator


if TYPE_CHECKING:
    from convtools.base import BaseConversion

PY_VERSION = sys.version_info[0:2]


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
    level = outer_args.level
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

    function_ctx = outer_args.base_conversion.as_function_ctx(
        outer_args.ctx, optimize_naive=True
    )
    function_ctx.add_arg("name_", c.escaped_string(outer_args.name_code))
    function_ctx.add_arg("data_", c.escaped_string(outer_args.data_code))
    function_ctx.add_arg("errors_", c.escaped_string(outer_args.errors_code))

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
            errors_code=f"errors_{level}",
        )
        args.type_to_model_meta[args.type_value] = model_meta

        is_dict_model = issubclass(original_model, DictModel)

        with function_ctx:
            model_code.add_line("def placeholder", 1)
            model_code.add_line(
                f"{args.errors_code} = errors_.get_lazy_item({args.name_code})",
                0,
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
                    f"{args.data_code}, prepare_errors{args.level} = {method_code}({args.data_code})",
                    0,
                )
                model_code.add_line(f"if prepare_errors{args.level}:", 1)
                model_code.add_line(
                    f'{args.errors_code}["__ERRORS"] = prepare_errors{args.level}',
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
                    if args.cast:
                        pipeline = pipeline.cast()

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
                        f"{field_code}, cls_method_errors_{args.level} = {fetch_field_code}",
                        0,
                    )
                    model_code.add_line(
                        f"if cls_method_errors_{args.level}:", 1
                    )
                    model_code.add_line(
                        f'{args.errors_code}[{repr(field_name)}]["__ERRORS"] = cls_method_errors_{args.level}',
                        -1,
                    )
                    model_code.add_line("else:", 1)
                else:
                    default = (
                        c.call_func(pipeline.default_factory)
                        if pipeline.default_factory is not _none
                        else (
                            c.escaped_string("_none")
                            if pipeline.default is _none
                            else c.naive(pipeline.default)
                        )
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

                if pipeline.required_check:
                    required_check_indent_level = model_code.indent_level
                    model_code.add_line(f"if {field_code} is not _none:", 1)
                    required_check_lines_number = len(model_code.lines_info)

                for step_chunk_index, steps in enumerate(step_chunks):
                    if step_condition:
                        model_code.add_line(f"if {step_condition}:", 1)
                        step_condition = step_condition_has_side_effects = None

                    if isinstance(steps[0], BaseValidator):
                        step_condition = c.and_(
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
                        step_condition_has_side_effects = True

                        if step_chunk_index == last_step_chunk_index and any(
                            field_type_value == validator_.ensures_type
                            for validator_ in steps
                        ):
                            output_type_is_ensured = True

                    elif isinstance(steps[0], BaseCaster):
                        last_caster_index = len(steps) - 1
                        for caster_index, caster in enumerate(steps):
                            if isinstance(caster, CasterToFinalType):
                                caster = ensure_caster(
                                    field_type_value, caster.overrides
                                )
                                if (
                                    step_chunk_index == last_step_chunk_index
                                    and caster_index == last_caster_index
                                ):
                                    output_type_is_ensured = True
                            elif (
                                step_chunk_index == last_step_chunk_index
                                and caster_index == last_caster_index
                                and caster.ensures_type == field_type_value
                            ):
                                output_type_is_ensured = True

                            caster.to_code(
                                args._replace(
                                    name_code=repr(field_name),
                                    data_code=field_code,
                                )
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
                            cast=False,
                        ),
                    )
                    if field_with_mutation:
                        field_names_with_mutation.add(field_name)

                if pipeline.required_check:
                    if (
                        len(model_code.lines_info)
                        == required_check_lines_number
                    ):
                        model_code.indent_level = (
                            required_check_indent_level + 1
                        )
                        model_code.add_line("pass", 0)
                    model_code.indent_level = required_check_indent_level
                    model_code.add_line("else:", 1)
                    model_code.add_line(
                        f'{args.errors_code}[{repr(field_name)}]["__ERRORS"] = {{"required": True}}',
                        -1,
                    )

            model_code.indent_level = current_indent_level

            model_code.add_line(
                f"if {args.name_code} not in {args.errors_code}:", 1
            )

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
                    f'{args.errors_code}["__ERRORS"] = validate_errors{args.level}',
                    -1,
                )
                model_code.add_line("else:", 1)
                model_code.add_line(f"return validated_data{args.level}", -2)

            else:

                model_code.add_line(
                    f"return {model_cls_code}({', '.join(field_codes)})",
                    -1,
                )

            model_code.lines_info[0] = (
                0,
                f"def {model_meta.converter_name}({function_ctx.get_def_all_args_code()}):",
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
        code.add_line(f"{outer_args.data_code} = {process_model_code}", 0)

        code.add_line(
            f"run_ctx_.visited_model_data[_id{code_suffix}][1].wrapped_object__ = {outer_args.data_code}",
            -1,
        )
    else:
        code.add_line(f"{outer_args.data_code} = {process_model_code}", 0)


def simple_type_to_code(args: TypeValueCodeGenArgs):
    if args.cast:
        casted = False
        for cast_overrides in args.cast_overrides_stack:
            if args.type_value not in cast_overrides:
                continue
            casted = True

            code = args.code
            caster_or_casters = cast_overrides[args.type_value]
            casters = (
                caster_or_casters
                if isinstance(caster_or_casters, list)
                else [caster_or_casters]
            )

            last_index = len(casters) - 1
            if last_index > 0:
                code.add_line(f"backup_{args.level} = {args.data_code}", 0)
            for index, caster in enumerate(casters):
                caster.to_code(args)
                if index != last_index:
                    code.add_line(
                        f"if {args.name_code} in {args.errors_code}:", 1
                    )
                    code.add_line(
                        f"del {args.errors_code}[{args.name_code}]", 0
                    )
                    code.add_line(f"{args.data_code} = backup_{args.level}", 0)

            break

        if not casted:
            caster = try_simple_type_to_caster(args.type_value)
            if caster is None:
                raise ValueError(
                    f"automatic casting to {args.type_value} is not supported"
                )
            caster.to_code(args)

    else:
        chunks = TypeValidator.chunk_types_to_simple_and_other(
            (args.type_value,)
        )
        if len(chunks) != 1 or chunks[0]["chunk_type"] != "simple":
            raise AssertionError

        bad_type_condition_code, set_error_code = TypeValidator.to_code(
            chunks[0]["types"],
            args,
        )
        args.code.add_line(f"if {bad_type_condition_code}:", 1)
        args.code.add_line(set_error_code, -1)
    return args.cast


NoneType = type(None)


def union_type_to_code(args: TypeValueCodeGenArgs):
    code = args.code
    current_indent = code.indent_level
    type_values = args.type_value.__args__

    if args.cast:
        last_index = len(type_values) - 1
        if NoneType in type_values:
            code.add_line(f"if {args.data_code} is not None:", 1)
            last_index = len(type_values) - 2
        else:
            last_index = len(type_values) - 1

        name_code = (
            f"backup_{args.level}"
            if args.name_code == args.data_code
            else args.name_code
        )
        if last_index > 0:
            code.add_line(f"backup_{args.level} = {args.data_code}", 0)
        for index, type_value in enumerate(
            type_ for type_ in type_values if type_ is not NoneType
        ):
            type_value_to_code(args._replace(type_value=type_value))
            if index != last_index:
                code.add_line(f"if {name_code} in {args.errors_code}:", 1)
                code.add_line(f"del {args.errors_code}[{name_code}]", 0)
                code.add_line(f"{args.data_code} = backup_{args.level}", 0)
    else:
        chunks = TypeValidator.chunk_types_to_simple_and_other(type_values)
        last_chunk_index = len(chunks) - 1
        for index, chunk in enumerate(chunks):
            if chunk["chunk_type"] == "simple":
                (
                    bad_type_condition_code,
                    set_error_code,
                ) = TypeValidator.to_code(chunk["types"], args)
                code.add_line(f"if {bad_type_condition_code}:", 1)
                if index == last_chunk_index:
                    code.add_line(set_error_code, -1)
            else:
                if len(chunk["types"]) != 1:
                    raise AssertionError

                type_value_to_code(args._replace(type_value=chunk["types"][0]))
                if index != last_chunk_index:
                    code.add_line(
                        f"if {args.name_code} in {args.errors_code}:", 1
                    )
                    code.add_line(
                        f"del {args.errors_code}[{args.name_code}]", 0
                    )

    code.indent_level = current_indent


def iter_pairs__(pairs, errors):
    for index, pair in enumerate(pairs):
        try:
            _, _ = pair
            yield pair
        except TypeError:
            errors["__ERRORS"] = {
                "pair": f"non-iterable item, type {type(pair).__name__}"
            }
        except ValueError as e:
            errors[index]["__ERRORS"] = {"pair": str(e)}


def dict_type_to_code(outer_args: TypeValueCodeGenArgs):
    outer_args.ctx["iter_pairs__"] = iter_pairs__
    code = outer_args.code
    initial_indent_level = code.indent_level
    level = outer_args.level

    dict_errors_code = f"errors_{level}"
    code.add_line(f"{dict_errors_code} = None", 0)
    if outer_args.cast:
        code.add_line("try:", 1)
        code.add_line(f"if isinstance({outer_args.data_code}, dict):", 1)
        code.add_line(f"pairs_{level} = {outer_args.data_code}.items()", -1)
        code.add_line("else:", 1)
        code.add_line(
            f"{dict_errors_code} = {outer_args.errors_code}.get_lazy_item({outer_args.name_code})",
            0,
        )
        code.add_line(
            f"pairs_{level} = iter_pairs__(iter({outer_args.data_code}), {dict_errors_code})",
            -2,
        )

        code.add_line("except TypeError:", 1)
        code.add_line(
            f'{outer_args.errors_code}[{outer_args.name_code}]["__ERRORS"] = {{"type": f"{{type({outer_args.data_code}).__name__}} not iterable"}}',
            -1,
        )
        code.add_line("except ValueError as e:", 1)
        code.add_line(
            f'{outer_args.errors_code}[{outer_args.name_code}]["__ERRORS"] = {{"pair_length": str(e)}}',
            -1,
        )
        code.add_line("except StopIteration:", 1)
        code.add_line(f"{outer_args.data_code} = {{}}", -1)
        code.add_line("else:", 1)
    else:
        bad_type_condition_code, set_error_code = TypeValidator.to_code(
            (dict,), outer_args
        )
        code.add_line(f"if {bad_type_condition_code}:", 1)
        code.add_line(set_error_code, -1)
        code.add_line("else:", 1)
        code.add_line(f"pairs_{level} = {outer_args.data_code}.items()", 0)

    key_code = f"key_{level}"
    value_code = f"value_{level}"
    dict_errors_key_code = f"errors_key_{level}"
    dict_errors_value_code = f"errors_value_{level}"
    dict_result_code = f"result_{level}"

    code.add_line(
        f"{dict_errors_code} = {outer_args.errors_code}.get_lazy_item({outer_args.name_code}) if {dict_errors_code} is None else {dict_errors_code}",
        0,
    )
    code.add_line(
        f'{dict_errors_key_code} = {dict_errors_code}.get_lazy_item("__KEYS")',
        0,
    )
    code.add_line(
        f'{dict_errors_value_code} = {dict_errors_code}.get_lazy_item("__VALUES")',
        0,
    )
    key_iteration_code = Code()
    value_iteration_code = Code()

    has_mutations = any(
        (
            type_value_to_code(
                outer_args._replace(
                    code=key_iteration_code,
                    type_value=outer_args.type_value.__args__[0],
                    name_code=key_code,
                    data_code=key_code,
                    errors_code=dict_errors_key_code,
                    path_before_model=(
                        outer_args.path_before_model
                        if outer_args.model_depth
                        else (outer_args.path_before_model, "__args__", 0)
                    ),
                ),
            ),
            type_value_to_code(
                outer_args._replace(
                    code=value_iteration_code,
                    type_value=outer_args.type_value.__args__[1],
                    name_code=key_code,
                    data_code=value_code,
                    errors_code=dict_errors_value_code,
                    path_before_model=(
                        outer_args.path_before_model
                        if outer_args.model_depth
                        else (outer_args.path_before_model, "__args__", 1)
                    ),
                ),
            ),
        )
    )

    if has_mutations or outer_args.cast:
        indent_level_before_for = code.indent_level
        key_iteration_as_expression = key_iteration_code.as_expression()
        value_iteration_as_expression = value_iteration_code.as_expression()
        if key_iteration_as_expression and value_iteration_as_expression:
            code.add_line(
                f"{dict_result_code} = {{ {key_iteration_as_expression}: {value_iteration_as_expression} for {key_code}, {value_code} in pairs_{level} }}",
                0,
            )
        else:
            code.add_line(f"{dict_result_code} = {{}}", 0)

            code.add_line(
                f"for {key_code}, {value_code} in pairs_{level}:",
                1,
            )
            code.add_code(value_iteration_code)
            code.add_code(key_iteration_code)
            code.add_line(f"{dict_result_code}[{key_code}] = {value_code}", -1)

        code.indent_level = indent_level_before_for

        code.add_line(
            f"if {outer_args.name_code} not in {outer_args.errors_code}:", 1
        )
        code.add_line(f"{outer_args.data_code} = {dict_result_code}", -1)

    else:
        code.add_line(
            f"for {key_code}, {value_code} in pairs_{level}:",
            1,
        )
        code.add_code(key_iteration_code)
        code.add_code(value_iteration_code)

    code.indent_level = initial_indent_level
    return has_mutations or outer_args.cast


def tuple_finite_type_to_code(outer_args: TypeValueCodeGenArgs):
    level = outer_args.level
    tuple_args = outer_args.type_value.__args__

    if not outer_args.cast:
        code = Code()
        bad_type_condition_code, set_error_code = TypeValidator.to_code(
            (tuple,),
            outer_args,
        )
        initial_indent_level = code.indent_level

        code.add_line(f"if {bad_type_condition_code}:", 1)
        code.add_line(set_error_code, -1)

        code.add_line("else:", 1)

        args = outer_args._replace(
            code=code,
            errors_code=f"errors_{level}",
        )
        code.add_line(
            f"if len({outer_args.data_code}) != {len(tuple_args)}:", 1
        )
        code.add_line(
            f'{outer_args.errors_code}[{outer_args.name_code}]["__ERRORS"] = {{"length": f"length is {{len({outer_args.data_code})}}, expected {len(tuple_args)}"}}',
            -1,
        )
        code.add_line("else:", 1)
        code.add_line(
            f"{args.errors_code} = {outer_args.errors_code}.get_lazy_item({outer_args.name_code})",
            0,
        )

        has_mutations = False
        for index, type_arg in enumerate(tuple_args):
            has_mutations = has_mutations or type_value_to_code(
                args._replace(
                    type_value=type_arg,
                    name_code=str(index),
                    data_code=f"{outer_args.data_code}[{index}]",
                    path_before_model=(
                        outer_args.path_before_model
                        if outer_args.model_depth
                        else (outer_args.path_before_model, "__args__", index)
                    ),
                )
            )

        if not has_mutations:
            outer_args.code.add_code(code)
            return has_mutations

    code = outer_args.code
    initial_indent_level = code.indent_level

    item_codes = [f"t{index}" for index in range(len(tuple_args))]

    code.add_line("try:", 1)
    if len(item_codes) > 1:
        code.add_line(
            f'{", ".join(item_codes)} = iter({outer_args.data_code})', -1
        )
        code.add_line("except TypeError:", 1)
        code.add_line(
            f'{outer_args.errors_code}[{outer_args.name_code}]["__ERRORS"] = {{"type": f"{{type({outer_args.data_code}).__name__}} not iterable"}}',
            -1,
        )
        code.add_line("except ValueError as e:", 1)
        code.add_line(
            f'{outer_args.errors_code}[{outer_args.name_code}]["__ERRORS"] = {{"length": str(e)}}',
            -1,
        )
    else:
        code.add_line(
            f"{item_codes[0]} = next(iter({outer_args.data_code}))", -1
        )
        code.add_line("except TypeError:", 1)
        code.add_line(
            f'{outer_args.errors_code}[{outer_args.name_code}]["__ERRORS"] = {{"type": f"{{type({outer_args.data_code}).__name__}} not iterable"}}',
            -1,
        )
        code.add_line("except StopIteration:", 1)
        code.add_line(
            f'{outer_args.errors_code}[{outer_args.name_code}]["__ERRORS"] = {{"length": "iterable is empty"}}',
            -1,
        )
    code.add_line("else:", 1)

    args = outer_args._replace(
        errors_code=f"errors_{level}",
    )

    code.add_line(
        f"{args.errors_code} = {outer_args.errors_code}.get_lazy_item({outer_args.name_code})",
        0,
    )

    for index, (type_arg, item_code) in enumerate(zip(tuple_args, item_codes)):
        type_value_to_code(
            args._replace(
                type_value=type_arg,
                name_code=str(index),
                data_code=item_code,
                path_before_model=(
                    outer_args.path_before_model
                    if outer_args.model_depth
                    else (outer_args.path_before_model, "__args__", index)
                ),
            ),
        )

    code.add_line(
        f"if {outer_args.name_code} not in {outer_args.errors_code}:", 1
    )
    if len(item_codes) > 1:
        code.add_line(f"{outer_args.data_code} = ({', '.join(item_codes)})", 0)
    else:
        code.add_line(f"{outer_args.data_code} = ({item_codes[0]},)", 0)
    code.indent_level = initial_indent_level
    return True


def tuple_variadic_type_to_code(outer_args: TypeValueCodeGenArgs):
    code = outer_args.code
    initial_indent_level = code.indent_level
    level = outer_args.level

    if outer_args.cast:
        code.add_line(
            f'if not hasattr({outer_args.data_code}, "__iter__"):', 1
        )
        code.add_line(
            f'{outer_args.errors_code}[{outer_args.name_code}]["__ERRORS"] = {{"type": f"{{type({outer_args.data_code}).__name__}} not iterable"}}',
            -1,
        )
        code.add_line("else:", 1)
    else:
        bad_type_condition_code, set_error_code = TypeValidator.to_code(
            (tuple,),
            outer_args,
        )
        code.add_line(f"if {bad_type_condition_code}:", 1)
        code.add_line(set_error_code, -1)
        code.add_line("else:", 1)

    args = outer_args._replace(
        code=Code(),
        type_value=outer_args.type_value.__args__[0],
        name_code=f"index_{level}",
        data_code=f"item_{level}",
        errors_code=f"errors_{level}",
        path_before_model=(
            outer_args.path_before_model
            if outer_args.model_depth
            else (outer_args.path_before_model, "__args__", 0)
        ),
    )
    has_mutations = type_value_to_code(args)

    code.add_line(
        f"{args.errors_code} = {outer_args.errors_code}.get_lazy_item({outer_args.name_code})",
        0,
    )

    indent_level_before_for = code.indent_level

    if has_mutations or outer_args.cast:
        result_code = f"result_{level}"
        code_as_expression = args.code.as_expression()
        if code_as_expression:
            code.add_line(
                f"{result_code} = [{code_as_expression} for {args.name_code}, {args.data_code} in enumerate({outer_args.data_code})]",
                0,
            )
        else:
            code.add_line(f"{result_code} = []", 0)
            code.add_line(
                f"for {args.name_code}, {args.data_code} in enumerate({outer_args.data_code}):",
                1,
            )
            code.add_code(args.code)
            code.add_line(f"{result_code}.append({args.data_code})", 0)

        code.indent_level = indent_level_before_for
        code.add_line(
            f"if {outer_args.name_code} not in {outer_args.errors_code}:", 1
        )

        code.add_line(f"{outer_args.data_code} = tuple({result_code})", 0)

    else:
        code.add_line(
            f"for {args.name_code}, {args.data_code} in enumerate({outer_args.data_code}):",
            1,
        )
        code.add_code(args.code)

    code.indent_level = initial_indent_level
    return has_mutations or outer_args.cast


def list_type_to_code(outer_args: TypeValueCodeGenArgs):
    code = outer_args.code
    initial_indent_level = code.indent_level
    level = outer_args.level

    if outer_args.cast:
        code.add_line(
            f'if not hasattr({outer_args.data_code}, "__iter__"):', 1
        )
        code.add_line(
            f'{outer_args.errors_code}[{outer_args.name_code}]["__ERRORS"] = {{"type": f"{{type({outer_args.data_code}).__name__}} not iterable"}}',
            -1,
        )
        code.add_line("else:", 1)
    else:
        bad_type_condition_code, set_error_code = TypeValidator.to_code(
            (list,),
            outer_args,
        )
        code.add_line(f"if {bad_type_condition_code}:", 1)
        code.add_line(set_error_code, -1)
        code.add_line("else:", 1)

    args = outer_args._replace(
        code=Code(),
        type_value=outer_args.type_value.__args__[0],
        name_code=f"index_{level}",
        data_code=f"item_{level}",
        errors_code=f"errors_{level}",
        path_before_model=(
            outer_args.path_before_model
            if outer_args.model_depth
            else (outer_args.path_before_model, "__args__", 0)
        ),
    )
    has_mutations = type_value_to_code(args)

    code.add_line(
        f"{args.errors_code} = {outer_args.errors_code}.get_lazy_item({outer_args.name_code})",
        0,
    )

    indent_level_before_for = code.indent_level

    if has_mutations or outer_args.cast:
        result_code = f"result_{level}"
        code_as_expression = args.code.as_expression()
        if code_as_expression:
            code.add_line(
                f"{result_code} = [{code_as_expression} for {args.name_code}, {args.data_code} in enumerate({outer_args.data_code})]",
                0,
            )
        else:
            code.add_line(f"{result_code} = []", 0)
            code.add_line(f"_append_{level} = {result_code}.append", 0)
            code.add_line(
                f"for {args.name_code}, {args.data_code} in enumerate({outer_args.data_code}):",
                1,
            )
            code.add_code(args.code)
            code.add_line(f"_append_{level}({args.data_code})", 0)

        code.indent_level = indent_level_before_for
        code.add_line(
            f"if {outer_args.name_code} not in {outer_args.errors_code}:", 1
        )

        code.add_line(f"{outer_args.data_code} = {result_code}", -1)

    else:
        code.add_line(
            f"for {args.name_code}, {args.data_code} in enumerate({outer_args.data_code}):",
            1,
        )
        code.add_code(args.code)

    code.indent_level = initial_indent_level
    return has_mutations or outer_args.cast


def set_type_to_code(outer_args: TypeValueCodeGenArgs):
    code = outer_args.code
    initial_indent_level = code.indent_level
    level = outer_args.level

    if outer_args.cast:
        code.add_line(
            f'if not hasattr({outer_args.data_code}, "__iter__"):', 1
        )
        code.add_line(
            f'{outer_args.errors_code}[{outer_args.name_code}]["__ERRORS"] = {{"type": f"{{type({outer_args.data_code}).__name__}} not iterable"}}',
            -1,
        )
        code.add_line("else:", 1)
    else:
        bad_type_condition_code, set_error_code = TypeValidator.to_code(
            (set,),
            outer_args,
        )
        code.add_line(f"if {bad_type_condition_code}:", 1)
        code.add_line(set_error_code, -1)
        code.add_line("else:", 1)

    args = outer_args._replace(
        code=Code(),
        type_value=outer_args.type_value.__args__[0],
        name_code=f"item_{level}",
        data_code=f"item_{level}",
        errors_code=f"errors_{level}",
        path_before_model=(
            outer_args.path_before_model
            if outer_args.model_depth
            else (outer_args.path_before_model, "__args__", 0)
        ),
    )
    has_mutations = type_value_to_code(args)

    code.add_line(
        f'{args.errors_code} = {outer_args.errors_code}.get_lazy_item({outer_args.name_code}).get_lazy_item("__SET_ITEMS")',
        0,
    )

    indent_level_before_for = code.indent_level

    if has_mutations or outer_args.cast:
        result_code = f"result_{level}"
        code_as_expression = args.code.as_expression()
        if code_as_expression:
            code.add_line(
                f"{result_code} = {{ {code_as_expression} for {args.name_code}, {args.data_code} in enumerate({outer_args.data_code}) }}",
                0,
            )
        else:
            code.add_line(f"{result_code} = set()", 0)
            code.add_line(
                f"for {args.data_code} in {outer_args.data_code}:",
                1,
            )
            code.add_code(args.code)
            code.add_line(f"{result_code}.add({args.data_code})", 0)

        code.indent_level = indent_level_before_for
        code.add_line(
            f"if {outer_args.name_code} not in {outer_args.errors_code}:", 1
        )

        code.add_line(f"{outer_args.data_code} = {result_code}", 0)

    else:
        code.add_line(
            f"for {args.data_code} in {outer_args.data_code}:",
            1,
        )
        code.add_code(args.code)

    code.indent_level = initial_indent_level
    return has_mutations or outer_args.cast


if PY_VERSION >= (3, 8):

    def literal_type_to_code(outer_args: TypeValueCodeGenArgs):
        try:
            args = set(outer_args.type_value.__args__)
        except TypeError:
            args = outer_args.type_value.__args__
        bad_condition_code = (
            c.escaped_string(outer_args.data_code)
            .not_in(c.naive(args))
            .gen_code_and_update_ctx("not needed", outer_args.ctx)
        )
        code = outer_args.code
        code.add_line(f"if {bad_condition_code}:", 1)
        code.add_line(
            f'{outer_args.errors_code}[{outer_args.name_code}]["__ERRORS"] = {{"literal": f"{{repr({outer_args.data_code})}} is invalid value" }}',
            -1,
        )
        return False


def is_model(type_value):
    return (  # pylint: disable=consider-using-ternary
        is_generic_alias(type_value)
        and is_model_cls(type_value.__origin__)
        or is_model_cls(type_value)
    )


def type_value_to_code(args: TypeValueCodeGenArgs):
    """Returns True if it added mutation code"""
    type_value = args.type_value
    code = args.code

    if is_model(type_value):
        kwargs = {
            "level": args.level + 1,
            "cast": False,
            "cast_overrides_stack": (),
        }

        if hasattr(type_value, "Meta"):
            meta = type_value.Meta
            if hasattr(meta, "cast"):
                kwargs["cast"] = meta.cast

            if hasattr(meta, "cast_overrides"):
                kwargs["cast_overrides_stack"] = (meta.cast_overrides,)

        model_type_to_code(
            args._replace(model_depth=args.model_depth + 1, **kwargs)
        )
        return True

    elif type_value is Any:
        code.add_line("pass", 0)
        return False

    elif isinstance(type_value, TypeVar):
        if type_value not in args.type_var_to_type_value:
            raise AssertionError("uninitialized TypeVar", type_value)
        return type_value_to_code(
            args._replace(type_value=args.type_var_to_type_value[type_value]),
        )

    elif is_union(type_value):
        if args.model_depth == 0:
            args.union_paths.append(args.path_before_model)
        return union_type_to_code(args._replace(level=args.level + 1))

    elif is_generic_alias(type_value):
        if is_generic_list_alias(type_value):
            return list_type_to_code(args._replace(level=args.level + 1))

        if is_generic_dict_alias(type_value):
            return dict_type_to_code(args._replace(level=args.level + 1))

        if is_generic_tuple_alias(type_value):
            tuple_args = type_value.__args__
            if len(tuple_args) == 2 and tuple_args[1] is ...:
                return tuple_variadic_type_to_code(
                    args._replace(level=args.level + 1)
                )
            return tuple_finite_type_to_code(
                args._replace(level=args.level + 1)
            )

        if is_generic_literal_alias(type_value):
            return literal_type_to_code(args._replace(level=args.level + 1))

        if is_generic_set_alias(type_value):
            return set_type_to_code(args._replace(level=args.level + 1))

        raise ValueError(f"{type_value} is not supported yet")

    else:
        return simple_type_to_code(args._replace(level=args.level + 1))
