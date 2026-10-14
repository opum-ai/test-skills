"""Differential oracle for mutant equivalence (TS-11, DEC-189).

A mutant is *equivalent* to the original only when, run over a recorded corpus,
its observable result matches the original's: the same exit code, the same
emitted records (stdout and stderr) and the same files written (added, changed
or removed, compared by content). A difference in wall time or in iteration
count alone is not observable, so it counts as equivalent.

Nothing here is hand-edited. The caller records the corpus and its seed; the
verdict is re-derived from the two runs, and the evidence (each corpus entry's
two observable results, and the first mismatch) is returned with it.

The module is stdlib-only, like the rest of the engine.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from typing import Dict, List, Optional, Sequence

SKIP_DIRS = {".git", "__pycache__", ".tmx", ".pytest_cache", ".hypothesis"}
DEFAULT_TIMEOUT = 60.0


def snapshot(root: str) -> Dict[str, str]:
    """{relative path: sha256} for every file under `root`, tooling directories excluded."""
    out: Dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            p = os.path.join(dirpath, fn)
            try:
                with open(p, "rb") as f:
                    out[os.path.relpath(p, root)] = hashlib.sha256(f.read()).hexdigest()
            except OSError:
                continue
    return out


def _run(python: str, cwd: str, argv: Sequence[str], env: Optional[dict], timeout: float) -> dict:
    e = dict(os.environ)
    e.update(env or {})
    try:
        r = subprocess.run([python, *argv], cwd=cwd, env=e, capture_output=True, text=True, timeout=timeout)
        return {"exit": r.returncode, "stdout": r.stdout, "stderr": r.stderr, "timeout": False}
    except subprocess.TimeoutExpired:
        return {"exit": None, "stdout": "", "stderr": "", "timeout": True}


def observable(python: str, root: str, argv: Sequence[str], env: Optional[dict] = None,
               timeout: float = DEFAULT_TIMEOUT) -> dict:
    """The observable result of one corpus entry: exit code, emitted records and files written.

    Wall time and iteration count are deliberately not part of it.
    """
    before = snapshot(root)
    r = _run(python, root, argv, env, timeout)
    after = snapshot(root)
    written = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    return {"exit": r["exit"], "stdout": r["stdout"], "stderr": r["stderr"],
            "written": written, "timeout": r["timeout"]}


def equivalent(python: str, original_dir: str, mutant_dir: str, corpus: Sequence[Sequence[str]],
               env: Optional[dict] = None, timeout: float = DEFAULT_TIMEOUT, seed: int = 0) -> dict:
    """Classify a mutant whose tree is at `mutant_dir` against the original at `original_dir`.

    Runs every corpus entry in both trees and compares the observable results. Returns
    {"equivalent": bool, "seed": seed, "evidence": [{"argv", "same", "original", "mutant"}, ...]},
    stopping at the first mismatch. `seed` is the recorded seed of the generated corpus.
    """
    evidence: List[dict] = []
    for argv in corpus:
        a = observable(python, original_dir, argv, env=env, timeout=timeout)
        b = observable(python, mutant_dir, argv, env=env, timeout=timeout)
        same = a == b
        evidence.append({"argv": list(argv), "same": same, "original": a, "mutant": b})
        if not same:
            return {"equivalent": False, "seed": seed, "evidence": evidence}
    return {"equivalent": True, "seed": seed, "evidence": evidence}
