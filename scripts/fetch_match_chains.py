"""Build data_chains/period_stats.csv

Run from the repository root, not from inside scripts/:
    python scripts/fetch_match_chains.py                    # all finals, 2021 on
    python scripts/fetch_match_chains.py --seasons 2024-2026
    python scripts/fetch_match_chains.py --seasons 2026 --all-rounds

Per-player, per-QUARTER kicks, handballs and disposals, from the AFL's own
play-by-play feed. This is the only source in or near this repository that can
answer an intra-game question: "disposals at half time", "third-quarter
touches", "first-quarter clearances". Everything else here, AFLTables, Wheelo,
footywire, Squiggle, carries full-match totals only, and the quarter columns in
`fitzroy_stats_all.csv` (HQ1P, AQ1P and friends) are TEAM SCORES, not player
stats.

The feed
--------
`https://api.afl.com.au/cfs/afl/matchChains/{providerId}` returns the match as a
list of chains, each with a `period` and a list of `stats` events. Every event
carries `periodSeconds`, `playerId`, `teamId` and a `description` ("Kick",
"Handball", "Loose Ball Get", "Spoil", 39 of them in a typical match).

It needs an `x-media-mis-token`, which is minted free and unauthenticated from
`POST /cfs/afl/WMCTok`. Akamai rejects that POST unless it carries Origin,
Referer and an explicit `Content-Length: 0`; without them you get a bare
"Bad Request" page rather than a JSON error, which is why _token() sets all
three. The fixture walk on `aflapi.afl.com.au` needs no token at all.

What counts as a disposal
-------------------------
The `disposal` field is non-null on exactly three descriptions (Kick, Ground
Kick, Handball) and null on the other 36, so a disposal is simply an event with
`disposal` not null, and there is no description list to maintain. Calibrated
against the AFL's own live half-time figures for the 2026 wildcard final this
reproduced 45 of 46 players exactly. Counting by description instead scored
37/46 with {Kick}, 44/46 with {Kick, Ground Kick}: the `disposal` field is the
better rule and it is the source's own definition. DISPOSAL_KEY records this.

Two boundaries, both in the source rather than chosen here
----------------------------------------------------------
1. COVERAGE STARTS IN 2021. `matchChains` returns HTTP 200 with an empty
   `matchChains` list for every season 2012-2020, checked across rounds 1, 5,
   15 and 23-27 in 2017-2020. It is not an error and not a missing-match case,
   so an unguarded run would write nothing and report success. FIRST_SEASON
   refuses the range instead.
2. THE FEED LAGS BADLY DURING A LIVE MATCH. Mid-fourth-quarter of the 2026
   wildcard final the chains had Sam Swadling on 20 disposals while the official
   `playerStats` feed had him on 30; both read 32 once the match finished. A
   live match therefore yields silently short quarters, so only matches whose
   fixture status is in FINISHED_STATUS are fetched. Re-run after the siren.

The guard
---------
Per-period disposals are summed per player and compared against the official
full-match figure from `playerStats/match`, which is a different endpoint
computed by Champion Data rather than by this script. Below MIN_MATCH_RATE the
run refuses to write, on the same principle as build_score_involvements.py: a
partial parse that looks like a full one is worse than no file.

Politeness
----------
Two requests per match, ~0.15s apart, plus one fixture page per 40 matches.
Raw JSON is cached under data_chains/raw/ (gitignored) so a re-run costs
nothing; pass --refresh to bypass the cache.
"""

import argparse
import json
import os
import sys
import time
from collections import defaultdict

import pandas as pd
import requests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO, "data_chains")
RAW_DIR = os.path.join(OUT_DIR, "raw")
OUT_CSV = os.path.join(OUT_DIR, "period_stats.csv")

AFLAPI = "https://aflapi.afl.com.au/afl/v2"
CFS = "https://api.afl.com.au/cfs/afl"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
DELAY = 0.15

# See "What counts as a disposal" above. Kept as a named constant so the rule is
# greppable and so a future change to it is a deliberate edit, not a typo.
DISPOSAL_KEY = "disposal"

# See boundary 1. Nothing earlier exists to fetch.
FIRST_SEASON = 2021

# See boundary 2. 'CONCLUDED' is what older seasons report, 'POSTGAME' is what a
# match reports in the hours after its own siren; both are final.
FINISHED_STATUS = {"CONCLUDED", "POSTGAME"}

MIN_MATCH_RATE = 0.98

# Champion Data club ids to the AFLTables spelling used everywhere else here.
# club_aliases.canonical_club then folds Footscray/Kangaroos style renames, but
# it is deliberately NOT applied at this layer: this file records the club
# string AFLTables would use for that season, and canonicalising is the reading
# layer's job (period_records.py does it).
CD_TEAM = {
    "CD_T10": "Adelaide", "CD_T20": "Brisbane Lions", "CD_T30": "Carlton",
    "CD_T40": "Collingwood", "CD_T50": "Essendon", "CD_T60": "Fremantle",
    "CD_T70": "Geelong", "CD_T80": "Hawthorn", "CD_T90": "Melbourne",
    "CD_T100": "North Melbourne", "CD_T110": "Port Adelaide",
    "CD_T120": "Richmond", "CD_T130": "St Kilda", "CD_T140": "Western Bulldogs",
    "CD_T150": "West Coast", "CD_T160": "Sydney", "CD_T1000": "Gold Coast",
    "CD_T1010": "Greater Western Sydney",
}


def _session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "application/json",
        "Referer": "https://www.afl.com.au/",
        "Origin": "https://www.afl.com.au",
    })
    return s


def _token(sess):
    """Mint a media token. All three headers below are load-bearing, see docstring."""
    r = sess.post(f"{CFS}/WMCTok", headers={"Content-Length": "0"}, timeout=20)
    r.raise_for_status()
    return r.json()["token"]


def _compseasons(sess):
    """{season_year: compSeasonId} for the men's premiership competition."""
    r = sess.get(f"{AFLAPI}/competitions/1/compseasons", params={"pageSize": 50}, timeout=20)
    r.raise_for_status()
    out = {}
    for c in r.json().get("compSeasons", []):
        if "Premiership" in c.get("name", ""):
            out[int(c["name"][:4])] = c["id"]
    return out


def _fixture(sess, comp_season_id, season):
    """Every match in a season, as flat dicts. No token needed."""
    matches, page = [], 0
    while True:
        r = sess.get(f"{AFLAPI}/matches",
                     params={"competitionId": 1, "compSeasonId": comp_season_id,
                             "pageSize": 40, "page": page}, timeout=30)
        r.raise_for_status()
        j = r.json()
        for m in j.get("matches", []):
            matches.append({
                "Season": season,
                "MatchId": m["providerId"],
                "RoundNumber": m["round"]["roundNumber"],
                "RoundName": m["round"]["name"],
                "Home": m["home"]["team"]["name"],
                "Away": m["away"]["team"]["name"],
                "utc": m.get("utcStartTime"),
                "status": m.get("status"),
            })
        page += 1
        if page >= j["meta"]["pagination"]["numPages"]:
            break
        time.sleep(DELAY)
    return matches


def _cached(sess, token, path, key, refresh):
    cache = os.path.join(RAW_DIR, key + ".json")
    if not refresh and os.path.exists(cache):
        with open(cache) as fh:
            return json.load(fh)
    r = sess.get(f"{CFS}/{path}", headers={"x-media-mis-token": token}, timeout=30)
    r.raise_for_status()
    j = r.json()
    with open(cache, "w") as fh:
        json.dump(j, fh)
    time.sleep(DELAY)
    return j


def _official(stats_json):
    """{playerId: (name, cd_team, kicks, handballs, disposals)} from playerStats."""
    out = {}
    for side in ("homeTeamPlayerStats", "awayTeamPlayerStats"):
        for row in stats_json.get(side, []):
            p = row["player"]["player"]["player"]
            n = p["playerName"]
            s = row["playerStats"]["stats"]
            out[p["playerId"]] = (
                f"{n.get('givenName', '')} {n.get('surname', '')}".strip(),
                row.get("teamId"),
                s.get("kicks"), s.get("handballs"), s.get("disposals"),
            )
    return out


def _periods(chains_json):
    """{(playerId, period): [kicks, handballs]} from the chain events."""
    tally = defaultdict(lambda: [0, 0])
    for chain in chains_json.get("matchChains", []):
        period = chain["period"]
        for ev in chain.get("stats", []):
            pid = ev.get("playerId")
            if not pid or not ev.get(DISPOSAL_KEY):
                continue
            # "Ground Kick" is a kick and carries a disposal; "Handball" is the
            # only handball description that does.
            idx = 1 if ev.get("description") == "Handball" else 0
            tally[(pid, period)][idx] += 1
    return tally


def build(seasons, finals_only, refresh):
    os.makedirs(RAW_DIR, exist_ok=True)
    sess = _session()
    token = _token(sess)
    comp = _compseasons(sess)

    rows, checked, agreed, skipped_live, empty = [], 0, 0, [], []

    for season in seasons:
        if season not in comp:
            print(f"  {season}: no compSeason on the AFL API, skipped")
            continue
        fixture = _fixture(sess, comp[season], season)
        if finals_only:
            fixture = [m for m in fixture if "Final" in m["RoundName"]]
        print(f"  {season}: {len(fixture)} matches")

        for m in fixture:
            if m["status"] not in FINISHED_STATUS:
                skipped_live.append(f"{season} {m['RoundName']} {m['MatchId']} ({m['status']})")
                continue
            mid = m["MatchId"]
            try:
                chains = _cached(sess, token, f"matchChains/{mid}", "ch_" + mid, refresh)
                stats = _cached(sess, token, f"playerStats/match/{mid}", "ps_" + mid, refresh)
            except requests.HTTPError as exc:
                print(f"    ! {mid}: {exc}")
                continue

            tally = _periods(chains)
            if not tally:
                empty.append(f"{season} {m['RoundName']} {mid}")
                continue
            official = _official(stats)

            per_player = defaultdict(int)
            for (pid, period), (k, h) in sorted(tally.items()):
                name, cd_team, _, _, _ = official.get(pid, (pid, None, None, None, None))
                per_player[pid] += k + h
                rows.append({
                    "Season": season,
                    "MatchId": mid,
                    "RoundNumber": m["RoundNumber"],
                    "RoundName": m["RoundName"],
                    "utc": m["utc"],
                    "Home": m["Home"],
                    "Away": m["Away"],
                    "PlayerId": pid,
                    "Player": name,
                    "Team": CD_TEAM.get(cd_team, cd_team),
                    "Period": period,
                    "Kicks": k,
                    "Handballs": h,
                    "Disposals": k + h,
                })
            # Guard: the sum over periods must equal the official match total,
            # which comes from a different endpoint we did not compute.
            for pid, (_, _, _, _, disp) in official.items():
                if disp is None:
                    continue
                checked += 1
                agreed += int(per_player.get(pid, 0) == disp)

    if not rows:
        raise SystemExit("Refusing to write: no chain rows were produced.")

    rate = agreed / checked if checked else 0.0
    print(f"\n  validation: {agreed}/{checked} players reconcile against the "
          f"official match totals ({rate:.2%})")
    if skipped_live:
        print(f"  skipped {len(skipped_live)} unfinished match(es); the chains feed "
              f"lags in play, re-run after the siren:")
        for s in skipped_live[:8]:
            print(f"    {s}")
    if empty:
        print(f"  {len(empty)} match(es) returned an empty chain list:")
        for s in empty[:8]:
            print(f"    {s}")
    if rate < MIN_MATCH_RATE:
        raise SystemExit(
            f"Refusing to write {OUT_CSV}: {rate:.2%} of players reconcile, below "
            f"the {MIN_MATCH_RATE:.0%} floor. A short quarter usually means a match "
            f"was still live when it was cached; re-run with --refresh.")

    df = pd.DataFrame(rows).sort_values(["Season", "MatchId", "Team", "Player", "Period"])
    os.makedirs(OUT_DIR, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    print(f"\n  wrote {OUT_CSV}: {len(df):,} rows, "
          f"{df.MatchId.nunique()} matches, seasons {df.Season.min()}-{df.Season.max()}")
    return 0


def _parse_seasons(text):
    if "-" in text:
        lo, hi = text.split("-", 1)
        seasons = list(range(int(lo), int(hi) + 1))
    else:
        seasons = [int(s) for s in text.split(",")]
    bad = [s for s in seasons if s < FIRST_SEASON]
    if bad:
        raise SystemExit(
            f"Refusing {bad}: the AFL chains feed returns an empty list for every "
            f"season before {FIRST_SEASON}. That is a boundary in the source, not a "
            f"fetch-range choice, and no other public feed carries player stats by "
            f"quarter. Ask for {FIRST_SEASON} onward.")
    return seasons


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seasons", default=f"{FIRST_SEASON}-2026",
                    help="e.g. 2026, 2021-2026, or 2021,2024 (default: 2021-2026)")
    ap.add_argument("--all-rounds", action="store_true",
                    help="fetch home-and-away rounds too (default: finals only)")
    ap.add_argument("--refresh", action="store_true",
                    help="bypass the raw JSON cache and refetch")
    args = ap.parse_args(argv)

    seasons = _parse_seasons(args.seasons)
    print(f"AFL match chains: seasons {seasons[0]}-{seasons[-1]}, "
          f"{'all rounds' if args.all_rounds else 'finals only'}")
    return build(seasons, finals_only=not args.all_rounds, refresh=args.refresh)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
