"""
add_cha_ching_history.py
Adds historical Cha Ching tips (Rounds 2-10, 2026) to data_betting/bets.csv.

- New bets are appended with is_cha_ching=True, stake=0, profit_loss=0.
- If an exact match (selection + bookmaker + odds) already exists in the CSV,
  that row is updated to is_cha_ching=True in-place instead of duplicating.
"""

import os
import uuid
import pandas as pd
from collections import Counter

DATA_DIR = "data_betting"
BETS_CSV = f"{DATA_DIR}/bets.csv"

BETS_COLS = [
    'bet_id', 'date', 'match', 'market_type', 'selection',
    'bookmaker', 'odds', 'stake', 'result', 'profit_loss',
    'is_cha_ching', 'cha_ching_criteria', 'notes',
]

DISP  = 'Disposals O/U'
GOAL  = 'Goals O/U'
MULTI = 'Multi'

# Approximate Thursday start-of-round dates for AFL 2026
ROUND_DATES = {
    2:  '2026-03-26',
    3:  '2026-04-02',
    4:  '2026-04-09',
    5:  '2026-04-17',
    6:  '2026-04-24',
    7:  '2026-05-01',
    8:  '2026-05-08',
    9:  '2026-05-15',
    10: '2026-05-22',
}

# Each entry: (round, market_type, selection, bookmaker, odds, result, notes)
# bookmaker='' uses 'Other'; odds=0.0 means unrecorded.
HISTORY = [
    # ── Round 2 ──────────────────────────────────────────────────────────────
    (2,  MULTI, "Sheldrick 20+ AND McInerney 20+",
                "TAB",        1.35, 'Win',  "Miss by 1 promo on TAB, without Heeney and Gulden"),
    (2,  GOAL,  "Thilthorpe 2+ goals",
                "",           1.44, 'Win',  ""),
    (2,  DISP,  "Harley Reid 20+",
                "Ladbrokes",  1.88, 'Win',  ""),

    # ── Round 3 ──────────────────────────────────────────────────────────────
    (3,  DISP,  "Sam Berry 20+",
                "Ladbrokes",  2.55, 'Win',  ""),
    (3,  DISP,  "Toby Greene 20+",
                "",           1.71, 'Win',  ""),
    (3,  DISP,  "Caleb Daniel under 23.5",
                "",           1.89, 'Win',  ""),

    # ── Round 4 ──────────────────────────────────────────────────────────────
    (4,  DISP,  "Isaac Heeney 22+",
                "Sportsbet",  1.63, 'Win',  ""),
    (4,  GOAL,  "Charlie Curnow 3+",
                "Ladbrokes",  1.57, 'Win',  ""),
    (4,  GOAL,  "Aaron Naughton 3+",
                "Bet365",     1.67, 'Win',  ""),

    # ── Round 5 ──────────────────────────────────────────────────────────────
    (5,  DISP,  "Niel Erasmus 20+",
                "TAB",        1.58, 'Loss', "Miss by 1 promo on TAB, had 18"),
    (5,  DISP,  "Sparrow 20+",
                "TAB",        1.70, 'Loss', "Had 18"),
    (5,  MULTI, "Jeremy Cameron AND Shannon Neale combine 5+",
                "Ladbrokes",  1.46, 'Win',  ""),

    # ── Round 6 ──────────────────────────────────────────────────────────────
    (6,  DISP,  "Sam Berry 20+",
                "",           1.48, 'Win',  ""),
    (6,  DISP,  "Izak Rankine 19+",
                "",           1.67, 'Win',  ""),
    (6,  DISP,  "Blake Howes 13+",
                "Pointsbet",  1.59, 'Win',  ""),
    (6,  DISP,  "Harley Reid 20+",
                "TAB",        1.72, 'Win',  ""),

    # ── Round 7 ──────────────────────────────────────────────────────────────
    (7,  GOAL,  "Charlie Curnow 3+",
                "",           0.0,  'Win',  ""),
    (7,  GOAL,  "Charlie Curnow 5+",
                "",           0.0,  'Win',  ""),
    (7,  DISP,  "GRLJ 18+",
                "Ladbrokes",  1.50, 'Win',  ""),
    (7,  DISP,  "Luke Jackson 19+",
                "Pointsbet",  1.56, 'Win',  ""),
    (7,  DISP,  "Elliot Yeo 19+",
                "Sportsbet",  1.61, 'Win',  ""),
    (7,  DISP,  "Ben Keays 13+",
                "Pointsbet",  1.63, 'Win',  ""),
    (7,  DISP,  "Toby Greene 20+",
                "Bet365",     1.65, 'Win',  ""),
    (7,  DISP,  "Ben Keays 15+",
                "Pointsbet",  2.20, 'Win',  ""),

    # ── Round 8 ──────────────────────────────────────────────────────────────
    (8,  MULTI, "Tim Kelly 19+ AND Harley Reid 20+ AND Yeo 17+ (SGM)",
                "Sportsbet",  1.80, 'Win',  ""),
    (8,  MULTI, "Sparrow 14+ AND Kysaiah Pickett 14+ AND Connor Idun 13+",
                "Pointsbet",  1.78, 'Win',  ""),

    # ── Round 9 ──────────────────────────────────────────────────────────────
    (9,  DISP,  "Durham over 20.5",
                "Ladbrokes",  1.91, 'Win',  ""),
    (9,  GOAL,  "Dan Curtin 1+",
                "Sportsbet",  1.95, 'Win',  ""),
    (9,  GOAL,  "Dan Curtin 2 goals",
                "Bet365",     6.25, 'Loss', ""),
    (9,  MULTI, "Sparrow 18+ AND Yeo 16+ AND W Duursma 14+",
                "Pointsbet",  1.89, 'Win',  ""),

    # ── Round 10 ─────────────────────────────────────────────────────────────
    (10, GOAL,  "Treacy 3+",
                "Sportsbet",  2.12, 'Loss', ""),
]


def _dedup_key(selection: str, bookmaker: str, odds: float) -> tuple:
    return (
        str(selection).strip().lower(),
        str(bookmaker).strip().lower(),
        str(round(float(odds), 2)),
    )


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    # Load existing
    if os.path.exists(BETS_CSV):
        existing = pd.read_csv(BETS_CSV)
        for c in BETS_COLS:
            if c not in existing.columns:
                existing[c] = None
    else:
        existing = pd.DataFrame(columns=BETS_COLS)

    # Build dedup index: key -> row index in existing
    existing_index = {}
    for i, row in existing.iterrows():
        k = _dedup_key(row['selection'], row['bookmaker'], row['odds'] or 0)
        existing_index[k] = i

    new_rows   = []
    updated    = []
    already_cc = []

    for (rnd, mtype, selection, bookmaker, odds, result, notes) in HISTORY:
        bookie = bookmaker.strip() if bookmaker.strip() else 'Other'
        key = _dedup_key(selection, bookie, odds)

        if key in existing_index:
            idx = existing_index[key]
            if existing.loc[idx, 'is_cha_ching']:
                already_cc.append(selection)
            else:
                existing.loc[idx, 'is_cha_ching'] = True
                if notes and str(existing.loc[idx, 'notes']).strip() in ('', 'nan', 'None'):
                    existing.loc[idx, 'notes'] = notes
                updated.append(selection)
        else:
            new_rows.append({
                'bet_id':             str(uuid.uuid4())[:8],
                'date':               ROUND_DATES[rnd],
                'match':              f"Round {rnd} 2026",
                'market_type':        mtype,
                'selection':          selection,
                'bookmaker':          bookie,
                'odds':               round(float(odds), 2) if odds else 0.0,
                'stake':              0.0,
                'result':             result,
                'profit_loss':        0.0,
                'is_cha_ching':       True,
                'cha_ching_criteria': '',
                'notes':              notes,
            })

    # Append new rows and save
    if new_rows:
        new_df   = pd.DataFrame(new_rows, columns=BETS_COLS)
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = existing

    combined.to_csv(BETS_CSV, index=False)

    # Stats over all CC bets we processed
    all_processed = new_rows + [
        {'result': existing.loc[existing_index[_dedup_key(s, b or 'Other', o)], 'result'],
         'market_type': mtype, 'selection': s}
        for (rnd, mtype, s, b, o, res, notes) in HISTORY
        if _dedup_key(s, b or 'Other', o) in existing_index
    ]
    all_results = [r['result'] for r in new_rows] + [
        existing.loc[i, 'result'] for i in [existing_index[_dedup_key(s, b or 'Other', o)]
        for (_, _, s, b, o, _, _) in HISTORY
        if _dedup_key(s, b or 'Other', o) in existing_index]
    ]
    total  = len(HISTORY)
    wins   = sum(1 for r in [nr['result'] for nr in new_rows] +
                 [existing.loc[existing_index[_dedup_key(s, b or 'Other', o)], 'result']
                  for (_, _, s, b, o, _, _) in HISTORY
                  if _dedup_key(s, b or 'Other', o) in existing_index]
                 if r == 'Win')
    losses = sum(1 for (_, _, s, b, o, res, _) in HISTORY if res == 'Loss')
    rate   = wins / total * 100 if total > 0 else 0.0

    mkt_counts = Counter(mtype for (_, mtype, *_) in HISTORY)

    print()
    print("=" * 50)
    print("  CHA CHING HISTORY — ROUNDS 2-10 2026")
    print("=" * 50)
    print(f"  Added (new) : {len(new_rows)}")
    print(f"  Updated CC  : {len(updated)}")
    if already_cc:
        print(f"  Already CC  : {len(already_cc)}")
    print()
    print("  RESULTS (all 31 tips):")
    print(f"    Total  : {total}")
    print(f"    Wins   : {wins}")
    print(f"    Losses : {losses}")
    print(f"    Win %%  : {wins/total*100:.1f}%%")
    print()
    print("  BY MARKET:")
    for mkt in [DISP, GOAL, MULTI]:
        print(f"    {mkt:<20} {mkt_counts.get(mkt, 0)}")
    if updated:
        print()
        print("  UPDATED (is_cha_ching set to True):")
        for s in updated:
            print(f"    {s}")
    print()
    print(f"  Saved: {BETS_CSV}")
    print("=" * 50)


if __name__ == "__main__":
    main()
