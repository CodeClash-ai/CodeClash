"""Stage 1 (structural) validator for classic-Robocode ports. No javac here (robocode.jar lives
in the arena image) — the real compile+battle gate is run_smoke_all.sh (stage 2). This checks each
ports/<slug>/ dir: a MyTank.java exists, declares `public class MyTank` extending a classic Robocode
base, has `package custom;` in every .java, and warns on the two things that bite this arena:
the literal token "custom" outside the package line (the harness sed would mangle it) and raw
java.io/threads/reflection (blocked by Robocode's security manager). Writes ports/_stage1.json.
"""

import json
import re
import sys
from pathlib import Path

PORTS = Path(__file__).parent / "ports"
BASES = ("AdvancedRobot", "JuniorRobot", "TeamRobot", "RateControlRobot", "Robot")
RAW_IO = (r"\bnew\s+File\b", r"\bFileReader\b", r"\bFileWriter\b", r"\bFileInputStream\b",
          r"\bnew\s+Thread\b", r"\bClass\.forName\b", r"java\.lang\.reflect")


def check(slug_dir: Path):
    warns = []
    javas = sorted(slug_dir.glob("*.java"))
    if not javas:
        return False, "no .java files", warns
    subdirs = [d for d in slug_dir.iterdir() if d.is_dir()]
    if subdirs:
        return False, f"nested subdirs not allowed (flat glob compile): {[d.name for d in subdirs]}", warns
    main = slug_dir / "MyTank.java"
    if not main.exists():
        return False, "missing MyTank.java", warns
    mtext = main.read_text()
    if not re.search(r"\bclass\s+MyTank\b", mtext):
        return False, "MyTank.java has no `class MyTank`", warns
    if not re.search(r"\bclass\s+MyTank\b[^{]*\bextends\s+\w+", mtext):
        return False, "MyTank must `extends` something (a Robocode base, directly or via a helper class)", warns
    # A classic Robocode base must appear somewhere in the port (MyTank directly, or a helper it extends).
    all_text = "\n".join(j.read_text() for j in javas)
    if not re.search(r"\bextends\s+(robocode\.)?(" + "|".join(BASES) + r")\b", all_text):
        return False, "no class in the port extends a classic Robocode base (AdvancedRobot/Robot/...)", warns
    for j in javas:
        t = j.read_text()
        if not re.search(r"^\s*package\s+custom\s*;", t, re.M):
            return False, f"{j.name} missing `package custom;`", warns
        # "custom" outside the package line -> sed-mangle risk
        for ln in t.splitlines():
            if "custom" in ln and not re.match(r"\s*package\s+custom\s*;", ln):
                warns.append(f"{j.name}: 'custom' token outside package line -> sed risk: {ln.strip()[:60]}")
                break
        if "dev.robocode.tankroyale" in t:
            return False, f"{j.name} uses Tank Royale API (not classic)", warns
        for pat in RAW_IO:
            if re.search(pat, t):
                warns.append(f"{j.name}: uses {pat} — may be blocked by security manager")
                break
    return True, "ok", warns


def main():
    slugs = sorted(d for d in PORTS.iterdir() if d.is_dir() and not d.name.startswith("_")) if PORTS.exists() else []
    results, npass = {}, 0
    for d in slugs:
        ok, msg, warns = check(d)
        results[d.name] = {"pass": ok, "msg": msg, "warnings": warns}
        line = f"  {'PASS' if ok else 'FAIL'}  {d.name}" + ("" if ok else f"   <- {msg}")
        print(line)
        for w in warns:
            print(f"        ! {w}")
        npass += ok
    (PORTS / "_stage1.json").write_text(json.dumps(results, indent=2, sort_keys=True))
    print(f"\nStage 1: {npass} pass / {len(slugs) - npass} fail  of {len(slugs)} ports (compile+battle gate is run_smoke_all.sh)")


if __name__ == "__main__":
    main()
