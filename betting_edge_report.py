"""
betting_edge_report.py

Where the out-of-sample model beats a naive market, and where it does not.

SOURCES - both out-of-sample, deliberately:
  predictions/backtest_game_level.csv  per player-game, walk-forward
  predictions/backtest_results.csv     per player-season (Analysis H only)
predictions/season_*.csv and predictions/game_level_*.csv are NOT used for any
projection: brownlow_model.py refits on all seasons before writing them, so they
are fitted values and would inflate every threshold here. game_level_*.csv is
read for Home.score / Away.score only - those are match facts, not predictions.

PLAYER-SEASON KEY: Season + ID, falling back to Season + Player_Name +
Playing.for where ID is blank. 11,671 player-seasons. backtest_results.csv
groups by Player_Name alone and so conflates 61 same-name pairs (two Josh
Kennedys etc.); Analysis H is labelled accordingly because Rank_Predicted and
Rank_Actual exist nowhere else.

THRESHOLDS are denominated in RAW projected votes, because that is what a market
line is denominated in. Season vote pools vary 918-1242 (1.35x), so wherever a
season-to-season comparison is made the normalised rate (per 22 games) is
reported alongside.

GAMES PLAYED IS HINDSIGHT. A threshold conditioned on full-season games played
is not bettable preseason. Every A/B/C table therefore also carries a
PROSPECTIVE cut: games and rate through round 12 only, projected forward
(proj_full = exp_through_R12 * season_rounds / 12). Cuts that separate only
with full-season hindsight are marked RETROSPECTIVE ONLY.

Run:  python betting_edge_report.py     ->  betting_edge_report.csv
"""

import os

import numpy as np
import pandas as pd
from scipy.stats import beta

GL = "predictions/backtest_game_level.csv"
BR = "predictions/backtest_results.csv"
OUT = "betting_edge_report.csv"

DEDUPE = ["Season", "Round_num", "Player_Name", "Playing.for"]
BANDS = [(1, 5, "1-5"), (6, 11, "6-11"), (12, 17, "12-17"), (18, 99, "18+")]
ERAS = [("2008-2023", list(range(2008, 2024))), ("2024-2025", [2024, 2025])]
MID_ROUND = 12
THIN = 100
ALPHA = 0.05          # one-sided 95%

_rows = []
_n_thresholds = 0


def emit(section, cut, key, **kw):
    r = {"section": section, "cut": cut, "key": key}
    r.update(kw)
    _rows.append(r)


# ----------------------------------------------------------------------
def cp_upper(k, n):
    """One-sided 95% Clopper-Pearson upper bound on a proportion."""
    if n == 0:
        return float("nan")
    if k >= n:
        return 1.0
    return float(beta.ppf(1 - ALPHA, k + 1, n - k))


def cp_lower(k, n):
    """One-sided 95% Clopper-Pearson lower bound on a proportion."""
    if n == 0:
        return float("nan")
    if k <= 0:
        return 0.0
    return float(beta.ppf(ALPHA, k, n - k + 1))


def lay_odds(p):
    """Break-even decimal odds for LAYING (betting against) an event of prob p,
    plus the odds needed for a 5% and 10% edge.

    Laying at decimal odds d: you keep 1 unit with prob (1-p), pay (d-1) with
    prob p.  EV = 1 - p*d.  Break-even at d = 1/p; +EV requires d BELOW that.
    """
    if p <= 0:
        return float("inf"), float("inf"), float("inf")
    return 1.0 / p, 0.95 / p, 0.90 / p


def back_odds(p):
    """Break-even decimal odds for BACKING an event of prob p."""
    return float("inf") if p <= 0 else 1.0 / p


# ----------------------------------------------------------------------
# load and aggregate
# ----------------------------------------------------------------------
def load():
    g = pd.read_csv(GL, low_memory=False)
    n0 = len(g)
    g = g.drop_duplicates(subset=DEDUPE, keep="first")
    print(f"game-level rows {n0:,} -> {len(g):,} after dedupe "
          f"(residual 2025 R24 Wheelo collision)")

    # Season + ID, falling back to name+team where ID is blank.
    pid = g["ID"].astype("object")
    fallback = "NM::" + g["Player_Name"].astype(str) + "::" + g["Playing.for"].astype(str)
    g["pkey"] = np.where(g["ID"].isna(), fallback, "ID::" + pid.astype(str))

    season_rounds = g.groupby("Season")["Round_num"].max().rename("season_rounds")

    mid = g[g["Round_num"] <= MID_ROUND]
    m = mid.groupby(["Season", "pkey"], as_index=False).agg(
        exp12=("Exp_Votes", "sum"), act12=("Brownlow.Votes", "sum"),
        games12=("Round_num", "count"))
    rest = g[g["Round_num"] > MID_ROUND]
    rr = rest.groupby(["Season", "pkey"], as_index=False).agg(
        act_rest=("Brownlow.Votes", "sum"))

    a = g.groupby(["Season", "pkey"], as_index=False).agg(
        exp=("Exp_Votes", "sum"), act=("Brownlow.Votes", "sum"),
        games=("Round_num", "count"), name=("Player_Name", "last"),
        team=("Playing.for", "last"))
    a = a.merge(m, on=["Season", "pkey"], how="left")
    a = a.merge(rr, on=["Season", "pkey"], how="left")
    a = a.merge(season_rounds, on="Season", how="left")
    for c in ("exp12", "act12", "games12", "act_rest"):
        a[c] = a[c].fillna(0)

    a["polled"] = a["act"] > 0
    a["polled_rest"] = a["act_rest"] > 0
    a["band"] = pd.cut(a["games"], [0, 5, 11, 17, 99],
                       labels=[b[2] for b in BANDS])
    # normalised to a 22-game season, for season-to-season comparison only
    a["exp_n22"] = a["exp"] * 22.0 / a["games"]
    a["act_n22"] = a["act"] * 22.0 / a["games"]

    # PROSPECTIVE view: information available at the end of round 12 only.
    gp = a["games12"].replace(0, np.nan)
    a["proj_full"] = a["exp12"] * a["season_rounds"] / MID_ROUND
    a["games_proj"] = (a["games12"] * a["season_rounds"] / MID_ROUND).round()
    a["band_proj"] = pd.cut(a["games_proj"], [0, 5, 11, 17, 99],
                            labels=[b[2] for b in BANDS])
    a.loc[gp.isna(), ["proj_full", "games_proj"]] = np.nan

    print(f"player-seasons: {len(a):,}   (ID-keyed {int((~g['ID'].isna()).any()) and a['pkey'].str.startswith('ID::').sum():,}"
          f", name-keyed {int(a['pkey'].str.startswith('NM::').sum())})")
    return g, a


# ----------------------------------------------------------------------
# A / B sweeps
# ----------------------------------------------------------------------
def sweep(a, expcol, outcol, ascending, section, cut, thin_note=""):
    """One threshold sweep. Returns the table; emits rows."""
    global _n_thresholds
    sub = a.dropna(subset=[expcol])
    rows = []
    for t in np.round(np.arange(0.0, 4.01, 0.1), 1):
        _n_thresholds += 1
        s = sub[sub[expcol] >= t] if ascending else sub[sub[expcol] <= t]
        n = len(s)
        k = int(s[outcol].sum())
        p = k / n if n else float("nan")
        if ascending:
            lo = cp_lower(k, n)
            rows.append({"threshold": t, "n": n, "polled": k, "rate": p,
                         "cp_lower": lo, "break_even_back": back_odds(p),
                         "thin": n < THIN})
            emit(section, cut, f">={t}", n=n, polled=k, rate=p, cp_lower=lo,
                 break_even_back=back_odds(p), thin=n < THIN)
        else:
            up = cp_upper(k, n)
            be, e5, e10 = lay_odds(p)
            r3 = 3.0 / n if (n and k == 0) else float("nan")
            rows.append({"threshold": t, "n": n, "polled": k, "rate": p,
                         "cp_upper": up, "rule_of_three": r3,
                         "break_even_lay": be, "lay_5pct": e5, "lay_10pct": e10,
                         "thin": n < THIN})
            emit(section, cut, f"<={t}", n=n, polled=k, rate=p, cp_upper=up,
                 rule_of_three=r3, break_even_lay=be, lay_5pct=e5,
                 lay_10pct=e10, thin=n < THIN)
    return pd.DataFrame(rows)


def print_desc(t, title, note=""):
    print(f"\n--- {title} ---{note}")
    print(f"{'thr':>5}{'n':>8}{'polled':>8}{'rate%':>9}{'CP95 up%':>10}"
          f"{'3/n%':>8}{'BE lay':>9}{'5% edge':>9}{'10% edge':>10}  flag")
    for _, r in t.iterrows():
        if r["n"] == 0:
            continue
        r3 = f"{r['rule_of_three']*100:>7.3f}" if pd.notna(r["rule_of_three"]) else f"{'-':>7}"
        be = f"{r['break_even_lay']:>8.2f}" if np.isfinite(r["break_even_lay"]) else f"{'inf':>8}"
        e5 = f"{r['lay_5pct']:>8.2f}" if np.isfinite(r["lay_5pct"]) else f"{'inf':>8}"
        e10 = f"{r['lay_10pct']:>9.2f}" if np.isfinite(r["lay_10pct"]) else f"{'inf':>9}"
        print(f"{r['threshold']:>5.1f}{int(r['n']):>8,}{int(r['polled']):>8}"
              f"{r['rate']*100:>9.3f}{r['cp_upper']*100:>10.3f}{r3}"
              f"{be}{e5}{e10}  {'THIN' if r['thin'] else ''}")


def print_asc(t, title, note=""):
    print(f"\n--- {title} ---{note}")
    print(f"{'thr':>5}{'n':>8}{'polled':>8}{'rate%':>9}{'CP95 lo%':>10}{'BE back':>10}  flag")
    for _, r in t.iterrows():
        if r["n"] == 0:
            continue
        be = f"{r['break_even_back']:>9.3f}" if np.isfinite(r["break_even_back"]) else f"{'inf':>9}"
        print(f"{r['threshold']:>5.1f}{int(r['n']):>8,}{int(r['polled']):>8}"
              f"{r['rate']*100:>9.3f}{r['cp_lower']*100:>10.3f}{be}  "
              f"{'THIN' if r['thin'] else ''}")


def first_zero(t):
    z = t[(t["n"] > 0) & (t["polled"] == 0)]
    return z.iloc[0] if len(z) else None


def first_all(t):
    z = t[(t["n"] > 0) & (t["rate"] >= 1.0)]
    return z.iloc[0] if len(z) else None


# ----------------------------------------------------------------------
# E - team bias
# ----------------------------------------------------------------------
def analysis_E(a):
    print("\n" + "#" * 104)
    print("# E - TEAM BIAS: mean projected vs mean actual season votes, per team")
    print("#" * 104)
    per = a.groupby(["Season", "team"], as_index=False).agg(
        n=("exp", "size"), exp=("exp", "mean"), act=("act", "mean"))
    per["resid"] = per["act"] - per["exp"]
    tot = per.groupby("team", as_index=False).agg(
        seasons=("resid", "size"), mean_resid=("resid", "mean"),
        sd=("resid", "std"), n=("n", "sum"))
    sign = per.merge(tot[["team", "mean_resid"]], on="team")
    sign["same"] = np.sign(sign["resid"]) == np.sign(sign["mean_resid"])
    cons = sign.groupby("team")["same"].mean().rename("sign_consistency")
    tot = tot.merge(cons, on="team").sort_values("mean_resid")
    print(f"{'team':<24}{'seasons':>8}{'player-szns':>13}{'mean resid':>12}"
          f"{'sd':>9}{'sign consist':>14}  verdict")
    for _, r in tot.iterrows():
        v = ("CONSISTENT" if r["sign_consistency"] >= 0.75 else
             "flips" if r["sign_consistency"] <= 0.60 else "mixed")
        print(f"{r['team']:<24}{int(r['seasons']):>8}{int(r['n']):>13,}"
              f"{r['mean_resid']:>+12.4f}{r['sd']:>9.4f}"
              f"{r['sign_consistency'] * 100:>13.1f}%  {v}")
        emit("E_team_bias", "all", r["team"], seasons=int(r["seasons"]),
             n=int(r["n"]), mean_resid=r["mean_resid"], sd=r["sd"],
             sign_consistency=r["sign_consistency"], verdict=v)
    print(f"\n  spread of team mean residuals: {tot['mean_resid'].min():+.4f} to "
          f"{tot['mean_resid'].max():+.4f} votes per player-season")
    print(f"  teams with >=75% sign consistency: "
          f"{int((tot['sign_consistency'] >= 0.75).sum())} of {len(tot)}")


# ----------------------------------------------------------------------
# F / G - result and margin
# ----------------------------------------------------------------------
def _scores():
    """Home.score / Away.score per game from the backfilled game_level files.

    Joined on the game key rather than ID: scores are a match fact, the game key
    has no nulls where ID has 4, and the two joins are equivalent. No prediction
    column is read from these files.
    """
    fr = []
    for s in range(2008, 2026):
        p = f"predictions/game_level_{s}.csv"
        if not os.path.exists(p):
            continue
        d = pd.read_csv(p, usecols=["Season", "Round_num", "Home.team",
                                    "Away.team", "Home.score", "Away.score"],
                        low_memory=False)
        fr.append(d.drop_duplicates(["Season", "Round_num", "Home.team",
                                     "Away.team"]))
    return pd.concat(fr, ignore_index=True)


def analysis_FG(g):
    sc = _scores()
    d = g.merge(sc, on=["Season", "Round_num", "Home.team", "Away.team"],
                how="left")
    miss = int(d["Home.score"].isna().sum())
    d = d.dropna(subset=["Home.score", "Away.score"]).copy()
    d["is_home"] = d["Playing.for"] == d["Home.team"]
    d["team_score"] = np.where(d["is_home"], d["Home.score"], d["Away.score"])
    d["opp_score"] = np.where(d["is_home"], d["Away.score"], d["Home.score"])
    d["won"] = d["team_score"] > d["opp_score"]
    d["drew"] = d["team_score"] == d["opp_score"]
    d["margin"] = (d["team_score"] - d["opp_score"]).abs()

    print("\n" + "#" * 104)
    print("# F - WINNERS AND LOSERS: is the winner skew already priced?")
    print("#" * 104)
    print(f"  rows joined {len(d):,}   unmatched and dropped {miss:,}")
    print(f"\n{'outcome':<10}{'n':>10}{'mean proj':>12}{'mean act':>11}"
          f"{'resid':>10}{'proj poll%':>12}{'act poll%':>11}{'act/proj':>10}  flag")
    for lbl, m in (("win", d["won"]), ("loss", ~d["won"] & ~d["drew"]),
                   ("draw", d["drew"])):
        s = d[m]
        n = len(s)
        if not n:
            continue
        pp = s["Poll_Prob"].mean() * 100
        ap = (s["Brownlow.Votes"] > 0).mean() * 100
        ratio = ap / pp if pp else float("nan")
        print(f"{lbl:<10}{n:>10,}{s['Exp_Votes'].mean():>12.4f}"
              f"{s['Brownlow.Votes'].mean():>11.4f}"
              f"{s['Brownlow.Votes'].mean() - s['Exp_Votes'].mean():>+10.4f}"
              f"{pp:>12.3f}{ap:>11.3f}{ratio:>10.3f}  "
              f"{'THIN' if n < THIN else ''}")
        emit("F_win_loss", "all", lbl, n=n, mean_exp=s["Exp_Votes"].mean(),
             mean_act=s["Brownlow.Votes"].mean(),
             resid=s["Brownlow.Votes"].mean() - s["Exp_Votes"].mean(),
             proj_poll_pct=pp, act_poll_pct=ap, ratio=ratio)

    print("\n" + "#" * 104)
    print("# G - MARGIN")
    print("#" * 104)
    d["mband"] = pd.cut(d["margin"], [-1, 11, 35, 10_000],
                        labels=["<12", "12-35", ">35"])
    print("\n  all player-games, by margin band and result:")
    print(f"{'band':<8}{'result':<8}{'n':>10}{'mean proj':>12}{'mean act':>11}"
          f"{'resid':>10}{'act poll%':>11}  flag")
    for b in ("<12", "12-35", ">35"):
        for lbl, m in (("win", d["won"]), ("loss", ~d["won"] & ~d["drew"])):
            s = d[(d["mband"] == b) & m]
            n = len(s)
            if not n:
                continue
            ap = (s["Brownlow.Votes"] > 0).mean() * 100
            print(f"{b:<8}{lbl:<8}{n:>10,}{s['Exp_Votes'].mean():>12.4f}"
                  f"{s['Brownlow.Votes'].mean():>11.4f}"
                  f"{s['Brownlow.Votes'].mean() - s['Exp_Votes'].mean():>+10.4f}"
                  f"{ap:>11.3f}  {'THIN' if n < THIN else ''}")
            emit("G_margin", b, lbl, n=n, mean_exp=s["Exp_Votes"].mean(),
                 mean_act=s["Brownlow.Votes"].mean(), act_poll_pct=ap)

    top = d.sort_values(["Season", "Round_num", "Home.team", "Away.team",
                         "Exp_Votes", "Poll_Prob", "Player_Name"],
                        ascending=[True] * 4 + [False, False, True])
    top = top.groupby(["Season", "Round_num", "Home.team", "Away.team"]).head(1)
    print("\n  TOP PROJECTED PLAYER per game, by margin band:")
    print(f"{'band':<8}{'n':>8}{'got 3%':>10}{'polled%':>10}{'zero%':>9}"
          f"{'mean proj':>12}{'mean act':>11}  flag")
    for b in ("<12", "12-35", ">35"):
        s = top[top["mband"] == b]
        n = len(s)
        if not n:
            continue
        g3 = (s["Brownlow.Votes"] == 3).mean() * 100
        pl = (s["Brownlow.Votes"] > 0).mean() * 100
        print(f"{b:<8}{n:>8,}{g3:>10.2f}{pl:>10.2f}{100 - pl:>9.2f}"
              f"{s['Exp_Votes'].mean():>12.4f}{s['Brownlow.Votes'].mean():>11.4f}"
              f"  {'THIN' if n < THIN else ''}")
        emit("G_margin_top", b, "top_projected", n=n, got3_pct=g3,
             polled_pct=pl, zero_pct=100 - pl,
             mean_exp=s["Exp_Votes"].mean(), mean_act=s["Brownlow.Votes"].mean())


# ----------------------------------------------------------------------
# H - rank accuracy
# ----------------------------------------------------------------------
def analysis_H():
    print("\n" + "#" * 104)
    print("# H - RANK ACCURACY FOR SEASON MARKETS")
    print("#" * 104)
    print("  *** COMPUTED OVER THE NAME-CONFLATED SET. backtest_results.csv groups by")
    print("  *** Player_Name alone, merging 61 same-name pairs (the two Josh Kennedys,")
    print("  *** Scott Thompson, Tom Lynch, Sam Reid, Mitch Brown, Bailey Williams...).")
    print("  *** Rank_Predicted / Rank_Actual exist in no other file, so this table")
    print("  *** cannot be rebuilt on the ID key without re-running the backtest.")
    r = pd.read_csv(BR, low_memory=False)
    print(f"\n{'season':>7}{'top5 in top5':>14}{'top10 in top10':>16}"
          f"{'fav actual rank':>17}{'fav won':>9}")
    t5, t10, favwin = [], [], []
    for s, d in r.groupby("Season"):
        p5 = set(d.nsmallest(5, "Rank_Predicted")["Player"])
        a5 = set(d.nsmallest(5, "Rank_Actual")["Player"])
        p10 = set(d.nsmallest(10, "Rank_Predicted")["Player"])
        a10 = set(d.nsmallest(10, "Rank_Actual")["Player"])
        fav = d[d["Rank_Predicted"] == 1]
        fr = int(fav["Rank_Actual"].min()) if len(fav) else None
        won = fr == 1
        t5.append(len(p5 & a5))
        t10.append(len(p10 & a10))
        favwin.append(won)
        print(f"{int(s):>7}{len(p5 & a5):>11}/5{len(p10 & a10):>14}/10"
              f"{str(fr):>17}{('yes' if won else 'no'):>9}")
        emit("H_rank", f"season_{int(s)}", "rank", top5_in_top5=len(p5 & a5),
             top10_in_top10=len(p10 & a10), fav_rank_actual=fr, fav_won=won)
    n = len(t5)
    print(f"\n  projected top 5 finishing top 5   : {sum(t5)}/{n * 5} = "
          f"{sum(t5) / (n * 5) * 100:.1f}%")
    print(f"  projected top 10 finishing top 10 : {sum(t10)}/{n * 10} = "
          f"{sum(t10) / (n * 10) * 100:.1f}%")
    print(f"  projected favourite won the medal : {sum(favwin)}/{n} = "
          f"{sum(favwin) / n * 100:.1f}%")
    emit("H_rank", "pooled", "summary", top5_rate=sum(t5) / (n * 5),
         top10_rate=sum(t10) / (n * 10), fav_win_rate=sum(favwin) / n, seasons=n)


# ----------------------------------------------------------------------
# I - the zero-vote game
# ----------------------------------------------------------------------
def analysis_I(g):
    print("\n" + "#" * 104)
    print("# I - THE ZERO-VOTE GAME: how often the top projected player polls nothing")
    print("#" * 104)
    top = g.sort_values(["Season", "Round_num", "Home.team", "Away.team",
                         "Exp_Votes", "Poll_Prob", "Player_Name"],
                        ascending=[True] * 4 + [False, False, True])
    top = top.groupby(["Season", "Round_num", "Home.team", "Away.team"]).head(1).copy()
    top["bin"] = pd.cut(top["Exp_Votes"], [-.01, .5, 1, 1.5, 2, 2.5, 3.01],
                        labels=["<=0.5", "0.5-1", "1-1.5", "1.5-2", "2-2.5", "2.5-3"])
    print(f"\n{'proj band':<12}{'n':>8}{'zero':>8}{'zero%':>9}{'polled%':>10}"
          f"{'got3%':>9}{'BE back zero':>14}  flag")
    for b, s in top.groupby("bin", observed=True):
        n = len(s)
        z = int((s["Brownlow.Votes"] == 0).sum())
        pz = z / n
        print(f"{str(b):<12}{n:>8,}{z:>8}{pz * 100:>9.2f}{(1 - pz) * 100:>10.2f}"
              f"{(s['Brownlow.Votes'] == 3).mean() * 100:>9.2f}"
              f"{back_odds(pz):>14.3f}  {'THIN' if n < THIN else ''}")
        emit("I_zero_game", "all", str(b), n=n, zero=z, zero_pct=pz * 100,
             polled_pct=(1 - pz) * 100,
             got3_pct=(s["Brownlow.Votes"] == 3).mean() * 100,
             break_even_back_zero=back_odds(pz), thin=n < THIN)
    n = len(top)
    z = int((top["Brownlow.Votes"] == 0).sum())
    print(f"\n  pooled: {z:,}/{n:,} = {z / n * 100:.2f}% of games the top projected "
          f"player polls nothing")
    emit("I_zero_game", "pooled", "all", n=n, zero=z, zero_pct=z / n * 100)


# ----------------------------------------------------------------------
# A / B / C / D
# ----------------------------------------------------------------------
def _zero_line(t, label):
    z = first_zero(t)
    if z is None:
        lo = t[t["n"] > 0]
        best = lo.loc[lo["rate"].idxmin()] if len(lo) else None
        if best is None:
            return f"    {label:<34} no rows"
        return (f"    {label:<34} never reaches zero; lowest rate "
                f"{best['rate'] * 100:.3f}% at <={best['threshold']:.1f} "
                f"(n={int(best['n']):,}, {int(best['polled'])} polled)")
    return (f"    {label:<34} zero polled first at <={z['threshold']:.1f}  "
            f"n={int(z['n']):,}  ceiling 3/n={3 / z['n'] * 100:.3f}%  "
            f"{'THIN' if z['n'] < THIN else ''}")


def _all_line(t, label):
    z = first_all(t)
    if z is None:
        hi = t[t["n"] > 0]
        best = hi.loc[hi["rate"].idxmax()] if len(hi) else None
        if best is None:
            return f"    {label:<34} no rows"
        return (f"    {label:<34} never reaches 100%; highest "
                f"{best['rate'] * 100:.2f}% at >={best['threshold']:.1f} "
                f"(n={int(best['n']):,})")
    return (f"    {label:<34} all polled first at >={z['threshold']:.1f}  "
            f"n={int(z['n']):,}  {'THIN' if z['n'] < THIN else ''}")


def analysis_ABCD(a):
    print("\n" + "#" * 104)
    print("# A - THE FADE: descending sweep on projected season votes")
    print("#" * 104)
    ta = sweep(a, "exp", "polled", False, "A_fade", "pooled")
    print_desc(ta, "A. pooled, all games bands, 2008-2025 (RETROSPECTIVE: uses "
                   "full-season games played)")
    print("\n  " + "-" * 90)
    print(_zero_line(ta, "pooled"))
    z = first_zero(ta)
    if z is not None:
        print(f"    n behind it: {int(z['n']):,} player-seasons. "
              f"{'Zero from this many is a rule.' if z['n'] >= 1000 else 'Treat with care.'}")

    print("\n" + "#" * 104)
    print("# B - THE MIRROR: ascending sweep")
    print("#" * 104)
    tb = sweep(a, "exp", "polled", True, "B_mirror", "pooled")
    print_asc(tb, "B. pooled, all games bands, 2008-2025")
    print("\n  " + "-" * 90)
    print(_all_line(tb, "pooled"))

    print("\n" + "#" * 104)
    print("# C - BY GAMES BAND AND ERA, RETROSPECTIVE vs PROSPECTIVE (round 12)")
    print("#" * 104)
    print("\n  RETROSPECTIVE cuts use full-season games played, which is hindsight.")
    print("  PROSPECTIVE cuts use only rounds 1-12: games to date, and the season")
    print("  projection extrapolated from the rate through R12. Outcome is the same")
    print("  full-season 'polled at least one vote'; polled_rest is the actually")
    print("  bettable outcome at R12 (votes in rounds 13+).")

    print("\n  --- C1. descending, by games band ---")
    for lo, hi, lbl in BANDS:
        s = a[a["band"] == lbl]
        t = sweep(s, "exp", "polled", False, "C_fade_band", f"retro_{lbl}")
        print(_zero_line(t, f"RETRO  games {lbl} (n={len(s):,})"))
    for lo, hi, lbl in BANDS:
        s = a[a["band_proj"] == lbl]
        t = sweep(s, "proj_full", "polled", False, "C_fade_band", f"prosp_{lbl}")
        t2 = sweep(s, "proj_full", "polled_rest", False, "C_fade_band_rest",
                   f"prosp_rest_{lbl}")
        print(_zero_line(t, f"PROSP  games {lbl} (n={len(s):,})"))
        print(_zero_line(t2, f"PROSP  games {lbl} rest-of-season"))

    print("\n  --- C2. descending, by era ---")
    for lbl, seasons in ERAS:
        s = a[a["Season"].isin(seasons)]
        t = sweep(s, "exp", "polled", False, "C_fade_era", f"retro_{lbl}")
        print(_zero_line(t, f"RETRO  {lbl} (n={len(s):,})"))
        sp = s.dropna(subset=["proj_full"])
        tp = sweep(sp, "proj_full", "polled", False, "C_fade_era", f"prosp_{lbl}")
        print(_zero_line(tp, f"PROSP  {lbl} (n={len(sp):,})"))

    print("\n  --- C3. ascending, by games band and era ---")
    for lo, hi, lbl in BANDS:
        s = a[a["band"] == lbl]
        t = sweep(s, "exp", "polled", True, "C_mirror_band", f"retro_{lbl}")
        print(_all_line(t, f"RETRO  games {lbl} (n={len(s):,})"))
    for lbl, seasons in ERAS:
        s = a[a["Season"].isin(seasons)]
        t = sweep(s, "exp", "polled", True, "C_mirror_era", f"retro_{lbl}")
        print(_all_line(t, f"RETRO  {lbl} (n={len(s):,})"))

    # ---- D ----
    z = first_zero(ta)
    thr = float(z["threshold"]) if z is not None else 0.4
    print("\n" + "#" * 104)
    print(f"# D - PER SEASON at the strongest threshold from A: projected <= {thr:.1f}")
    print("#" * 104)
    print(f"\n{'season':>7}{'below thr':>11}{'polled':>8}{'rate%':>9}"
          f"{'norm rate%':>12}{'sqd/season':>12}  flag")
    tot_n = tot_k = 0
    for s, d in a.groupby("Season"):
        sub = d[d["exp"] <= thr]
        n = len(sub)
        k = int(sub["polled"].sum())
        tot_n += n
        tot_k += k
        nrm = (sub["act_n22"] > 0).mean() * 100 if n else float("nan")
        print(f"{int(s):>7}{n:>11,}{k:>8}{(k / n * 100 if n else float('nan')):>9.3f}"
              f"{nrm:>12.3f}{n:>12,}  {'THIN' if n < THIN else ''}")
        emit("D_per_season", f"season_{int(s)}", f"<={thr}", n=n, polled=k,
             rate=(k / n if n else np.nan), norm_rate=nrm / 100 if n else np.nan)
    print(f"\n  pooled {tot_k}/{tot_n:,} = {tot_k / tot_n * 100:.3f}%")
    print(f"  bets available per season: ~{tot_n / a['Season'].nunique():,.0f}")
    worst = None
    for s, d in a.groupby("Season"):
        sub = d[d["exp"] <= thr]
        k = int(sub["polled"].sum())
        if worst is None or k > worst[1]:
            worst = (int(s), k)
    print(f"  worst single season: {worst[0]} with {worst[1]} polled")
    return ta, tb, thr


# ----------------------------------------------------------------------
def main():
    print("=" * 104)
    print("BETTING EDGE REPORT   ***  OUT-OF-SAMPLE  ***")
    print("=" * 104)
    print("source: predictions/backtest_game_level.csv (walk-forward, per player-game)")
    print("        predictions/backtest_results.csv    (Analysis H only)")
    print("player-season key: Season + ID, falling back to Season + Player_Name +")
    print("        Playing.for where ID is blank")
    print("thresholds denominated in RAW projected votes; normalised (per 22 games)")
    print("        rates reported where seasons are compared")

    g, a = load()
    print(f"seasons {int(a['Season'].min())}-{int(a['Season'].max())}, "
          f"{len(a):,} player-seasons, {len(g):,} player-games")

    print("\nGAMES BAND DISTRIBUTION (retrospective vs prospective at R12)")
    print(f"{'band':<8}{'retro n':>10}{'retro polled%':>15}"
          f"{'prosp n':>10}{'prosp polled%':>15}")
    for lo, hi, lbl in BANDS:
        r_ = a[a["band"] == lbl]
        p_ = a[a["band_proj"] == lbl]
        print(f"{lbl:<8}{len(r_):>10,}{r_['polled'].mean() * 100:>14.2f}%"
              f"{len(p_):>10,}"
              f"{(p_['polled'].mean() * 100 if len(p_) else float('nan')):>14.2f}%")

    ta, tb, thr = analysis_ABCD(a)
    analysis_E(a)
    analysis_FG(g)
    analysis_H()
    analysis_I(g)

    pd.DataFrame(_rows).to_csv(OUT, index=False)
    print("\n" + "=" * 104)
    print(f"distinct thresholds tested: {_n_thresholds:,}")
    print("  Every sweep runs 0.0-4.0 in 0.1 steps (41 points) over many cuts, so")
    print("  the lowest p-value here is not the finding. Judge on n and on whether a")
    print("  cut survives the era split and the prospective (R12) version.")
    print(f"Full output -> {OUT} ({len(_rows):,} rows)")
    print("ALL FIGURES OUT-OF-SAMPLE")
    print("=" * 104)


if __name__ == "__main__":
    main()
