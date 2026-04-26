import argparse
import ast
import sys
from pathlib import Path


ROOT = Path(__file__).parent
AGGREGATIONS_SOURCE = ROOT / "src" / "convtools" / "_aggregations.py"
README = ROOT / "README.md"
AGGREGATIONS_DOC = ROOT / "docs" / "aggregations.md"

START_MARKER = "<!-- reducer-inventory:start -->"
END_MARKER = "<!-- reducer-inventory:end -->"


def get_reduce_func_assignments():
    module = ast.parse(AGGREGATIONS_SOURCE.read_text())
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == "ReduceFuncs":
            source_lines = AGGREGATIONS_SOURCE.read_text().splitlines()
            reducers = []
            missing_descriptions = []
            for child in node.body:
                if not isinstance(child, ast.Assign):
                    continue
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        description = get_preceding_public_comment(
                            source_lines, child.lineno
                        )
                        if not description:
                            missing_descriptions.append(target.id)
                        reducers.append((target.id, description))
            if missing_descriptions:
                raise AssertionError(
                    "missing ReduceFuncs descriptions: {}".format(
                        ", ".join(missing_descriptions)
                    )
                )
            return reducers
    raise AssertionError("could not find ReduceFuncs class")


def get_preceding_public_comment(source_lines, lineno):
    comments = []
    line_index = lineno - 2
    while line_index >= 0:
        line = source_lines[line_index].strip()
        if not line.startswith("#:"):
            break
        comments.append(line[2:].strip())
        line_index -= 1
    comments.reverse()
    return " ".join(comment for comment in comments if comment)


def split_reducers(reducers):
    value_reducers = []
    dict_reducers = []
    for name, description in reducers:
        if name.startswith("Dict"):
            dict_reducers.append((name, description))
        else:
            value_reducers.append((name, description))
    return sorted(value_reducers), sorted(dict_reducers)


def as_inline_code_list(reducers):
    names = [name for name, _description in reducers]
    return ", ".join("`{}`".format(name) for name in names)


def escape_table_cell(value):
    return value.replace("|", "\\|")


def make_table(reducers):
    rows = [
        "| Reducer | Description |",
        "| ------- | ----------- |",
    ]
    for name, description in reducers:
        rows.append(
            "| `{}` | {} |".format(name, escape_table_cell(description))
        )
    return "\n".join(rows)


def make_readme_block(reducers):
    value_reducers, dict_reducers = split_reducers(reducers)
    return "\n".join(
        [
            START_MARKER,
            "Built-in reducers are exposed as `c.ReduceFuncs.*`:",
            "",
            "* Value reducers: {}".format(as_inline_code_list(value_reducers)),
            "* Dict reducers: {}".format(as_inline_code_list(dict_reducers)),
            "",
            "Dict reducers aggregate into dictionaries whose values are "
            "reduced per key. For reducer arguments, defaults, `None` "
            "handling, and examples, see [Aggregations]"
            "(https://convtools.readthedocs.io/en/latest/aggregations/"
            "#creducefuncs).",
            "",
            "You can also define custom reducers with `c.reduce` by passing any "
            "two-argument reduce function.",
            END_MARKER,
        ]
    )


def make_docs_block(reducers):
    value_reducers, dict_reducers = split_reducers(reducers)
    return "\n".join(
        [
            START_MARKER,
            "The public reducer inventory is generated from `c.ReduceFuncs`:",
            "",
            "##### Value reducers",
            "",
            make_table(value_reducers),
            "",
            "##### Dict reducers",
            "",
            make_table(dict_reducers),
            "",
            "Dict reducers aggregate into dictionaries whose values are reduced per key. "
            "See [Reducers API](#reducers-api) below for argument counts, defaults, "
            "`None` handling, `initial=` support, and edge-case notes.",
            "",
            "You can also define custom reducers with `c.reduce` by passing any "
            "two-argument reduce function, for example "
            "`c.reduce(lambda a, b: a + b, c.item(\"amount\"), initial=0)`.",
            END_MARKER,
        ]
    )


def replace_block(path, block):
    content = path.read_text()
    start = content.index(START_MARKER)
    end = content.index(END_MARKER, start) + len(END_MARKER)
    return content[:start] + block + content[end:]


def update_file(path, block, check):
    old_content = path.read_text()
    new_content = replace_block(path, block)
    if old_content == new_content:
        return True
    if check:
        print("{} reducer inventory is stale".format(path), file=sys.stderr)
        return False
    path.write_text(new_content)
    print("updated {}".format(path))
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if generated reducer inventories are stale",
    )
    args = parser.parse_args()

    reducers = get_reduce_func_assignments()
    ok = True
    ok &= update_file(README, make_readme_block(reducers), args.check)
    ok &= update_file(AGGREGATIONS_DOC, make_docs_block(reducers), args.check)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
