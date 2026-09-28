"""One-click weekly update.

Every step runs for season.LIVE_SEASON (season.py); the "_2026" in some script
names predates that and means nothing now.

Eleven steps in two loops (twelve when the coaches fetch is on), each run as its
own subprocess. The R loop goes first because predict_2026.py depends on the
CSVs it writes.

R loop:
    1. fetch_stats.R <season>    player stats from AFLTables (fitzRoy)
       fetch_coaches.R <season>  coaches votes, GUARDED, only when season.py
                                 sets coaches_fetch (off for 2026, on for 2027)

Python loop:
    2. scraper_odds.py         Oddschecker bookmaker odds
    3. scraper_betfair.py      Betfair predictions
    4. scraper_espn.py         ESPN predictions, season totals and per-round
                               (skips until season.py has the season's article)
    5. scraper_afl.py          AFL Predictor votes
    6. update_wheelo_2026.py   Wheelo ratings
    7. scraper_advanced.py     footywire advanced stats for the season
    8. build_score_involvements.py   joins them onto fitzRoy IDs
    9. predict_2026.py         predictions (stack.py applies here once it
                               is trained on an earlier season than the one
                               predicted; see stack.py)
   10. draft_posts.py          drafts/round_<display>.md
   11. landing_summary.py      site/landing.json
   12. export_site.py          site/data/, the JSON the Next.js pages read

Steps 11 and 12 write artifacts, not pages. Both are git tracked, so running
this changes nothing the public can see: the numbers reach the live site only
once the files are committed and pushed to master, and an uncommitted run leaves
the site on last week's figures. The front end (the cha-ching-brownlow repo)
fetches them from raw.githubusercontent.com and revalidates hourly, falling back
to its own committed copy of landing.json when the fetch fails.

Nothing here stops on failure. A missing target is skipped with a note and a
non-zero exit only prints a warning, so every step runs regardless of what the
step before it did. Each step's own exit code is therefore the only honest
report of whether it worked, and reading the console is the only way to find
out. The R step additionally carries a wall-clock limit (R_TIMEOUT); exceeding
it kills that step and is logged like any other failure, rather than ending the
run.

streaks.py is NOT part of either loop and nothing imports it. The post-round
sequence is two commands:

    python update.py
    python streaks.py     writes drafts/streaks_r<display round>.md
"""

import subprocess
import sys
import os

import season
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

def run_r_script(r_script_path, description, args=()):
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
        result = subprocess.run([rscript, r_script_path, *args], capture_output=False,
                                text=True, timeout=R_TIMEOUT)
    except subprocess.TimeoutExpired:
        print(f"! {r_script_path} exceeded the {R_TIMEOUT}s limit and was killed, "
              f"continuing to the next step")
        return 1
    if result.returncode != 0:
        print(f"! R script finished with warnings (this may be normal)")
    return result.returncode

def run_script(script_name, args=()):
    print(f"\n{'='*50}")
    print(f"Running {script_name}...")
    print('='*50)
    result = subprocess.run(
        [sys.executable, script_name, *args],
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
    SEASON = str(season.LIVE_SEASON)
    r_scripts = [
        ("fetch_stats.R", (SEASON,), f"Fetching {SEASON} player stats from AFLTables (R/fitzRoy)"),
    ]
    # The coaches fetch is on per season in season.py. It is off for 2026, whose
    # rounds 24-25 were transcribed by hand past where fitzRoy's feed stopped.
    # fetch_coaches.R replaces the old unguarded data_2026/fetch_coaches.R and
    # refuses to write a fetch missing ANY game already on disk, which is what
    # a refetch did on 27 September 2026 (finals labelled as rounds 24-29).
    if season.cfg().get("coaches_fetch"):
        r_scripts.append(("fetch_coaches.R", (SEASON,), f"Fetching {SEASON} coaches votes (R/fitzRoy, guarded)"))
    for r_script, args, description in r_scripts:
        if os.path.exists(r_script):
            print(f"\n>> {description}...")
            run_r_script(r_script, description, args)
        else:
            print(f"\n! {r_script} not found — skipping")

    py_scripts = [
        ("scraper_odds.py",        "Scraping bookmaker odds"),
        ("scraper_betfair.py",     "Scraping Betfair Brownlow predictions"),
        ("scraper_espn.py",        "Scraping ESPN Brownlow predictions (season + per-round votes)"),
        ("scraper_afl.py",         "Scraping AFL Predictor Brownlow votes"),
        ("update_wheelo_2026.py",  f"Updating Wheelo {SEASON} ratings"),
        # footywire's metres gained / real score involvements / intercepts. The
        # stack's ranker reads them (stack.py) and the rebuilt join also feeds the
        # dashboard's Stat Filter. build_score_involvements.py joins the rounds
        # already in game_level_2026.csv; the round being predicted is joined in
        # memory by stack.advanced_for. So: scrape, rebuild, predict.
        (("scraper_advanced.py", SEASON), "Scraping footywire advanced stats"),
        ("build_score_involvements.py", "Joining footywire stats onto player IDs"),
        ("predict_2026.py",        f"Generating {SEASON} predictions"),
        ("draft_posts.py",         "Generating draft posts"),
        ("landing_summary.py",     "Writing site/landing.json for the front door"),
        ("export_site.py",         "Writing site/data/ for the Next.js pages"),
    ]
    for script, description in py_scripts:
        # An entry is a script name, or a (script, arg, ...) tuple for a step
        # that needs arguments, like the season scraper_advanced.py scrapes.
        script, args = (script[0], script[1:]) if isinstance(script, tuple) else (script, ())
        if os.path.exists(script):
            print(f"\n>> {description}...")
            run_script(script, args)
        else:
            print(f"\n! {script} not found — skipping")

    elapsed = (datetime.now() - start).seconds
    print(f"\n{'='*50}")
    print(f"OK Update complete in {elapsed}s")
    print(f"Refresh your dashboard to see latest data.")
    print('='*50)
