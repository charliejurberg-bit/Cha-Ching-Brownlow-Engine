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
    """Pull 2026 coaches votes via fitzRoy R script"""
    import subprocess
    r_script = """
library(fitzRoy)
coaches <- fetch_coaches_votes(season = 2026, comp = "AFLM")
write.csv(coaches, "data_2026/coaches_votes_2026.csv", row.names = FALSE)
cat("Done\\n")
"""
    script_path = "data_2026/fetch_coaches.R"
    with open(script_path, 'w') as f:
        f.write(r_script)
    
    # Try to find Rscript
    r_paths = [
        r"C:\Program Files\R\R-4.6.0\bin\Rscript.exe",
        r"C:\Program Files\R\R-4.5.0\bin\Rscript.exe",
        r"C:\Program Files\R\R-4.4.0\bin\Rscript.exe",
        r"C:\Program Files\R\R-4.3.0\bin\Rscript.exe",
        "Rscript"
    ]
    
    for rpath in r_paths:
        try:
            result = subprocess.run([rpath, script_path], capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                print("✓ Coaches votes fetched via R")
                return True
            else:
                print(f"R error: {result.stderr[:200]}")
        except FileNotFoundError:
            continue
        except Exception as e:
            print(f"R error: {e}")
            continue
    
    print("⚠ Could not run R automatically. Please run fetch_coaches.R manually in RGui.")
    return False

if __name__ == "__main__":
    print("=" * 50)
    print("2026 STATS SCRAPER")
    print("=" * 50)
    df = fetch_squiggle_stats(2026)
    fetch_coaches_votes_2026()
    print("\nDone. Run predict_2026.py next.")
