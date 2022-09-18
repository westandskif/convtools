import pytest

from convtools import conversion as c
from convtools.base import (
    BaseConversion,
    CodeGenerationOptions,
    CodeGenerationOptionsCtx,
    This,
)
from convtools.utils import Code


def test_code_generation_ctx():
    with CodeGenerationOptionsCtx() as options:
        assert isinstance(options, CodeGenerationOptions)

        assert options.reducers_run_stage is None
        assert (
            CodeGenerationOptionsCtx.get_option_value("reducers_run_stage")
            is None
        )

        options.reducers_run_stage = True
        assert (
            CodeGenerationOptionsCtx.get_option_value("reducers_run_stage")
            is True
        )

        with CodeGenerationOptionsCtx() as options2:
            assert options2.reducers_run_stage is True
            assert (
                CodeGenerationOptionsCtx.get_option_value("reducers_run_stage")
                is True
            )

            options2.to_defaults("reducers_run_stage")
            assert options2.reducers_run_stage is None

            options2.reducers_run_stage = True
            options2.to_defaults()
            assert options2.reducers_run_stage is None
            assert (
                CodeGenerationOptionsCtx.get_option_value("reducers_run_stage")
                is None
            )

            assert options.reducers_run_stage is True

        assert (
            CodeGenerationOptionsCtx.get_option_value("reducers_run_stage")
            is True
        )

    assert (
        CodeGenerationOptionsCtx.get_option_value("reducers_run_stage") is None
    )


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
    for (where, word, with_what, expected_result) in cases:
        result = BaseConversion.replace_word(where, word, with_what)
        assert result == expected_result


def test_add_sources():
    converter = This().gen_converter(debug=False)
    code_storage = converter.__globals__["__convtools__code_storage"]
    for (
        converter_name,
        code_piece,
    ) in code_storage.name_to_code_piece.items():
        code_storage.add_sources(converter_name, code_piece.code_str)
        with pytest.raises(Exception):
            code_storage.add_sources(converter_name, code_piece.code_str + " ")

    converter = c.escaped_string("abc + 1").gen_converter(debug=True)
    with pytest.raises(NameError):
        converter(None)
    converter.__globals__["__convtools__code_storage"].dump_sources()


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
    assert not c({"a": 1}).item("a").ignores_input()
    assert not c({"a": 1}).item(c.item("a")).ignores_input()
    assert not c.inline_expr("{}()").pass_args(c.this).ignores_input()
    assert not c.aggregate({"a": 1}).ignores_input()
    assert not c.this.add_label("a").ignores_input()
    assert not c(int).call(c.item(0)).ignores_input()


def test_code():
    code = Code()
    code.add_line("a = 1", 0, "1")
    assert code.as_expression() == "1"
    code.add_line("b = 2", 0, "2")
    assert code.as_expression() is None
