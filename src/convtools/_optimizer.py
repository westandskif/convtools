"""Optimizers for generated python code."""

import ast
from ast import AST
from ast import Assign as AstAssign
from ast import Load as AstLoad
from ast import Module as AstModule
from ast import Name as AstName
from ast import Store as AstStore
from ast import expr as AstExpr
from ast import parse as ast_parse
from collections import defaultdict, deque
from enum import Enum, auto
from itertools import chain
from typing import Any, Callable, Dict, Tuple

from ._utils import PY_VERSION, ast_unparse


class IterMode(Enum):
    """Mode for iterating over list values in visit_by_attr."""

    ALL = auto()
    FIRST_ONLY = auto()
    ALL_BUT_FIRST = auto()


def ast_are_fuzzy_equal(left, right, fuzzy_cmp, fields_to_skip=frozenset()):
    """Check if two AST nodes are fuzzy-equal using the provided comparison."""
    cls_left = type(left)
    if issubclass(cls_left, AST):
        if cls_left is not type(right):  # pylint: disable=unidiomatic-typecheck
            return False

        if fuzzy_cmp(left, right):
            return True

        for field in right._fields:  # pylint: disable=protected-access
            if field in fields_to_skip:
                continue

            right_values = getattr(right, field)
            left_values = getattr(left, field)

            if isinstance(right_values, list):
                if len(right_values) != len(left_values):
                    return False
                for left_item, right_item in zip(left_values, right_values):
                    if not ast_are_fuzzy_equal(
                        left_item, right_item, fuzzy_cmp, fields_to_skip
                    ):
                        return False
            elif not ast_are_fuzzy_equal(
                left_values, right_values, fuzzy_cmp, fields_to_skip
            ):
                return False

        return True

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
        index_ = ctx.get_last_used(left_body)
        length = len(left_body)
        while index_ < length:
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
            index_ += 1

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


def node_from_node_path(path):
    if isinstance(path[1], str):
        return getattr(path[0], path[1])

    return path[1]


def replace_node_by_node_path(path, new_node):
    if isinstance(path[1], str):
        setattr(path[0], path[1], new_node)
    else:
        body, item_to_search = path
        for index, item in enumerate(body):
            if item is item_to_search:
                body[index] = new_node
                return
        raise AssertionError("bug")


class ExprInfo:
    """ast expression usage info."""

    __slots__ = [
        "node_paths",
        "number",
        "children",
    ]

    def __init__(self):
        self.node_paths = []
        self.number = 0
        self.children = []

    def to_dict(self):  # pragma: no cover
        return {
            "node_paths": self.node_paths,
            "number": self.number,
            # "children": self.children
            # and [child.to_dict() for child in self.children],
        }


class CodeLayer:
    """Stores info about ast node bodies (lists of statements)."""

    __slots__ = [
        "body",
        "opt_above",
        "opt_below",
        "expr_code_to_info",
        "children",
        "propagate_with_coeff",
        "_inserted_optimizations",
    ]

    def __init__(self, body, opt_above, opt_below):
        self.body = body
        self.opt_above = opt_above
        self.opt_below = opt_below
        self.expr_code_to_info: "Dict[str, ExprInfo]" = defaultdict(ExprInfo)
        self.children = []
        self.propagate_with_coeff = None
        self._inserted_optimizations = 0

    def to_dict(self):  # pragma: no cover
        return {
            "body": self.body,
            "opt_above": self.opt_above,
            "opt_below": self.opt_below,
            "propagate_with_coeff": self.propagate_with_coeff,
            "expr_code_to_info": {
                expr_code: info.to_dict()
                for expr_code, info in self.expr_code_to_info.items()
            },
            "children": [child.to_dict() for child in self.children],
        }

    def track_expr_chain(self, expr_code_tree):
        expr_code_to_info = self.expr_code_to_info

        for expr_code, l_expr_info in expr_code_tree.items():
            if expr_code in expr_code_to_info:
                expr_info = expr_code_to_info[expr_code]
                expr_info.node_paths.extend(l_expr_info.node_paths)
                expr_info.number += l_expr_info.number
            else:
                expr_code_to_info[expr_code] = l_expr_info

    def insert_optimization(self, node):
        item_to_search = self.opt_above or self.opt_below
        if item_to_search:
            for i, item in enumerate(self.body):
                if item is item_to_search:
                    index = (
                        i
                        if self.opt_above
                        else i + 1 + self._inserted_optimizations
                    )
                    break
            else:
                raise AssertionError("bug")
        else:
            index = self._inserted_optimizations
        self._inserted_optimizations += 1
        self.body.insert(index, node)


class NewLayerCtx:
    """Manages code layers of OptimizationStage1."""

    __slots__ = ["visitor", "code_layer", "prev"]

    def __init__(self, visitor, code_layer):
        self.visitor = visitor
        self.code_layer = code_layer

    def __enter__(self):
        visitor = self.visitor
        self.prev = visitor.parent_layer, visitor.current_layer
        visitor.current_layer.children.append(self.code_layer)
        visitor.parent_layer = visitor.current_layer
        visitor.current_layer = self.code_layer
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.visitor.parent_layer, self.visitor.current_layer = self.prev


class NoTrackNumbersCtx:
    """Stops OptimizationStage1 expr number counting."""

    __slots__ = [
        "visitor",
        "prev_mode_track_numbers",
    ]

    def __init__(self, visitor):
        self.visitor = visitor
        self.prev_mode_track_numbers = None

    def __enter__(self):
        visitor = self.visitor
        self.prev_mode_track_numbers = visitor.mode_track_numbers
        visitor.mode_track_numbers = False

    def __exit__(self, exc_type, exc_value, exc_traceback):
        visitor = self.visitor
        visitor.mode_track_numbers = self.prev_mode_track_numbers


class ExprChainCollector:
    """Snapshots OptimizationStage1 found expression chains."""

    __slots__ = [
        "visitor",
        "prev_mode_collect_expr_chain",
        "prev_parent_expr_code",
        "prev_expr_code_tree",
        "expr_code_tree",
    ]

    def __init__(self, visitor):
        self.visitor = visitor

    def start(self):
        visitor = self.visitor
        if visitor.mode_collect_expr_chain:
            raise AssertionError("bug")

        self.prev_mode_collect_expr_chain = visitor.mode_collect_expr_chain

        self.prev_parent_expr_code = visitor.parent_expr_code
        self.prev_expr_code_tree = visitor.expr_code_tree

        visitor.mode_collect_expr_chain = True
        visitor.parent_expr_code = None
        visitor.expr_code_tree = defaultdict(ExprInfo)

    def stop(self):
        visitor = self.visitor
        visitor.mode_collect_expr_chain = self.prev_mode_collect_expr_chain

        self.expr_code_tree = visitor.expr_code_tree

        visitor.parent_expr_code = self.prev_parent_expr_code
        visitor.expr_code_tree = self.prev_expr_code_tree


class OptimizationStage1(ast.NodeVisitor):
    """Common sub-expression elimination by ast node visitor."""

    __slots__ = [
        "tree",
        "_consumed_exprs",
        "current_layer",
        "expr_code_tree",
        "exprs_to_optimize",
        "mode_collect_expr_chain",
        "mode_track_numbers",
        "no_side_effects_test",
        "condition_is_transparent_test",
        "node_path",
        "parent_expr_code",
        "parent_layer",
        "root_layer",
        "stack_expr_visibilities",
        "methods",
        "global_expr_code_to_child_code",
        "global_expr_code_to_parent_code",
        "_node_code_cache",
        "_side_effects",
    ]

    def __init__(self):
        self.exprs_to_optimize = set()
        self._consumed_exprs = set()
        self.methods: Dict[str, Callable] = defaultdict(
            lambda: self.generic_visit
        )
        self._node_code_cache = {}
        self.global_expr_code_to_child_code = defaultdict(set)
        self.global_expr_code_to_parent_code = defaultdict(set)
        for name in dir(self):
            if name.startswith("visit_"):
                self.methods[name] = getattr(self, name)
        self._side_effects = 0

    def _init_optimization_params(
        self, tree, no_side_effects_test, condition_is_transparent_test
    ):
        self.tree = tree
        self.no_side_effects_test = no_side_effects_test
        self.condition_is_transparent_test = condition_is_transparent_test

        self.root_layer = CodeLayer(self.tree.body, None, None)
        self.parent_layer = self.root_layer
        self.current_layer = self.root_layer

        self.node_path: "Tuple[Any, Any]" = (None, None)

        self.mode_collect_expr_chain = None
        self.mode_track_numbers = True

        self.parent_expr_code = None
        self.expr_code_tree = defaultdict(ExprInfo)
        self.stack_expr_visibilities = None

    def use_expression(self, expression_code):
        if expression_code not in self._consumed_exprs:
            self._consumed_exprs.add(expression_code)
            # a and (a + 1) -> a and a + 1
            # or simply a/2 -> a / 2
            self.exprs_to_optimize.add(ast_unparse(ast_parse(expression_code)))
        return expression_code

    def run(self, tree, no_side_effects_test, condition_is_transparent_test):
        self._init_optimization_params(
            tree, no_side_effects_test, condition_is_transparent_test
        )
        self.raw_visit(self.tree)
        self._propagate_expression_counts()
        self._apply_common_subexpression_elimination()

    def _propagate_expression_counts(self):
        """Propagate expression counts from child layers to parents."""
        if self.root_layer is None:
            raise AssertionError("bug")

        paths_to_process: "deque[Tuple[CodeLayer, ...]]" = deque(
            [(self.root_layer,)]
        )
        while paths_to_process:
            layer_path = paths_to_process.popleft()
            layer_children = layer_path[-1].children
            if layer_children:
                self_in_the_middle = False
                propagation_is_possible = True
                for code_layer in layer_children:
                    if code_layer.propagate_with_coeff is None:
                        propagation_is_possible = False

                    if propagation_is_possible:
                        self_in_the_middle = True
                        paths_to_process.append(layer_path + (code_layer,))
                    else:
                        paths_to_process.append((code_layer,))
                if self_in_the_middle:
                    continue

            for index in range(len(layer_path) - 1, 0, -1):
                current_child = layer_path[index]
                current_parent = layer_path[index - 1]
                for expr_code, info in current_child.expr_code_to_info.items():
                    parent_info = current_parent.expr_code_to_info[expr_code]
                    parent_info.number += info.number * (
                        current_child.propagate_with_coeff or 0
                    )
                    parent_info.children.append(info)

                    if info.children:
                        parent_info.children.extend(info.children)

    def _apply_common_subexpression_elimination(self):
        """Replace duplicate expressions with temporary variables."""
        code_layers_to_process = deque([self.root_layer])
        number_of_replacements = 0

        while code_layers_to_process:
            layer = code_layers_to_process.popleft()
            for child_layer in layer.children:
                code_layers_to_process.append(child_layer)

            exprs_to_optimize = sorted(
                [
                    (self.get_expr_depth_below(expr_code), expr_code, info)
                    for expr_code, info in layer.expr_code_to_info.items()
                    if info.number > 1
                ]
            )
            max_idx_expr_to_optimize = len(exprs_to_optimize) - 1
            for i in range(max_idx_expr_to_optimize + 1):
                _, expr_code, info = exprs_to_optimize[i]

                if info.children:
                    for child_info in info.children:
                        child_info.number = -1

                if i < max_idx_expr_to_optimize:
                    _, next_expr_code, next_info = exprs_to_optimize[i + 1]
                    if (
                        info.number == next_info.number
                        and next_expr_code
                        in self.global_expr_code_to_parent_code[expr_code]
                        and len(
                            self.global_expr_code_to_parent_code[expr_code]
                        )
                        == 1
                    ):
                        info.number = -1
                        continue

                info.number = -1
                local_var_name = f"_tmp{number_of_replacements}_"
                number_of_replacements += 1

                new_node = AstName(id=local_var_name, ctx=AstLoad())
                replacement_node = None

                for expr_info in chain(
                    (info,), info.children if info.children else ()
                ):
                    while expr_info.node_paths:
                        node_path = expr_info.node_paths.pop()
                        if replacement_node is None:
                            replacement_node = AstAssign(
                                targets=[
                                    AstName(id=local_var_name, ctx=AstStore())
                                ],
                                value=node_from_node_path(node_path),
                            )
                            # ast visit_Assign get_type_comment fails without it
                            replacement_node.lineno = None  # type: ignore
                        replace_node_by_node_path(node_path, new_node)

                layer.insert_optimization(replacement_node)

    def get_expr_depth_below(self, expr_code):
        global_expr_code_to_child_code = self.global_expr_code_to_child_code
        stack = [(expr_code, 0)]
        max_depth = -1
        visited = {expr_code}
        while stack:
            expr, depth = stack.pop()
            children = global_expr_code_to_child_code[expr]
            if children:
                for l_expr in children:
                    if l_expr not in visited:  # pragma: no cover
                        stack.append((l_expr, depth + 1))
                        visited.add(l_expr)
            elif max_depth < depth:
                max_depth = depth

        return max_depth

    def visit(self, node):
        raise NotImplementedError

    def visit_by_attr(
        self,
        node,
        attr,
        mode=None,
        _stmt_attrs=frozenset(["body", "orelse", "finalbody"]),
        split_layer_after_side_effects=True,
    ):
        value = getattr(node, attr)
        parent_expr_code = self.parent_expr_code
        if isinstance(value, list):
            if mode is None or mode is IterMode.ALL:
                index = 0
                length = len(value)
            elif mode is IterMode.FIRST_ONLY:
                index = 0
                length = min(1, len(value))
            else:  # IterMode.ALL_BUT_FIRST
                index = 1
                length = len(value)

            if attr in _stmt_attrs:
                while index < length:
                    item = value[index]
                    self.node_path = (value, item)
                    side_effects = self._side_effects
                    self.methods[f"visit_{item.__class__.__name__}"](item)
                    if (
                        side_effects < self._side_effects
                        and split_layer_after_side_effects
                    ):
                        self.split_layer_below(item)
                    index += 1

            else:
                while index < length:
                    item = value[index]
                    if isinstance(item, AST):  # pragma: no cover
                        self.node_path = (value, item)
                        self.methods[f"visit_{item.__class__.__name__}"](item)
                        self.parent_expr_code = parent_expr_code
                    index += 1
        elif isinstance(value, AST):
            self.node_path = (node, attr)
            self.methods[f"visit_{value.__class__.__name__}"](value)
            self.parent_expr_code = parent_expr_code

    def raw_visit(self, node):
        self.methods[f"visit_{node.__class__.__name__}"](node)

    def generic_visit(
        self,
        node,
        _non_idempotent_expr_nodes=frozenset(
            [
                "Dict",
                "List",
                "Set",
                "DictComp",
                "ListComp",
                "SetComp",
                "GeneratorExp",
                "Call",
                "NamedExpr",
            ]
        ),
    ):
        expr_chain_collector = None
        node_name = node.__class__.__name__

        if isinstance(node, AstExpr):
            if self.mode_collect_expr_chain:
                if node_name not in _non_idempotent_expr_nodes:
                    expr_code = self.get_node_code(node)
                    expr_info = self.expr_code_tree[expr_code]
                    if self.parent_expr_code is not None:
                        self.global_expr_code_to_child_code[
                            self.parent_expr_code
                        ].add(expr_code)
                        self.global_expr_code_to_parent_code[expr_code].add(
                            self.parent_expr_code
                        )
                    expr_info.number += self.mode_track_numbers
                    expr_info.node_paths.append(self.node_path)

                    self.parent_expr_code = expr_code

            else:
                expr_code = self.get_node_code(node)
                if expr_code in self.exprs_to_optimize:
                    expr_chain_collector = ExprChainCollector(self)
                    expr_chain_collector.start()
                    if node_name not in _non_idempotent_expr_nodes:
                        expr_info = self.expr_code_tree[expr_code]
                        expr_info.number += self.mode_track_numbers
                        expr_info.node_paths.append(self.node_path)
                        self.parent_expr_code = expr_code
                    else:
                        self.parent_expr_code = None

        if node_name in self.CUSTOM_EXPR_VISITORS:
            self.CUSTOM_EXPR_VISITORS[node_name](self, node)

        else:
            for field in node._fields:  # pylint: disable=protected-access
                self.visit_by_attr(node, field)

        if expr_chain_collector is not None:
            expr_chain_collector.stop()
            self.current_layer.track_expr_chain(
                expr_chain_collector.expr_code_tree
            )

    def get_node_code(self, node):
        if self.parent_expr_code is not None:
            key = (self.parent_expr_code, self.node_path[-1])
        else:
            key = id(node)

        if key in self._node_code_cache:
            return self._node_code_cache[key]

        expr_code = ast_unparse(node)
        self._node_code_cache[key] = expr_code
        return expr_code

    def _custom_expr_visit_call(self, node):
        self.visit_by_attr(node, "func")
        self.visit_by_attr(node, "args")
        self.visit_by_attr(node, "keywords")
        self.may_have_side_effects(node)

    def _custom_expr_visit_list(self, node):
        self.visit_by_attr(node, "elts")

    def _custom_expr_visit_dict(self, node):
        self.visit_by_attr(node, "keys")
        self.visit_by_attr(node, "values")

    def _custom_expr_visit_comp(self, node):
        self.visit_by_attr(node.generators[0], "iter")

    def _custom_expr_visit_ifexp(self, node):
        self.visit_by_attr(node, "test")
        with NoTrackNumbersCtx(self):
            self.visit_by_attr(node, "body")
            self.visit_by_attr(node, "orelse")

    def _custom_expr_visit_named_expr(self, node):
        self.may_have_side_effects(node.target)
        self.visit_by_attr(node, "value")

    def _custom_expr_visit_bool_op(self, node):
        self.visit_by_attr(node, "values", IterMode.FIRST_ONLY)
        with NoTrackNumbersCtx(self):
            self.visit_by_attr(node, "values", IterMode.ALL_BUT_FIRST)

    CUSTOM_EXPR_VISITORS = {
        "Call": _custom_expr_visit_call,
        "List": _custom_expr_visit_list,
        "Set": _custom_expr_visit_list,
        "Tuple": _custom_expr_visit_list,
        "Dict": _custom_expr_visit_dict,
        "ListComp": _custom_expr_visit_comp,
        "SetComp": _custom_expr_visit_comp,
        "DictComp": _custom_expr_visit_comp,
        "GeneratorExp": _custom_expr_visit_comp,
        "IfExp": _custom_expr_visit_ifexp,
        "NamedExpr": _custom_expr_visit_named_expr,
        "BoolOp": _custom_expr_visit_bool_op,
    }

    def new_layer_ctx(self, body, *, opt_above=None, opt_below=None):
        return NewLayerCtx(self, CodeLayer(body, opt_above, opt_below))

    def split_layer_below(self, node):
        self.current_layer = CodeLayer(self.current_layer.body, None, node)
        self.parent_layer.children.append(self.current_layer)

    def report_side_effect(self):
        self._side_effects += 1

    def may_have_side_effects(self, node):
        # if self.mode_collect_expr_chain:
        #     return False
        result = not self.no_side_effects_test(node)
        if result:
            self.report_side_effect()
        return result

    def visit_If(self, node):
        propagate_with_coeff = (
            0.5 if self.condition_is_transparent_test(node.test) else 0
        )
        side_effects = self._side_effects
        self.visit_by_attr(node, "test")
        with self.new_layer_ctx(node.body) as ctx:
            self.visit_by_attr(
                node, "body", split_layer_after_side_effects=False
            )
            ctx.code_layer.propagate_with_coeff = propagate_with_coeff

        if node.orelse:
            with self.new_layer_ctx(node.orelse) as ctx:
                self.visit_by_attr(
                    node, "orelse", split_layer_after_side_effects=False
                )
                ctx.code_layer.propagate_with_coeff = propagate_with_coeff

        if side_effects < self._side_effects:
            self.split_layer_below(node)

    def visit_Try(self, node):
        with self.new_layer_ctx(node.body):
            self.visit_by_attr(node, "body")
        for handler in node.handlers:
            with self.new_layer_ctx(handler.body):
                self.visit_by_attr(handler, "body")
        with self.new_layer_ctx(node.orelse):
            self.visit_by_attr(node, "orelse")
        with self.new_layer_ctx(node.finalbody):
            self.visit_by_attr(node, "finalbody")

    def visit_Constant(self, node):
        pass

    if PY_VERSION < (3, 8):

        def visit_Str(self, node):
            pass

        def visit_Num(self, node):
            pass

    def visit_Name(self, node):
        pass

    def visit_Delete(self, node):  # pylint: disable=unused-argument
        self.report_side_effect()

    def visit_While(self, node):
        with self.new_layer_ctx(node.body):
            self.visit_by_attr(node, "body")
        self.report_side_effect()

    def visit_For(self, node):
        self.visit_by_attr(node, "iter")
        with self.new_layer_ctx(node.body):
            self.visit_by_attr(node, "body")
        self.report_side_effect()

    def visit_With(self, node):
        self.visit_by_attr(node, "items")
        with self.new_layer_ctx(node.body):
            self.visit_by_attr(node, "body")
        self.report_side_effect()

    visit_AsyncFor = visit_For

    def visit_Module(self, node):
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        # var assignments in class defs are not safe
        raise NotImplementedError

    def visit_FunctionDef(self, node):
        with self.new_layer_ctx(node.body):
            self.visit_by_attr(node, "body")
        self.report_side_effect()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Assign(self, node):
        self.visit_by_attr(node, "value")
        self.may_have_side_effects(node)

    def visit_Assert(self, node):
        self.visit_by_attr(node, "test")
        self.report_side_effect()

    def visit_AugAssign(self, node):
        self.visit_by_attr(node, "value")
        self.may_have_side_effects(node)

    def not_implemented(self, node):
        raise NotImplementedError

    visit_Nonlocal = visit_Global = not_implemented

    if PY_VERSION >= (3, 10):

        visit_Match = not_implemented
