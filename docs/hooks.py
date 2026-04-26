"""MkDocs build hooks."""

from pathlib import Path

from convtools import __version__


LLMS_EXAMPLES = {
    "{llms_example_scalar}": "llms__scalar.py",
    "{llms_example_iter_filter}": "llms__iter_filter.py",
    "{llms_example_aggregation}": "llms__aggregation.py",
    "{llms_example_join}": "llms__join.py",
    "{llms_example_table}": "llms__table.py",
}


def on_config(config):
    """Render package metadata placeholders in plugin configuration."""
    llmstxt = config["plugins"].get("llmstxt")
    if llmstxt is None:
        return config

    description = llmstxt.config.get("markdown_description")
    if description:
        examples_root = Path(config["docs_dir"]) / "examples-raw"
        for placeholder, filename in LLMS_EXAMPLES.items():
            description = description.replace(
                placeholder,
                (examples_root / filename).read_text(encoding="utf-8").rstrip(),
            )
        llmstxt.config["markdown_description"] = description.replace(
            "{convtools_version}", __version__
        )
    return config
