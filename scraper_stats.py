"""
2026 Stats Scraper
Pulls current season player stats from Squiggle API round by round
"""

import requests
import pandas as pd
import os
import json
from datetime import datetime

os.makedirs("data_2026", exist_ok=True)

HEADERS = {"User-Agent": "BrownlowEngine/1.0 (personal research)"}

def fetch_squiggle_stats(season=2026):
    all_rows = []
    print(f"Fetching {season} stats from Squiggle API...")
    
    for round_num in range(1, 30):
        url = f"https://api.squiggle.com.au/?q=stats;season={season};round={round_num}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                print(f"  Round {round_num}: stopped (status {r.status_code})")
                break
            data = r.json()
            if 'stats' not in data or len(data['stats']) == 0:
                print(f"  Round {round_num}: no data — season complete up to previous round")
                break
            rows = data['stats']
            for row in rows:
                row['season'] = season
                row['round'] = round_num
            all_rows.extend(rows)
            print(f"  Round {round_num}: {len(rows)} player rows")
        except Exception as e:
            print(f"  Round {round_num}: error — {e}")
            break
    
    if not all_rows:
        print("No data retrieved from Squiggle.")
        return None
    
    df = pd.DataFrame(all_rows)
    df.to_csv("data_2026/squiggle_stats_2026.csv", index=False)
    print(f"\n✓ Saved {len(df)} rows to data_2026/squiggle_stats_2026.csv")
    print(f"  Columns: {list(df.columns)}")
    return df

def fetch_coaches_votes_2026():
    """Coaches votes for season.LIVE_SEASON, through the GUARDED fetch_coaches.R.

    This used to write its own R script, with season 2026 and an unconditional
    write.csv, to data_2026/fetch_coaches.R and run it. That is the refetch
    CLAUDE.md warns deletes the hand-transcribed rounds 24-25, and on 27
    September 2026 the feed would have done exactly that (finals labelled as
    rounds 24-29). fetch_coaches.R refuses any fetch missing a game already on
    disk. season.py can also switch the fetch off for a season, as it is for 2026.
    """
    import subprocess
    import season
    if not season.cfg().get("coaches_fetch"):
        print(f"coaches fetch is off for {season.LIVE_SEASON} in season.py; skipped")
        return False
    r_paths = [
        r"C:\Program Files\R\R-4.6.0\bin\Rscript.exe",
        r"C:\Program Files\R\R-4.5.3\bin\Rscript.exe",
        r"C:\Program Files\R\R-4.5.0\bin\Rscript.exe",
        r"C:\Program Files\R\R-4.4.0\bin\Rscript.exe",
        "Rscript",
    ]
    for rpath in r_paths:
        try:
            result = subprocess.run([rpath, "fetch_coaches.R", str(season.LIVE_SEASON)],
                                    capture_output=True, text=True, timeout=300)
        except FileNotFoundError:
            continue
        print(result.stdout[-400:])
        return result.returncode == 0
    print("Could not find Rscript. Run: Rscript fetch_coaches.R <season>")
    return False

if __name__ == "__main__":
    print("=" * 50)
    import season
    print(f"{season.LIVE_SEASON} STATS SCRAPER")
    print("=" * 50)
    df = fetch_squiggle_stats(season.LIVE_SEASON)
    fetch_coaches_votes_2026()
    print("\nDone. Run predict_2026.py next.")
