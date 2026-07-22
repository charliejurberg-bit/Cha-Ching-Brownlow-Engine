"""
Merge Wheelo CSVs
Run this if you manually downloaded CSVs from Wheelo
Place all CSVs in data_wheelo/ folder and run this script
"""

import pandas as pd
import os
import re
import glob

OUTPUT_DIR = "data_wheelo"
all_data = []

print("Merging Wheelo CSVs...")

# Find all wheelo CSVs
files = list(set(
    glob.glob(f"{OUTPUT_DIR}/wheelo_*.csv") +
    glob.glob(f"{OUTPUT_DIR}/downloads/*.csv") +
    glob.glob(f"{OUTPUT_DIR}/*.csv")
))


def _is_ingestable(path):
    """Only per-season Wheelo CSVs are merged.

    Excluded:
      - *all_seasons*  the merge output itself (would compound on every run)
      - *_prev*        point-in-time snapshots (e.g. wheelo_2026_prev.csv);
                       ingesting one duplicates that season's rows
      - non-.csv       spreadsheets dropped in data_wheelo/ (e.g. the xlsx)
    """
    fname = os.path.basename(path).lower()
    if not fname.endswith('.csv'):
        return False
    if 'all_seasons' in fname:
        return False
    if '_prev' in fname:
        return False
    return True


skipped = sorted(os.path.basename(f) for f in files if not _is_ingestable(f))
files = [f for f in files if _is_ingestable(f)]

print(f"Ingesting {len(files)} CSV files:")
for f in sorted(files):
    print(f"  - {os.path.basename(f)}")
if skipped:
    print(f"Skipped {len(skipped)}: {', '.join(skipped)}")

for filepath in sorted(files):
    try:
        df = pd.read_csv(filepath)
        
        # Try to extract season/round from filename
        fname = os.path.basename(filepath)
        season_match = re.search(r'(20\d{2})', fname)
        round_match = re.search(r'[Rr]ound?[\s_]?(\d+)', fname)
        
        if 'Season' not in df.columns and season_match:
            df['Season'] = int(season_match.group(1))
        if 'Round' not in df.columns and round_match:
            df['Round'] = int(round_match.group(1))
        
        all_data.append(df)
        print(f"  ✓ {fname}: {len(df)} rows, {len(df.columns)} cols")
    except Exception as e:
        print(f"  ✗ {filepath}: {e}")

if all_data:
    df_all = pd.concat(all_data, ignore_index=True)
    df_all.to_csv(f"{OUTPUT_DIR}/wheelo_all_seasons.csv", index=False)
    print(f"\n✓ Merged {len(df_all):,} rows")
    if 'Season' in df_all.columns:
        print("Rows per season:")
        for season, count in df_all.groupby('Season').size().items():
            print(f"  {int(season)}: {count:,}")
    print(f"Columns: {list(df_all.columns)}")
else:
    print("No data to merge")
