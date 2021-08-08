import pytest

from convtools.base import (
    BaseConversion,
    CodeGenerationOptions,
    CodeGenerationOptionsCtx,
    This,
)


def test_code_generation_ctx():
    with CodeGenerationOptionsCtx() as options:
        assert isinstance(options, CodeGenerationOptions)

        assert options.inline_pipes_only is False
        assert (
            CodeGenerationOptionsCtx.get_option_value("inline_pipes_only")
            is False
        )

        options.inline_pipes_only = True
        assert (
            CodeGenerationOptionsCtx.get_option_value("inline_pipes_only")
            is True
        )

        with CodeGenerationOptionsCtx() as options2:
            assert options2.inline_pipes_only is True
            assert (
                CodeGenerationOptionsCtx.get_option_value("inline_pipes_only")
                is True
            )

            options2.to_defaults("inline_pipes_only")
            assert options2.inline_pipes_only is False

            options2.inline_pipes_only = True
            options2.to_defaults()
            assert options2.inline_pipes_only is False
            assert (
                CodeGenerationOptionsCtx.get_option_value("inline_pipes_only")
                is False
            )

            assert options.inline_pipes_only is True

        assert (
            CodeGenerationOptionsCtx.get_option_value("inline_pipes_only")
            is True
        )

    assert (
        CodeGenerationOptionsCtx.get_option_value("inline_pipes_only") is False
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


def test_count_words():
    cases = [(" abc abc abc abc abcc aabc aabcc abc", "abc", 5)]

    for (where, what, expected_result) in cases:
        result = BaseConversion.count_words(where, what)
        assert result == expected_result


def test_add_sources():
    converter_callable = This().gen_converter(debug=False)

    for (
        converter_name,
        item,
    ) in converter_callable._name_to_converter.items():
        converter_callable.add_sources(converter_name, item["code_str"])
        with pytest.raises(Exception):
            converter_callable.add_sources(
                converter_name, item["code_str"] + " "
            )
