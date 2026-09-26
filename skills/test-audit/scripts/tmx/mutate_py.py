"""Python AST mutants: a small, classic operator set (Offutt's sufficient operators plus
statement deletion), enough to tell a test that checks behavior from one that only executes it.

Each mutant re-renders the whole module with `ast.unparse`, so formatting is lost in the
mutated copy, but semantics are exact and line numbers are recorded against the original.
"""
from __future__ import annotations

import ast
import copy
import re
from typing import Iterator, List, Tuple

CMP_SWAP = {
    ast.Lt: [ast.LtE, ast.GtE], ast.LtE: [ast.Lt, ast.Gt], ast.Gt: [ast.GtE, ast.LtE],
    ast.GtE: [ast.Gt, ast.Lt], ast.Eq: [ast.NotEq], ast.NotEq: [ast.Eq],
    ast.In: [ast.NotIn], ast.NotIn: [ast.In], ast.Is: [ast.IsNot], ast.IsNot: [ast.Is],
}
BIN_SWAP = {
    ast.Add: [ast.Sub], ast.Sub: [ast.Add], ast.Mult: [ast.Div], ast.Div: [ast.Mult, ast.FloorDiv],
    ast.FloorDiv: [ast.Div, ast.Mult], ast.Mod: [ast.Mult], ast.Pow: [ast.Mult],
    ast.BitAnd: [ast.BitOr], ast.BitOr: [ast.BitAnd],
}
NUMERIC_STR = re.compile(r"^-?\d+(\.\d+)?$")
OPERATORS = ["cmp", "arith", "bool", "not", "const", "return", "cond", "stmt", "raise", "call", "round"]
# Builtins a wrong-but-plausible implementation swaps (a subtotal that takes the max, not the sum).
CALL_SWAP = {"min": "max", "max": "min", "any": "all", "all": "any", "sum": "max"}
# Rounding modes: money code lives or dies on these (banker's vs half-up).
ROUND_SWAP = {"ROUND_HALF_UP": "ROUND_HALF_EVEN", "ROUND_HALF_EVEN": "ROUND_HALF_UP",
              "ROUND_HALF_DOWN": "ROUND_HALF_UP", "ROUND_UP": "ROUND_DOWN", "ROUND_DOWN": "ROUND_UP",
              "ROUND_CEILING": "ROUND_FLOOR", "ROUND_FLOOR": "ROUND_CEILING"}
# "extreme" (Niedermayr; Descartes): empty a whole function body. One mutant per function, so it is
# a cheap first pass that finds pseudo-tested functions. Opt-in via --operators extreme,...
ALL_OPERATORS = OPERATORS + ["extreme"]


def _sym(op) -> str:
    return {ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=", ast.Eq: "==", ast.NotEq: "!=",
            ast.In: "in", ast.NotIn: "not in", ast.Is: "is", ast.IsNot: "is not", ast.Add: "+",
            ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.FloorDiv: "//", ast.Mod: "%",
            ast.Pow: "**", ast.BitAnd: "&", ast.BitOr: "|", ast.And: "and", ast.Or: "or"}.get(op, op.__name__)


def _skip_lines(tree: ast.AST) -> set:
    """Lines we never mutate: docstrings, `if __name__ == ...`, type-only and logging lines."""
    skip = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and \
                isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
            skip.update(range(body[0].lineno, (body[0].end_lineno or body[0].lineno) + 1))
        if isinstance(node, ast.If) and isinstance(node.test, ast.Compare) and \
                isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__":
            skip.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            f = node.value.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            owner = getattr(getattr(f, "value", None), "id", "")
            if owner in ("log", "logger", "logging") or name in ("print",):
                skip.add(node.lineno)
    return skip


def candidates(tree: ast.AST) -> Iterator[Tuple[int, str, str, object]]:
    """Yield (node_index, op_family, description, variant) for every mutable site."""
    skip = _skip_lines(tree)
    in_annotation = set()
    for node in ast.walk(tree):
        for fld in ("annotation", "returns"):
            sub = getattr(node, fld, None)
            if sub is not None:
                in_annotation.update(id(n) for n in ast.walk(sub))
    for idx, node in enumerate(ast.walk(tree)):
        line = getattr(node, "lineno", None)
        if line is None or line in skip or id(node) in in_annotation:
            continue
        if isinstance(node, ast.Compare):
            for k, op in enumerate(node.ops):
                for new in CMP_SWAP.get(type(op), []):
                    yield idx, "cmp", f"{_sym(type(op))} -> {_sym(new)}", (k, new)
        elif isinstance(node, ast.BinOp) and type(node.op) in BIN_SWAP:
            for new in BIN_SWAP[type(node.op)]:
                yield idx, "arith", f"{_sym(type(node.op))} -> {_sym(new)}", new
        elif isinstance(node, ast.AugAssign) and type(node.op) in BIN_SWAP:
            for new in BIN_SWAP[type(node.op)]:
                yield idx, "arith", f"{_sym(type(node.op))}= -> {_sym(new)}=", new
        elif isinstance(node, ast.BoolOp):
            new = ast.Or if isinstance(node.op, ast.And) else ast.And
            yield idx, "bool", f"{_sym(type(node.op))} -> {_sym(new)}", new
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            yield idx, "not", "drop `not`", None
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and NUMERIC_STR.match(node.value):
            # Numeric strings are how money and rates are written (Decimal("0.0825")); bump the last digit.
            v = node.value
            bumped = v[:-1] + str((int(v[-1]) + 1) % 10)
            yield idx, "const", f"{v!r} -> {bumped!r}", bumped
        elif isinstance(node, ast.Constant) and not isinstance(node.value, str) and node.value is not None:
            v = node.value
            if isinstance(v, bool):
                yield idx, "const", f"{v} -> {not v}", (not v)
            elif isinstance(v, (int, float)):
                yield idx, "const", f"{v} -> {v + 1}", v + 1
                yield idx, "const", f"{v} -> {v - 1}", v - 1
        elif isinstance(node, ast.Return) and node.value is not None and \
                not (isinstance(node.value, ast.Constant) and node.value.value is None):
            yield idx, "return", "return value -> None", None
        elif isinstance(node, (ast.If, ast.While)) and not isinstance(node.test, ast.Constant):
            yield idx, "cond", "negate condition", None
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            yield idx, "stmt", "delete call statement", None
        elif isinstance(node, ast.Raise):
            yield idx, "raise", "delete raise (validation skipped)", None
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in CALL_SWAP:
            yield idx, "call", f"{node.func.id}() -> {CALL_SWAP[node.func.id]}()", CALL_SWAP[node.func.id]
        elif isinstance(node, (ast.Name, ast.Attribute)) and \
                (node.id if isinstance(node, ast.Name) else node.attr) in ROUND_SWAP:
            nm = node.id if isinstance(node, ast.Name) else node.attr
            yield idx, "round", f"{nm} -> {ROUND_SWAP[nm]}", ROUND_SWAP[nm]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("__"):
            yield idx, "extreme", f"empty body of {node.name}()", None


def apply(tree: ast.AST, idx: int, family: str, variant) -> ast.AST:
    t = copy.deepcopy(tree)
    node = list(ast.walk(t))[idx]
    if family == "cmp":
        k, new = variant
        node.ops[k] = new()
    elif family == "arith":
        node.op = variant()
    elif family == "bool":
        node.op = variant()
    elif family == "not":
        _replace(t, node, node.operand)
    elif family == "const":
        node.value = variant
    elif family == "return":
        node.value = ast.Constant(value=None)
    elif family == "cond":
        node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
    elif family == "stmt":
        _replace(t, node, ast.Pass())
    elif family == "raise":
        _replace(t, node, ast.Pass())
    elif family == "call":
        node.func = ast.Name(id=variant, ctx=ast.Load())
    elif family == "round":
        if isinstance(node, ast.Name):
            node.id = variant
        else:
            node.attr = variant
    elif family == "extreme":
        doc = node.body[:1] if (node.body and isinstance(node.body[0], ast.Expr) and
                                isinstance(getattr(node.body[0], "value", None), ast.Constant)) else []
        node.body = doc + [ast.Return(value=ast.Constant(value=None))]
    return ast.fix_missing_locations(t)


def _replace(tree: ast.AST, old: ast.AST, new: ast.AST) -> None:
    for parent in ast.walk(tree):
        for fld, val in ast.iter_fields(parent):
            if isinstance(val, list):
                for i, v in enumerate(val):
                    if v is old:
                        val[i] = new
                        ast.copy_location(new, old)
                        return
            elif val is old:
                setattr(parent, fld, new)
                ast.copy_location(new, old)
                return


def mutants_for(source: str, operators: List[str] = OPERATORS) -> Iterator[Tuple[int, str, str, str]]:
    """Yield (line, family, description, mutated_source)."""
    tree = ast.parse(source)
    nodes = list(ast.walk(tree))
    seen = {ast.unparse(tree)}  # a mutant that renders identically is equivalent by construction
    for idx, fam, desc, var in candidates(tree):
        if fam not in operators:
            continue
        src = ast.unparse(apply(tree, idx, fam, var))
        if src in seen:
            continue
        seen.add(src)
        yield nodes[idx].lineno, fam, desc, src
