"""Stage 1 validator: mirrors the arena's validate_code locally (no Docker/scml needed
since ports are stdlib-only). For each ports/*.py: syntax-compile, import, assert a
top-level callable `decide`, and call it with the arena's validation observation
(must return dict or None). Prints PASS/FAIL per file and writes ports/_stage1.json.
"""

import ast
import importlib.util
import json
import sys
from pathlib import Path

PORTS = Path(__file__).parent / "ports"
VALIDATE_OBS = {"event": "validate", "awi": {}, "state": {}, "nmi": {}}


def check(path: Path):
    src = path.read_text()
    try:
        ast.parse(src)
    except SyntaxError as e:
        return False, f"syntax: {e}"
    try:
        spec = importlib.util.spec_from_file_location(f"port_{path.stem}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as e:
        return False, f"import: {type(e).__name__}: {e}"
    if not hasattr(mod, "decide") or not callable(mod.decide):
        return False, "no callable decide"
    # stdlib-only guard: fail if it imported scml/negmas/numpy
    for banned in ("scml", "negmas", "numpy"):
        if banned in src and f"import {banned}" in src:
            return False, f"imports banned module: {banned}"
    try:
        r = mod.decide(dict(VALIDATE_OBS))
    except Exception as e:
        return False, f"decide raised on validate obs: {type(e).__name__}: {e}"
    if not (r is None or isinstance(r, dict)):
        return False, f"decide returned {type(r).__name__}, need dict/None"
    return True, "ok"


def main():
    results = {}
    files = sorted(PORTS.glob("*.py"))
    files = [f for f in files if not f.name.startswith("_")]
    passed = failed = 0
    for f in files:
        ok, msg = check(f)
        results[f.name] = {"pass": ok, "msg": msg}
        print(f"  {'PASS' if ok else 'FAIL'}  {f.name}" + ("" if ok else f"   <- {msg}"))
        passed += ok
        failed += not ok
    (PORTS / "_stage1.json").write_text(json.dumps(results, indent=2, sort_keys=True))
    print(f"\nStage 1: {passed} pass / {failed} fail  of {len(files)} ports")
    sys.exit(0)


if __name__ == "__main__":
    main()
