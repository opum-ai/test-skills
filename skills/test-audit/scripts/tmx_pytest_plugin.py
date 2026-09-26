"""pytest plugin used by `tmx.py collect-pytest`. Load with `-p tmx_pytest_plugin`.

Environment:
  TMX_OUT     path of the JSON results file to write (required)
  TMX_COVER   comma-separated source paths; when set, record per-test line coverage
  TMX_SELECT  path of a file listing node ids to run; everything else is deselected
"""
import json
import os
import time

import pytest

_results = {"tests": {}, "coverage": {}, "collection_errors": 0, "errored_modules": []}
_cov = None


@pytest.hookimpl(tryfirst=True)
def pytest_load_initial_conftests(early_config, parser, args):
    global _cov
    src = os.environ.get("TMX_COVER")
    if src and _cov is None:
        import coverage  # the target environment must have coverage installed

        data_file = os.environ["TMX_OUT"] + ".coverage"
        paths = [s for s in src.split(",") if s]
        files = [os.path.abspath(p) for p in paths if os.path.isfile(p)]
        dirs = [p for p in paths if not os.path.isfile(p)]
        # coverage's `source` takes directories/packages; a single file must go through `include`.
        _cov = coverage.Coverage(source=dirs or None, include=files or None, data_file=data_file,
                                 branch=False, config_file=False)
        _cov.start()


def pytest_collection_modifyitems(session, config, items):
    sel = os.environ.get("TMX_SELECT")
    if not sel:
        return
    with open(sel) as f:
        wanted = {line.rstrip("\n") for line in f if line.strip()}
    keep = [i for i in items if i.nodeid in wanted]
    drop = [i for i in items if i.nodeid not in wanted]
    if drop:
        config.hook.pytest_deselected(items=drop)
    items[:] = keep


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    if _cov is not None:
        _cov.switch_context(item.nodeid)
    start = time.perf_counter()
    yield
    rec = _results["tests"].setdefault(item.nodeid, {"file": item.location[0]})
    rec["duration"] = round(time.perf_counter() - start, 6)
    if _cov is not None:
        _cov.switch_context("")


def pytest_runtest_logreport(report):
    rec = _results["tests"].setdefault(report.nodeid, {"file": report.location[0]})
    prev = rec.get("outcome")
    if report.failed:
        rec["outcome"] = "failed"
    elif report.when == "call" and prev != "failed":
        rec["outcome"] = report.outcome  # passed / skipped
    elif report.skipped and prev is None:
        rec["outcome"] = "skipped"


def pytest_collectreport(report):
    if report.failed:
        _results["collection_errors"] += 1
        _results["errored_modules"].append(report.nodeid.split("::")[0])


def pytest_sessionfinish(session, exitstatus):
    if _cov is not None:
        _cov.stop()
        _cov.save()
        data = _cov.get_data()
        root = str(session.config.rootpath)
        for fname in data.measured_files():
            rel = os.path.relpath(fname, root)
            by_line = data.contexts_by_lineno(fname)
            for line, ctxs in by_line.items():
                for c in ctxs:
                    if c:
                        _results["coverage"].setdefault(c, []).append(f"{rel}:{line}")
        for c in _results["coverage"]:
            _results["coverage"][c].sort(key=lambda s: (s.rsplit(":", 1)[0], int(s.rsplit(":", 1)[1])))
    _results["exitstatus"] = int(exitstatus)
    with open(os.environ["TMX_OUT"], "w") as f:
        json.dump(_results, f)
