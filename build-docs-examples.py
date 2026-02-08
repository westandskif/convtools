import os
from glob import glob
import subprocess
from hashlib import sha256

from convtools.contrib.tables import Table
from convtools import conversion as c

DOCS_ROOT = "./docs"

RAW_EXAMPLES_DIR = os.path.join(DOCS_ROOT, "examples-raw")
MD_EXAMPLES_DIRNAME = os.path.join(DOCS_ROOT, "examples-md")

LAST_BUILD_LOG = os.path.join(MD_EXAMPLES_DIRNAME, ".last_build.csv")

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
    yield from glob(os.path.join(RAW_EXAMPLES_DIR, "**/*.py"), recursive=True)


def indent_lines(s, indent):
    return "\n".join(f"{indent}{line}" for line in s.splitlines())


def write_md_example(raw_example_path, output):
    md_example_path = (
        "%s.md"
        % raw_example_path.replace(
            RAW_EXAMPLES_DIR, MD_EXAMPLES_DIRNAME
        ).rsplit(".", 1)[0]
    )
    with open(raw_example_path, "r") as f_in:
        new_content = f"""```python
{f_in.read()}
```
"""

    result = subprocess.run(
        ["sha256sum", md_example_path], capture_output=True
    )
    if result.returncode == 0:
        output = result.stdout.decode("utf-8")
        if (
            output
            and output.split(" ", 1)[0]
            == sha256(new_content.encode("utf-8")).hexdigest()
        ):
            print(
                f"CHECKED EXAMPLE: {get_md_path_to_include(md_example_path)}"
            )
            return

    with open(ensure_dir(md_example_path), "w") as f_out:
        f_out.write(new_content)
    print(f"BUILT EXAMPLE  : {get_md_path_to_include(md_example_path)}")


def build_example(path):
    result = subprocess.run(["python", path], capture_output=True)
    if result.returncode != 0:
        raise AssertionError(f"failed for {path}")
    write_md_example(
        raw_example_path=path, output=result.stdout.decode("utf-8")
    )


def build_examples():
    if os.path.exists(LAST_BUILD_LOG):
        path_to_last_build_time = {
            row["path"]: row["mtime"]
            for row in Table.from_csv(LAST_BUILD_LOG, header=True)
            .update(mtime=c.col("mtime").as_type(float))
            .into_iter_rows(dict)
        }
    else:
        path_to_last_build_time = {}

    logs = []
    for path in get_raw_examples():
        mtime = os.path.getmtime(path)
        logs.append({"path": path, "mtime": mtime})
        if (
            path in path_to_last_build_time
            and mtime <= path_to_last_build_time[path]
        ):
            print(f"UP TO DATE: {path}")
            continue
        build_example(path)

    Table.from_rows(logs).into_csv(ensure_dir(LAST_BUILD_LOG))


if __name__ == "__main__":
    build_examples()
