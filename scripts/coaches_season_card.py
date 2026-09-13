"""Biggest season in the AFL Coaches Association award, one player marked.

    python scripts/coaches_season_card.py "Nick Daicos" 1
    python scripts/coaches_season_card.py "Nick Daicos" 1 --rows 6 --preview

Writes a PNG to drafts/ (gitignored). Portrait 1200x1500 at S=2, downsampled
once to Twitter's 2048 long edge, same as the other countdown cards. Fonts,
colours and the CHA CHING mark are imported from countdown_card rather than
restated. No footer text, by standing rule: the window and the qualifier sit in
the header, where they are set at a size that survives a timeline.

WHY THIS CARD EXISTS
The coaches are the only people who rate every game of a season on the record
and are not the umpires, so their award is the one independent read on a
Brownlow favourite that exists before count night. A card built on it says
something the model cannot be accused of having invented.

THE ARCHIVE IS NOT SAFE TO SUM RAW AND THE REPAIR HERE IS ITS OWN
coaches_guard.clean_source is the repo's display-side repair and it is not used
here, because it does not reach the defect that matters most to a SEASON total.
It drops fixtures that fail the 30 test and player-rounds that duplicate, over
the ceiling or fractional, which removes every Grand Final block from 2021 on.
It does not remove 2020's, where the last round's nine games are repeated
forward across five phantom rounds that each sum to 30, carry integer values and
duplicate no player-round key. Left in, 2020 reads 208 home-and-away games
against the AFL's 153 and Christian Petracca reads 128 votes against a true 78,
which would put a phantom season third on this ladder.

The repair used instead is a DEDUPE ON THE VOTE BLOCK: a game is identified by
its club pair plus the exact list of players and votes, and a block that has
already appeared in an earlier round is a repeat. Two genuinely different games
cannot share all three. It removes 84 of the archive's 4,481 games and
reconciles 2020 to 153 home-and-away plus 9 finals exactly. If coaches_guard
ever adopts the same test, delete this and call it.

A GRAND FINAL WEARING A HOME-AND-AWAY ROUND LABEL IS A SECOND DEFECT ENTIRELY
The vote-block dedupe above cannot see it and neither can the round cut, which
keeps every round up to the last one holding five or more games. Three Grand
Finals sit inside the archive under an ordinary round number: 2018's and 2019's
under round 19, 2021's under round 20. A Grand Final is not a repeat of another
game, so its block is unique; it sums to 30; it duplicates no player-round key.
It passes every test the repo has. 2018 round 16 also carries a corrupt
"Collingwood v Collingwood" row that behaves the same way.

The fingerprint is that A CLUB CANNOT PLAY TWICE IN ONE ROUND, and that is what
_drop_leaked_finals tests. Four fixtures and 116 votes come out.

2021 is why this matters and not merely tidy. It was carrying the Grand Final
AND missing a genuine home-and-away game, so the coverage test below saw 198
against the archive's 198 and passed it as complete. Two errors cancelling made
a contaminated season look like the clean ones. Clayton Oliver ranked sixth on
this ladder at 112 votes when his home-and-away figure is 107, and Petracca's 96
is really 86. Removing the Grand Final drops 2021 to 197 and it is now excluded,
where it belongs. 2019 moves the other way: it was excluded only because the
Grand Final inflated it to 199 against 198, and it is now complete and ranked.

The check is worth keeping even once it finds nothing, and there is a specific
reason to trust it beyond the four it catches. A final stamped on a round where
neither of its clubs played would not repeat a club and would slip through. But
after the repair NO season has more feed games than the archive holds; every
remaining discrepancy is a shortfall. A surplus is exactly what an undetected
extra game would look like, and there is none left anywhere.

SEASONS THE FEED DOES NOT FULLY COVER ARE EXCLUDED FROM THE RANKING
Six seasons are short of the archive's fixture list even after both repairs:
2011, 2018, 2021, 2023, 2024 and 2025, the worst being 2025 at 188 games of 207.
A
missing game is a missing chance to poll, so a total from one of those seasons
is a floor rather than a figure and cannot be ranked against a complete one.
They are not silently dropped: every run prints the worst case each excluded
season could hold, computed as the player's counted total plus ten for every
game of his own the feed lacks. On the current archive the highest such ceiling
is 141, against a drawn record of 147, so the ranking survives the exclusion
being wrong in the most pessimistic direction available. Any run where that
ceiling exceeds the leader prints a warning and the copy has to say so.
"""

import argparse
import os
import re
import sys

import pandas as pd
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import features as feat  # noqa: E402  the repo's own name normaliser
from countdown_card import (  # noqa: E402
    BG, INK, MUTED, RANK_INK, EMERALD, LINE,
    W, H, S, draw_mark, font, ordinal, set_fonts, FONT_SETS,
)

OUT_DIR = "drafts"
COACHES_ALL = "coaches_votes_all.csv"
COACHES_CUR = "data_2026/coaches_votes_2026.csv"
STATS_ALL = "fitzroy_stats_all.csv"
STATS_CUR = "data_2026/afltables_2026.csv"
HIST_GAME_LEVEL = "data_history/game_level_{}.csv"
EARLY = (2004, 2005, 2006)      # before fitzroy_stats_all.csv starts
KEY = ["Season", "Round", "Home.Team", "Away.Team"]
VOTES_PER_GAME = 30             # 5-4-3-2-1 from each of two coaches
MAX_PER_GAME = 10               # both coaches' top place to one player
MIN_GAMES = 12
BAR = "#1c2a36"
CLUB = {"ADEL": "Adelaide", "BL": "Brisbane Lions", "CARL": "Carlton",
        "COLL": "Collingwood", "ESS": "Essendon", "FRE": "Fremantle",
        "GCFC": "Gold Coast", "GEEL": "Geelong",
        "GWS": "Greater Western Sydney", "HAW": "Hawthorn", "MELB": "Melbourne",
        "NMFC": "North Melbourne", "PORT": "Port Adelaide", "RICH": "Richmond",
        "STK": "St Kilda", "SYD": "Sydney", "WB": "Western Bulldogs",
        "WCE": "West Coast"}

# The feed names a fixture's clubs differently again in Home.Team / Away.Team:
# nicknames where the archive uses the bare city. The archive has its own drift,
# carrying "Kangaroos" before the 2008 rename. Both sides go through this before
# any fixture is compared, or _drop_leaked_finals reads a naming difference as a
# missing game and deletes a real one.
FIXTURE_CLUB = {"Adelaide Crows": "Adelaide", "Geelong Cats": "Geelong",
                "Gold Coast Suns": "Gold Coast",
                "GWS Giants": "Greater Western Sydney",
                "Kangaroos": "North Melbourne", "Sydney Swans": "Sydney",
                "West Coast Eagles": "West Coast"}


def _played():
    """One row per player-game in the stats archive: Season, name, club.

    Also carries the fixture it belongs to, as round plus canonical club pair,
    so _drop_leaked_finals can ask what the archive holds for a given round.
    """
    def take(d, season=None):
        d = d[pd.to_numeric(d["Round"], errors="coerce").notna()]
        return pd.DataFrame({
            "Season": d["Season"] if season is None else season,
            "P": (d["First.name"].astype(str).str.strip() + " "
                  + d["Surname"].astype(str).str.strip()),
            "club": d["Playing.for"].replace({"Kangaroos": "North Melbourne"}),
            "rd": pd.to_numeric(d["Round"]).astype(int),
            "hm": d["Home.team"].replace(FIXTURE_CLUB),
            "aw": d["Away.team"].replace(FIXTURE_CLUB)})

    frames = [take(pd.read_csv(STATS_ALL, low_memory=False)),
              take(pd.read_csv(STATS_CUR, low_memory=False), 2026)]
    for yr in EARLY:
        h = pd.read_csv(HIST_GAME_LEVEL.format(yr), low_memory=False)
        h = h[pd.to_numeric(h["Round_num"], errors="coerce").notna()]
        frames.append(pd.DataFrame({
            "Season": yr, "P": h["Player_Name"],
            "club": h["Playing.for"].replace({"Kangaroos": "North Melbourne"}),
            "rd": pd.to_numeric(h["Round_num"]).astype(int),
            "hm": h["Home.team"].replace(FIXTURE_CLUB),
            "aw": h["Away.team"].replace(FIXTURE_CLUB)}))
    pl = pd.concat(frames, ignore_index=True)
    return pl.assign(gid=pl.rd.astype(str) + pl.hm + pl.aw)


def _clean(cv):
    """Deduped, 30-checked, home-and-away coaches rows. See the module docstring."""
    sig = (cv.groupby(KEY)
             .apply(lambda x: tuple(sorted(zip(x["Player.Name"], x["Coaches.Votes"]))),
                    include_groups=False).rename("sig").reset_index()
             .sort_values(["Season", "Round"]))
    keep = set(map(tuple, sig.drop_duplicates(
        ["Season", "Home.Team", "Away.Team", "sig"], keep="first")[KEY].values))
    n0 = cv.groupby(KEY).ngroups
    cv = cv[[t in keep for t in
             zip(cv.Season, cv.Round, cv["Home.Team"], cv["Away.Team"])]]
    n_dup = n0 - cv.groupby(KEY).ngroups

    tot = cv.groupby(KEY)["Coaches.Votes"].transform("sum")
    n_bad = cv.groupby(KEY).ngroups - cv[tot == VOTES_PER_GAME].groupby(KEY).ngroups
    cv = cv[tot == VOTES_PER_GAME].copy()

    # A round is home-and-away up to the last one holding five or more games.
    # NOT "every round with five or more": Opening Round from 2024 has two to
    # four and is home and away, and dropping it cost a 9-vote game.
    sz = (cv.groupby(["Season", "Round"])
            .apply(lambda d: d.groupby(["Home.Team", "Away.Team"]).ngroups,
                   include_groups=False).rename("n").reset_index())
    cut = sz[sz.n >= 5].groupby("Season")["Round"].max()
    cv = cv[cv.Round <= cv.Season.map(cut)].copy()

    cv["club"] = cv["Player.Name"].str.extract(r"\(([^)]*)\)\s*$")[0].map(CLUB)
    cv["P"] = cv["Player.Name"].str.replace(
        r"\s*\([^)]*\)\s*$", "", regex=True).str.strip()
    if cv.club.isna().any():
        bad = sorted(cv.loc[cv.club.isna(), "Player.Name"].str[-8:].unique())[:5]
        raise SystemExit(f"unmapped club code in {bad}")
    return cv, n_dup, n_bad


def _drop_leaked_finals(cv, pl):
    """Remove a final the feed filed under a home-and-away round label.

    See the module docstring. The test is that a club cannot play twice in one
    round, so a round where one does is carrying a fixture that does not belong
    to it. Which of the two is the intruder comes from the archive rather than
    from a guess: the archive is the authority on which home-and-away games
    happened, so the fixture it holds no room for in that round is the one that
    goes. A round with no repeated club is never touched.

    Deliberately narrower than "drop anything the archive lacks". A feed that is
    merely missing games, which is most of them, must stay missing so the
    coverage test can see the shortfall and exclude the season. Only a surplus
    is removed here.
    """
    have = set(zip(pl.Season, pl.rd, pl.hm, pl.aw))
    hm = cv["Home.Team"].replace(FIXTURE_CLUB)
    aw = cv["Away.Team"].replace(FIXTURE_CLUB)
    drop, mask = [], pd.Series(False, index=cv.index)
    for (sn, rd), s in cv.assign(hm=hm, aw=aw).groupby(["Season", "Round"]):
        fx = sorted(set(zip(s.hm, s.aw)))
        n = pd.Series([c for f in fx for c in f]).value_counts()
        twice = set(n[n > 1].index)
        for h, a in fx:
            if not twice & {h, a} or (sn, rd, h, a) in have:
                continue
            hit = (cv.Season == sn) & (cv.Round == rd) & (hm == h) & (aw == a)
            drop.append((int(sn), int(rd), h, a, int(cv.loc[hit, "Coaches.Votes"].sum())))
            mask |= hit
    return cv[~mask], drop


def _resolve(cv, pl):
    """Rewrite the feed's spelling to the archive's, keyed on season and club."""
    tgt = pl.drop_duplicates(["Season", "P", "club"]).copy()
    tgt["k"] = tgt.P.map(feat.normalise_name)
    cv = cv.copy()
    cv["k"] = cv.P.map(feat.normalise_name)
    cv["A"] = tgt.set_index(["Season", "k", "club"]).P.reindex(
        pd.MultiIndex.from_arrays([cv.Season, cv.k, cv.club])).values

    # Layer 2, surname plus season plus club, accepted only where the surname is
    # unique in that club and season. Two Carrs at Fremantle in 2006 is why the
    # uniqueness test refuses rather than guessing.
    miss = cv.A.isna()
    if miss.any():
        def sur(s):
            return s.str.rsplit(" ", n=1).str[-1].str.lower()
        tgt["s"] = sur(tgt.P)
        u = tgt.groupby(["Season", "s", "club"]).P.agg(["first", "size"])
        u = u[u["size"] == 1]["first"]
        cv.loc[miss, "A"] = u.reindex(pd.MultiIndex.from_arrays(
            [cv.Season[miss], sur(cv.P[miss]), cv.club[miss]])).values
    return cv[cv.A.notna()], int(cv.A.isna().sum())


def build(player, rows):
    cv = pd.concat([pd.read_csv(COACHES_ALL, low_memory=False),
                    pd.read_csv(COACHES_CUR)], ignore_index=True)
    cv, n_dup, n_bad = _clean(cv)
    pl = _played()
    cv, leaked = _drop_leaked_finals(cv, pl)
    cv, n_lost = _resolve(cv, pl)

    games = pl.groupby(["Season", "P", "club"]).size().rename("games")
    feed = cv.groupby("Season").apply(
        lambda d: d.groupby(["Round", "Home.Team", "Away.Team"]).ngroups,
        include_groups=False)
    arc = pl.groupby("Season").gid.nunique()
    cov = pd.DataFrame({"feed": feed, "archive": arc}).dropna()
    complete = sorted(cov[cov.feed == cov.archive].index)

    t = (cv.assign(ten=(cv["Coaches.Votes"] == MAX_PER_GAME).astype(int))
           .groupby(["Season", "A", "club"])
           .agg(cv=("Coaches.Votes", "sum"), tens=("ten", "sum"))
           .join(games.rename_axis(["Season", "A", "club"]), how="left")
           .reset_index().rename(columns={"A": "name"}))
    t = t[t.games.notna()]
    t["games"] = t.games.astype(int)

    q = t[(t.games >= MIN_GAMES) & t.Season.isin(complete)].sort_values(
        "cv", ascending=False).reset_index(drop=True)
    q["rank"] = q.cv.rank(ascending=False, method="min").astype(int)
    hit = q[q.name == player]
    if hit.empty:
        raise SystemExit(f"{player} has no {MIN_GAMES}+ game season in a "
                         f"complete-feed season")
    me = hit.sort_values("cv", ascending=False).iloc[0]

    # Worst case each excluded season could hold: counted total plus ten for
    # every game of his own the feed lacks.
    ceil = []
    for s in sorted(set(t.Season) - set(complete)):
        sub = t[(t.Season == s) & (t.games >= MIN_GAMES)].copy()
        cg = cv[cv.Season == s].groupby("club").apply(
            lambda d: d.groupby(["Round", "Home.Team", "Away.Team"]).ngroups,
            include_groups=False)
        sub["ceil"] = sub.cv + MAX_PER_GAME * (sub.games - sub.club.map(cg)).clip(lower=0)
        b = sub.sort_values("ceil", ascending=False).iloc[0]
        ceil.append((int(s), b["name"], float(b.cv), float(b.ceil)))

    return {"rows": q.head(rows).to_dict("records"), "me": me.to_dict(),
            "n_qual": len(q), "complete": complete, "excluded": sorted(
                set(t.Season) - set(complete)), "ceilings": ceil,
            "n_dup": n_dup, "n_bad": n_bad, "n_lost": n_lost, "leaked": leaked,
            "y0": int(t.Season.min()), "y1": int(t.Season.max())}


def draw(player, place, b, preview=False):
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = 56 * S, (W - 56) * S

    def text(xy, t, f, fill, anchor="la"):
        k.text(xy, t, font=f, fill=fill, anchor=anchor)

    def fit(t, role, size, width):
        while size > 18 and k.textlength(t, font=font(role, size)) > width:
            size -= 2
        return font(role, size)

    draw_mark(img, m, 44 * S, 29)
    text((right, 44 * S), f"BROWNLOW COUNTDOWN   {ordinal(place).upper()}",
         font("display", 29), MUTED, anchor="ra")
    k.rectangle([m, 100 * S, right, 101 * S], fill=LINE)

    text((m, 128 * S), "MOST COACHES VOTES",
         fit("MOST COACHES VOTES", "name", 72, right - m), INK)
    text((m, 214 * S), "IN A SEASON",
         fit("IN A SEASON", "name", 72, right - m), INK)
    sub = f"AFLCA AWARD   {b['y0']} TO {b['y1']}   HOME AND AWAY"
    text((m, 310 * S), sub, fit(sub, "display", 29, right - m), RANK_INK)
    sub2 = f"MAXIMUM 10 A GAME   {MIN_GAMES} GAMES OR MORE"
    text((m, 350 * S), sub2, fit(sub2, "display", 29, right - m), MUTED)
    k.rectangle([m, 398 * S, right, 399 * S], fill=LINE)

    # Row geometry: the gap BETWEEN rows must beat the gaps inside one, and the
    # figure is set level with its own name so it can never read as the next
    # player's. See bog_share_card for the version of this that was wrong.
    rows = b["rows"]
    top, bot = 438 * S, 1252 * S
    rh = (bot - top) // max(len(rows), 1)
    bx0, bx1 = m + 62 * S, right - 150 * S
    span = bx1 - bx0
    scale = max(r["cv"] for r in rows)

    for ri, r in enumerate(rows):
        y = top + ri * rh
        if ri:
            k.rectangle([m, y - 22 * S, right, y - 21 * S], fill=LINE)
        me = r["name"] == player and r["Season"] == b["me"]["Season"]
        ink = EMERALD if me else INK
        text((m, y + 2 * S), str(r["rank"]), font("display", 38),
             EMERALD if me else RANK_INK)
        text((bx0, y - 4 * S), r["name"].upper(),
             fit(r["name"].upper(), "name", 44, span), ink)
        text((right, y - 12 * S), f"{r['cv']:.0f}", font("fig", 52), ink,
             anchor="ra")
        line = f"{int(r['Season'])}      {r['games']} GAMES"
        text((bx0, y + 46 * S), line, fit(line, "display", 25, span), MUTED)
        by = y + 82 * S
        k.rectangle([bx0, by, bx1, by + 18 * S], fill=BAR)
        k.rectangle([bx0, by, bx0 + int(span * r["cv"] / scale), by + 18 * S],
                    fill=EMERALD if me else RANK_INK)

    k.rectangle([m, 1292 * S, right, 1293 * S], fill=LINE)
    me, half = b["me"], m + (right - m) // 2
    poss = MAX_PER_GAME * me["games"]
    second = next((r for r in b["rows"] if r["rank"] > me["rank"]), None)
    pairs = [
        (m, f"{100 * me['cv'] / poss:.0f}%", EMERALD,
         "OF EVERY VOTE AVAILABLE", f"{me['cv']:.0f} OF A POSSIBLE {poss}"),
    ]
    if second:
        pairs.append((half, f"+{me['cv'] - second['cv']:.0f}", INK,
                      "ON THE OLD RECORD",
                      f"{second['name'].upper()} {int(second['Season'])}"))
    for x, big, col, lab, s2 in pairs:
        text((x, 1320 * S), big, font("fig", 88), col)
        text((x, 1418 * S), lab, font("display", 27), INK)
        text((x, 1454 * S), s2, fit(s2, "display", 25, half - m - 20 * S), MUTED)

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", player.lower()).strip("_")
    path = os.path.join(OUT_DIR, f"countdown_{place:02d}_{slug}_coaches_season.png")
    long_edge = max(W, H) * S
    if long_edge > 2048:
        img = img.resize((int(W * S * 2048 / long_edge), 2048), Image.LANCZOS)
    img.save(path, "PNG", optimize=True)
    prev = None
    if preview:
        prev = path.replace(".png", "_timeline.png")
        img.resize((350, int(350 * img.height / img.width)),
                   Image.LANCZOS).save(prev, "PNG")
    return path, prev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("player")
    ap.add_argument("place", type=int)
    ap.add_argument("--rows", type=int, default=6, help="ladder rows (default 6)")
    ap.add_argument("--font", default="twcen", help=", ".join(FONT_SETS))
    ap.add_argument("--preview", action="store_true",
                    help="also write the 350px version Twitter shows on a phone")
    a = ap.parse_args()
    set_fonts(a.font)
    b = build(a.player, a.rows)
    path, prev = draw(a.player, a.place, b, a.preview)
    me = b["me"]
    print(f"OK  wrote {path}")
    if prev:
        print(f"    timeline preview: {prev}")
    print(f"    repair: {b['n_dup']} repeated game blocks dropped, "
          f"{b['n_bad']} games failing the {VOTES_PER_GAME} test, "
          f"{b['n_lost']} rows unmatched to the archive")
    print(f"    finals filed under a home-and-away round: {len(b['leaked'])}")
    for sn, rd, home, away, v in b["leaked"]:
        print(f"      {sn} r{rd:<2} {home} v {away}  ({v} votes)")
    print(f"    ranked on {len(b['complete'])} complete-feed seasons, "
          f"{b['n_qual']:,} player-seasons of {MIN_GAMES}+ games")
    print(f"    excluded (feed short of the fixture list): "
          + ", ".join(str(s) for s in b["excluded"]))
    print(f"    {a.player} {int(me['Season'])}: {me['cv']:.0f} votes from "
          f"{me['games']} games ({me['cv'] / me['games']:.2f} a game), "
          f"{me['tens']} perfect 10s, rank {ordinal(me['rank'])}")
    for r in b["rows"]:
        mark = "  <<" if r is not None and r["name"] == a.player and \
            r["Season"] == me["Season"] else ""
        print(f"      {r['rank']:2d} {int(r['Season'])}  {r['name']:22} "
              f"{r['cv']:5.0f}  {r['games']:2d}g  {r['tens']} tens{mark}")
    worst = max(b["ceilings"], key=lambda c: c[3]) if b["ceilings"] else None
    if worst:
        print(f"    worst case in an excluded season: {worst[1]} {worst[0]} "
              f"counted {worst[2]:.0f}, ceiling {worst[3]:.0f}")
        if worst[3] > me["cv"]:
            print("    WARNING an excluded season could exceed the drawn "
                  "leader. The claim is not safe as stated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
