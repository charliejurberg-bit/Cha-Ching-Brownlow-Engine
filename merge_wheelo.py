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
files = [f for f in files if 'all_seasons' not in f]
print(f"Found {len(files)} CSV files")

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
    print(f"Columns: {list(df_all.columns)}")
else:
    print("No data to merge")
