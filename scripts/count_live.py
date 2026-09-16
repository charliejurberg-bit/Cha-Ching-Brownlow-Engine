"""Who wins from here, live, off the AFL feed during the count.

    python scripts/count_live.py                     # one read, as the count stands
    python scripts/count_live.py --top 20
    python scripts/count_live.py --odds "Nick Daicos=1.30, Bailey Smith=6.00"
    python scripts/count_live.py --from-file payload.json     # rehearse, no network

WHAT THIS IS FOR
count_sim.py holds the conditional 3-2-1 engine but only ever ran --backtest, so
on the night there was nothing that turned the live feed into a number. This is
that missing half: it reads the feed, works out which games have actually been
read out, freezes those votes, and simulates only what is left. The answer is a
win probability for a count in progress, which is the one quantity an in-running
market prices slowly and the model already knows.

WHY IT REFUSES BEFORE THE COUNT
The award endpoint serves the AFL's own PREDICTOR between counts and the live
votes on the night, at the same URL, in the same shape, with no field saying
which. So this asks count_night.classify the same question the Live Tracker
asks, and refuses on PREDICTOR and on UNKNOWN. A win probability computed off
predicted votes would look exactly like a real one.

WHAT COUNTS AS READ, AND WHY IT IS DONE PER GAME
A round is read out game by game over several minutes. Treating a part-read
round as wholly unknown understates whoever has just polled in it, which is
precisely the player an in-running market is repricing. So currency is taken at
GAME level: every match id in the feed with a vote against it has been read.
game_level's Game_ID is our own composite key and not the AFL's match id, so the
fixture behind each match id is recovered from the CLUBS of its own vote
getters, which the feed does carry. Three votes in a game go to at most two
clubs, and each club plays once in a round, so the fixture is identified by
intersection against that round's fixture list.

ROUND NUMBERING is the feed's here, as everywhere that touches this endpoint:
Opening Round is 0 and game_level's Round_num is one ahead. See CLAUDE.md.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import count_night as cn                                    # noqa: E402
import count_sim                                            # noqa: E402
import count_tweets as ct                                   # noqa: E402
import night_pack as npk                                    # noqa: E402

DEFAULT_SIMS = 40000


def games_read(players, game_2026):
    """(set of Game_ID already read, {display_round: games read}).

    Identifies each read fixture from the clubs of its vote getters. A match id
    whose fixture cannot be pinned down is skipped rather than guessed: the cost
    of skipping is that one game is simulated when it is already known, which
    understates a player slightly; the cost of guessing wrong is freezing votes
    onto the wrong game, which is unrecoverable.
    """
    club_of = {p["id"]: ct.FEED_CLUBS.get(p.get("teamId")) for p in players}
    by_match = {}
    for rd, pid, _pts, mid in ct.vote_entries(players):
        if mid:
            by_match.setdefault((rd, mid), set()).add(club_of.get(pid))

    fx = game_2026[["Round_num", "Home.team", "Away.team",
                    "Game_ID"]].drop_duplicates().copy()
    fx["_disp"] = fx.Round_num - 1
    pairs = {gid: {h, a} for gid, h, a
             in zip(fx.Game_ID, fx["Home.team"], fx["Away.team"])}
    by_disp = {}
    for gid, disp in zip(fx.Game_ID, fx._disp):
        by_disp.setdefault(int(disp), []).append(gid)

    read, per_round = set(), {}
    for (rd, _mid), clubs in sorted(by_match.items()):
        clubs = {c for c in clubs if c}
        if not clubs:
            continue
        cand = [gid for gid in by_disp.get(int(rd), [])
                if gid not in read and clubs <= pairs[gid]]
        if len(cand) == 1:
            read.add(cand[0])
            per_round[int(rd)] = per_round.get(int(rd), 0) + 1
    return read, per_round


def build(players, d, sims, seed=0):
    """Freeze what has been read, simulate what has not."""
    g = d["game_2026"]
    read, per_round = games_read(players, g)
    gpr = ct.games_per_round({"game_2026": g})

    votes_by_pid = {}
    for _rd, pid, pts, _mid in ct.vote_entries(players):
        votes_by_pid[pid] = votes_by_pid.get(pid, 0) + pts
    polled = {pid for pid, v in votes_by_pid.items() if v}
    roster, _game_to_pid, warnings = ct.build_roster(players, polled, d)

    current, unplaced = {}, []
    for pid, v in votes_by_pid.items():
        if not v:
            continue
        name = roster.get(pid, {}).get("game")
        if name:
            current[name] = current.get(name, 0) + v
        else:
            unplaced.append((roster.get(pid, {}).get("name", str(pid)), v))

    remaining = g[~g.Game_ID.isin(read)].copy()
    chances, finals = count_sim.chances_from_frame(
        remaining, current, n_sims=sims, seed=seed)
    return dict(read=read, per_round=per_round, gpr=gpr, current=current,
                remaining=remaining, chances=chances, finals=finals,
                unplaced=unplaced, warnings=warnings, roster=roster)


def parse_odds(text):
    out = {}
    for part in (text or "").split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            try:
                out[k.strip()] = float(v)
            except ValueError:
                pass
    return out


def report(r, top, odds):
    n_read, n_tot = len(r["read"]), sum(r["gpr"].values())
    print("\n  games read {} of {}   ({:.0%} of the count)".format(
        n_read, n_tot, n_read / max(n_tot, 1)))
    for rd in sorted(r["per_round"]):
        if r["per_round"][rd] < r["gpr"].get(rd, 0):
            lab = "Opening Round" if rd == 0 else "Round {}".format(rd)
            print("  reading {} now: {} of {} games read, the rest simulated"
                  .format(lab, r["per_round"][rd], r["gpr"][rd]))
    for who, v in r["unplaced"]:
        print("  WARNING {} has {} votes and no model row, so he is missing "
              "from the simulation entirely".format(who, v))

    rows = []
    for name, c in r["chances"].items():
        cur = r["current"].get(name, 0)
        if c < 0.0005 and not cur:
            continue
        rows.append((name, cur, c, r["finals"].get(name, 0.0)))
    rows.sort(key=lambda t: (-t[2], -t[3]))

    head = "  {:2s} {:26s} {:>4} {:>15} {:>7} {:>10}".format(
        "", "Player", "now", "expected final", "WIN", "breakeven")
    if odds:
        head += " {:>8} {:>7}".format("market", "edge")
    print("\n" + head)
    print("  " + "-" * (len(head) - 2))
    for i, (name, cur, c, fin) in enumerate(rows[:top], 1):
        be = "${:,.2f}".format(1 / c) if c > 0 else "-"
        line = "  {:2d} {:26s} {:4.0f} {:15.1f} {:7.1%} {:>10}".format(
            i, name[:26], cur, fin, c, be)
        if odds:
            m = odds.get(name)
            line += " {:>8} {:>7}".format(
                "${:.2f}".format(m) if m else "",
                "{:+.0%}".format(c * m - 1) if m else "")
        print(line)

    if odds:
        print("\n  edge is the model's expected return per dollar at that price.")
        miss = [k for k in odds if k not in r["chances"]]
        if miss:
            print("  NOT FOUND in the model frame, so not priced: {}"
                  .format(", ".join(miss)))
    for w in r["warnings"][:5]:
        print("  note: {}".format(w))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sims", type=int, default=DEFAULT_SIMS)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--odds", default="",
                    help='"Nick Daicos=1.30, Bailey Smith=6.00"')
    ap.add_argument("--from-file", dest="from_file",
                    help="a captured award payload, for rehearsal without the feed")
    ap.add_argument("--allow-predictor", action="store_true",
                    help="rehearsal only: simulate off the AFL's predictor payload")
    args = ap.parse_args(argv)

    if args.from_file:
        with open(args.from_file, encoding="utf-8") as fh:
            blob = json.load(fh)
        players = blob["players"] if isinstance(blob, dict) else blob
        if isinstance(players, dict):
            raise SystemExit("--from-file wants the raw award payload (a "
                             "players LIST), not a count_night digest")
    else:
        sid, _sname = cn.season_id()
        players = cn.fetch(sid)

    state, why = cn.classify(cn.digest(players), cn.load_snapshot())
    print("  feed state: {} - {}".format(state, why))
    if state not in ("COUNTING", "COUNTED") and not args.allow_predictor:
        raise SystemExit(
            "  refusing: {}. These are the AFL's predicted votes, not the "
            "count. Pass --allow-predictor to simulate off them anyway, which "
            "is a rehearsal and not a price.".format(why))

    d = npk.load()
    r = build(players, d, args.sims)
    report(r, args.top, parse_odds(args.odds))
    return 0


if __name__ == "__main__":
    sys.exit(main())
