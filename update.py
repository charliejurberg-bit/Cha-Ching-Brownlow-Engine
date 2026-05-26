"""
One-click update script
Runs: R stats fetch -> R coaches votes -> odds scrape -> 2026 prediction -> done
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
    result = subprocess.run([rscript, r_script_path], capture_output=False, text=True, timeout=180)
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
            print(f"\n&gt;&gt; {description}...")
            run_r_script(r_script, description)
        else:
            print(f"\n! {r_script} not found — skipping")

    py_scripts = [
        ("scraper_odds.py", "Scraping bookmaker odds"),
        ("predict_2026.py", "Generating 2026 predictions"),
    ]
    for script, description in py_scripts:
        if os.path.exists(script):
            print(f"\n&gt;&gt; {description}...")
            run_script(script)
        else:
            print(f"\n! {script} not found — skipping")

    elapsed = (datetime.now() - start).seconds
    print(f"\n{'='*50}")
    print(f"OK Update complete in {elapsed}s")
    print(f"Refresh your dashboard to see latest data.")
    print('='*50)
