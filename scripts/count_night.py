"""Count-night feed handling: snapshot the predictor now, tell it from the count later.

    python scripts/count_night.py status [--season 2026]   # what is the count doing
    python scripts/count_night.py rounds [--season 2026]   # per-round votes, once counting
    python scripts/count_night.py snapshot                 # legacy, see below

STATUS AND ROUNDS READ THE LIVE FEED (since 29 September 2026). On count night
2026 the award endpoint below never flipped: it served the predictor all night
and `status` answered PREDICTOR through a count that was 80% done. Both commands
now read scripts/bfawards_feed.py, the feed the AFL's own live tracker page
uses, whose explicit `status` field (LIVE during the count, CONCLUDED after it)
needs no snapshot. Everything from here down describes the snapshot design,
which the Streamlit Live Tracker's fallback path used; it is kept for the
record and for `snapshot`, and its central claim, that the award endpoint
carries the count on the night, turned out false.

THE PROBLEM THIS SOLVES, AND WHY IT NEEDS A BEFORE-PICTURE
The AFL award endpoint that dashboard.fetch_live_brownlow_data reads carries the
AFL's Brownlow PREDICTOR outside of count night, and carries the real votes as
they are read out on the night. Nothing in the payload says which. There is no
type field, no flag, no separate path: the same URL returns the same shape
either way, so a consumer that simply reads totalVotes cannot tell a prediction
from a result.

That the endpoint is a predictor between counts is measured rather than assumed,
against two completed seasons:

    season   endpoint says          actually was
    2025     Dawson 32, Daicos 31   Rowell 39 (not in the endpoint's top five)
    2024     Cripps 33, Daicos 33   Cripps 45, Daicos 38

So `is_live = any(totalVotes > 0)`, which is what the dashboard currently uses,
is TRUE year round and cannot gate anything.

THE DETECTOR, WHICH NEEDS NO FLAG AND NO THIRD PARTY
Take a snapshot of the predictor before the count and compare against it. Three
states fall out, and each is decidable from the payload alone:

  PREDICTOR   identical to the snapshot. The count has not started.
  COUNTING    partial. Fewer than 6 votes per completed game, only some rounds
              populated, and the populated set grows between polls.
  COUNTED     complete again (6 x games) but different from the snapshot.

The partial state is the one that makes this safe. A live count is read out
round by round from Opening Round forward, so mid-count the feed necessarily
holds less than a full season of votes, while the predictor always holds exactly
6 x 207 = 1,242. A full-but-changed payload is the finished count.

WHY THE SNAPSHOT IS COMMITTED RATHER THAN CACHED
It is evidence with an expiry: once the count starts, the pre-count predictor
state cannot be recovered from anywhere. A scratchpad file that gets cleared
takes the detector with it. It is small (a few hundred rows of name and total).
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import season as season_cfg  # noqa: E402

BASE = "https://aflapi.afl.com.au/afl/v2"
HDRS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/131.0.0.0 Safari/537.36"),
    "Accept": "application/json",
    "Referer": "https://www.afl.com.au/brownlow-medal/live-tracker",
}
SNAPSHOT = season_cfg.data_path("brownlow_predictor_snapshot.json")
SEASON = season_cfg.LIVE_SEASON
# 207 in 2026, 18 clubs x 23 / 2 (CLAUDE.md). From season.py, which leaves it
# None until the fixture is known; FULL_VOTES is then None and the COUNTED
# test cannot fire, which fails toward UNKNOWN rather than toward "final".
GAMES_2026 = season_cfg.cfg()["games"]
FULL_VOTES = GAMES_2026 * 6 if GAMES_2026 else None
TMO = (5, 15)


def season_id(season=SEASON):
    r = requests.get(f"{BASE}/competitions/1/compseasons?pageSize=20",
                     headers=HDRS, timeout=TMO)
    r.raise_for_status()
    for s in r.json().get("compSeasons", []):
        if str(season) in s.get("name", "") and "Premiership" in s.get("name", ""):
            return s["id"], s["name"]
    raise SystemExit(f"no Premiership compSeason found for {season}")


def fetch(sid):
    """Every player row the award endpoint holds, across all pages.

    Paginated to exhaustion rather than to the dashboard's 5 pages. Five pages
    is right for a leaderboard and wrong here: a player on 1 vote can still be
    the row that moves a record, and the whole point of this module is to be
    able to say the payload is COMPLETE, which a truncated read cannot.
    """
    out, page = [], 0
    while True:
        r = requests.get(
            f"{BASE}/compseasons/{sid}/award/brownlow"
            f"?page={page}&pageSize=100", headers=HDRS, timeout=TMO)
        if r.status_code != 200:
            break
        batch = r.json().get("players", [])
        if not batch:
            break
        out.extend(batch)
        page += 1
        if page > 20:                     # guard against an endless feed
            break
    return out


def digest(players):
    """The comparable shape: totals, per-round votes, and the invariants."""
    rows, per_round = {}, {}
    for p in players:
        name = f"{p.get('firstName','')} {p.get('surname','')}".strip()
        key = f"{name}|{p.get('teamId')}"
        rows[key] = p.get("totalVotes", 0)
        for rkey, entries in (p.get("rounds") or {}).items():
            for e in entries:
                pts = e.get("points", 0)
                if pts:
                    per_round.setdefault(int(rkey), {})[name] = pts
    total = sum(rows.values())
    return {
        "players": rows,
        "per_round": {str(k): v for k, v in sorted(per_round.items())},
        "total_votes": total,
        "rounds_with_votes": sorted(per_round),
        "n_players": len(rows),
    }


def classify(cur, snap):
    """PREDICTOR / COUNTING / COUNTED / UNKNOWN, with the reason stated.

    Deliberately refuses to guess. UNKNOWN is a real answer here: publishing
    nothing is always recoverable, and publishing the AFL's predictions as the
    result is not.
    """
    if snap is None:
        return "UNKNOWN", ("no pre-count snapshot on disk, so a prediction "
                           "cannot be told from a result. Run `snapshot` "
                           "before count night")
    same = cur["players"] == snap["players"]
    full = cur["total_votes"] == FULL_VOTES
    if same:
        return "PREDICTOR", (f"byte-identical to the snapshot taken "
                             f"{snap.get('taken_at','?')}. The count has not "
                             f"started")
    if not full:
        done = len(cur["rounds_with_votes"])
        return "COUNTING", (f"partial: {cur['total_votes']:,} of "
                            f"{FULL_VOTES or 0:,} votes, {done} of 25 rounds "
                            f"populated. The count is running")
    return "COUNTED", (f"complete at {cur['total_votes']:,} votes and "
                       f"different from the snapshot. The count has finished")


def load_snapshot():
    if not os.path.exists(SNAPSHOT):
        return None
    with open(SNAPSHOT, encoding="utf-8") as fh:
        return json.load(fh)


def cmd_snapshot(args):
    sid, sname = season_id()
    players = fetch(sid)
    d = digest(players)
    if d["total_votes"] != FULL_VOTES:
        print(f"WARNING: feed holds {d['total_votes']:,} votes, not the "
              f"{FULL_VOTES or 0:,} a complete predictor carries. Snapshotting "
              f"anyway, but check whether the count has already started.")
    d["taken_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    d["season"] = sname
    d["season_id"] = sid
    if os.path.exists(SNAPSHOT) and not args.force:
        raise SystemExit(f"{SNAPSHOT} already exists. It is a before-picture "
                         f"and overwriting it after the count starts destroys "
                         f"the detector. Pass --force only if you are certain "
                         f"the count has not begun.")
    os.makedirs(os.path.dirname(SNAPSHOT), exist_ok=True)
    with open(SNAPSHOT, "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=1, sort_keys=True)
    top = sorted(d["players"].items(), key=lambda kv: -kv[1])[:5]
    print(f"wrote {SNAPSHOT}")
    print(f"  {sname}, {d['n_players']} players, {d['total_votes']:,} votes, "
          f"rounds {min(d['rounds_with_votes'])}-{max(d['rounds_with_votes'])}")
    for k, v in top:
        print(f"  {k.split('|')[0]:28} {v}")
    return 0


def _live(args):
    """(status, rows, label) off the live feed for --season (default LIVE_SEASON)."""
    import bfawards_feed as bf
    season = args.season or SEASON
    try:
        pid = bf.season_ids(season)[1]
    except LookupError:
        return None, [], f"{season}: the AFL has not published this season yet"
    status, rows = bf.players(pid, roster=False)
    return status, rows, f"{season} ({pid})"


def _state(status, total):
    if status == "CONCLUDED":
        return "COUNTED"
    if status == "LIVE":
        return "COUNTED" if FULL_VOTES and total >= FULL_VOTES else "COUNTING" if total else "LIVE, NOTHING READ YET"
    return f"NOT STARTED (feed status {status!r})"


def cmd_status(args):
    status, rows, label = _live(args)
    print(label)
    if status is None and not rows:
        return 0
    total = sum(r["totalVotes"] for r in rows)
    rounds = sorted({int(k) for r in rows for k in r["rounds"]})
    print(f"  state:  {_state(status, total)}")
    print(f"  feed:   {len(rows)} vote-getters, {total:,} votes, "
          f"{len(rounds)} rounds{f' ({rounds[0]}-{rounds[-1]})' if rounds else ''}")
    for r in sorted(rows, key=lambda r: -r["totalVotes"])[:10]:
        print(f"    {r['firstName'] + ' ' + r['surname']:28} {r['totalVotes']}")
    return 0


def cmd_rounds(args):
    status, rows, label = _live(args)
    if status not in ("LIVE", "CONCLUDED"):
        raise SystemExit(f"refusing: {label}, feed status {status!r}. Nothing has been counted.")
    per = {}
    for r in rows:
        for k, entries in r["rounds"].items():
            for e in entries:
                per.setdefault(int(k), []).append((e["points"], f"{r['firstName']} {r['surname']}"))
    for rnd in sorted(per):
        print("Opening Round:" if rnd == 0 else f"Round {rnd}:")
        for pts, name in sorted(per[rnd], key=lambda x: -x[0]):
            print(f"  {pts}  {name}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("snapshot", help="save the pre-count predictor state")
    sp.add_argument("--force", action="store_true")
    for name, h in (("status", "what the live count is doing right now"),
                    ("rounds", "per-round votes, once the count has started")):
        p = sub.add_parser(name, help=h)
        p.add_argument("--season", type=int, help="default: season.LIVE_SEASON")
    args = ap.parse_args(argv)
    return {"snapshot": cmd_snapshot, "status": cmd_status,
            "rounds": cmd_rounds}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
