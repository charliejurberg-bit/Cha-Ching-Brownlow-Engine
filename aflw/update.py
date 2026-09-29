"""The AFLW weekly chain: new round in, site data out.

    python aflw/update.py

Fetches the live season's stats and coaches votes, rebuilds the frame, prints
the board, and rewrites site/data/aflw/. Like update.py it runs every step and
reports each exit code; nothing is published until the engine repo is
committed and pushed, which is what the site reads.

After the AFLW count: python aflw/fetch_votes.py <season> saves it (the feed
must say CONCLUDED), then refit the regime on the new season (see CLAUDE.md,
"AFLW Best and Fairest") before trusting any scenario again.
"""

import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RSCRIPT = next((p for p in (r"C:\Program Files\R\R-4.6.0\bin\Rscript.exe",
                            r"C:\Program Files\R\R-4.5.3\bin\Rscript.exe") if os.path.exists(p)), "Rscript")
SEASON = "2026"

STEPS = [
    ("stats", [RSCRIPT, "aflw/fetch_stats.R", SEASON]),
    ("coaches", [RSCRIPT, "aflw/fetch_coaches.R", SEASON]),
    ("frame", [sys.executable, "aflw/build.py"]),
    ("board", [sys.executable, "aflw/predict.py", SEASON]),
    ("site", [sys.executable, "aflw/export_site_aflw.py"]),
]


def main():
    codes = {}
    for name, cmd in STEPS:
        print(f"== {name}", flush=True)
        codes[name] = subprocess.run(cmd, cwd=REPO).returncode
    print("\n" + "  ".join(f"{k} {'ok' if v == 0 else f'FAILED ({v})'}" for k, v in codes.items()))
    return 1 if any(codes.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
