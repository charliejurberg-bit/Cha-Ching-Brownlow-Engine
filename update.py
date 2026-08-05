"""One-click weekly update.

Ten steps in two loops, each run as its own subprocess. The R loop goes first
because predict_2026.py depends on the CSVs it writes.

R loop:
    1. data_2026/fetch_stats_2026.R   2026 player stats from AFLTables (fitzRoy)
    2. data_2026/fetch_coaches.R      2026 coaches votes (fitzRoy)

Python loop:
    3. scraper_odds.py         Oddschecker bookmaker odds
    4. scraper_betfair.py      Betfair predictions
    5. scraper_espn.py         ESPN predictions, season totals and per-round
    6. scraper_afl.py          AFL Predictor votes
    7. update_wheelo_2026.py   Wheelo 2026 ratings
    8. predict_2026.py         2026 predictions
    9. draft_posts.py          drafts/round_<display>.md
   10. landing_summary.py      site/landing.json

Step 10 writes an artifact, not a page. site/landing.json is git tracked, so
running this changes nothing the public can see: the numbers reach the live site
only once the file is committed and pushed, and an uncommitted run leaves the
site on last week's figures. Committing is necessary rather than sufficient. The
front end is a separate repo that statically imports its own copy of the file,
so the pushed artifact still has to get across to that repo before a build will
show it.

Nothing here stops on failure. A missing target is skipped with a note and a
non-zero exit only prints a warning, so every step runs regardless of what the
step before it did. Each step's own exit code is therefore the only honest
report of whether it worked, and reading the console is the only way to find
out. The R steps additionally carry a wall-clock limit (R_TIMEOUT); exceeding it
kills that step and is logged like any other failure, rather than ending the
run.

streaks.py is NOT part of either loop and nothing imports it. The post-round
sequence is two commands:

    python update.py
    python streaks.py     writes drafts/streaks_r<display round>.md
"""

import subprocess
import sys
import os
from datetime import datetime

R_PATHS = [
    r"C:\Program Files\R\R-4.6.0\bin\Rscript.exe",
    r"C:\Program Files\R\R-4.5.3\bin\Rscript.exe",
    r"C:\Program Files\R\R-4.5.0\bin\Rscript.exe",
    r"C:\Program Files\R\R-4.4.0\bin\Rscript.exe",
    r"C:\Program Files\R\R-4.3.0\bin\Rscript.exe",
    "Rscript",
]

# Wall-clock limit for one R step. Quoted in the timeout warning, so it lives
# here rather than inline at the call.
R_TIMEOUT = 180

def find_rscript():
    for path in R_PATHS:
        try:
            result = subprocess.run([path, "--version"], capture_output=True, timeout=10)
            if result.returncode == 0:
                return path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None

def run_r_script(r_script_path, description):
    print(f"\n{'='*50}")
    print(f"Running R: {description}...")
    print('='*50)
    rscript = find_rscript()
    if not rscript:
        print("! Rscript not found — skipping R step. Run manually in RStudio.")
        return 1
    # A timeout is the one call in here that raises, and an uncaught one took
    # the whole update down with it — the R steps run first, so the eight
    # Python steps after them never started. Treated like a failed Python step
    # instead: logged, non-zero return, chain continues. Nothing is lost from
    # the console, since capture_output=False means whatever R printed before
    # the kill has already been written out.
    #
    # TimeoutExpired only. A missing binary cannot reach here (find_rscript
    # validated it with --version) and a missing .R file is checked by the
    # caller, so a broader catch would bury faults rather than step past a
    # known one.
    try:
        result = subprocess.run([rscript, r_script_path], capture_output=False,
                                text=True, timeout=R_TIMEOUT)
    except subprocess.TimeoutExpired:
        print(f"! {r_script_path} exceeded the {R_TIMEOUT}s limit and was killed, "
              f"continuing to the next step")
        return 1
    if result.returncode != 0:
        print(f"! R script finished with warnings (this may be normal)")
    return result.returncode

def run_script(script_name):
    print(f"\n{'='*50}")
    print(f"Running {script_name}...")
    print('='*50)
    result = subprocess.run(
        [sys.executable, script_name],
        capture_output=False,
        text=True
    )
    if result.returncode != 0:
        print(f"! {script_name} finished with warnings (this may be normal)")
    return result.returncode

if __name__ == "__main__":
    start = datetime.now()
    print("BROWNLOW ENGINE -- WEEKLY UPDATE")
    print(f"Started: {start.strftime('%Y-%m-%d %H:%M')}")

    # R data fetch first — predict_2026.py depends on these CSVs
    r_scripts = [
        ("data_2026/fetch_stats_2026.R", "Fetching 2026 player stats from AFLTables (R/fitzRoy)"),
        ("data_2026/fetch_coaches.R", "Fetching 2026 coaches votes (R/fitzRoy)"),
    ]
    for r_script, description in r_scripts:
        if os.path.exists(r_script):
            print(f"\n>> {description}...")
            run_r_script(r_script, description)
        else:
            print(f"\n! {r_script} not found — skipping")

    py_scripts = [
        ("scraper_odds.py",        "Scraping bookmaker odds"),
        ("scraper_betfair.py",     "Scraping Betfair Brownlow predictions"),
        ("scraper_espn.py",        "Scraping ESPN Brownlow predictions (season + per-round votes)"),
        ("scraper_afl.py",         "Scraping AFL Predictor Brownlow votes"),
        ("update_wheelo_2026.py",  "Updating Wheelo 2026 ratings"),
        ("predict_2026.py",        "Generating 2026 predictions"),
        ("draft_posts.py",         "Generating draft posts"),
        ("landing_summary.py",     "Writing site/landing.json for the front door"),
    ]
    for script, description in py_scripts:
        if os.path.exists(script):
            print(f"\n>> {description}...")
            run_script(script)
        else:
            print(f"\n! {script} not found — skipping")

    elapsed = (datetime.now() - start).seconds
    print(f"\n{'='*50}")
    print(f"OK Update complete in {elapsed}s")
    print(f"Refresh your dashboard to see latest data.")
    print('='*50)
