"""
merge_extended_data.py
Combines the newly fetched 2007-2014 stats and 2006-2014 coaches votes
with the existing 2015-2025 files.

Produces:
  fitzroy_stats_all.csv       (2007–2025 player stats)
  coaches_votes_all.csv       (2006–2025 coaches votes)

Run after fetch_extended_data.R:
  python merge_extended_data.py
"""

import pandas as pd
import os

def check_file(path):
    if not os.path.exists(path):
        print(f"ERROR: {path} not found. Run fetch_extended_data.R first.")
        return False
    return True

# ── Merge player stats ────────────────────────────────────────
print("Merging player stats...")

new_stats_path = "fitzroy_stats_2007_2014.csv"
old_stats_path = "fitzroy_stats_2015_2025.csv"

if not check_file(new_stats_path) or not check_file(old_stats_path):
    exit(1)

stats_new = pd.read_csv(new_stats_path, low_memory=False)
stats_old = pd.read_csv(old_stats_path, low_memory=False)

# Align columns — old file is the reference; add any missing cols to new as NaN
for col in stats_old.columns:
    if col not in stats_new.columns:
        stats_new[col] = float('nan')

stats_all = pd.concat([stats_new[stats_old.columns], stats_old], ignore_index=True)
stats_all = stats_all.sort_values(['Season', 'Round'], ignore_index=True)
stats_all.to_csv("fitzroy_stats_all.csv", index=False)
print(f"  {len(stats_new):,} new rows + {len(stats_old):,} existing = {len(stats_all):,} total")
print(f"  Seasons: {sorted(stats_all['Season'].dropna().unique().astype(int).tolist())}")
print(f"  -> fitzroy_stats_all.csv")

# ── Merge coaches votes ───────────────────────────────────────
print("\nMerging coaches votes...")

new_cv_path = "coaches_votes_2006_2014.csv"
old_cv_path = "coaches_votes_2015_2025.csv"

if not check_file(new_cv_path) or not check_file(old_cv_path):
    print("WARNING: Could not merge coaches votes.")
else:
    cv_new = pd.read_csv(new_cv_path, low_memory=False)
    cv_old = pd.read_csv(old_cv_path, low_memory=False)

    for col in cv_old.columns:
        if col not in cv_new.columns:
            cv_new[col] = float('nan')

    cv_all = pd.concat([cv_new[cv_old.columns], cv_old], ignore_index=True)
    cv_all = cv_all.sort_values(['Season', 'Round'], ignore_index=True)
    cv_all.to_csv("coaches_votes_all.csv", index=False)
    print(f"  {len(cv_new):,} new rows + {len(cv_old):,} existing = {len(cv_all):,} total")
    print(f"  Seasons: {sorted(cv_all['Season'].dropna().unique().astype(int).tolist())}")
    print(f"  -> coaches_votes_all.csv")

print("\nDone. Re-run brownlow_model.py and backtest.py to use extended data.")
