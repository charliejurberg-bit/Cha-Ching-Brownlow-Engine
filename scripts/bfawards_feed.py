"""The AFL's LIVE Brownlow vote feed, and the reason it exists.

`count_night.py` reads `aflapi.afl.com.au/afl/v2/compseasons/{id}/award/brownlow`.
On count night 2026 that endpoint did NOT flip to the live count: at 20:26, with
five rounds already read out on the broadcast, it was still byte-identical to
the predictor snapshot taken on 10 September. The AFL's own live tracker page
was showing the real votes at the same moment, so the data existed and we were
reading the wrong feed.

The page's real source, found by sniffing its network calls:

    https://api.afl.com.au/cfs/afl/bfawards/season/{seasonProviderId}
    https://api.afl.com.au/cfs/afl/bfawards/leaderboard/season/{seasonProviderId}

Three things make it the right feed and the old one wrong:

- It carries an explicit ``status`` field ("LIVE"). The award endpoint has no
  such field, which is the whole reason the snapshot comparison had to exist.
- It is round-complete: ``matchVotes`` holds one entry per match actually read
  out, so finished-round detection needs no guessing.
- It agrees with the broadcast. Round 1 CD_M20260140101 reads 3 Jagga Smith,
  2 Patrick Cripps, 1 Tim Taranto, which is what was read out on air, where the
  award endpoint claimed 3 Jagga Smith, 2 Sam Lalor, 1 Sam Walsh.

It needs an ``x-media-mis-token``, minted exactly as `fetch_match_chains.py`
mints one: unauthenticated, free, and requiring Origin, Referer and an explicit
``Content-Length: 0`` on the POST.

`players()` returns rows in the SHAPE THE AWARD ENDPOINT USES, so every existing
consumer (count_night.digest, count_tweets.build_context) works unchanged. The
team id is translated from the provider id (CD_T140) to the numeric id (8) that
`FEED_CLUBS` is keyed on, via the aflapi teams endpoint rather than by matching
club names: the two feeds spell six clubs differently and name matching there is
exactly the trap `AFL_AWARD_TEAM_FIXES` exists to document.
"""

import os
import sys

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import season as season_cfg  # noqa: E402

CFS = "https://api.afl.com.au/cfs/afl"
BASE = "https://aflapi.afl.com.au/afl/v2"

HDRS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/140.0.0.0 Safari/537.36"),
    "Origin": "https://www.afl.com.au",
    "Referer": "https://www.afl.com.au/",
    "Accept": "application/json",
}

TMO = (5, 20)

_IDS = {}


def season_ids(season=None):
    """(numeric compSeason id, provider id) for a season's Premiership, e.g.
    (85, "CD_S2026014") for 2026. Looked up by NAME from the same list
    count_night.season_id() reads, so a new season needs no constant here.
    These were written in as 85 and "CD_S2026014" until 27 September 2026."""
    season = season_cfg.LIVE_SEASON if season is None else season
    if season not in _IDS:
        r = requests.get(f"{BASE}/competitions/1/compseasons?pageSize=20", headers=HDRS, timeout=TMO)
        r.raise_for_status()
        for c in r.json().get("compSeasons", []):
            if str(season) in c.get("name", "") and "Premiership" in c.get("name", ""):
                _IDS[season] = (c["id"], c["providerId"])
                break
        else:
            # LookupError, not SystemExit: the dashboard imports this and catches
            # Exception, which SystemExit is not. Before the AFL publishes a new
            # season's compSeason (the weeks after a rollover), SystemExit went
            # straight through the Live Tracker's handler.
            raise LookupError(f"no Premiership compSeason found for {season}")
    return _IDS[season]


def token(sess=None):
    """A media token. Akamai 400s the POST without an explicit Content-Length."""
    sess = sess or requests.Session()
    sess.headers.update(HDRS)
    r = sess.post(f"{CFS}/WMCTok", headers={"Content-Length": "0"}, timeout=20)
    r.raise_for_status()
    return r.json()["token"], sess


def team_ids():
    """{provider id -> numeric id} for the 18 senior clubs.

    Ids above 18 are academy and women's sides sharing club names, so the
    mapping is taken from the first 18 rather than by name.
    """
    r = requests.get(f"{BASE}/teams?pageSize=50", headers=HDRS, timeout=TMO)
    r.raise_for_status()
    out = {}
    for t in r.json().get("teams", []):
        if isinstance(t.get("id"), int) and 1 <= t["id"] <= 18:
            out[t["providerId"]] = t["id"]
    return out


def award_roster():
    """Every eligible player from the award endpoint, votes stripped.

    Downstream keys players on the award endpoint's numeric ``id``, and the
    live feed carries only the provider form (CD_I297373). The award endpoint's
    VOTES are the stale predictor on count night, but its ROSTER and its ids
    are not, so it stays the authority on identity alone.

    It is also the only source of players who polled nothing. The live feed
    carries vote-getters and no one else, and several things downstream ask a
    question about a player BECAUSE he has no votes: the snub test wants the
    model's first pick in a game to have polled zero, and cannot tell "polled
    zero" from "absent from the payload". Returning the full roster with
    ``totalVotes`` zeroed restores the shape the award endpoint always had.
    """
    out, page = [], 0
    while True:
        r = requests.get(f"{BASE}/compseasons/{season_ids()[0]}/award/brownlow"
                         f"?page={page}&pageSize=100", headers=HDRS, timeout=TMO)
        if r.status_code != 200:
            break
        batch = r.json().get("players", [])
        if not batch:
            break
        for p in batch:
            if p.get("providerId") and isinstance(p.get("id"), int):
                out.append({
                    "id": p["id"],
                    "providerId": p["providerId"],
                    "firstName": p.get("firstName", ""),
                    "surname": p.get("surname", ""),
                    "teamId": p.get("teamId"),
                    "eligible": p.get("eligible", True),
                    "totalVotes": 0,
                    "rounds": {},
                })
        page += 1
        if page > 40:
            break
    return out


def raw(season=None, sess=None, tok=None):
    """The live payload: (status, matchVotes, leaderboard). `season` is the
    provider id (CD_S2026014); None means season.LIVE_SEASON's."""
    if season is None:
        season = season_ids()[1]
    if tok is None:
        tok, sess = token(sess)
    h = {"x-media-mis-token": tok}
    s = sess.get(f"{CFS}/bfawards/season/{season}", headers=h, timeout=30)
    s.raise_for_status()
    sj = s.json()
    l = sess.get(f"{CFS}/bfawards/leaderboard/season/{season}",
                 headers=h, timeout=30)
    l.raise_for_status()
    return sj.get("status"), sj.get("matchVotes", []), l.json().get("leaderboard", [])


def players(season=None, roster=True):
    """Live votes in the award endpoint's player shape.

    Returns (status, rows). Votes are built from ``matchVotes`` rather than
    from the leaderboard's ``roundByRoundVotes``, because matchVotes is the
    per-match record and carries the matchId every finished-round test keys
    on. The leaderboard is read only for the team id and the eligible flag.

    ``roster=True`` walks the award endpoint as well, for the numeric player
    ids and for every player on zero votes. The drafter needs both, and the
    zero-vote half is not optional for it: see `award_roster`.

    ``roster=False`` returns the vote-getters alone and skips that 21-page
    walk. The Live Tracker bridges on name plus club, computes its blanked and
    bolter panels from the model frame rather than from feed absence, and
    refetches every 60 seconds all night, so it takes the cheap read.
    """
    status, match_votes, board = raw(season)
    tmap = team_ids()

    meta = {}
    for e in board:
        p = e.get("player") or {}
        meta[p.get("playerId")] = (e.get("team") or {}, e.get("eligible", True))

    rows = {}
    if roster:
        # Seeded with every eligible player on zero votes, then the live votes
        # are laid over the top. A vote-getter the roster somehow omits still
        # gets created by the setdefault below.
        for p in award_roster():
            rows[p["providerId"]] = p

    for m in match_votes:
        mid, rn = m.get("matchId"), m.get("roundNumber")
        for v in m.get("votes") or []:
            p = v.get("player") or {}
            pid = p.get("playerId")
            if pid is None or not v.get("votes"):
                continue
            team, elig = meta.get(pid, (v.get("team") or {}, v.get("eligible", True)))
            r = rows.setdefault(pid, {
                "id": None,
                "providerId": pid,
                "firstName": p.get("givenName", ""),
                "surname": p.get("surname", ""),
                "teamId": tmap.get(team.get("teamId")),
                "eligible": elig,
                "totalVotes": 0,
                "rounds": {},
            })
            r["rounds"].setdefault(str(rn), []).append(
                {"providerId": mid, "points": v["votes"]})
            r["totalVotes"] += v["votes"]

    checks = [("teamId", "club")] + ([("id", "player id")] if roster else [])
    for field, what in checks:
        bad = [r for r in rows.values() if r[field] is None]
        if bad:
            raise SystemExit(
                f"{len(bad)} players with an unmapped {field}, first: "
                f"{bad[0]['firstName']} {bad[0]['surname']}. "
                f"Refusing rather than guessing a {what}.")

    return status, list(rows.values())


if __name__ == "__main__":
    st, ps = players()
    tot = sum(p["totalVotes"] for p in ps)
    rounds = sorted({int(k) for p in ps for k in p["rounds"]})
    print(f"status={st}  players={len(ps)}  votes={tot}  rounds={rounds}")
