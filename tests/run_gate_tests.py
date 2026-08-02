"""Regression runner for draft_gate.py.

Usage:
    python tests/run_gate_tests.py

Runs the gate against every fixture in tests/fixtures/ and compares the exit
code against the one declared in that fixture's sibling .expected file. Any
mismatch is a failure and the runner exits 1.

An .expected file is two lines, the second optional:

    exit: 1
    check: CHECK 5 finals reconciliation

The check line is worth carrying wherever it is known. A fixture that fails
for the wrong reason still exits 1, so exit code alone cannot tell a working
check from one that broke and had its failure taken over by another check
running earlier. That is not hypothetical: adding CHECK 6 made a draft fail on
an absence token before it ever reached the check the fixture was written for,
and the exit code did not move.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
GATE = ROOT / "draft_gate.py"


def read_expected(path):
    """Parse a .expected file into (exit_code, check_name_or_None)."""
    code, check = None, None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key == "exit":
            code = int(value)
        elif key == "check":
            check = value
    if code is None:
        raise ValueError(f"{path.name} declares no exit code")
    return code, check


def failed_check(stdout):
    """The check name from a gate failure, or None if it did not fail."""
    for line in stdout.splitlines():
        if line.startswith("FAIL  "):
            return line[len("FAIL  "):].strip()
    return None


def main():
    fixtures = sorted(FIXTURES.glob("*.md"))
    if not fixtures:
        print(f"no fixtures found in {FIXTURES}")
        return 1

    width = max(len(f.stem) for f in fixtures)
    results = []

    for fixture in fixtures:
        spec = fixture.with_suffix(".expected")
        if not spec.is_file():
            results.append((fixture.stem, "?", "?", "NO .expected"))
            continue

        want_code, want_check = read_expected(spec)
        run = subprocess.run(
            [sys.executable, str(GATE), str(fixture)],
            capture_output=True, text=True, cwd=ROOT,
        )
        got_check = failed_check(run.stdout)

        if run.returncode != want_code:
            verdict = "FAIL exit"
        elif want_check and got_check != want_check:
            # Right exit code, wrong reason: the fixture is no longer testing
            # what it was written to test.
            verdict = f"FAIL reason: {got_check or 'passed'}"
        else:
            verdict = "ok"

        results.append((fixture.stem, want_code, run.returncode, verdict))

    print(f"{'fixture':<{width}}  want  got  result")
    print(f"{'-' * width}  ----  ---  ------")
    for name, want, got, verdict in results:
        print(f"{name:<{width}}  {str(want):>4}  {str(got):>3}  {verdict}")

    bad = [r for r in results if r[3] != "ok"]
    print()
    print(f"{len(results) - len(bad)}/{len(results)} passed")
    if bad:
        for name, _, _, verdict in bad:
            print(f"  {name}: {verdict}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
