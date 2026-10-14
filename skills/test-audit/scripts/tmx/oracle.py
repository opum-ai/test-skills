"""Differential oracle for mutant equivalence (TS-11, DEC-189).

A mutant is *equivalent* to the original only when BOTH hold:

* **Reach.** Every line the mutation touches (`required_lines`) is among the lines the
  corpus *executed* in the original (`covered`). A mutant on a line the corpus never
  reached is "unreached", not equivalent: that is untested code, not a proof (DEC-189
  clause 1: equivalence is proven, never claimed).
* **Match.** Run over the corpus, its observable result matches the original's: the same
  exit code, the same emitted records (stdout and stderr) and the same files written
  (added, changed by content or mode, or removed). A difference in wall time or in
  iteration count alone is not observable, so it counts as equivalent.

Nothing here is hand-edited. The caller records the corpus and its seed; the verdict is
re-derived from the two runs, and the evidence (each corpus entry's two observable
results, and the first mismatch) is returned with it.

Sandboxing and what it can and cannot see. Each run has HOME and TMPDIR pointed inside
``<tree>/.oracle-sandbox``, so a write to the home directory or the temp directory lands
in the watched tree; the snapshot walks the whole tree (nothing skipped), so writes into
``.git``, ``__pycache__`` or ``.tmx`` are visible too. NOT observable here: a write to an
absolute path outside the tree, and a file created and then deleted within a single run
(the snapshot compares the tree before and after the run, so a transient file leaves no
trace). The run directory is normalised out of stdout and stderr, PYTHONHASHSEED is
pinned to 0, and the environment that shapes the result is recorded with the verdict.

Generated inputs are a later slice: this module compares a caller-provided corpus and
records the seed, but does not itself generate inputs from it.

The module is stdlib-only, like the rest of the engine.
"""
from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from typing import Dict, List, Optional, Sequence

SANDBOX = ".oracle-sandbox"
# The channels this process-level oracle observes, recorded on every verdict (DEC-189 (5)). A
# mutant whose only difference is a write to some other absolute path is a KNOWN FALSE EQUIVALENT,
# accepted as proportionate; classing is limited to the named speed-only classes.
OBSERVED = "workspace, home, tmp"
DEFAULT_TIMEOUT = 60.0


def _file_state(path: str) -> Optional[dict]:
    try:
        st = os.stat(path)
    except OSError:
        return None
    if not stat.S_ISREG(st.st_mode):
        return None
    try:
        with open(path, "rb") as f:
            body = hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None
    return {"sha256": body, "mode": stat.S_IMODE(st.st_mode)}


def snapshot(root: str) -> Dict[str, dict]:
    """{relative path: {sha256, mode}} for every regular file under `root`; no directory is
    skipped, so writes into .git, __pycache__, .tmx or the sandbox are all visible."""
    out: Dict[str, dict] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(dirnames)
        for fn in sorted(filenames):
            p = os.path.join(dirpath, fn)
            s = _file_state(p)
            if s is not None:
                out[os.path.relpath(p, root)] = s
    return out


def _sandbox(root: str) -> Dict[str, str]:
    home = os.path.join(root, SANDBOX, "home")
    tmp = os.path.join(root, SANDBOX, "tmp")
    os.makedirs(home, exist_ok=True)
    os.makedirs(tmp, exist_ok=True)
    # PYTHONDONTWRITEBYTECODE: an imported sibling would otherwise leave a __pycache__/*.pyc in
    # each tree with a different mtime, so every mutant of an imported module, comment-only edits
    # included, would read non-equivalent.
    return {"HOME": home, "TMPDIR": tmp, "TMP": tmp, "TEMP": tmp, "PYTHONHASHSEED": "0",
            "PYTHONDONTWRITEBYTECODE": "1"}


def _run(python: str, cwd: str, argv: Sequence[str], env: Optional[dict], timeout: float) -> dict:
    e = dict(os.environ)
    e.update(_sandbox(cwd))
    e.update(env or {})
    try:
        r = subprocess.run([python, *argv], cwd=cwd, env=e, capture_output=True, text=True, timeout=timeout)
        return {"exit": r.returncode, "stdout": r.stdout, "stderr": r.stderr, "timeout": False, "env": e}
    except subprocess.TimeoutExpired:
        return {"exit": None, "stdout": "", "stderr": "", "timeout": True, "env": e}


def _normalise(text: str, root: str) -> str:
    return text.replace(os.path.realpath(root), "<RUN>").replace(root, "<RUN>")


def _recorded_env(e: dict, root: str) -> dict:
    """The sandbox variables ACTUALLY passed, with the run directory normalised out, so two trees
    of the same source record the same environment (a hard-coded constant would not show drift)."""
    keys = ("HOME", "TMPDIR", "PYTHONHASHSEED", "PYTHONDONTWRITEBYTECODE")
    return {k: _normalise(str(e.get(k, "")), root) for k in keys}


def observable(python: str, root: str, argv: Sequence[str], env: Optional[dict] = None,
               timeout: float = DEFAULT_TIMEOUT) -> dict:
    """The observable result of one corpus entry: exit code, emitted records (with the run
    directory normalised out) and files written anywhere in the tree. Wall time and iteration
    count are deliberately not part of it; the environment actually passed is recorded.

    The sandbox temp directory is NOT part of the file channel: a program that leaves a
    random-named tempfile there would otherwise read as observable. Files written anywhere else
    under the tree are."""
    before = snapshot(root)
    r = _run(python, root, argv, env, timeout)
    after = snapshot(root)
    changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))
    written = [k for k in changed if not k.startswith(SANDBOX + "/tmp/")]
    # The state of each changed path, so two trees that change the SAME path to DIFFERENT content
    # (or different modes) are not read as equivalent.
    written_state = {k: (after[k] if k in after else "removed") for k in written}
    return {"exit": r["exit"], "stdout": _normalise(r["stdout"], root), "stderr": _normalise(r["stderr"], root),
            "written": written, "written_state": written_state, "timeout": r["timeout"],
            "env": _recorded_env(r["env"], root)}


def equivalent(python: str, original_dir: str, mutant_dir: str, corpus: Sequence[Sequence[str]],
               env: Optional[dict] = None, timeout: float = DEFAULT_TIMEOUT, seed: int = 0,
               required_lines: Optional[Sequence[int]] = None,
               covered: Optional[Sequence[int]] = None) -> dict:
    """Classify a mutant whose tree is at `mutant_dir` against the original at `original_dir`.

    `required_lines` are the lines the mutation touches; `covered` are the lines the corpus
    executed in the original. DEC-189 makes a mutant equivalent only if the corpus EXECUTES the
    mutated line, so the reach guard FAILS CLOSED: with no reach information (`required_lines`
    is None) the result is unreached, never equivalent. With reach information, any required line
    not covered is unreached; otherwise every corpus entry is run in both trees and the observable
    results compared, stopping at the first mismatch.

    Returns {"equivalent", "unreached", "observed", "seed", "evidence": [{"argv", "same",
    "original", "mutant"}, ...]}. "observed" is the channel list DEC-189 (5) requires on every
    verdict. `seed` is the recorded seed of the (later-slice) generated corpus.
    """
    if required_lines is None:
        return {"equivalent": False, "unreached": True, "missing_lines": [],
                "reason": "no reach information", "observed": OBSERVED, "seed": seed, "evidence": []}
    cov = {int(x) for x in (covered or ())}
    missing = sorted({int(x) for x in required_lines} - cov)
    if missing:
        return {"equivalent": False, "unreached": True, "missing_lines": missing,
                "observed": OBSERVED, "seed": seed, "evidence": []}
    evidence: List[dict] = []
    for argv in corpus:
        a = observable(python, original_dir, argv, env=env, timeout=timeout)
        b = observable(python, mutant_dir, argv, env=env, timeout=timeout)
        same = a == b
        evidence.append({"argv": list(argv), "same": same, "original": a, "mutant": b})
        if not same:
            return {"equivalent": False, "unreached": False, "observed": OBSERVED,
                    "seed": seed, "evidence": evidence}
    return {"equivalent": True, "unreached": False, "observed": OBSERVED, "seed": seed, "evidence": evidence}
