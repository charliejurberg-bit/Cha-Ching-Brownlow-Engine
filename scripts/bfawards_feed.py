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

import requests

CFS = "https://api.afl.com.au/cfs/afl"
BASE = "https://aflapi.afl.com.au/afl/v2"
SEASON_PID = "CD_S2026014"

HDRS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/140.0.0.0 Safari/537.36"),
    "Origin": "https://www.afl.com.au",
    "Referer": "https://www.afl.com.au/",
    "Accept": "application/json",
}

TMO = (5, 20)


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


def player_ids():
    """{player provider id -> numeric id} from the award endpoint's roster.

    Downstream keys every player on the award endpoint's numeric ``id``, and
    the live feed carries only the provider form (CD_I297373). The award
    endpoint's VOTES are the stale predictor on count night, but its roster and
    its ids are not, so it stays the authority on identity alone.
    """
    out, page = {}, 0
    while True:
        r = requests.get(f"{BASE}/compseasons/85/award/brownlow"
                         f"?page={page}&pageSize=100", headers=HDRS, timeout=TMO)
        if r.status_code != 200:
            break
        batch = r.json().get("players", [])
        if not batch:
            break
        for p in batch:
            if p.get("providerId") and isinstance(p.get("id"), int):
                out[p["providerId"]] = p["id"]
        page += 1
        if page > 40:
            break
    return out


def raw(season=SEASON_PID, sess=None, tok=None):
    """The live payload: (status, matchVotes, leaderboard)."""
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


def players(season=SEASON_PID, with_ids=True):
    """Live votes in the award endpoint's player shape.

    Returns (status, rows). Built from ``matchVotes`` rather than from the
    leaderboard's ``roundByRoundVotes``, because matchVotes is the per-match
    record and carries the matchId every finished-round test keys on. The
    leaderboard is read only for the team id and the eligible flag.

    ``with_ids=False`` skips the numeric player id mapping, which costs a
    21-page walk of the award endpoint. The drafter keys on that id and needs
    it; the Live Tracker bridges on name plus club and does not, and it refetches
    every 60 seconds all night, so it asks for the cheap version.
    """
    status, match_votes, board = raw(season)
    tmap = team_ids()
    imap = player_ids() if with_ids else {}

    meta = {}
    for e in board:
        p = e.get("player") or {}
        meta[p.get("playerId")] = (e.get("team") or {}, e.get("eligible", True))

    rows = {}
    for m in match_votes:
        mid, rn = m.get("matchId"), m.get("roundNumber")
        for v in m.get("votes") or []:
            p = v.get("player") or {}
            pid = p.get("playerId")
            if pid is None or not v.get("votes"):
                continue
            team, elig = meta.get(pid, (v.get("team") or {}, v.get("eligible", True)))
            r = rows.setdefault(pid, {
                "id": imap.get(pid),
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

    checks = [("teamId", "club")] + ([("id", "player id")] if with_ids else [])
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
