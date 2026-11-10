import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from glob import glob

DOCS_ROOT = "./docs"

RAW_EXAMPLES_DIR = os.path.join(DOCS_ROOT, "examples-raw")
MD_EXAMPLES_DIRNAME = os.path.join(DOCS_ROOT, "examples-md")

_ensured_dirs = set()


def ensure_dir(file_path):
    dir_to_ensure = os.path.dirname(file_path)
    if dir_to_ensure in _ensured_dirs:
        return file_path
    _ensured_dirs.add(dir_to_ensure)
    os.makedirs(dir_to_ensure, exist_ok=True)
    return file_path


def get_md_path_to_include(file_path):
    return os.path.relpath(file_path, DOCS_ROOT)


def get_raw_examples():
    return sorted(
        glob(os.path.join(RAW_EXAMPLES_DIR, "**/*.py"), recursive=True)
    )


def get_md_example_path(raw_example_path):
    return (
        "%s.md"
        % raw_example_path.replace(
            RAW_EXAMPLES_DIR, MD_EXAMPLES_DIRNAME
        ).rsplit(".", 1)[0]
    )


def is_llms_example(path):
    return os.path.basename(path).startswith("llms__")


def format_md_example(raw_source, output):
    content = f"""```python
{raw_source}
```
"""
    rendered_output = output.strip()
    if rendered_output:
        content += f"""
Printed output:

```python
{rendered_output}
```
"""
    return content


def run_raw_example(path):
    abs_path = os.path.abspath(path)
    result = subprocess.run(
        [sys.executable, abs_path],
        capture_output=True,
        check=False,
        cwd=tempfile.gettempdir(),
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise AssertionError(f"failed for {path}:\n{stderr}")
    return path, result.stdout.decode("utf-8")


def write_md_example(raw_example_path, output):
    md_example_path = get_md_example_path(raw_example_path)
    with open(raw_example_path, "r", encoding="utf-8") as f_in:
        new_content = format_md_example(f_in.read(), output)

    if os.path.exists(md_example_path):
        with open(md_example_path, "r", encoding="utf-8") as f_existing:
            if f_existing.read() == new_content:
                print(
                    f"CHECKED EXAMPLE: {get_md_path_to_include(md_example_path)}"
                )
                return

    with open(ensure_dir(md_example_path), "w", encoding="utf-8") as f_out:
        f_out.write(new_content)
    print(f"BUILT EXAMPLE  : {get_md_path_to_include(md_example_path)}")


def prune_orphaned_md_examples(expected_md_paths):
    for md_path in sorted(
        glob(os.path.join(MD_EXAMPLES_DIRNAME, "**/*.md"), recursive=True)
    ):
        if os.path.normpath(md_path) not in expected_md_paths:
            os.remove(md_path)
            print(f"REMOVED ORPHAN : {get_md_path_to_include(md_path)}")


def build_examples():
    raw_paths = get_raw_examples()
    with ThreadPoolExecutor() as pool:
        results = list(pool.map(run_raw_example, raw_paths))
    for path, stdout in results:
        if is_llms_example(path):
            print(f"CHECKED LLMS EXAMPLE (no md): {path}")
            continue
        write_md_example(raw_example_path=path, output=stdout)

    prune_orphaned_md_examples(
        {
            os.path.normpath(get_md_example_path(path))
            for path in raw_paths
            if not is_llms_example(path)
        }
    )


if __name__ == "__main__":
    build_examples()
