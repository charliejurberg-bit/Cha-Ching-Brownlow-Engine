"""Recover AFLW Best and Fairest votes per match for the seasons the live feed
does not hold (2017 to 2023), from the AFL's published articles.

    python aflw/recover_votes.py [season ...]

Writes data_aflw/votes_<season>.csv in fetch_votes.py's shape (matchId, round,
playerId, player, team, votes), so every season reads the same downstream.

SOURCES, each an afl.com.au article that lists every match's 3-2-1. The site
resolves /news/<id>/<slug> by id and ignores the slug, so a wrong id serves
some other page with HTTP 200: every page is checked against its own <title>
before it is parsed (the same trap data_injury/ hit; see CLAUDE.md).

EVERY ROW IS JOINED TO THE STATS BY THE PLAYER'S AFL ID, found within the one
match the vote was given in: the vote's club and round pick the match, and the
name (full, or "B Davey" initial form in 2017) picks one of that club's players
in it. A name that matches nobody, or two people, refuses rather than guesses,
and the season is not written until every match totals 6 and every vote row has
an id. The published season totals (Wikipedia's leaderboard, TOTALS below) are
then checked against the file as an acceptance test, the check that proved the
2026 coaches transcription (CLAUDE.md, "Update chain").
"""

import html
import os
import re
import sys
import unicodedata

import pandas as pd
import requests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "data_aflw")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"}

# season label -> (article url, expected <title> fragment, format)
# The number before each name is the votes, in either order: 2017 lists them
# 1-2-3 ("1. B Davey (Carlton)" is ONE vote), 2022 lists 3-2-1. Reading 2017's
# "1." as best on ground gave Erin Phillips 10 against her published 14, which is
# how the order was settled: as votes, all ten published 2017 totals reconcile.
ARTICLES = {
    "2017": ("https://www.afl.com.au/news/90433/x", "All the votes", "votes"),
    "2022S7": ("https://www.afl.com.au/aflw/news/1001575/x", "Season Seven Best and Fairest", "votes"),
    # womens.afl, the AFLW site until 2022, is gone: its ids now redirect to the
    # afl.com.au/aflw home page. These two survive only in the Internet Archive.
    "2020": ("https://web.archive.org/web/2020id_/https://womens.afl/news/50256/"
             "who-polled-where-round-by-round-votes-for-aflw-b-f", "Who polled where", "votes"),
    "2021": ("https://web.archive.org/web/20210512111422id_/https://womens.afl/news/72094/"
             "aflw-b-f-your-club-s-leader-every-vote-from-every-game", "every vote from every game", "votes"),
    "2022S6": ("https://web.archive.org/web/20220406070028id_/https://www.womens.afl/news/92493/"
               "aflw-b-f-your-club-s-leader-every-vote-from-every-game", "every vote from every game", "votes"),
}

# Published top-of-count totals, for the acceptance test (Wikipedia, each season's
# "AFL Women's best and fairest" page), written in the STATS' spelling, which uses
# formal given names: Wikipedia's Ally Anderson is Alexandra, Maddy Prespakis is
# Madison. Georgie Prespakis (15, ineligible) is left out of 2022S7 only because
# the copy of the table this was checked against garbled her figure.
TOTALS = {
    # 2022S6 from Wikipedia: Bates 21, Hatchard 20, Marinoff 18.
    "2022S6": {"Emily Bates": 21, "Anne Hatchard": 20, "Ebony Marinoff": 18},
    # 2020 and 2021 from each season's Wikipedia leaderboard and the 2021
    # article's own club-by-club leaders.
    "2020": {"Madison Prespakis": 15, "Kiara Bowers": 12, "Emma Kearney": 11},
    "2021": {"Brianna Davey": 15, "Kiara Bowers": 15, "Alyce Parker": 14, "Ellie Blackburn": 14,
             "Anne Hatchard": 13, "Karen Paxman": 13, "Monique Conti": 12, "Madison Prespakis": 10,
             "Ashleigh Riddell": 10, "Georgia Patrikios": 7, "Mikayla Bowen": 5,
             "Kalinda Howarth": 3},
    "2017": {"Erin Phillips": 14, "Ellie Blackburn": 10, "Karen Paxman": 10, "Lara Filocamo": 9,
             "Kaitlyn Ashmore": 8, "Jess Dal Pos": 7, "Emma Kearney": 7, "Elise O'Dea": 7,
             "Daisy Pearce": 7, "Darcy Vescio": 7},
    "2022S7": {"Alexandra Anderson": 21, "Monique Conti": 19, "Ebony Marinoff": 18, "Madison Prespakis": 17,
               "Olivia Purcell": 16, "Alyce Parker": 15, "Charlie Rowbottom": 15,
               "Ellie Blackburn": 14, "Kiara Bowers": 14},
}

ROUND_WORDS = {w: i for i, w in enumerate(
    "ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE TEN ELEVEN TWELVE".split(), start=1)}

# Club spellings in the articles -> the stats files' team.name.
CLUBS = {
    "adelaide": "Adelaide Crows", "adelaide crows": "Adelaide Crows", "adel": "Adelaide Crows",
    "brisbane": "Brisbane Lions", "brisbane lions": "Brisbane Lions", "bris": "Brisbane Lions",
    "carlton": "Carlton", "carl": "Carlton", "collingwood": "Collingwood", "coll": "Collingwood",
    "essendon": "Essendon", "ess": "Essendon", "fremantle": "Fremantle", "frem": "Fremantle",
    "geelong": "Geelong Cats", "geelong cats": "Geelong Cats", "geel": "Geelong Cats",
    "gold coast": "Gold Coast SUNS", "gold coast suns": "Gold Coast SUNS", "gcs": "Gold Coast SUNS",
    "gws": "GWS GIANTS", "gws giants": "GWS GIANTS", "greater western sydney": "GWS GIANTS",
    "hawthorn": "Hawthorn", "haw": "Hawthorn", "melbourne": "Melbourne", "melb": "Melbourne",
    "north melbourne": "North Melbourne", "nth": "North Melbourne",
    "port adelaide": "Port Adelaide", "port": "Port Adelaide", "richmond": "Richmond", "rich": "Richmond",
    "st kilda": "St Kilda", "stk": "St Kilda", "sydney": "Sydney Swans", "sydney swans": "Sydney Swans",
    "syd": "Sydney Swans", "west coast": "West Coast Eagles", "west coast eagles": "West Coast Eagles",
    "wce": "West Coast Eagles", "western bulldogs": "Western Bulldogs", "wbd": "Western Bulldogs",
    "western": "Western Bulldogs",
    # womens.afl's short forms (2020, 2021). Kangaroos is North Melbourne.
    "adel": "Adelaide Crows", "bris": "Brisbane Lions", "carl": "Carlton", "coll": "Collingwood",
    "frem": "Fremantle", "fre": "Fremantle", "geel": "Geelong Cats", "gc": "Gold Coast SUNS", "gold coast suns": "Gold Coast SUNS",
    "gws giants": "GWS GIANTS", "melb": "Melbourne", "kang": "North Melbourne", "kangaroos": "North Melbourne",
    "nm": "North Melbourne", "rich": "Richmond", "stk": "St Kilda", "wc": "West Coast Eagles",
    "wb": "Western Bulldogs", "wbd": "Western Bulldogs",
}


# Published names no rule should guess, mapped to the stats' spelling. Each is a
# nickname AND a misspelling at once, so the initial and similarity tests both
# (rightly) refuse it. Keep this short; every entry is a hand-checked fact.
NAME_FIXES = {
    "Mua Laloiofi": "Vaomua Laloifi",   # 2023 club totals; Carlton
}


def club(s):
    k = re.sub(r"\s+", " ", str(s).strip().lower())
    if k not in CLUBS:
        raise ValueError(f"unknown club {s!r}")
    return CLUBS[k]


def norm(s):
    """Lower-case name tokens. A full stop is a token break, so womens.afl's
    "M.Prespakis" and "Em. King" split into an initial and a surname; an
    apostrophe is deleted, as the stats spell O'Dea."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = s.replace("’", "").replace("'", "").replace("-", " ").replace(".", " ")
    return re.sub(r"[^a-z ]", "", s.lower()).split()


def _get(url):
    """GET with retries: the Internet Archive answers 'Temporarily Offline' with
    a 200 in bursts, which is retried rather than parsed."""
    import time
    for attempt in range(5):
        try:
            r = requests.get(url, headers=UA, timeout=90)
            if r.status_code == 200 and "Temporarily Offline" not in r.text:
                return r
        except requests.RequestException:
            pass
        time.sleep(10 * (attempt + 1))
    raise SystemExit(f"{url}: unreachable after retries")


def page_text(url, must):
    r = _get(url)
    title = re.search(r"<title>(.*?)</title>", r.text, re.S).group(1)
    if must not in html.unescape(title):
        raise SystemExit(f"{url}: title {title.strip()!r} is not the expected article")
    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", r.text, flags=re.S)
    txt = html.unescape(re.sub(r"<[^>]+>", "\n", body)).replace("�", "").replace("\xa0", " ")
    return [ln.strip() for ln in txt.split("\n") if ln.strip()]


def parse(lines, fmt):
    """[(round, match line, votes, name, club or None)] from the article body."""
    out, rnd, match = [], None, None
    for ln in lines:
        m = re.fullmatch(r"(?:ROUND|Round)\s+(\w+)", ln)
        if m:
            w = m.group(1).upper()
            rnd = int(w) if w.isdigit() else ROUND_WORDS.get(w)
            continue
        if rnd is None:
            continue
        if re.fullmatch(r".+\svs?\s.+", ln) and not re.match(r"^\d", ln):
            match = ln
            continue
        # The full stop is optional: 2022S7 prints "1 Alison Drennan GCS" once.
        m = re.fullmatch(r"([123])(?:\.\s*|\s+)(.+?)\s*(?:\((.+?)\)|\s([A-Z]{2,4}))?", ln)
        # A trailing number or "votes" is a leaderboard line ("1. Madison
        # Prespakis (Carlton) 15" closes the 2020 article), and "2 hrs 11 mins
        # ago" is a page timestamp; neither is a vote.
        if m and match and not re.search(r"\d\s*$|\bvotes?\s*$|\bago\s*$", ln):
            n = int(m.group(1))
            votes = n
            code = m.group(3) or m.group(4)
            out.append((rnd, match, votes, m.group(2).strip(), code))
    return out


def load_stats(season):
    year = season[:4]
    st = pd.read_csv(os.path.join(OUT, f"stats_{year}.csv"), low_memory=False)
    if season.endswith(("S6", "S7")):
        st = st[st["compSeason.shortName"].str.endswith("Season " + season[-1])]
    st = st[st["round.name"].str.match(r"^(Round|Week) \d+$") & st["status"].eq("CONCLUDED")]
    st["rnd"] = st["round.roundNumber"].astype(int)
    st["_team"] = st["team.name"]
    st["_given"] = st["player.player.player.givenName"].map(norm)
    st["_sur"] = st["player.player.player.surname"].map(norm)
    return st


def resolve(rows, st):
    """Each vote -> (matchId, playerId). Refuses on no match or two."""
    out, bad = [], []
    # One article match -> one stats match, chosen once so all three of its votes
    # land together. The stated round first; failing that the same club pair
    # anywhere in the season, nearest round first, never a match already
    # claimed: 2022S6 replayed COVID-postponed games under other round numbers
    # (its round 4 Bulldogs v Fremantle is filed as "Round 10"). Two meetings of
    # one pair are two games; the claim rule keeps them apart, as the men's
    # build_score_involvements.py join does.
    chosen, claimed = {}, set()
    for rnd, match, votes, name, code in rows:
        key = (rnd, match)
        if key not in chosen:
            home, away = [club(x) for x in re.split(r"\s+vs?\s+", match)]
            pair = st[st["home.team.name"].isin([home, away]) & st["away.team.name"].isin([home, away])]
            opts = (pair.drop_duplicates("providerId")[["providerId", "rnd"]]
                    .assign(d=lambda d: (d.rnd - rnd).abs()).sort_values(["d", "rnd"]))
            opts = opts[~opts.providerId.isin(claimed)]
            chosen[key] = opts.providerId.iloc[0] if len(opts) else None
            if chosen[key] is not None:
                claimed.add(chosen[key])
        if chosen[key] is None:
            bad.append((rnd, match, name, "no unclaimed fixture")); continue
        g = st[st.providerId == chosen[key]]
        # The stated club first; then, if nobody there has the name, both sides of
        # the one match the vote is for. The 2020 article gives Chiocci to
        # Carlton and Hatchard to St Kilda; the match is never in doubt.
        hit = _find(g[g._team == club(code)] if code else g, name)
        if hit.empty and code:
            hit = _find(g, name)
        if len(hit) != 1:
            bad.append((rnd, match, name, f"{len(hit)} players")); continue
        r = hit.iloc[0]
        out.append({"matchId": r.providerId, "round": rnd, "playerId": r["player.player.player.playerId"],
                    "player": f"{r['player.player.player.givenName']} {r['player.player.player.surname']}",
                    "team": r._team, "votes": votes})
    return pd.DataFrame(out), bad


def _find(cand, name):
    """The one player in `cand` the published name can mean, or an empty or
    multi-row frame when it means nobody or several."""
    name = NAME_FIXES.get(name.strip(), name)
    parts = norm(name)
    sur, first = parts[-1:], parts[:-1]
    hit = cand.loc[cand._sur.map(lambda s: s[-1:] == sur or " ".join(s) == " ".join(parts[1:])).astype(bool)]
    if hit.empty:
        # One spelling slip ("Kerryn Petersen" for Peterson, "D.Porter" for
        # Danielle Ponter): a surname at least 0.8 similar whose given name
        # also starts with the published initial, accepted only if it is the
        # one such player.
        import difflib
        close = cand.loc[cand._sur.map(lambda s: bool(s) and difflib.SequenceMatcher(
            None, s[-1], sur[0] if sur else "").ratio() >= 0.8).astype(bool)]
        if first:
            close = close.loc[close._given.map(lambda gv: bool(gv) and gv[0][0] == first[0][0]).astype(bool)]
        if close["player.player.player.playerId"].nunique() == 1:
            hit = close
    if len(hit) > 1 and first:
        hit = hit.loc[hit._given.map(lambda gv: bool(gv) and gv[0].startswith(first[0])).astype(bool)]
    return hit.drop_duplicates("player.player.player.playerId")


def main(argv):
    for season in argv or sorted(ARTICLES):
        url, must, fmt = ARTICLES[season]
        rows = parse(page_text(url, must), fmt)
        st = load_stats(season)
        df, bad = resolve(rows, st)
        per = df.groupby("matchId")["votes"].sum() if not df.empty else pd.Series(dtype=int)
        print(f"{season}: {len(rows)} vote lines, {df.matchId.nunique() if not df.empty else 0} matches "
              f"of {st.providerId.nunique()} played, {len(bad)} unresolved")
        for b in bad[:15]:
            print("   unresolved:", b)
        wrong = per[per != 6]
        if bad or len(wrong):
            print(f"   refusing to write: {len(wrong)} matches not totalling 6")
            continue
        tot = df.groupby("player")["votes"].sum()
        for p, want in TOTALS.get(season, {}).items():
            got = int(tot.get(p, 0))
            if got != want:
                raise SystemExit(f"   {season}: {p} totals {got}, published {want}; refusing")
        df.insert(0, "season", season)
        df.to_csv(os.path.join(OUT, f"votes_{season}.csv"), index=False)
        print(f"   wrote votes_{season}.csv, published totals reconcile ({len(TOTALS.get(season, {}))} checked)")


if __name__ == "__main__":
    main(sys.argv[1:])
