"""Code generation helpers.

e.g.
 - recently used cache
 - options ctx manager
"""

import ast
import os
import sys
import tempfile
import threading
from ast import AST
from ast import Expr as AstExprStmt
from ast import If as AstIf
from ast import Module as AstModule
from ast import Name as AstName
from ast import expr as AstExpr
from ast import parse as ast_parse
from collections import defaultdict, deque
from importlib import import_module
from io import StringIO
from itertools import chain
from weakref import finalize


PY_VERSION = sys.version_info[:2]
if PY_VERSION == (3, 6):

    from typing import (  # type: ignore
        Any,
        Callable,
        Dict,
        Generator,
        Generic,
        GenericMeta,
        Iterator,
        List,
        MutableMapping,
        Optional,
        Tuple,
        Type,
        TypeVar,
        cast,
    )

    class BaseCtxMeta(GenericMeta):
        def __init__(
            cls, name, bases, kwargs
        ):  # pylint: disable=no-self-argument
            super().__init__(name, bases, kwargs)
            cls._ctx = threading.local()

else:
    from typing import (
        Any,
        Callable,
        Dict,
        Generator,
        Generic,
        Iterator,
        List,
        MutableMapping,
        Optional,
        Tuple,
        Type,
        TypeVar,
        cast,
    )

    class BaseCtxMeta(type):  # type: ignore
        def __init__(cls, name, bases, kwargs):
            super().__init__(name, bases, kwargs)
            cls._ctx = threading.local()


black: "Optional[Any]" = None
try:
    import black as black_  # pragma: no cover

    black = black_  # pragma: no cover
except ImportError:
    pass


class BaseOptionsMeta(type):
    def __init__(cls, name, bases, kwargs):
        super().__init__(name, bases, kwargs)
        cls._option_attrs = {
            k: v
            for k, v in kwargs.items()
            if not k.startswith("_") and k not in {"clone", "to_defaults"}
        }


class BaseOptions(object, metaclass=BaseOptionsMeta):
    """Container object, which carries current code-gen options."""

    _option_attrs: dict

    def clone(self):
        clone = self.__class__()
        for option_attr in self._option_attrs:
            setattr(clone, option_attr, getattr(self, option_attr))
        return clone

    def to_defaults(self, option_name=None):
        if option_name:
            setattr(self, option_name, self._option_attrs[option_name])
        else:
            for option_attr, value in self._option_attrs.items():
                setattr(self, option_attr, value)


OT = TypeVar("OT", bound=BaseOptions)


class BaseCtx(
    Generic[OT], metaclass=BaseCtxMeta
):  # pylint:disable=invalid-metaclass
    """Context manager to manage option objects."""

    options_cls: Type[OT]
    _ctx: threading.local

    def __enter__(self) -> OT:
        self._ctx.prev_options = getattr(self._ctx, "options", None)
        if self._ctx.prev_options:
            self._ctx.options = self._ctx.prev_options.clone()
        else:
            self._ctx.options = self.options_cls()
        return self._ctx.options

    def __exit__(self, exc_type, exc_value, tb):
        self._ctx.options = self._ctx.prev_options
        self._ctx.prev_options = None

    @classmethod
    def get_option_value(cls, option_name):
        options = getattr(cls._ctx, "options", None)
        if not options:
            options = cls.options_cls
        return getattr(options, option_name)


def format_code(s):  # pragma: no cover
    if black is None:
        return s
    try:
        s = black.format_str(
            s, mode=black.FileMode(line_length=160)  # type: ignore
        )
    except black.InvalidInput:
        pass
    return s


CODE_FORMATTING_AVAILABLE = black is not None


class Code:
    """Code builder for multi-statement code pieces."""

    __slots__ = ["lines_info", "indent_level"]

    def __init__(self):
        self.lines_info = []
        self.indent_level = 0

    def add_line(self, line: str, next_line_indent_incr: int):
        self.lines_info.append((self.indent_level, line))
        self.indent_level += next_line_indent_incr
        if self.indent_level < 0:
            raise AssertionError("negative indentation level")

    def add_code(self, code: "Code"):
        for indent_level, line in code.lines_info:
            self.lines_info.append((indent_level + self.indent_level, line))

    def incr_indent_level(self, incr: int):
        self.indent_level += incr

    def to_string(self, base_indent_level: int, single_indent: str = "    "):
        stream = StringIO()
        write_ = stream.write
        for indent_level, line in self.lines_info:
            required_indent = base_indent_level + indent_level
            _ = 0
            while _ < required_indent:
                write_(single_indent)
                _ += 1
            write_(line)
            write_("\n")
        return stream.getvalue()

    def clone(self):
        copy = Code()
        copy.lines_info = self.lines_info[:]
        copy.indent_level = self.indent_level
        return copy


class CodeParams:
    """Code-gen tree-like helper to generate assignments when needed."""

    def __init__(self):
        self.name_to_uses = defaultdict(int)
        self.name_to_code = {}
        self.name_to_deps = defaultdict(list)
        self.id_to_naive_code = {}
        self.params = []

    def naive_code(self, value, ctx):
        key = id(value)
        if key not in self.id_to_naive_code:
            self.id_to_naive_code[key] = convtools_base.NaiveConversion(
                value
            ).gen_code_and_update_ctx(None, ctx)
        return self.id_to_naive_code[key]

    def create(self, code, name, used_names=()):
        self.name_to_code[name] = code
        for used_name in used_names:
            self.name_to_deps[name].append(used_name)

    def use_param(self, name):
        self.name_to_uses[name] += 1
        self.params.append(name)

        names_to_check_deps = [name]
        visited_deps = set()
        while names_to_check_deps:
            name_ = names_to_check_deps.pop()
            visited_deps.add(name_)
            for dep_ in self.name_to_deps[name_]:
                self.name_to_uses[dep_] += 2
                if dep_ in visited_deps:
                    raise ValueError("cyclic dependency detected", name, dep_)
                names_to_check_deps.insert(0, dep_)

    def create_and_use_param(self, code, name):
        self.create(code, name)
        self.use_param(name)

    def iter_assignments(self):
        for name, code in self.name_to_code.items():
            if self.name_to_uses[name] > 1:
                yield f"{name} = {code}"

    def get_format_args(self):
        return tuple(
            self.name_to_code[name] if self.name_to_uses[name] == 1 else name
            for name in self.params
        )


class LazyDebugDir:
    """Lazy debug directory to store generated code sources."""

    def __init__(self):
        self.debug_dir = None
        self.dir_initialized = False

    def get(self) -> str:
        if self.debug_dir is None:
            self.debug_dir = os.environ.get(
                "PY_CONVTOOLS_DEBUG_DIR", None
            ) or os.path.join(tempfile.gettempdir(), "py_convtools_debug")
        return self.debug_dir

    def ensure_initialized(self):
        if not self.dir_initialized:
            os.makedirs(self.get(), exist_ok=True)
            self.dir_initialized = True


debug_dir = LazyDebugDir()


class CodePiece:
    """Piece of generated code."""

    __slots__ = (
        "converter_name",
        "code_parts",
        "abs_path",
        "is_dumped",
    )

    def __init__(self, converter_name, code_parts, abs_path, is_dumped):
        self.converter_name = converter_name
        self.code_parts = code_parts
        self.abs_path = abs_path
        self.is_dumped = is_dumped


class CodeStorage:
    """Container which stores generated code pieces.

    It allows to dump code sources on disk into a debug directory.
    """

    __slots__ = ["key_to_code_piece", "converter_names", "__weakref__"]

    def __init__(self):
        self.key_to_code_piece: "Dict[str, CodePiece]" = {}
        self.converter_names = set()
        finalize(self, drop_dumped_code, self.key_to_code_piece)

    def add_sources(self, converter_name, code_str):
        def_name = f"def {converter_name}("
        code_parts = (def_name, code_str.replace(def_name, ""))

        code_piece = self.key_to_code_piece.get(code_parts[1])
        if code_piece is not None:
            return code_piece, False

        if converter_name in self.converter_names:
            raise ValueError(
                "converter with a different code already exists",
                converter_name,
            )
        self.converter_names.add(converter_name)

        abs_path = os.path.join(
            debug_dir.get(), f"_{id(self)}_{converter_name}.py"
        )
        code_piece = self.key_to_code_piece[code_parts[1]] = CodePiece(
            converter_name, code_parts, abs_path, False
        )
        return code_piece, True

    def dump_sources(self):
        debug_dir.ensure_initialized()
        for code_piece in self.key_to_code_piece.values():
            if not code_piece.is_dumped:
                with open(code_piece.abs_path, "w", encoding="utf-8") as f:
                    f.write("".join(code_piece.code_parts))
                code_piece.is_dumped = True


def drop_dumped_code(key_to_code_piece):
    for code_piece in key_to_code_piece.values():
        if code_piece.is_dumped:
            try:
                os.remove(code_piece.abs_path)
            except FileNotFoundError:  # pragma: no cover
                pass


T = TypeVar("T")


def iter_windows(
    collection: Iterator[T], width, step
) -> Generator[Tuple[T, ...], None, None]:
    window: "deque[T]" = deque(maxlen=width)
    window_append = window.append

    index = 0
    for index, obj in enumerate(collection):
        window_append(obj)
        if index % step == 0:
            yield tuple(window)

    if window:
        index += 1
        window.popleft()
        while window:
            if index % step == 0:
                yield tuple(window)
            index += 1
            window.popleft()


obj_getattribute = object.__getattribute__


class LazyModule:
    """Lazy import helper."""

    __slots__ = ["name", "package", "_module"]

    def __init__(self, name, package=None):
        """Init self."""
        self.name = name
        self.package = package
        self._module = None

    def __getattribute__(self, name):
        module = obj_getattribute(self, "_module")
        if module is None:
            module = self._module = import_module(
                obj_getattribute(self, "name"),
                obj_getattribute(self, "package"),
            )
        return getattr(module, name)


class _None:
    """Custom None type.

    For the sake of typing AND ability to tell None from "undefined" optional
    parameters.
    """


_none = _None()


def get_builtins_dict():
    builtins = globals()["__builtins__"]
    if isinstance(builtins, dict):
        return builtins
    # for pypy
    return {
        name: getattr(builtins, name) for name in dir(builtins)
    }  # pragma: no cover


convtools_base = LazyModule("convtools._base")


def ast_are_fuzzy_equal(left, right, fuzzy_cmp, fields_to_skip=None):
    cls_left = type(left)
    if issubclass(cls_left, AST):
        if cls_left is not type(right):
            return False

        if fuzzy_cmp(left, right):
            return True

        for right_field in right._fields:  # pylint: disable=protected-access
            if fields_to_skip is not None and right_field in fields_to_skip:
                continue

            right_value_or_values = getattr(right, right_field)
            left_value_or_values = getattr(left, right_field)
            if isinstance(right_value_or_values, list):
                if len(right_value_or_values) != len(left_value_or_values):
                    return False

                for left_value, right_value in zip(
                    left_value_or_values, right_value_or_values
                ):
                    if not ast_are_fuzzy_equal(
                        left_value, right_value, fuzzy_cmp, fields_to_skip
                    ):
                        return False
            elif not ast_are_fuzzy_equal(
                left_value_or_values,
                right_value_or_values,
                fuzzy_cmp,
                fields_to_skip,
            ):
                return False

        return True

        # return type(left) is type(right)
    else:
        return left == right


class AstMergeCtx:
    """Holds last used indexes for multi-statement AST nodes."""

    __slots__ = ["_body_id_to_last_used_index"]

    def __init__(self):
        self._body_id_to_last_used_index = {}

    def use_index(self, body, index):
        body_id = id(body)
        if body_id in self._body_id_to_last_used_index:
            self._body_id_to_last_used_index[body_id] = max(
                self._body_id_to_last_used_index[body_id], index
            )
        else:
            self._body_id_to_last_used_index[body_id] = index

    def get_last_used(self, body):
        body_id = id(body)
        if body_id in self._body_id_to_last_used_index:
            return self._body_id_to_last_used_index[body_id]
        return 0

    def get_index_to_insert_to(self, body):
        body_id = id(body)
        if body_id in self._body_id_to_last_used_index:
            self._body_id_to_last_used_index[body_id] += 1
        else:
            self._body_id_to_last_used_index[body_id] = 0
        return self._body_id_to_last_used_index[body_id]


def ast_merge(
    left_body,
    right,
    fuzzy_cmp,
    ctx=None,
    _attrs_with_stmts=frozenset(["body", "orelse", "handlers", "finalbody"]),
):
    if ctx is None:
        ctx = AstMergeCtx()

    if isinstance(left_body, AstModule):
        left_body = left_body.body

    if isinstance(right, AST):
        if not hasattr(right, "body"):
            left_body.insert(ctx.get_index_to_insert_to(left_body), right)
            return

        if isinstance(right, AstModule):
            for right_stmt in right.body:
                ast_merge(left_body, right_stmt, fuzzy_cmp, ctx)
            return

        left = None
        for index_ in range(ctx.get_last_used(left_body), len(left_body)):
            left_stmt = left_body[index_]
            if ast_are_fuzzy_equal(
                left_stmt,
                right,
                fuzzy_cmp,
                fields_to_skip=_attrs_with_stmts,
            ):
                left = left_stmt
                ctx.use_index(left_body, index_)
                break

        if left is None:
            left_body.insert(ctx.get_index_to_insert_to(left_body), right)
        else:
            for (
                right_field
            ) in right._fields:  # pylint: disable=protected-access
                if right_field in _attrs_with_stmts:
                    for value in getattr(right, right_field):
                        ast_merge(
                            getattr(left_stmt, right_field),
                            value,
                            fuzzy_cmp,
                            ctx,
                        )

    else:
        raise AssertionError


def ast_parse_expr(expr, for_visitor=False):
    node = cast(AstExprStmt, ast_parse(expr).body[0])
    if for_visitor:
        return node
    return node.value


if PY_VERSION < (3, 9):
    from astunparse import unparse as _ast_unparse  # type: ignore

    backported_ast_unparse = cast(Callable[[AST], str], _ast_unparse)

    def ast_unparse(tree):
        return backported_ast_unparse(tree).strip()

else:
    from ast import unparse as ast_unparse  # pylint: disable=ungrouped-imports


class ExprPartInfo:
    """Usage info of an expression part."""

    __slots__ = ["number", "replacements"]

    def __init__(self):
        self.number = 0
        self.replacements = set()

    @classmethod
    def init_expr_part_to_info(cls):
        return defaultdict(cls)

    def to_dict(self):  # pragma: no cover
        return {"number": self.number, "replacements": self.replacements}

    def __repr__(self):
        return f"ExprPartInfo(number={self.number}, replacements={repr(self.replacements)})"


class TreeInfo:
    __slots__ = ["body", "children", "expr_part_to_info"]

    def __init__(self, body):
        self.body = body
        self.children = []
        self.expr_part_to_info = ExprPartInfo.init_expr_part_to_info()

    def to_dict(self):  # pragma: no cover
        return {
            "body": self.body,
            "children": [child.to_dict() for child in self.children],
            "expr_part_to_info": {
                expr_part: info.to_dict()
                for expr_part, info in self.expr_part_to_info.items()
            },
        }


class NodeStackItem:
    __slots__ = ["ref_count", "expr_to_node"]

    def __init__(self):
        self.ref_count = 1
        self.expr_to_node = {}

    def to_dict(self):  # pragma: no cover
        return {"ref_count": self.ref_count, "expr_to_node": self.expr_to_node}


class OptimizationVisitor(ast.NodeVisitor):
    """Builds a tree, counting expr part usages."""

    __slots__ = [
        "name_to_expr",
        "expr_to_expr_parts",
        "used_names",
        "trees",
        "tree_body_initialized",
        "dirty",
    ]

    def __init__(self, name_to_expr, expr_to_expr_parts):
        self.name_to_expr = name_to_expr
        self.expr_to_expr_parts = expr_to_expr_parts
        self.used_names = set()
        self.trees = [TreeInfo(None)]
        self.tree_body_initialized = False
        self.dirty = None

    def generic_visit(
        self,
        node,
        _attrs_with_stmts=frozenset(
            ["body", "orelse", "handlers", "finalbody"]
        ),
    ):
        """Called if no explicit visitor function exists for a node."""
        for field in node._fields:  # pylint: disable=protected-access
            value = getattr(node, field)
            if isinstance(value, list):
                if (
                    not self.tree_body_initialized
                    and field in _attrs_with_stmts
                ):
                    self.trees[-1].body = value
                    self.tree_body_initialized = True

                for item in value:
                    if isinstance(item, AST):  # pragma: no cover
                        self.visit(item)
            elif isinstance(value, AST):
                self.visit(value)

    def visit_If(self, node: AstIf):
        self.dirty = False
        self.visit(node.test)
        if self.dirty:
            self.dirty = False

            tree_info = TreeInfo(node.body)
            self.trees[-1].children.append(tree_info)
            self.trees.append(tree_info)
            for l_node in node.body:
                self.visit(l_node)
            self.trees.pop()

            tree_info = TreeInfo(node.orelse)
            self.trees[-1].children.append(tree_info)
            self.trees.append(tree_info)
            for l_node in node.orelse:
                self.visit(l_node)
            self.trees.pop()

        else:
            prev_mapping = self.trees[-1].expr_part_to_info
            body_mapping = self.trees[-1].expr_part_to_info = (
                ExprPartInfo.init_expr_part_to_info()
            )
            for l_node in node.body:
                self.visit(l_node)

            orelse_mapping = self.trees[-1].expr_part_to_info = (
                ExprPartInfo.init_expr_part_to_info()
            )
            for l_node in node.orelse:
                self.visit(l_node)
            self.trees[-1].expr_part_to_info = prev_mapping

            for key in set(chain(body_mapping, orelse_mapping)):
                body_info = body_mapping[key]
                orelse_info = orelse_mapping[key]
                prev_info = prev_mapping[key]
                prev_info.number += max(
                    body_info.number,
                    orelse_info.number,
                )
                prev_info.replacements.update(body_info.replacements)
                prev_info.replacements.update(orelse_info.replacements)

    def visit_Name(self, node):
        if node.id.startswith("n_"):
            self.used_names.add(node.id)
            expr_part_to_info = self.trees[-1].expr_part_to_info
            expr = self.name_to_expr[node.id]
            expr_part_to_info[expr].replacements.add(node.id)

            stack = [expr]
            while stack:
                expr = stack.pop()
                expr_part_to_info[expr].number += 1
                stack.extend(self.expr_to_expr_parts[expr])

            self.dirty = True


class NodeReplacerByCode(ast.NodeTransformer):
    """Replaces parts of expressions with another AST nodes."""

    __slots__ = ["expr_to_node_stack"]

    def __init__(self, expr_to_node_stack: List[NodeStackItem]):
        self.expr_to_node_stack = expr_to_node_stack

    def visit_Constant(self, node):
        return node

    def generic_visit(self, node):
        if isinstance(node, AstExpr):
            code = ast_unparse(node)
            for item in self.expr_to_node_stack:
                expr_to_node = item.expr_to_node
                if code in expr_to_node:
                    return expr_to_node[code]

        # copy of underlying implementation
        for (
            field
        ) in (
            node._fields  # pylint: disable=protected-access
        ):  # pragma: no cover
            old_value = getattr(node, field)
            if isinstance(old_value, list):
                new_values = []
                for value in old_value:
                    if isinstance(value, AST):
                        new_value = self.visit(value)
                        if new_value is None:
                            continue
                        elif not isinstance(new_value, AST):
                            new_values.extend(new_value)
                            continue
                    new_values.append(new_value)
                old_value[:] = new_values
            elif isinstance(old_value, AST):
                new_node = self.visit(old_value)
                if new_node is None:
                    delattr(node, field)
                else:
                    setattr(node, field, new_node)
        return node


class OptimizationReplacerByName(ast.NodeTransformer):
    """Transforms AST, replacing variables with AST nodes."""

    __slots__ = ["name_to_new_node"]

    def __init__(self, name_to_new_node):
        self.name_to_new_node = name_to_new_node

    def visit_Name(self, node):
        if node.id in self.name_to_new_node:
            return self.name_to_new_node[node.id]
        return node

    def generic_visit(self, node):  # pragma: no cover
        # copy of underlying implementation
        for field in node._fields:  # pylint: disable=protected-access
            old_value = getattr(node, field)
            if isinstance(old_value, list):
                new_values = []
                for value in old_value:
                    if isinstance(value, AST):
                        new_value = self.visit(value)
                        if new_value is None:
                            continue
                        elif not isinstance(new_value, AST):
                            new_values.extend(new_value)
                            continue
                    new_values.append(new_value)
                old_value[:] = new_values
            elif isinstance(old_value, AST):
                new_node = self.visit(old_value)
                if new_node is None:
                    delattr(node, field)
                else:
                    setattr(node, field, new_node)
        return node


class CodeOptimizer:
    """Optimizes common subexpressions."""

    __slots__ = [
        "var_name",
        "replacement_to_expr",
        "expr_to_expr_parts",
        "expr_part_to_parents",
        "expr_to_number",
    ]

    def __init__(self, var_name):
        self.var_name = var_name
        self.replacement_to_expr = {}
        self.expr_to_expr_parts = defaultdict(set)
        self.expr_part_to_parents = defaultdict(set)
        self.expr_to_number = {}

    def use_expression(self, expression_code):
        if (
            self.var_name not in expression_code
            or self.var_name == expression_code
        ):
            return expression_code

        while expression_code.startswith("(") and expression_code.endswith(
            ")"
        ):
            expression_code = expression_code[1:-1]

        if expression_code not in self.expr_to_expr_parts:
            paths: "List[Tuple[AST, ...]]" = [
                (ast_parse_expr(expression_code),)
            ]
            while paths:
                path = paths.pop()
                node = path[-1]
                if isinstance(node, AstName) and node.id == self.var_name:
                    expr_parts = [
                        ast_unparse(path[index]) if index else expression_code
                        for index in range(len(path) - 1)
                    ]
                    for index in range(len(expr_parts) - 1):
                        self.expr_to_expr_parts[expr_parts[index]].add(
                            expr_parts[index + 1]
                        )
                        self.expr_part_to_parents[expr_parts[index + 1]].add(
                            expr_parts[index]
                        )
                else:
                    for (
                        field
                    ) in node._fields:  # pylint: disable=protected-access
                        child_or_children = getattr(node, field)
                        if isinstance(child_or_children, AST):
                            paths.append(path + (child_or_children,))
                        elif isinstance(child_or_children, list):
                            for child in child_or_children:
                                paths.append(path + (child,))

        if expression_code not in self.expr_to_number:
            self.expr_to_number[expression_code] = len(self.expr_to_number)
        replacement = f"n_{self.expr_to_number[expression_code]}__{len(self.replacement_to_expr)}"
        self.replacement_to_expr[replacement] = expression_code
        return replacement

    def get_expr_depth_below(self, expr_part):
        stack = [(expr_part, 0)]
        max_depth = -1
        while stack:
            expr_part, depth = stack.pop()
            expr_parts = self.expr_to_expr_parts[expr_part]
            if expr_parts:
                for l_expr_part in expr_parts:
                    stack.append((l_expr_part, depth + 1))
            elif depth > max_depth:
                max_depth = depth
        return max_depth

    def get_replacement_to_node(self, tree):
        visitor = OptimizationVisitor(
            self.replacement_to_expr,
            self.expr_to_expr_parts,
        )
        visitor.visit(tree)

        paths_to_process: "deque[Tuple[TreeInfo, ...]]" = deque(
            [(visitor.trees[0],)]
        )
        while paths_to_process:
            l_path = paths_to_process.popleft()
            l_children = l_path[-1].children
            if l_children:
                for l_tree_info in l_children:
                    paths_to_process.append(l_path + (l_tree_info,))
                continue

            for index in range(len(l_path) - 1, 0, -1):
                child_expr_part_to_info = l_path[index].expr_part_to_info
                for expr_part_code, info in child_expr_part_to_info.items():
                    if info.number == 0:
                        continue
                    for parent_index in range(index):
                        if (
                            expr_part_code
                            in l_path[parent_index].expr_part_to_info
                        ):
                            parent_info = l_path[
                                parent_index
                            ].expr_part_to_info[expr_part_code]
                            parent_info.number += info.number
                            info.number = 0
                            break

        # breakpoint()  # pp visitor.trees[0].to_dict()
        number_of_replacements = 0
        replacement_to_node = {}
        tree_info_to_process = deque([visitor.trees[0]])
        body_id_to_insert_index: "MutableMapping[int, int]" = defaultdict(int)
        expr_to_node_stack: "List[NodeStackItem]" = []
        node_replacer_by_code = NodeReplacerByCode(expr_to_node_stack)

        while tree_info_to_process:
            tree_info = tree_info_to_process.pop()
            expr_to_node_stack.append(NodeStackItem())
            for l_tree_info in tree_info.children:
                tree_info_to_process.append(l_tree_info)
                expr_to_node_stack[-1].ref_count += 1

            replacements = set()
            for expr_part_code, info in sorted(
                tree_info.expr_part_to_info.items(),
                key=lambda item: (
                    item[1].number < 2,
                    (
                        -1
                        if item[1].number < 2
                        else self.get_expr_depth_below(item[0])
                    ),
                ),
            ):
                replacements.update(info.replacements)

                if expr_part_code == self.var_name or info.number < 2:
                    continue

                parents = self.expr_part_to_parents[expr_part_code]
                if parents and all(
                    info.number
                    == tree_info.expr_part_to_info[
                        parent_expr_part_code
                    ].number
                    for parent_expr_part_code in parents
                ):
                    continue

                local_var_name = f"_r{number_of_replacements}_"
                number_of_replacements += 1
                tree_info.body.insert(
                    body_id_to_insert_index[id(tree_info.body)],
                    node_replacer_by_code.visit(
                        ast_parse(f"{local_var_name} = {expr_part_code}")
                    ).body[0],
                )
                body_id_to_insert_index[id(tree_info.body)] += 1

                expr_to_node_stack[-1].expr_to_node[expr_part_code] = (
                    ast_parse_expr(local_var_name)
                )

            for replacement in replacements:
                expr = self.replacement_to_expr[replacement]
                expr_node = None
                for item in expr_to_node_stack:
                    l_expr_to_node = item.expr_to_node
                    if expr in l_expr_to_node:
                        expr_node = l_expr_to_node[expr]
                        break

                if expr_node is None:
                    expr_node = expr_to_node_stack[-1].expr_to_node[expr] = (
                        node_replacer_by_code.visit(
                            ast_parse_expr(expr, for_visitor=True)
                        ).value
                    )
                replacement_to_node[replacement] = expr_node

            expr_to_node_stack[-1].ref_count -= 1
            while expr_to_node_stack and not expr_to_node_stack[-1].ref_count:
                expr_to_node_stack.pop()

        return replacement_to_node
