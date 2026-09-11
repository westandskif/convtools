import ast
import os
import shutil
import tempfile

import pytest

from convtools import conversion as c
from convtools._base import (
    BaseConversion,
    ConverterOptions,
    ConverterOptionsCtx,
    This,
    _signature_param_names,
)
from convtools._utils import CodeParams, CodeStorage, debug_dir


def test_code_generation_ctx():
    with ConverterOptionsCtx() as options:
        assert isinstance(options, ConverterOptions)

        assert options.debug is False
        assert ConverterOptionsCtx.get_option_value("debug") is False

        options.debug = True
        assert ConverterOptionsCtx.get_option_value("debug") is True

        with ConverterOptionsCtx() as options2:
            assert options2.debug is True
            assert ConverterOptionsCtx.get_option_value("debug") is True

            options2.to_defaults("debug")
            assert options2.debug is False

            options2.debug = True
            options2.to_defaults()
            assert options2.debug is False
            assert ConverterOptionsCtx.get_option_value("debug") is False

            assert options.debug is True

        assert ConverterOptionsCtx.get_option_value("debug") is True

    assert ConverterOptionsCtx.get_option_value("debug") is False


def test_code_generation_ctx_deep_nesting():
    with ConverterOptionsCtx() as options:
        options.debug = True
        assert ConverterOptionsCtx.get_option_value("debug") is True

        with ConverterOptionsCtx():
            with ConverterOptionsCtx():
                pass
            assert ConverterOptionsCtx.get_option_value("debug") is True

        assert ConverterOptionsCtx.get_option_value("debug") is True

        with ConverterOptionsCtx() as options2:
            assert options2.debug is True
            options2.debug = False
            assert ConverterOptionsCtx.get_option_value("debug") is False

        assert ConverterOptionsCtx.get_option_value("debug") is True

        try:
            with ConverterOptionsCtx():
                with ConverterOptionsCtx():
                    raise ValueError("boom")
        except ValueError:
            pass

        assert ConverterOptionsCtx.get_option_value("debug") is True

    assert ConverterOptionsCtx.get_option_value("debug") is False


def test_replace_word():
    cases = [
        ("abc", "abc", "cde", "cde"),
        ("aabc", "abc", "cde", "aabc"),
        ("abcc", "abc", "cde", "abcc"),
        ("aabcc", "abc", "cde", "aabcc"),
        ("aabc 1", "abc", "cde", "aabc 1"),
        ("1 abcc", "abc", "cde", "1 abcc"),
        ("abc 1", "abc", "cde", "cde 1"),
        ("1 abc", "abc", "cde", "1 cde"),
        ("1 abccabc _abc abc 2", "abc", "cde", "1 abccabc _abc cde 2"),
        (" aabc ", "abc", "cde", " aabc "),
        (" abcc ", "abc", "cde", " abcc "),
        (" abc ", "abc", "cde", " cde "),
        (" abc abc abc abc  ", "abc", "cde", " cde cde cde cde  "),
    ]
    for where, word, with_what, expected_result in cases:
        result = BaseConversion.replace_word(where, word, with_what)
        assert result == expected_result


def test_add_sources():
    converter = This().gen_converter(debug=False)
    code_storage = converter.__globals__["__convtools__code_storage"]
    for code_piece in code_storage.key_to_code_piece.values():
        code_storage.add_sources(
            code_piece.converter_name, "".join(code_piece.code_parts)
        )
        with pytest.raises(Exception):
            code_storage.add_sources(
                code_piece.converter_name, "".join(code_piece.code_parts) + " "
            )

    converter = c.escaped_string("abc + 1").gen_converter(debug=True)
    with pytest.raises(NameError):
        converter(None)
    converter.__globals__["__convtools__code_storage"].dump_sources()

    conversion = This()
    ctx = conversion._init_ctx()
    name = conversion.gen_random_name("abc", ctx)
    code_str = f"def {name}(): return 1"
    assert ctx[conversion.compile_converter(name, code_str, ctx)]() == 1

    code_storage = CodeStorage()
    _, added = code_storage.add_sources("a", "tst")
    assert added
    _, added = code_storage.add_sources("a", "tst")
    assert not added


def test_dump_sources_unwritable_debug_dir(monkeypatch):
    monkeypatch.setenv("PY_CONVTOOLS_DEBUG_DIR", "/dev/null/x")
    monkeypatch.setattr(debug_dir, "debug_dir", None)
    monkeypatch.setattr(debug_dir, "dir_initialized", False)
    converter = c.item("missing").gen_converter()
    with pytest.raises(KeyError):
        converter({})


def test_dump_sources_recreates_removed_dir(monkeypatch):
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("PY_CONVTOOLS_DEBUG_DIR", tmp)
    monkeypatch.setattr(debug_dir, "debug_dir", None)
    monkeypatch.setattr(debug_dir, "dir_initialized", False)
    converter = c.item("missing").gen_converter()
    debug_dir.ensure_initialized()
    debug_dir.ensure_initialized()
    shutil.rmtree(tmp)
    with pytest.raises(KeyError):
        converter({})
    assert os.path.isdir(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


def test_strict_ctx_guard():
    assert BaseConversion.strict_ctx
    conv = This()
    ctx = conv._init_ctx()
    with pytest.raises(AssertionError, match="unregistered ctx key"):
        ctx["undeclared"] = 1
    name = conv.gen_random_name("ok", ctx)
    ctx[name] = 1
    del ctx[name]
    ctx["__debug"] = True
    del ctx["__debug"]
    with pytest.raises(AssertionError, match="unregistered ctx key"):
        del ctx["undeclared"]
    with pytest.raises(AssertionError, match="not allowed"):
        ctx.update({"undeclared": 1})
    with pytest.raises(AssertionError, match="not allowed"):
        ctx.__ior__({"undeclared": 1})
    with pytest.raises(AssertionError, match="not allowed"):
        ctx.pop("__debug")
    with pytest.raises(AssertionError, match="not allowed"):
        ctx.popitem()
    with pytest.raises(AssertionError, match="not allowed"):
        ctx.clear()


def test_init_ctx_is_exact_dict_when_strict_off():
    prev = BaseConversion.strict_ctx
    try:
        BaseConversion.strict_ctx = False
        ctx = This()._init_ctx()
        assert type(ctx) is dict
    finally:
        BaseConversion.strict_ctx = prev


def test_gen_random_suffix_retries_on_composed_collision():
    conv = This()
    ctx = conv._init_ctx()
    ctx[BaseConversion.INPUT_ARG_RENAME_MAP]["foo_"] = None
    suffix = conv.gen_random_suffix(ctx, "foo")
    assert suffix != "_"
    assert f"foo{suffix}" in ctx[BaseConversion.GENERATED_NAMES]


def test_signature_param_names_non_function(monkeypatch):
    import convtools._base as base

    real_parse = ast.parse

    def fake_parse(source, *args, **kwargs):
        if isinstance(source, str) and source.startswith("def _("):
            return real_parse("x = 1")
        return real_parse(source, *args, **kwargs)

    monkeypatch.setattr(base.ast, "parse", fake_parse)
    assert _signature_param_names("x") == set()


def test_ignores_input():
    assert c(0).ignores_input()
    assert c(int).ignores_input()
    assert c(int).call().ignores_input()
    assert c.label("a").ignores_input()
    assert c.inline_expr("{}()").pass_args(int).ignores_input()
    assert c.escaped_string("int()").ignores_input()
    assert c({"a": c.input_arg("key")}).ignores_input()
    assert not c.iter({"a": 1}).ignores_input()
    assert not c.this.ignores_input()
    assert c({"a": 1}).item("a").ignores_input()
    assert not c({"a": 1}).item(c.item("a")).ignores_input()
    assert not c.inline_expr("{}()").pass_args(c.this).ignores_input()
    assert not c.aggregate({"a": 1}).ignores_input()
    assert not c.this.add_label("a").ignores_input()
    assert not c(int).call(c.item(0)).ignores_input()


def test_code_params():
    params = CodeParams()

    params.create("0", "z")
    params.create("1", "a")
    params.create("2", "b", used_names="a")
    params.create("3", "c", used_names="z")
    params.create("4", "d")

    params.use_param("b")
    params.use_param("d")
    params.create_and_use_param("5", "e")
    params.use_param("e")
    assert params.get_format_args() == ("2", "4", "e", "e")
    assert list(params.iter_assignments()) == [
        "a = 1",
        "e = 5",
    ]

    params = CodeParams()
    params.create("0", "z", used_names="a")
    params.create("1", "a", used_names="z")
    with pytest.raises(ValueError):
        params.use_param("z")

    # Diamond DAG: a → b, a → c → b (shared dep, no cycle)
    params = CodeParams()
    params.create("1", "b")
    params.create("2", "c", used_names=["b"])
    params.create("3", "a", used_names=["b", "c"])
    params.use_param("a")
    assert params.get_format_args() == ("3",)
    assert list(params.iter_assignments()) == ["b = 1", "c = 2"]

    # Longer true cycle: a → b → c → a
    params = CodeParams()
    params.create("1", "a", used_names=["b"])
    params.create("2", "b", used_names=["c"])
    params.create("3", "c", used_names=["a"])
    with pytest.raises(ValueError):
        params.use_param("a")
