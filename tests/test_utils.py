import ast
import asyncio
import os
import shutil
import sys
import tempfile
import threading

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

from .utils import _StrictCtx


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


@pytest.mark.skipif(
    sys.version_info < (3, 7),
    reason="OptionsCtx is thread-local on 3.6: no contextvars",
)
def test_options_ctx_asyncio_isolation():
    async def run():
        started = asyncio.Event()
        release = asyncio.Event()
        results = {}

        async def task_a():
            with ConverterOptionsCtx() as options:
                options.debug = True
                started.set()
                await release.wait()
                results["a"] = ConverterOptionsCtx.get_option_value("debug")

        async def task_b():
            await started.wait()
            results["b"] = ConverterOptionsCtx.get_option_value("debug")
            release.set()

        await asyncio.gather(task_a(), task_b())
        assert results["a"] is True
        assert results["b"] is False

    asyncio.run(run())


def test_options_ctx_thread_isolation():
    seen = []

    def other():
        seen.append(ConverterOptionsCtx.get_option_value("debug"))

    with ConverterOptionsCtx() as options:
        options.debug = True
        thread = threading.Thread(target=other)
        thread.start()
        thread.join()
        assert ConverterOptionsCtx.get_option_value("debug") is True
    assert seen == [False]


def test_options_ctx_reentrancy():
    ctx = ConverterOptionsCtx()
    with ctx as options:
        options.debug = True
        with ctx as inner:
            assert inner.debug is True
            inner.debug = False
            assert ConverterOptionsCtx.get_option_value("debug") is False
        assert ConverterOptionsCtx.get_option_value("debug") is True
    assert ConverterOptionsCtx.get_option_value("debug") is False


def test_base_ctx_import_fallback(monkeypatch):
    from convtools import _utils as u

    monkeypatch.setattr(u, "contextvars", None)

    class FallbackOptions(u.BaseOptions):
        debug = False

    class FallbackCtx(u.BaseCtx):
        options_cls = FallbackOptions

    assert FallbackCtx._use_contextvars is False
    assert FallbackCtx.get_option_value("debug") is False
    ctx = FallbackCtx()
    with ctx as opts:
        opts.debug = True
        assert FallbackCtx.get_option_value("debug") is True
        with ctx as opts2:
            assert opts2.debug is True
            opts2.debug = False
            assert FallbackCtx.get_option_value("debug") is False
        assert FallbackCtx.get_option_value("debug") is True
    assert FallbackCtx.get_option_value("debug") is False


def test_explicit_debug_false_overrides_global(capsys):
    with ConverterOptionsCtx() as options:
        options.debug = True
        This().gen_converter(debug=False)
        assert capsys.readouterr().out == ""
        This().execute(1, debug=False)
        assert capsys.readouterr().out == ""
        This().gen_converter()
        assert capsys.readouterr().out != ""

    This().gen_converter(debug=True)
    assert capsys.readouterr().out != ""


def test_global_debug_execute_dumps_sources(monkeypatch):
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("PY_CONVTOOLS_DEBUG_DIR", tmp)
    monkeypatch.setattr(debug_dir, "debug_dir", None)
    monkeypatch.setattr(debug_dir, "dir_initialized", False)
    try:
        with ConverterOptionsCtx() as options:
            options.debug = True
            This().gen_converter()
            assert not [
                name for name in os.listdir(tmp) if name.endswith(".py")
            ]
            assert This().execute(1) == 1
            assert [name for name in os.listdir(tmp) if name.endswith(".py")]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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
    assert BaseConversion.ctx_factory is _StrictCtx
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
    prev = BaseConversion.ctx_factory
    try:
        BaseConversion.ctx_factory = dict
        ctx = This()._init_ctx()
        assert type(ctx) is dict
    finally:
        BaseConversion.ctx_factory = prev


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
