"""Team vote winner: each player's chance of polling the most votes at his club.

    python team_votes.py --check          # backtest the variants, 2008-2025
    python team_votes.py 2026             # print one season's clubs

The market Sportsbet calls "Teams" and Dabble "team vote winner": per club,
who finishes the count with the most Brownlow votes. It is a season question,
so it runs on the season simulator `scripts/sb_placings_board.py` already uses
for placings (count_sim's conditional 3-2-1 per game, a per-player lognormal
multiplier per simulated season), and asks of every simulated season who tops
each club rather than who tops the league.

DEAD HEATS ARE SPLIT, AS THE BOOKS SETTLE THEM
Two players level on top of a club each hold half of it. Counting both as a win
would overstate every club where the leaders are close, which is most of them
in a sport that settles on integers.

A PLAYER WHO CHANGED CLUBS IS TWO RUNNERS
Keyed by player and the club he played for, the way the markets list him, so
his votes at each club count only there.

SHARPENING IS FOR THE CLASSIFIER, NOT THE STACK
The classifier's probabilities are compressed (CLAUDE.md, "Model architecture"),
so the simulator raises each game's columns to a power before drawing. From
2027 the live season's figures come from stack.py, whose last layer was fitted
to the votes and already carries that confidence; sharpening it again would
count it twice. `gamma_for` reads the frame's `prob_source` and picks.
"""

import os
import sys

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(REPO, "scripts"))

from sb_placings_board import BATCH, GAMMA, _prepare, _season_batch  # noqa: E402

BACKTEST = os.path.join(REPO, "predictions", "backtest_game_level.csv")
SIMS = 20_000


def gamma_for(frame):
    """1.0 for the stack's probabilities, the classifier's sharpening otherwise."""
    src = frame.get("prob_source")
    return 1.0 if src is not None and (src == "stack").any() else GAMMA


def _club_codes(keys):
    clubs = pd.Index([k.split("|", 1)[1] for k in keys])
    codes, names = pd.factorize(clubs)
    return codes, list(names)


def _lead_share(tot, codes, n_clubs):
    """(n, players) dead-heat share of top spot at the player's club."""
    share = np.zeros(tot.shape, dtype=np.float64)
    for j in range(n_clubs):
        cols = np.flatnonzero(codes == j)
        sub = tot[:, cols]
        top = sub == sub.max(axis=1, keepdims=True)
        share[:, cols] = top / top.sum(axis=1, keepdims=True)
    return share


def simulate(frame, n_sims=SIMS, seed=0, gamma=None, dispersed=True):
    """Per runner (player|club): P(club leader), mean, 10th and 90th percentile
    of season votes, and raw expected votes."""
    gamma = gamma_for(frame) if gamma is None else gamma
    keys, games, sigma, ev = _prepare(frame, gamma)
    if not dispersed:
        sigma = np.zeros_like(sigma)
    codes, _ = _club_codes(keys)
    n_clubs = codes.max() + 1
    rng = np.random.default_rng(seed)
    lead = np.zeros(len(keys))
    totals, done = [], 0
    while done < n_sims:
        n = min(BATCH, n_sims - done)
        tot = _season_batch(games, sigma, n, rng)
        lead += _lead_share(tot, codes, n_clubs).sum(axis=0)
        totals.append(tot)
        done += n
    tot = np.vstack(totals)
    out = pd.DataFrame({
        "player": [k.split("|", 1)[0] for k in keys],
        "club": [k.split("|", 1)[1] for k in keys],
        "p_lead": lead / n_sims,
        "mean": tot.mean(axis=0),
        "lo": np.percentile(tot, 10, axis=0),
        "hi": np.percentile(tot, 90, axis=0),
        "exp_votes": ev,
    }, index=keys)
    return out


def actual_share(frame):
    """The count's own club leaders, dead heats split, keyed like simulate()."""
    key = frame.Player_Name.astype(str) + "|" + frame["Playing.for"].astype(str)
    votes = frame.assign(_key=key).groupby("_key")["Brownlow.Votes"].sum()
    codes, _ = _club_codes(votes.index)
    share = _lead_share(votes.to_numpy()[None, :], codes, codes.max() + 1)[0]
    return pd.Series(share, index=votes.index), votes


VARIANTS = {
    "sharpened, dispersed (placings recipe)": dict(gamma=GAMMA, dispersed=True),
    "unsharpened, dispersed": dict(gamma=1.0, dispersed=True),
    "sharpened, independent games": dict(gamma=GAMMA, dispersed=False),
}


def check(sims=5000):
    """Walk-forward: every 2008-2025 season from its own out-of-sample games."""
    b = pd.read_csv(BACKTEST).drop_duplicates(
        subset=["Season", "Round_num", "Home.team", "Away.team", "Player_Name"])
    rows = []
    for season, d in b.groupby("Season"):
        got, _ = actual_share(d)
        for name, kw in VARIANTS.items():
            sim = simulate(d, sims, seed=int(season), **kw)
            rows.append(sim.assign(got=got.reindex(sim.index).fillna(0), season=season, variant=name))
        print(f"  {season}", flush=True)
    bt = pd.concat(rows)
    bands = [0, .02, .05, .1, .2, .35, .5, .65, .8, .9, 1.0001]
    for name, v in bt.groupby("variant", sort=False):
        live = v[v.p_lead >= 0.005]
        brier = ((live.p_lead - live.got) ** 2).mean()
        # the favourite at each club: how often he led, against how often he was said to
        fav = v.sort_values("p_lead").groupby(["season", "club"]).tail(1)
        ll = -np.log(v[v.got > 0].p_lead.clip(1e-4)).mean()
        print(f"\n  {name}: Brier {brier:.4f}, log loss of the actual leader {ll:.3f}; "
              f"favourites said {fav.p_lead.sum():.1f}, led {fav.got.sum():.1f} of {len(fav)} clubs")
        t = (live.assign(band=pd.cut(live.p_lead, bands, right=False))
             .groupby("band", observed=True)
             .agg(n=("got", "size"), said=("p_lead", "mean"), got=("got", "mean")))
        print(t.to_string(float_format=lambda x: f"{x:.3f}"))
    return bt


def main(argv):
    os.chdir(REPO)
    if "--check" in argv:
        check()
        return
    import site_data as sd
    season = int(argv[0]) if argv else sd.season_cfg.current_season()
    g = sd.load_game(season)
    sim = simulate(g, seed=season)
    for club, c in sim.sort_values("p_lead", ascending=False).groupby("club"):
        print(f"\n  {club}")
        for _, r in c.head(4).iterrows():
            print(f"    {r.player:26s} {r.p_lead:6.1%}  mean {r['mean']:4.1f}")


if __name__ == "__main__":
    main(sys.argv[1:])
