"""Your actual bets, live, as the count is read out.

    python scripts/count_slip.py                      # live
    python scripts/count_slip.py --from-file p.json   # rehearse

WHY THIS EXISTS AND count_live.py DOES NOT ANSWER IT
count_live.py prints a win probability, which in a season with a $1.05 favourite
answers a question nobody is asking. A real slip is almost never about who wins:
it is about whether a player clears a line, cracks a top 20, tops his club, or
polls the 3 in one particular game. Those all need the same simulation, and they
need it reported per BET rather than per player.

So this reads the feed, freezes the games already read out, simulates the rest,
and then asks each bet its own question. Every line comes back as one of:

    LANDED    already mathematically certain, whatever happens next
    DEAD      already impossible
    <p>       still live, with the probability it lands from here

WHAT MAKES A BET SETTLE EARLY
Most lines resolve before the count ends and the simulation is what proves it.
An under is LANDED once the player's remaining games cannot carry him past the
line, which usually happens with rounds still to be read. A 10+ votes bet is
LANDED the moment he reaches 10. Knowing which of your bets are already decided
is the thing a leaderboard cannot tell you.

THE NUMBERS ARE THE MODEL'S, AND THE MODEL IS NOT NEUTRAL
Probabilities here come from the same per-game distribution every bet on the
slip was priced off. They are calibrated for per-game 3 votes (3,467 walk-forward
games) and for season totals (validated separately), but they are NOT independent
evidence: if the model is wrong, this will be wrong in the same direction and
will say so confidently. Use it to see what has settled, not to re-price.
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import count_live as cl                                     # noqa: E402
import count_night as cn                                    # noqa: E402
import count_tweets as ct                                   # noqa: E402
import night_pack as npk                                    # noqa: E402

SLIP = "data_betting/brownlow_slip_2026.csv"
SIMS = 20000

# Named player sets the group markets settle on. Sportsbet's own groupings,
# read off the live board rather than guessed.
GROUPS = {
    "GROUP_B": ["Max Gawn", "Harry Sheezel", "Izak Rankine",
                "Nasiah Wanganeen-Milera", "Jason Horne-Francis", "Kysaiah Pickett"],
    "GROUP_C": ["Jacob van Rooyen", "Jack Gunston", "Josh Treacy",
                "Charlie Curnow", "Jye Amiss", "Logan Morris"],
    "GROUP_D": ["Lachie Ash", "Jarman Impey", "John Noble",
                "Wayne Milera", "Josh Daicos", "Nick Blakey"],
}


def _club_set(game_2026, club, exclude=()):
    d = game_2026[game_2026["Playing.for"] == club]
    return [p for p in d.Player_Name.unique() if p not in exclude]


def simulate(players, d, sims=SIMS, seed=0):
    """(names, totals array, games-read info) with read games frozen."""
    g = d["game_2026"]
    read, per_round = cl.games_read(players, g)
    votes = {}
    for _rd, pid, pts, _mid in ct.vote_entries(players):
        votes[pid] = votes.get(pid, 0) + pts
    polled = {p for p, v in votes.items() if v}
    roster, _gp, _w = ct.build_roster(players, polled, d)

    current = {}
    for pid, v in votes.items():
        nm = roster.get(pid, {}).get("game")
        if v and nm:
            current[nm] = current.get(nm, 0) + v

    remaining = g[~g.Game_ID.isin(read)].copy()
    remaining["_gkey"] = (remaining.Round_num.astype(str) + "|"
                          + remaining["Home.team"].astype(str) + "|"
                          + remaining["Away.team"].astype(str))
    names = pd.Index(sorted(set(g.Player_Name) | set(current)))
    remaining["_pidx"] = names.get_indexer(remaining.Player_Name)
    # per-round points keyed by the MODEL's name, so a read game can be settled
    # as fact rather than simulated: this is what turns "READ" into LANDED/LOST.
    by_rd = {}
    for rd, pid, pts, _mid in ct.vote_entries(players):
        nm = roster.get(pid, {}).get("game")
        if nm:
            by_rd[(nm, int(rd))] = by_rd.get((nm, int(rd)), 0) + pts
    import count_sim
    games = count_sim._game_arrays(remaining)
    rng = np.random.default_rng(seed)
    rem = count_sim.simulate_remaining(games, len(names), sims, rng)
    base = np.array([current.get(n, 0) for n in names], dtype=np.int32)
    totals = rem.astype(np.int32) + base[None, :]
    return names, totals, base, read, per_round, remaining, by_rd


def make_window_sims(g, read, remaining, by_rd, sims, seed=1):
    """Totals inside a range of display rounds, read games frozen.

    "Leader after round 10" and "most votes in rounds 17-24" are the same
    question over different ranges, and neither is answerable from season
    totals: a player can lead the whole count and not lead a window of it.
    Cached per range, since each call is a fresh simulation.
    """
    import count_sim
    cache = {}

    def run(lo, hi):
        if (lo, hi) in cache:
            return cache[(lo, hi)]
        sub = g[(g.Round_num - 1 >= lo) & (g.Round_num - 1 <= hi)]
        if sub.empty:
            cache[(lo, hi)] = None
            return None
        pool = sorted(sub.Player_Name.unique())
        pidx = {p: i for i, p in enumerate(pool)}
        # frozen half: real votes from games in range already read
        base = np.zeros(len(pool), dtype=np.int32)
        for (nm, rd), pts in by_rd.items():
            if lo <= rd <= hi and nm in pidx:
                base[pidx[nm]] += pts
        # simulated half: games in range NOT yet read
        rem = remaining[(remaining.Round_num - 1 >= lo) & (remaining.Round_num - 1 <= hi)].copy()
        if rem.empty:
            cache[(lo, hi)] = (pool, base[None, :])
            return cache[(lo, hi)]
        rem["_pidx"] = [pidx.get(p, -1) for p in rem.Player_Name]
        rem = rem[rem._pidx >= 0]
        arrs = count_sim._game_arrays(rem)
        drawn = count_sim.simulate_remaining(arrs, len(pool), sims,
                                             np.random.default_rng(seed))
        cache[(lo, hi)] = (pool, drawn.astype(np.int32) + base[None, :])
        return cache[(lo, hi)]

    return run


def settle(bet, names, totals, base, read, remaining, g, by_rd, win_sims):
    """(status, probability) for one bet line."""
    idx = {n: i for i, n in enumerate(names)}
    kind, who, arg = bet.kind, bet.player, str(bet.arg)

    if kind == "game3":
        rd = int(arg)
        gm = g[(g.Round_num - 1 == rd) & (g.Player_Name == who)]
        if gm.empty:
            return "NO ROW", np.nan
        gid = gm.Game_ID.iloc[0]
        if gid in read:
            # The game has been read out, so this is no longer a probability.
            # A player can only hold one vote entry per round, so 3 points
            # against that round IS the 3 votes in that game.
            return ("LANDED", 1.0) if by_rd.get((who, rd), 0) == 3 else ("LOST", 0.0)
        if who not in idx:
            return "NO ROW", np.nan
        sub = remaining[remaining.Game_ID == gid]
        if sub.empty:
            return "READ", np.nan
        r = sub[sub.Player_Name == who]
        p = float(r.P_3.iloc[0] / sub.P_3.sum()) if len(r) else 0.0
        return "live", p

    if who not in idx:
        return "NO ROW", np.nan
    t = totals[:, idx[who]]
    cur = int(base[idx[who]])

    if kind == "atleast":
        n = int(float(arg))
        if cur >= n:
            return "LANDED", 1.0
        if t.max() < n:
            return "DEAD", 0.0
        return "live", float((t >= n).mean())

    if kind in ("under", "over"):
        line = float(arg)
        p = float((t < line).mean()) if kind == "under" else float((t > line).mean())
        if kind == "under" and t.max() < line:
            return "LANDED", 1.0
        if kind == "under" and cur > line:
            return "DEAD", 0.0
        if kind == "over" and cur > line:
            return "LANDED", 1.0
        if kind == "over" and t.max() < line:
            return "DEAD", 0.0
        return "live", p

    if kind == "topn":
        n = int(float(arg))
        order = np.argsort(-totals, axis=1)
        rank = np.empty_like(order)
        np.put_along_axis(rank, order, np.arange(totals.shape[1])[None, :] + 1, axis=1)
        return "live", float((rank[:, idx[who]] <= n).mean())

    if kind == "group":
        members = GROUPS.get(arg)
        if members is None and arg == "WEST_COAST_NO_REID":
            members = _club_set(g, "West Coast", exclude=("Harley Reid",))
        members = [m for m in (members or []) if m in idx]
        if who not in members:
            return "NOT IN SET", np.nan
        cols = np.array([idx[m] for m in members])
        sub = totals[:, cols]
        mine = totals[:, idx[who]][:, None]
        wins = (mine > sub).sum(1) == len(members) - 1
        ties = ((mine == sub).sum(1) - 1)
        p = float((wins | ((mine >= sub).all(1) & (ties > 0))).mean())
        if p >= 0.9999:
            return "LANDED", 1.0
        if p <= 0.0001:
            return "DEAD", 0.0
        return "live", p

    if kind in ("window", "leader"):
        # Both are "most votes inside a range of rounds". Simulated over that
        # range only, with rounds already read frozen at their real values -
        # so once the range is fully read the answer is a fact, not a forecast.
        lo, hi = (0, int(arg)) if kind == "leader" else tuple(int(x) for x in arg.split("-"))
        tot = win_sims(lo, hi)
        if tot is None or who not in tot[0]:
            return "NO ROW", np.nan
        wnames, wt = tot
        j = wnames.index(who)
        best = wt.max(1)
        p = float(((wt[:, j] == best) & (wt[:, j] > 0)).mean())
        if p >= 0.9999:
            return "LANDED", 1.0
        if p <= 0.0001:
            return "DEAD", 0.0
        return "live", p

    return "?", np.nan


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--slip", default=SLIP)
    ap.add_argument("--from-file", dest="from_file")
    ap.add_argument("--allow-predictor", action="store_true")
    ap.add_argument("--sims", type=int, default=SIMS)
    args = ap.parse_args(argv)

    if args.from_file:
        blob = json.load(open(args.from_file, encoding="utf-8"))
        players = blob["players"] if isinstance(blob, dict) else blob
    else:
        sid, _ = cn.season_id()
        players = cn.fetch(sid)

    state, why = cn.classify(cn.digest(players), cn.load_snapshot())
    print(f"  feed state: {state} - {why}")
    if state not in ("COUNTING", "COUNTED") and not args.allow_predictor:
        raise SystemExit(f"  refusing: {why}. Nothing to settle yet.")

    d = npk.load()
    g = d["game_2026"]
    names, totals, base, read, per_round, remaining, by_rd = simulate(players, d, args.sims)
    win_sims = make_window_sims(g, read, remaining, by_rd, args.sims)
    slip = pd.read_csv(args.slip)

    print(f"  games read {len(read)} of 207   ({len(read)/207:.0%} of the count)\n")
    print(f"  {'BET':44s} {'$':>6} {'stake':>6} {'status':>9} {'return':>8}")
    print("  " + "-" * 80)
    live_ev = 0.0
    landed = dead = 0
    out = []
    for b in slip.itertuples():
        st, p = settle(b, names, totals, base, read, remaining, g, by_rd, win_sims)
        label = f"{b.player} {b.note}"[:44]
        if st == "LANDED":
            landed += 1; live_ev += b.stake * (b.odds - 1)
            shown, ret = "LANDED", f"+${b.stake*(b.odds-1):.0f}"
        elif st in ("DEAD", "LOST"):
            dead += 1; live_ev -= b.stake
            shown, ret = st, f"-${b.stake:.0f}"
        elif st in ("live", "approx"):
            live_ev += b.stake * (p * b.odds - 1)
            shown = f"{p:.0%}" + ("~" if st == "approx" else "")
            ret = f"${b.stake*b.odds:.0f}"
        else:
            shown, ret = st, ""
        out.append((label, b.odds, b.stake, shown, ret))
        print(f"  {label:44s} {b.odds:6.2f} {b.stake:6.2f} {shown:>9} {ret:>8}")
    print("  " + "-" * 80)
    print(f"  {landed} landed, {dead} dead, {len(slip)-landed-dead} live")
    print(f"  expected position from here: {live_ev:+.2f} on {slip.stake.sum():.2f} staked")
    print("\n  ~ = approximate: window and leader markets are scored off expected")
    print("    votes rather than simulated, so treat those two as indicative.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
