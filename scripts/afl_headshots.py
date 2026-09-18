# -*- coding: utf-8 -*-
"""The AFL's own cutout headshot for any player, by AFLTables name.

    python scripts/afl_headshots.py "Patrick Cripps" "Tom Papley"

Downloads to `ChaChingContent/headshots/<Player Name>.png` (gitignored) and
returns the path. Already-downloaded players are not refetched.

WHY THIS EXISTS
`ChaChingContent/` holds hand-sourced action shots, and there are fourteen of
them. A deck that names any player in the league cannot be built on fourteen
photographs. These are 1080x1080 RGBA cutouts with a real alpha channel, so the
background is the card's rather than whatever stand the player was in front of,
and every slide in a deck renders identically.

THE URL IS NOT GUESSABLE AND THE ENDPOINT NEEDS A TOKEN
It is carried as `playerProfile.photoUrl` on
`api.afl.com.au/cfs/afl/playerProfile/{providerId}`, which needs the same
`x-media-mis-token` that fetch_match_chains.py mints from `POST /cfs/afl/WMCTok`
(that POST needs Origin, Referer and an explicit Content-Length: 0, or Akamai
answers with an HTML "Bad Request" rather than a JSON error). The path embeds a
season and a club code, so it moves when a player is traded and cannot be built
by hand. Dropping the `?im=Scale` query returns the full 1080 square; keeping it
returns 0.6 scale.

TWO ID SOURCES, THE CHEAP ONE FIRST
`data_chains/period_stats.csv` already carries Champion Data ids against
AFLTables spellings, but only for players who appeared in a final from 2021 on,
which is 491 of them. Anything it misses falls through to the AFL's own player
list, 17,677 rows over 177 pages, cached once to `data_2026/afl_player_ids.csv`.
That list spans every era, so a name shared across generations is ambiguous:
the most recently debuted player wins and the collision is printed, because
guessing silently is how a card ends up carrying the wrong man's face.
"""

import os
import sys

import pandas as pd
import requests
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fetch_match_chains as chains                               # noqa: E402
from features import normalise_name                               # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, "ChaChingContent", "headshots")
PERIOD_STATS = os.path.join(REPO, "data_chains", "period_stats.csv")
ID_CACHE = os.path.join(REPO, "data_2026", "afl_player_ids.csv")
AFLAPI = "https://aflapi.afl.com.au/afl/v2"
# fetch_match_chains.UA is the bare user agent STRING, not a header dict.
HDRS = {"User-Agent": chains.UA}

_ids = None
_roster = None
_session = None


def _session_with_token():
    global _session
    if _session is None:
        s = chains._session()
        s.headers["x-media-mis-token"] = chains._token(s)
        _session = s
    return _session


def _chain_ids():
    """{normalised name: providerId} from the play-by-play archive."""
    global _ids
    if _ids is None:
        d = pd.read_csv(PERIOD_STATS, usecols=["PlayerId", "Player"]).drop_duplicates("Player")
        _ids = {normalise_name(n): p for n, p in zip(d.Player, d.PlayerId)}
    return _ids


def _roster_ids():
    """{normalised name: [(debutYear, providerId), ...]} from the AFL's list."""
    global _roster
    if _roster is not None:
        return _roster
    if os.path.exists(ID_CACHE):
        d = pd.read_csv(ID_CACHE)
    else:
        print("  building the AFL player id cache, this runs once")
        rows, page = [], 0
        while True:
            r = requests.get(f"{AFLAPI}/players", headers=HDRS, timeout=30,
                             params={"pageSize": 100, "page": page})
            r.raise_for_status()
            body = r.json()
            for p in body.get("players", []):
                rows.append({"name": f"{p.get('firstName', '')} {p.get('surname', '')}".strip(),
                             "providerId": p.get("providerId"),
                             "debut": p.get("debutYear")})
            page += 1
            if page >= body["meta"]["pagination"]["numPages"]:
                break
        d = pd.DataFrame(rows)
        os.makedirs(os.path.dirname(ID_CACHE), exist_ok=True)
        d.to_csv(ID_CACHE, index=False)
        print(f"  cached {len(d)} players to {ID_CACHE}")
    d["_n"] = d.name.map(normalise_name)
    # The live list mixes "2019" and 2019, which sorted() refuses to compare.
    # Only the first, cache-building run sees it; read_csv coerces on the next.
    d["debut"] = pd.to_numeric(d.debut, errors="coerce")
    _roster ={n: sorted(zip(g.debut.fillna(0), g.providerId), reverse=True)
               for n, g in d.groupby("_n")}
    return _roster


def provider_id(name):
    key = normalise_name(name)
    hit = _chain_ids().get(key)
    if hit:
        return hit
    cands = _roster_ids().get(key)
    if not cands:
        return None
    if len(cands) > 1:
        print(f"  {name}: {len(cands)} players share this name, taking the "
              f"one who debuted {int(cands[0][0])}")
    return cands[0][1]


def head(name, refresh=False):
    """Local path to the cutout, or None if the AFL has no photo for him."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{name}.png")
    if os.path.exists(path) and not refresh:
        return path
    pid = provider_id(name)
    if not pid:
        print(f"  {name}: no provider id")
        return None
    s = _session_with_token()
    r = s.get(f"{chains.CFS}/playerProfile/{pid}", timeout=25)
    if r.status_code != 200:
        print(f"  {name}: playerProfile {r.status_code}")
        return None
    url = (r.json().get("playerProfile") or {}).get("photoUrl")
    if not url:
        print(f"  {name}: profile carries no photoUrl")
        return None
    img = requests.get(url.split("?")[0], headers=HDRS, timeout=30)
    if img.status_code != 200:
        print(f"  {name}: photo {img.status_code}")
        return None
    with open(path, "wb") as fh:
        fh.write(img.content)
    with Image.open(path) as im:
        if im.mode != "RGBA":
            print(f"  {name}: photo has no alpha channel, it will composite as a box")
        print(f"  {name}: {im.size[0]}x{im.size[1]}")
    return path


if __name__ == "__main__":
    for n in sys.argv[1:]:
        print(n, "->", head(n))
