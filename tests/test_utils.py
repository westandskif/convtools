from convtools.base import CodeGenerationOptions, CodeGenerationOptionsCtx


def test_code_generation_ctx():
    with CodeGenerationOptionsCtx() as options:
        assert isinstance(options, CodeGenerationOptions)

        assert options.labeling is False
        assert CodeGenerationOptionsCtx.get_option_value("labeling") is False

        options.labeling = True
        assert CodeGenerationOptionsCtx.get_option_value("labeling") is True

        with CodeGenerationOptionsCtx() as options2:
            assert options2.labeling is True
            assert (
                CodeGenerationOptionsCtx.get_option_value("labeling") is True
            )

            options2.to_defaults("labeling")
            assert options2.labeling is False

            options2.labeling = True
            options2.to_defaults()
            assert options2.labeling is False
            assert (
                CodeGenerationOptionsCtx.get_option_value("labeling") is False
            )

            assert options.labeling is True

        assert CodeGenerationOptionsCtx.get_option_value("labeling") is True

    assert CodeGenerationOptionsCtx.get_option_value("labeling") is False
