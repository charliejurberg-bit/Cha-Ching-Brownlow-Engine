"""
accuracy_report.py

Measures how well the saved per-game predictions match actual Brownlow votes.

IMPORTANT - THESE NUMBERS ARE IN-SAMPLE.
brownlow_model.py runs GroupKFold only to print a CV MAE; it then refits on
everything (`model.fit(X, y, sample_weight=w)`) and writes every
predictions/game_level_{season}.csv from that full-data model. So the
Exp_Votes / P_1 / P_2 / P_3 in those files were produced by a model that had
already seen that season's votes in training. Every table below is therefore
an UPPER BOUND on true out-of-sample skill.

predictions/backtest_results.csv IS genuinely out-of-sample (walk-forward:
train on all prior seasons, predict the target season), but it is aggregated
per player per season - columns are Season, Player, Team, Actual_Votes,
Predicted_Votes, Rank_Predicted, Rank_Actual. It carries no Round_num and no
game identifier, so it cannot support the per-game top-3 questions in
reports 2 and 3. Hence this report runs on game_level_* and labels itself.

Run:
    python accuracy_report.py

Writes accuracy_report.csv alongside the terminal tables.
"""

import argparse
import os

import numpy as np
import pandas as pd

PRED_DIR = "predictions"
SEASONS = list(range(2007, 2026))          # 2026 excluded: no actual votes yet
GAME_KEY = ["Season", "Round_num", "Home.team", "Away.team"]
# Identity key for a player-game. Deliberately NOT ID-based: ID is null for the
# four Billy Wilson rows in both sources, and name+team cannot collide within a
# single game.
DEDUPE_KEY = ["Season", "Round_num", "Player_Name", "Playing.for"]
BACKTEST_PATH = os.path.join(PRED_DIR, "backtest_game_level.csv")

USECOLS = ["Season", "Round_num", "Home.team", "Away.team", "ID", "Player_Name",
           "Playing.for", "Brownlow.Votes", "Exp_Votes", "P_1", "P_2", "P_3",
           "Poll_Prob"]

# Set by main() from --source.
LABEL = "IN-SAMPLE - UPPER BOUND"
OUT_CSV = "accuracy_report.csv"

# Era cuts. 2024 and 2025 were predicted with the misaligned Wheelo rounds that
# commit 7459987 fixed but did not retrain, so those two seasons measure a model
# state that no longer exists. They are kept visible and never pooled into the
# headline.
CUTS = [
    ("2007-2023 (HEADLINE)", list(range(2007, 2024))),
    ("2024-2025 (stale Wheelo)", [2024, 2025]),
    ("2007-2025 (all, reference)", SEASONS),
]

_rows = []          # tidy rows for accuracy_report.csv


def emit(report, cut, key, metric, value):
    _rows.append({"report": report, "cut": cut, "key": key,
                  "metric": metric, "value": value})


# ----------------------------------------------------------------------
# load
# ----------------------------------------------------------------------
def _season_frames(source):
    """Yield (season, raw frame) for the chosen source."""
    if source == "backtest":
        allg = pd.read_csv(BACKTEST_PATH, low_memory=False)
        missing = [c for c in USECOLS if c not in allg.columns]
        if missing:
            raise SystemExit(f"ABORT: {BACKTEST_PATH} missing columns: {missing}")
        for s in sorted(allg["Season"].dropna().unique().astype(int)):
            yield int(s), allg[allg["Season"] == s][USECOLS].copy()
    else:
        for s in SEASONS:
            path = os.path.join(PRED_DIR, f"game_level_{s}.csv")
            yield s, pd.read_csv(path, usecols=USECOLS, low_memory=False)


def load(source, min_season):
    frames, drop_log = [], []
    for s, df in _season_frames(source):
        if s < min_season:
            continue
        n0 = len(df)

        # "Dedupe on the full row" is a no-op on both sources: the duplicated
        # 2025 Round_num 24 players are NOT identical rows. They differ across
        # every Wheelo column (RatingPoints, Rating_Q1-Q4, Equity_*, Supercoach,
        # TimeOnGround, ...) and therefore also in P_1/P_2/P_3/Exp_Votes - one
        # player-game picked up two different Wheelo rating rows, which is the
        # residual Round 24 collision in wheelo_2025.csv. Deduping on the
        # identity key is what actually removes them. keep='first' is arbitrary
        # but deterministic between two rows that cannot be told apart without
        # re-deriving the Wheelo merge.
        df = df.drop_duplicates()
        n1 = len(df)
        df = df.drop_duplicates(subset=DEDUPE_KEY, keep="first")
        n2 = len(df)
        drop_log.append((s, n0, n0 - n1, n1 - n2, n2))
        frames.append(df)

    print("=" * 100)
    print("EXCLUSION 1 - duplicate player-games")
    print("=" * 100)
    print(f"{'season':>7} {'rows in':>9} {'full-row dupes':>15} "
          f"{'key dupes':>11} {'rows kept':>10}")
    tot0 = totf = totk = 0
    for s, n0, nf, nk, n2 in drop_log:
        tot0 += n0
        totf += nf
        totk += nk
        if nf or nk:
            print(f"{s:>7} {n0:>9,} {nf:>15,} {nk:>11,} {n2:>10,}")
    print(f"{'TOTAL':>7} {tot0:>9,} {totf:>15,} {totk:>11,} {tot0 - totf - totk:>10,}")
    print(f"  full-row dedupe dropped {totf} rows (the stated rule is a no-op)")
    print(f"  identity-key dedupe dropped {totk} rows, all 2025 Round_num 24")
    emit("exclusions", "all", "full_row_dupes_dropped", "rows", totf)
    emit("exclusions", "all", "key_dupes_dropped", "rows", totk)

    df = pd.concat(frames, ignore_index=True)
    df["Brownlow.Votes"] = pd.to_numeric(df["Brownlow.Votes"], errors="coerce")
    df["Exp_Votes"] = pd.to_numeric(df["Exp_Votes"], errors="coerce")
    return df


def drop_bad_games(df):
    """Exclude any game whose actual votes do not sum to 6."""
    sums = df.groupby(GAME_KEY, dropna=False)["Brownlow.Votes"].transform("sum")
    bad = sums != 6
    n_bad_games = df.loc[bad, GAME_KEY].drop_duplicates().shape[0]
    print()
    print("=" * 100)
    print("EXCLUSION 2 - games whose actual votes do not sum to 6")
    print("=" * 100)
    if n_bad_games:
        offenders = (df.loc[bad].groupby(GAME_KEY)["Brownlow.Votes"].sum()
                     .reset_index().rename(columns={"Brownlow.Votes": "vote_sum"}))
        print(offenders.to_string(index=False))
    print(f"  games excluded : {n_bad_games}")
    print(f"  rows excluded  : {int(bad.sum()):,}")
    print("  (before the identity-key dedupe this was 2 games / 131 rows in 2025;")
    print("   the duplicated players were double-counting their own votes.)")
    emit("exclusions", "all", "bad_vote_sum_games_dropped", "games", n_bad_games)
    emit("exclusions", "all", "bad_vote_sum_rows_dropped", "rows", int(bad.sum()))
    return df.loc[~bad].copy()


# ----------------------------------------------------------------------
# per-game table
# ----------------------------------------------------------------------
def build_games(df):
    """One row per game with projected top 3 and actual 3/2/1, plus tie flag.

    Deterministic ordering: Exp_Votes desc, then Poll_Prob desc, then P_3 desc,
    then Player_Name asc. The tie flag records whether the raw Exp_Votes at the
    3rd and 4th positions were equal, i.e. whether the tiebreak actually decided
    who made the projected top 3.
    """
    df = df.sort_values(
        ["Season", "Round_num", "Home.team", "Away.team",
         "Exp_Votes", "Poll_Prob", "P_3", "Player_Name"],
        ascending=[True, True, True, True, False, False, False, True],
    )
    out = []
    for key, g in df.groupby(GAME_KEY, dropna=False, sort=False):
        ev = g["Exp_Votes"].values
        names = g["Player_Name"].values
        votes = g["Brownlow.Votes"].values
        if len(g) < 4:
            continue
        proj = list(names[:3])
        tie3 = bool(ev[2] == ev[3])
        a3 = names[votes == 3]
        a2 = names[votes == 2]
        a1 = names[votes == 1]
        if len(a3) != 1 or len(a2) != 1 or len(a1) != 1:
            continue                      # malformed vote allocation
        actual = [a3[0], a2[0], a1[0]]
        overlap = len(set(proj) & set(actual))
        out.append({
            "Season": key[0], "Round_num": key[1],
            "Home.team": key[2], "Away.team": key[3],
            "proj1": proj[0], "proj2": proj[1], "proj3": proj[2],
            "act3": actual[0], "act2": actual[1], "act1": actual[2],
            "overlap": overlap,
            "exact_order": bool(proj[0] == actual[0] and proj[1] == actual[1]
                                and proj[2] == actual[2]),
            "p1_got3": bool(proj[0] == actual[0]),
            "p2_got2": bool(proj[1] == actual[1]),
            "p3_got1": bool(proj[2] == actual[2]),
            "p1_polled": bool(proj[0] in actual),
            "act3_in_proj3": bool(actual[0] in proj),
            "tie_at_3": tie3,
        })
    g = pd.DataFrame(out)
    if not g.empty:
        for k in (3, 2, 1, 0):
            g[f"overlap_{k}"] = g["overlap"] == k
    return g


# ----------------------------------------------------------------------
# reports
# ----------------------------------------------------------------------
def report1(df, cut_name, seasons):
    sub = df[df["Season"].isin(seasons)]
    if sub.empty:
        return
    step = 0.2
    b = np.floor(sub["Exp_Votes"] / step) * step
    b = b.clip(lower=0.0)
    tmp = sub.assign(_b=b.round(1))
    rows = []
    for lo, g in tmp.groupby("_b"):
        n = len(g)
        av = g["Brownlow.Votes"]
        rows.append({
            "bucket": f"[{lo:.1f}, {lo + step:.1f})",
            "n": n,
            "mean_exp": g["Exp_Votes"].mean(),
            "mean_actual": av.mean(),
            "gap": av.mean() - g["Exp_Votes"].mean(),
            "pct_3": (av == 3).mean() * 100,
            "pct_2": (av == 2).mean() * 100,
            "pct_1": (av == 1).mean() * 100,
            "pct_0": (av == 0).mean() * 100,
            "thin": "THIN" if n < 30 else "",
        })
    t = pd.DataFrame(rows)
    print(f"\n--- REPORT 1 calibration | {cut_name} ---   ({LABEL})")
    print(f"{'bucket':<14}{'n':>9}{'mean_exp':>10}{'mean_act':>10}{'gap':>9}"
          f"{'%3':>7}{'%2':>7}{'%1':>7}{'%0':>8}  flag")
    for _, r in t.iterrows():
        print(f"{r['bucket']:<14}{r['n']:>9,}{r['mean_exp']:>10.3f}"
              f"{r['mean_actual']:>10.3f}{r['gap']:>+9.3f}"
              f"{r['pct_3']:>7.1f}{r['pct_2']:>7.1f}{r['pct_1']:>7.1f}"
              f"{r['pct_0']:>8.1f}  {r['thin']}")
        for m in ("n", "mean_exp", "mean_actual", "gap", "pct_3", "pct_2",
                  "pct_1", "pct_0"):
            emit("1_calibration", cut_name, r["bucket"], m, r[m])
        emit("1_calibration", cut_name, r["bucket"], "thin", r["n"] < 30)


def report2(games, cut_name, seasons):
    g = games[games["Season"].isin(seasons)]
    if g.empty:
        return
    n = len(g)
    vals = {
        "games": n,
        "pct_all3_set": (g["overlap"] == 3).mean() * 100,
        "pct_exactly2": (g["overlap"] == 2).mean() * 100,
        "pct_exactly1": (g["overlap"] == 1).mean() * 100,
        "pct_none": (g["overlap"] == 0).mean() * 100,
        "pct_exact_order": g["exact_order"].mean() * 100,
        "pct_tie_at_3rd": g["tie_at_3"].mean() * 100,
    }
    print(f"\n--- REPORT 2 top-3 as a set | {cut_name} ---   ({LABEL})")
    print(f"  games                         : {vals['games']:,}")
    print(f"  all 3 correct (set, any order): {vals['pct_all3_set']:6.2f}%")
    print(f"  exactly 2 correct             : {vals['pct_exactly2']:6.2f}%")
    print(f"  exactly 1 correct             : {vals['pct_exactly1']:6.2f}%")
    print(f"  none correct                  : {vals['pct_none']:6.2f}%")
    print(f"  exact order (3-2-1 all right) : {vals['pct_exact_order']:6.2f}%")
    print(f"  Exp_Votes tie at 3rd position : {vals['pct_tie_at_3rd']:6.2f}%")
    for k, v in vals.items():
        emit("2_top3_set", cut_name, "pooled", k, v)


def report3(games, cut_name, seasons):
    g = games[games["Season"].isin(seasons)]
    if g.empty:
        return
    vals = {
        "games": len(g),
        "pct_top_polled_3": g["p1_got3"].mean() * 100,
        "pct_second_polled_2": g["p2_got2"].mean() * 100,
        "pct_third_polled_1": g["p3_got1"].mean() * 100,
        "pct_top_polled_any": g["p1_polled"].mean() * 100,
        "pct_actual3_in_proj_top3": g["act3_in_proj3"].mean() * 100,
    }
    print(f"\n--- REPORT 3 per-vote hit rate | {cut_name} ---   ({LABEL})")
    print(f"  games                              : {vals['games']:,}")
    print(f"  top projected polled 3             : {vals['pct_top_polled_3']:6.2f}%")
    print(f"  second projected polled 2          : {vals['pct_second_polled_2']:6.2f}%")
    print(f"  third projected polled 1           : {vals['pct_third_polled_1']:6.2f}%")
    print(f"  top projected polled anything      : {vals['pct_top_polled_any']:6.2f}%")
    print(f"  actual 3-vote getter in proj top 3 : {vals['pct_actual3_in_proj_top3']:6.2f}%")
    for k, v in vals.items():
        emit("3_hit_rate", cut_name, "pooled", k, v)


def per_season_table(games, title, cols, labels):
    print(f"\n--- {title} | PER SEASON ---   ({LABEL})")
    hdr = f"{'season':>7}{'games':>8}" + "".join(f"{l:>12}" for l in labels)
    print(hdr)
    for s in SEASONS:
        g = games[games["Season"] == s]
        if g.empty:
            continue
        era = "  <- stale Wheelo" if s >= 2024 else ""
        line = f"{s:>7}{len(g):>8,}"
        for c in cols:
            v = g[c].mean() * 100
            line += f"{v:>11.2f}%"
            emit(title, f"season_{s}", "per_season", c, v)
        print(line + era)


# ----------------------------------------------------------------------
def main():
    global LABEL, OUT_CSV
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", choices=("game_level", "backtest"),
                    default="game_level",
                    help="game_level = in-sample (default); "
                         "backtest = out-of-sample walk-forward")
    ap.add_argument("--min-season", type=int, default=2007,
                    help="restrict to seasons >= this, for like-for-like cuts")
    ap.add_argument("--out", default=None, help="output CSV path")
    args = ap.parse_args()

    oos = args.source == "backtest"
    LABEL = "OUT-OF-SAMPLE" if oos else "IN-SAMPLE - UPPER BOUND"
    OUT_CSV = args.out or ("accuracy_report_oos.csv" if oos
                           else "accuracy_report.csv")

    print("=" * 100)
    print(f"ACCURACY REPORT   ***  {LABEL}  ***")
    print("=" * 100)
    if oos:
        print(f"source: {BACKTEST_PATH}")
        print("Walk-forward: for each target season the model was trained ONLY on")
        print("strictly prior seasons (backtest.py: train = Season < target_season),")
        print("so no row below was seen by the model that scored it. These are")
        print("honest out-of-sample figures, not a ceiling.")
    else:
        print("source: predictions/game_level_*.csv")
        print("These predictions come from a model refit on ALL seasons")
        print("(brownlow_model.py: model.fit(X, y, sample_weight=w), then")
        print("model.predict_proba per season). The model saw these votes in")
        print("training. Treat every number as a ceiling.")
    print(f"season floor: {args.min_season}")

    df = load(args.source, args.min_season)
    df = drop_bad_games(df)
    games = build_games(df)

    print()
    print("=" * 100)
    print("GAME COUNTS AFTER EXCLUSIONS")
    print("=" * 100)
    gc = games.groupby("Season").size()
    print(f"{'season':>7}{'games':>8}")
    for s, n in gc.items():
        print(f"{int(s):>7}{n:>8,}")
        emit("game_counts", f"season_{int(s)}", "games", "n", n)
    print(f"{'TOTAL':>7}{len(games):>8,}")

    print()
    print("#" * 100)
    print("# REPORT 1 - CALIBRATION BY PROJECTED-VOTE BUCKET")
    print("#" * 100)
    for name, seasons in CUTS:
        report1(df, name, seasons)
    print("\n--- REPORT 1 per season: gap = mean(actual) - mean(projected), "
          "all rows ---")
    print(f"{'season':>7}{'rows':>10}{'mean_exp':>11}{'mean_act':>11}{'gap':>10}")
    for s in SEASONS:
        sub = df[df["Season"] == s]
        me, ma = sub["Exp_Votes"].mean(), sub["Brownlow.Votes"].mean()
        era = "  <- stale Wheelo" if s >= 2024 else ""
        print(f"{s:>7}{len(sub):>10,}{me:>11.4f}{ma:>11.4f}{ma - me:>+10.4f}{era}")
        emit("1_calibration", f"season_{s}", "per_season", "mean_exp", me)
        emit("1_calibration", f"season_{s}", "per_season", "mean_actual", ma)
        emit("1_calibration", f"season_{s}", "per_season", "gap", ma - me)

    print()
    print("#" * 100)
    print("# REPORT 2 - TOP 3 AS A SET")
    print("#" * 100)
    for name, seasons in CUTS:
        report2(games, name, seasons)
    per_season_table(
        games, "2_top3_set",
        ["overlap_3", "overlap_2", "overlap_1", "overlap_0", "exact_order", "tie_at_3"],
        ["all 3", "exactly 2", "exactly 1", "none", "exact ord", "tie@3rd"])

    print()
    print("#" * 100)
    print("# REPORT 3 - PER-VOTE HIT RATE")
    print("#" * 100)
    for name, seasons in CUTS:
        report3(games, name, seasons)
    per_season_table(
        games, "3_hit_rate",
        ["p1_got3", "p2_got2", "p3_got1", "p1_polled", "act3_in_proj3"],
        ["top->3", "2nd->2", "3rd->1", "top polled", "act3 in t3"])

    pd.DataFrame(_rows).to_csv(OUT_CSV, index=False)
    print()
    print("=" * 100)
    print(f"Full output written to {OUT_CSV} ({len(_rows):,} rows)")
    print(f"ALL FIGURES ABOVE ARE {LABEL}")
    print("=" * 100)


if __name__ == "__main__":
    main()
