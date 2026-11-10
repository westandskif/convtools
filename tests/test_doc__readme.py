import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYTHON_FENCE_RE = re.compile(r"```python\n(.*?)\n```", re.DOTALL)


def test_readme_python_blocks():
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    matches = list(PYTHON_FENCE_RE.finditer(readme_text))
    assert matches
    for match in matches:
        start_line = readme_text.count("\n", 0, match.start(1))
        padded_source = ("\n" * start_line) + match.group(1)
        namespace = {"__name__": "__main__"}
        exec(
            compile(padded_source, "README.md", "exec"), namespace
        )  # noqa: S102
