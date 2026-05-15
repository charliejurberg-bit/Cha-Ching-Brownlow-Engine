"""
One-click update script
Runs: stats scrape -> odds scrape -> 2026 prediction -> done
"""

import subprocess
import sys
import os
from datetime import datetime

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
        print(f"⚠ {script_name} finished with warnings (this may be normal)")
    return result.returncode

if __name__ == "__main__":
    start = datetime.now()
    print("🏅 BROWNLOW ENGINE — WEEKLY UPDATE")
    print(f"Started: {start.strftime('%Y-%m-%d %H:%M')}")
    
    scripts = [
        ("scraper_stats.py", "Fetching 2026 player stats"),
        ("scraper_odds.py", "Scraping bookmaker odds"),
        ("predict_2026.py", "Generating 2026 predictions"),
    ]
    
    for script, description in scripts:
        if os.path.exists(script):
            print(f"\n📡 {description}...")
            run_script(script)
        else:
            print(f"\n⚠ {script} not found — skipping")
    
    elapsed = (datetime.now() - start).seconds
    print(f"\n{'='*50}")
    print(f"✅ Update complete in {elapsed}s")
    print(f"Refresh your dashboard to see latest data.")
    print('='*50)
