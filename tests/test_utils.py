import pytest

from convtools import conversion as c
from convtools.base import (
    BaseConversion,
    ConverterOptions,
    ConverterOptionsCtx,
    This,
)
from convtools.utils import Code


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
    code_str = "def abc(): return 1"
    assert ctx[conversion.compile_converter("abc", code_str, ctx)]() == 1


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
