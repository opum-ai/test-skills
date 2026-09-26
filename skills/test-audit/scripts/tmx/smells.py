"""Static test-smell scan and structural clone clustering.

Python files get a full AST pass. JS/TS files get a regex pass that is deliberately
conservative (it only reports what it can see on the page). Every smell names the rule from
references/smells.md that it evidences; a smell is a *candidate* for review, not a verdict.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
from typing import Dict, List

ASSERT_CALL = re.compile(r"^(assert\w*|expect\w*|should\w*|verify\w*|check\w*)$", re.I)
MOCK_NAMES = {"patch", "Mock", "MagicMock", "AsyncMock", "create_autospec", "mocker", "monkeypatch"}
PUBLIC_UNDERSCORE = {"_replace", "_asdict", "_fields", "_make", "_field_defaults"}   # namedtuple API
JS_TEST = re.compile(r"^\s*(?:it|test)(?:\.each\([^)]*\))?\s*\(\s*(['\"`])(.+?)\1", re.M)


def _files(paths: List[str]):
    for p in paths:
        if os.path.isfile(p):
            yield p
            continue
        for d, dirs, fs in os.walk(p):
            dirs[:] = [x for x in dirs if not x.startswith(".") and x not in ("node_modules", "__pycache__")]
            for f in sorted(fs):
                if re.match(r"(test_.*\.py|.*_test\.py|.*\.(test|spec)\.[jt]sx?)$", f):
                    yield os.path.join(d, f)


def _is_test_fn(node) -> bool:
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test")


def _test_functions(tree):
    for node in tree.body:
        if _is_test_fn(node):
            yield None, node
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for sub in node.body:
                if _is_test_fn(sub):
                    yield node.name, sub


def _guards_assertion(node) -> bool:
    return any(isinstance(x, ast.Assert) or (isinstance(x, ast.Call) and ASSERT_CALL.match(_call_name(x)))
               for x in ast.walk(node))


def _pure(e) -> bool:
    """No calls anywhere in the expression (so comparing it with itself cannot fail)."""
    return not any(isinstance(x, (ast.Call, ast.Await, ast.Yield, ast.NamedExpr)) for x in ast.walk(e))


def _call_name(call: ast.Call) -> str:
    f = call.func
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return ""


def py_smells(path: str, src_roots: List[str]) -> List[dict]:
    with open(path) as f:
        text = f.read()
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return [{"file": path, "test": None, "smell": "unparseable", "detail": str(e)}]
    src_pkgs = {os.path.basename(os.path.normpath(r)) for r in src_roots}
    out = []
    for cls, fn in _test_functions(tree):
        tid = f"{path}::{cls + '::' if cls else ''}{fn.name}"
        asserts, weak, taut, mocks, private = 0, 0, 0, 0, []
        sleeps = branches = prints = swallow = big_literal = 0
        for n in ast.walk(fn):
            if isinstance(n, ast.Assert):
                asserts += 1
                t = n.test
                if isinstance(t, ast.Constant) and bool(t.value):
                    taut += 1
                elif isinstance(t, ast.Compare) and len(t.comparators) == 1 and \
                        isinstance(t.ops[0], (ast.Eq, ast.Is, ast.LtE, ast.GtE)) and _pure(t.left) and \
                        ast.dump(t.left) == ast.dump(t.comparators[0]):
                    taut += 1   # `x == x` on a pure expression; calls (determinism checks) and != (NaN) are fine
                elif isinstance(t, ast.Call) and _call_name(t) in ("isinstance", "callable", "hasattr"):
                    weak += 1
                elif isinstance(t, ast.Compare) and len(t.ops) == 1 and isinstance(t.ops[0], ast.IsNot) and \
                        isinstance(t.comparators[0], ast.Constant) and t.comparators[0].value is None:
                    weak += 1
                elif isinstance(t, ast.Name):
                    weak += 1
            elif isinstance(n, ast.Call):
                name = _call_name(n)
                if ASSERT_CALL.match(name) or name in ("raises", "warns", "approx"):
                    asserts += 1
                if name in MOCK_NAMES:
                    mocks += 1
                    if name == "patch" and n.args and isinstance(n.args[0], ast.Constant) and \
                            isinstance(n.args[0].value, str):
                        target = n.args[0].value
                        if target.split(".")[0] in src_pkgs and any(p.startswith("_") for p in target.split(".")[1:]):
                            private.append(target)
                if name == "sleep" and not (n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == 0):
                    sleeps += 1   # sleep(0) just yields to the event loop
                if name == "print":
                    prints += 1
            elif isinstance(n, ast.With):
                for item in n.items:
                    if isinstance(item.context_expr, ast.Call) and _call_name(item.context_expr) in ("raises", "warns"):
                        asserts += 1
            elif isinstance(n, (ast.If, ast.For, ast.While)) and n is not fn and _guards_assertion(n):
                branches += 1   # branching or looping around an assertion (a loop that builds data is fine)
            elif isinstance(n, ast.Try):
                if any(all(isinstance(s, ast.Pass) for s in h.body) for h in n.handlers):
                    swallow += 1
            elif isinstance(n, ast.Attribute) and n.attr.startswith("_") and not n.attr.startswith("__") \
                    and n.attr not in PUBLIC_UNDERSCORE \
                    and not (isinstance(n.value, ast.Name) and n.value.id in ("self", "cls")):
                private.append(n.attr)   # the test's own helpers and namedtuple's API are not internals
            elif isinstance(n, ast.Constant) and isinstance(n.value, str) and len(n.value) > 400:
                big_literal += 1
            elif isinstance(n, (ast.Dict, ast.List)) and len(getattr(n, "keys", None) or getattr(n, "elts", [])) > 40:
                big_literal += 1
        decos = [ast.unparse(d) for d in fn.decorator_list]
        if any("mocker" == a.arg for a in fn.args.args):
            mocks += 1
        start = min([d.lineno for d in fn.decorator_list] + [fn.lineno])
        rec = lambda s, d="": out.append({"file": path, "test": tid, "line": fn.lineno, "start": start,  # noqa: E731
                                          "end": fn.end_lineno, "smell": s, "detail": d})
        if asserts == 0:
            rec("no-assertion", "executes code but checks nothing (Art. IV: every test must be able to fail)")
        if taut:
            rec("tautology", f"{taut} assertion(s) that cannot fail")
        if asserts and weak == asserts - 0 and weak:
            rec("weak-assertion", "only type/existence/truthiness checks")
        if mocks >= 3:
            rec("mock-heavy", f"{mocks} mocks/patches (Art. VI: mock only at architectural boundaries)")
        elif mocks:
            rec("mocks", f"{mocks} mock(s)/patch(es)")   # informational; the gate compares it to the rigor limit
        if private:
            rec("implementation-coupled", "touches private names: " + ", ".join(sorted(set(private))[:5]))
        if sleeps:
            rec("sleep", f"{sleeps} sleep call(s): slow and a flake source")
        if branches:
            rec("conditional-logic", f"{branches} if/for/while in the test body")
        if swallow:
            rec("swallowed-exception", "try/except: pass hides failures")
        if big_literal:
            rec("snapshot-literal", "large literal expectation; likely a change detector")
        if asserts > 8:
            rec("assertion-roulette", f"{asserts} assertions in one test")
        if any(re.match(r"^(pytest\.mark\.skip|unittest\.skip)(\(|$)", d) for d in decos):   # not skipif
            rec("skipped", "permanently skipped test: fix or delete (Art. XI)")
        if prints:
            rec("print", "print in test: output nobody reads")
    return out


def js_smells(path: str) -> List[dict]:
    with open(path, errors="replace") as f:
        text = f.read()
    out = []
    starts = [(m.start(), m.group(2)) for m in JS_TEST.finditer(text)]
    for i, (pos, name) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        body = text[pos:end]
        line = text.count("\n", 0, pos) + 1
        tid = f"{path}::{name}"
        end_line = text.count("\n", 0, end) + 1
        rec = lambda s, d="": out.append({"file": path, "test": tid, "line": line, "end": end_line,  # noqa: E731
                                          "smell": s, "detail": d})
        if not re.search(r"\b(expect|assert|should)\w*\s*[.(]", body):
            rec("no-assertion", "no expect/assert in the test body")
        if re.search(r"toMatch(Inline)?Snapshot", body):
            rec("snapshot", "snapshot assertion: review as a change detector")
        if re.search(r"setTimeout|\bsleep\(|waitForTimeout", body):
            rec("sleep", "timer-based waiting")
        n_mock = len(re.findall(r"\b(jest|vi)\.(mock|spyOn|fn)\b|sinon\.", body))
        if n_mock >= 3:
            rec("mock-heavy", f"{n_mock} mocks/spies")
        if re.search(r"expect\(\s*true\s*\)\.toBe\(\s*true\s*\)", body):
            rec("tautology", "expect(true).toBe(true)")
        if re.search(r"\.(skip|todo)\s*\(", body[:40]):
            rec("skipped", "skipped test")
    return out


def main(a) -> int:
    smells: List[dict] = []
    n_files = 0
    for f in _files(a.paths):
        n_files += 1
        smells += py_smells(f, a.src) if f.endswith(".py") else js_smells(f)
    by_kind: Dict[str, int] = {}
    for s in smells:
        by_kind[s["smell"]] = by_kind.get(s["smell"], 0) + 1
    report = {"files": n_files, "smells": len(smells), "by_kind": dict(sorted(by_kind.items())), "items": smells}
    if a.out:
        with open(a.out, "w") as f:
            json.dump(report, f, indent=1)
    print(json.dumps({k: report[k] for k in ("files", "smells", "by_kind")}, indent=1))
    return 0


# ---------------------------------------------------------------- clone clustering

class _FoldNeg(ast.NodeTransformer):
    """`-1` parses as UnaryOp(USub, 1); fold it so it clusters and reads as the literal -1."""

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, (ast.USub, ast.UAdd)) and isinstance(node.operand, ast.Constant) and \
                isinstance(node.operand.value, (int, float)) and not isinstance(node.operand.value, bool):
            v = -node.operand.value if isinstance(node.op, ast.USub) else node.operand.value
            return ast.copy_location(ast.Constant(value=v), node)
        return node


class _Normalize(ast.NodeTransformer):
    """Erase what varies between copy-pasted tests: literal values and the test's own name."""

    def visit_Constant(self, node):
        return ast.copy_location(ast.Constant(value=type(node.value).__name__), node)


def _shape(fn) -> str:
    f = _Normalize().visit(_FoldNeg().visit(ast.parse(ast.unparse(fn))))
    body = f.body[0]
    body.name = "_"
    body.decorator_list = []
    return hashlib.sha1(ast.dump(body, annotate_fields=False).encode()).hexdigest()[:12]


def _literals(fn) -> List[str]:
    fn = _FoldNeg().visit(ast.parse(ast.unparse(fn))).body[0]
    consts = [n for n in ast.walk(fn) if isinstance(n, ast.Constant) and not
              (isinstance(n.value, str) and n.value == ast.get_docstring(fn))]
    consts.sort(key=lambda n: (n.lineno, n.col_offset))   # source order, so rows read like the code
    return [repr(n.value) for n in consts]


def clones_main(a) -> int:
    groups: Dict[str, List[dict]] = {}
    for f in _files(a.paths):
        if not f.endswith(".py"):
            continue
        with open(f) as fh:
            try:
                tree = ast.parse(fh.read())
            except SyntaxError:
                continue
        for cls, fn in _test_functions(tree):
            tid = f"{f}::{cls + '::' if cls else ''}{fn.name}"
            groups.setdefault(_shape(fn), []).append({"test": tid, "line": fn.lineno, "literals": _literals(fn)})
    clusters = []
    for h, members in groups.items():
        if len(members) < a.min_size:
            continue
        cols = list(zip(*[m["literals"] for m in members])) if len({len(m["literals"]) for m in members}) == 1 else []
        varying = [i for i, col in enumerate(cols) if len(set(col)) > 1]
        clusters.append({"shape": h, "size": len(members), "tests": [m["test"] for m in members],
                         "varying_literal_positions": varying,
                         "rows": [[m["literals"][i] for i in varying] for m in members] if cols else [],
                         "suggestion": "collapse into one parametrized test, or one property if the rows "
                                       "follow a rule (Art. VII)"})
    clusters.sort(key=lambda c: -c["size"])
    report = {"clusters": len(clusters), "tests_in_clusters": sum(c["size"] for c in clusters),
              "collapsible_to": len(clusters), "items": clusters}
    if a.out:
        with open(a.out, "w") as f:
            json.dump(report, f, indent=1)
    print(json.dumps({k: report[k] for k in ("clusters", "tests_in_clusters", "collapsible_to")}, indent=1))
    for c in clusters[:10]:
        print(f"  {c['size']:3} x {c['tests'][0]} ...")
    return 0
