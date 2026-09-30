"""Run every backend test suite and exit non-zero if any fail."""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUITES = sorted(HERE.glob("test_*.py"))

failed = []
checks = 0
for suite in SUITES:
    result = subprocess.run(
        [sys.executable, suite.name], cwd=HERE, capture_output=True, text=True
    )
    passed = sum(1 for line in result.stdout.splitlines() if line.lstrip().startswith("ok"))
    checks += passed
    status = "passed" if result.returncode == 0 else "FAILED"
    print(f"{suite.name:<20} {passed:>3} checks  {status}")
    if result.returncode != 0:
        failed.append(suite.name)
        print(result.stdout[-2000:], result.stderr[-2000:], sep="\n")

print(f"\n{checks} checks across {len(SUITES)} suites")
if failed:
    print(f"failed: {', '.join(failed)}")
    sys.exit(1)
