"""Club all-time Brownlow vote ladder, with one player's season projected on.

    python scripts/club_votes_card.py "Zak Butters" 14
    python scripts/club_votes_card.py "Zak Butters" 14 --preview
    python scripts/club_votes_card.py "Jordan Dawson" 8 --rate --floor 50

Writes a PNG to drafts/ (gitignored). Portrait 1200x1500, drawn at S=2 and
downsampled once to Twitter's 2048 long edge, per compare_card.py's note: an
image shipped at 3000px tall is resampled by THEIR resizer at a non-integer
factor and the hairlines come apart on the timeline.

Fonts, colours and the CHA CHING mark are imported from countdown_card rather
than restated, so the countdown reads as one set of cards.

WHAT THE LADDER COUNTS, AND WHY IT IS NARROWER THAN A CAREER TOTAL
Votes polled FOR THIS CLUB, not career votes. They are the same number for a
one-club player and are not for anyone else, and the claim being made is a club
record, so the club is the filter. Boak, Wines, Gray and Butters are all
one-club players, so nothing on the Port card turns on this, but a Fremantle or
a Hawthorn card would.

The archive splits at 2006 and both halves are needed. fitzroy_stats_all.csv
starts at 2007 and Port Adelaide entered the AFL in 1997, so reading only that
file would silently drop a decade and cost Warren Tredrea and Gavin Wanganeen
most of their votes. Every club that predates 2007 has the same exposure.

Brownlow votes are per game from 1984 (see CLAUDE.md, "Brownlow votes before
1984"), which is comfortably before any Port Adelaide season. For an older club
the ladder is capped at 1984 and the footer says so, because the season-total
file that reaches 1924 carries no club attribution and cannot extend it.

--rate: THE SAME VOTES OVER GAMES PLAYED, WHICH IS A DIFFERENT LADDER
Total votes is a longevity ladder as much as a quality one, and a player four
seasons into a club cannot win it. Dawson is 10th at Adelaide on 73 and 1st on
0.81 a game, and the second number is the claim worth posting. --rate draws that
ladder: top by votes per game among players clearing --floor games FOR THE CLUB.

THREE THINGS THE RATE MODE DOES THAT THE TOTAL MODE DOES NOT
1. FINALS ARE DROPPED. Brownlow votes are not awarded in finals, so a finals row
   contributes 0 votes and 1 game and silently deflates a rate. It cannot touch
   a total, which is why the total mode never had to care. Dawson reads 0.793
   over 92 games with finals in and 0.811 over 90 with them out, and the second
   is the figure every other vote table in this repo uses. Rounds are dropped by
   the standard test, a Round label that will not coerce to a number.
2. NO PROJECTION GHOST, AND THAT IS A DECISION RATHER THAN AN OMISSION.
   The total mode's ghost earns its place by crossing rungs. On a rate ladder
   it crosses nothing: Dawson's 0.811 becomes 0.851 with the model's 2026 line
   folded in and he was already 1st, so the ghost is a five-pixel sliver on the
   longest bar whose label lands on top of the figure beside it. It also puts a
   model number on a card whose whole claim is settled history. The season the
   ladder excludes is reported on stdout instead, for the copy to carry.
3. THE FLOOR IS PART OF THE CLAIM AND GOES IN THE HEADER. A rate with no games
   floor is won by whoever played three games and polled once. The floor is
   chosen, so the card states it rather than leaving the reader to assume one.

THE PROJECTION IS AN EXPECTED VALUE AND IS LABELLED AS ONE
The added figure is Exp_Total_Votes from predictions/season_2026.csv, the model
run, not awarded votes. The card prints the projected total, the gap it has to
close, and the word PROJECTED, because a bar that crosses a line looks like a
result whatever the number beside it says.
"""

import argparse
import os
import re
import sys

import pandas as pd
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from countdown_card import (  # noqa: E402
    BG, INK, MUTED, RANK_INK, EMERALD, LINE, PANEL,
    ABBR, W, H, S, draw_mark, font, ordinal, set_fonts, FONT_SETS,
)

OUT_DIR = "drafts"
STATS_HIST = "data_history/fitzroy_stats_1965_2006.csv.gz"
STATS_ALL = "fitzroy_stats_all.csv"
SEASON_2026 = "predictions/season_2026.csv"
VOTES_FROM = 1984          # first season the per-game archive carries votes
PROJ_SEASON = 2026

# The settled bars. Slate rather than INK: four white bars and one emerald reads
# as five accents fighting, and the ladder's job is to make the emerald one
# obvious at 350px wide.
BAR = "#31404e"
# Ghost bar for the projected slice. A fill rather than a hatch: at the 0.29
# scale Twitter shows in a timeline, a diagonal hatch at this bar height turns
# into a smear of noise, and a flat dark emerald still reads as "not solid".
GHOST = "#1d5f4c"
GHOST_INK = "#4ea88a"      # the label for it, lifted enough to survive the downscale


def _name(d):
    return (d["First.name"].astype(str).str.strip() + " "
            + d["Surname"].astype(str).str.strip())


# THE ARCHIVES AND THE PREDICTIONS DISAGREE ON TWO CLUB NAMES, and the failure
# is silent enough to look like a missing player. The club is read from
# predictions/season_2026.csv, which uses the AFL's current names, while both
# stats archives carry Team as the club's older or shorter form. Sixteen of the
# eighteen match on the nose; these two do not, and a Bontempelli card died on
# "no rows for club 'Western Bulldogs'" rather than on anything about him.
# Checked by differencing the two name sets rather than by listing what looked
# wrong: Fitzroy is the only other archive-side name with no 2026 equivalent and
# it is a defunct club, correctly absent.
CLUB_ALIAS = {"Western Bulldogs": "Footscray",
              "Greater Western Sydney": "GWS"}


def _archive_club(club):
    return CLUB_ALIAS.get(club, club)


def club_ladder(club):
    """Every player's Brownlow votes polled for `club`, biggest first."""
    club = _archive_club(club)
    frames = []
    for path in (STATS_HIST, STATS_ALL):
        d = pd.read_csv(path, low_memory=False)
        d = d[(d["Team"] == club) & (d["Season"] >= VOTES_FROM)]
        if not d.empty:
            frames.append(d[["Season", "First.name", "Surname", "Brownlow.Votes"]])
    if not frames:
        raise SystemExit(f"no rows for club {club!r} in the archives")
    d = pd.concat(frames, ignore_index=True)
    d["name"] = _name(d)
    g = (d.groupby("name")
           .agg(votes=("Brownlow.Votes", "sum"),
                first=("Season", "min"), last=("Season", "max"))
           .sort_values("votes", ascending=False)
           .reset_index())
    g["votes"] = g["votes"].astype(int)
    g["rank"] = g["votes"].rank(method="min", ascending=False).astype(int)
    return g, int(d["Season"].min()), int(d["Season"].max())


def _home_and_away(d):
    """Drop finals. A string Round label (QF/EF/SF/PF/GF) will not coerce."""
    return d[pd.to_numeric(d["Round"], errors="coerce").notna()]


def rate_ladder(club, floor):
    """Votes per home-and-away game for `club`, best first, floor applied.

    Games are games FOR THIS CLUB, matching the numerator. A traded player's
    games at his other clubs belong to neither side of this fraction.
    """
    club = _archive_club(club)
    frames = []
    for path in (STATS_HIST, STATS_ALL):
        d = pd.read_csv(path, low_memory=False)
        d = d[(d["Team"] == club) & (d["Season"] >= VOTES_FROM)]
        if not d.empty:
            frames.append(_home_and_away(
                d[["Season", "Round", "First.name", "Surname", "Brownlow.Votes"]]))
    if not frames:
        raise SystemExit(f"no rows for club {club!r} in the archives")
    d = pd.concat(frames, ignore_index=True)
    d["name"] = _name(d)
    g = (d.groupby("name")
           .agg(games=("Brownlow.Votes", "size"),
                polls=("Brownlow.Votes", lambda s: int((s > 0).sum())),
                votes=("Brownlow.Votes", "sum"),
                first=("Season", "min"), last=("Season", "max"))
           .reset_index())
    g["votes"] = g["votes"].astype(int)
    g = g[g["games"] >= floor].copy()
    if g.empty:
        raise SystemExit(f"no {club} player reaches {floor} games")
    g["rate"] = g["votes"] / g["games"]
    g = g.sort_values("rate", ascending=False).reset_index(drop=True)
    g["rank"] = g["rate"].rank(method="min", ascending=False).astype(int)
    return g, int(d["Season"].min()), int(d["Season"].max())


def projection(player):
    """(expected votes, games, club, leaderboard rank) for PROJ_SEASON."""
    s = pd.read_csv(SEASON_2026)
    s["_bare"] = s["Player_Name"].map(
        lambda v: re.sub(r"\s*\([^)]*\)\s*$", "", str(v)).strip())
    hit = s[s["_bare"].str.lower() == player.lower()]
    if hit.empty:
        raise SystemExit(f"{player!r} not in {SEASON_2026}")
    if len(hit) > 1:
        raise SystemExit(f"{player!r} is ambiguous: {list(hit['_bare'])}")
    r = hit.iloc[0]
    rank = int((s["Exp_Total_Votes"] > r["Exp_Total_Votes"]).sum()) + 1
    return float(r["Exp_Total_Votes"]), int(r["Games"]), str(r["Team"]), rank


def build(player, n_above=3):
    exp, games, club, board_rank = projection(player)
    lad, yr0, yr1 = club_ladder(club)
    me = lad[lad["name"].str.lower() == player.lower()]
    if me.empty:
        raise SystemExit(f"{player!r} has no votes recorded for {club}")
    me = me.iloc[0]
    career = int(me["votes"])
    proj = career + exp

    # The NEAREST players above him, not the top of the ladder. For a player
    # sitting 4th the two are the same set, which is why the Port card did not
    # expose the difference. For one sitting 9th they are not: Newcombe's top
    # three are Sam Mitchell, Crawford and Platten, none of whom he goes near,
    # while the men he actually passes are Sewell and Franklin at 5th and 6th
    # nearest. A ladder card exists to show a move, so it has to show the rungs
    # the move crosses.
    above = (lad[lad["votes"] > career]
             .nsmallest(n_above, "votes")
             .sort_values("votes", ascending=False))
    rows = [dict(rank=int(r["rank"]), name=r["name"], votes=int(r["votes"]),
                 span=(int(r["first"]), int(r["last"])), me=False)
            for _, r in above.iterrows()]
    rows.append(dict(rank=int(me["rank"]), name=me["name"], votes=career,
                     span=(int(me["first"]), int(me["last"])), me=True,
                     proj=proj, exp=exp, games=games))

    # A PLAYER ALREADY 1st HAS NO RUNGS ABOVE HIM, and without this the card
    # draws a single row on an otherwise empty page with the settled figure and
    # the projected figure overprinting each other. Bontempelli holds the
    # Bulldogs record by 38 votes and is the case. Show the men BEHIND him
    # instead: the claim is then the size of the lead rather than a move, which
    # is the only claim a record holder's ladder can make. The projection is
    # still drawn because he is still adding to the record.
    if len(rows) == 1:
        below = (lad[lad["votes"] < career]
                 .nlargest(n_above + 2, "votes")
                 .sort_values("votes", ascending=False))
        rows += [dict(rank=int(r["rank"]), name=r["name"], votes=int(r["votes"]),
                      span=(int(r["first"]), int(r["last"])), me=False)
                 for _, r in below.iterrows()]

    # The bar he is chasing: the lowest player still ahead of him. Passing means
    # strictly more, so the gap to a player on V is V - career + 1.
    # Only players genuinely ABOVE him can be chased. Once the fallback above
    # puts men behind him into `rows`, a plain "everyone but me" filter picks
    # the lowest of THOSE and the footer reads "Needs -106 to pass Macrae".
    ahead = [r for r in rows if not r["me"] and r["votes"] > career]
    target = min(ahead, key=lambda r: r["votes"]) if ahead else None
    new_rank = int((lad["votes"] > proj).sum()) + 1
    return dict(club=club, rows=rows, career=career, exp=exp, proj=proj,
                games=games, board_rank=board_rank, new_rank=new_rank,
                cur_rank=int(me["rank"]), target=target, yr0=yr0, yr1=yr1)


def draw(player, place, b, preview=False):
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = 56 * S, (W - 56) * S

    def text(xy, t, f, fill, anchor="la"):
        k.text(xy, t, font=f, fill=fill, anchor=anchor)

    def fit(t, role, size, width):
        """Shrink until it fits. Club names run from ESSENDON to GWS to WESTERN."""
        while size > 20 and k.textlength(t, font=font(role, size)) > width:
            size -= 2
        return font(role, size)

    # -- masthead --------------------------------------------------
    draw_mark(img, m, 44 * S, 29)
    text((right, 44 * S), f"BROWNLOW COUNTDOWN   {ordinal(place).upper()}",
         font("display", 29), MUTED, anchor="ra")
    k.rectangle([m, 100 * S, right, 101 * S], fill=LINE)

    club_t = ABBR.get(b["club"], b["club"].upper())
    text((m, 130 * S), club_t, fit(club_t, "name", 80, right - m), INK)
    # A club that entered the AFL after 1984 has its whole history covered; an
    # older one does not, and saying "club history" there would overclaim by up
    # to eighty seasons. The per-game vote archive is the boundary, not a choice.
    scope = ("MOST BROWNLOW VOTES IN CLUB HISTORY" if b["yr0"] > VOTES_FROM
             else f"MOST BROWNLOW VOTES SINCE {VOTES_FROM}")
    text((m, 234 * S), scope, font("display", 30), MUTED)
    text((m, 276 * S), f"{b['yr0']}-{PROJ_SEASON}", font("display", 30), RANK_INK)
    k.rectangle([m, 330 * S, right, 331 * S], fill=LINE)

    # -- the ladder ------------------------------------------------
    rows = b["rows"]
    top, bot = 372 * S, 1244 * S
    rh = (bot - top) // len(rows)
    bx0 = m + 62 * S                      # bars start clear of the rank numeral
    bx1 = right - 122 * S                 # and stop clear of the figure
    span = bx1 - bx0
    scale = max(max(r["votes"] for r in rows), b["proj"])
    bh = 34 * S

    def bar_end(v):
        return bx0 + int(span * v / scale)

    chase_x = None
    for ri, r in enumerate(rows):
        y = top + ri * rh
        if ri:
            k.rectangle([m, y - 22 * S, right, y - 21 * S], fill=LINE)
        me = r["me"]
        text((m, y + 4 * S), str(r["rank"]), font("display", 44),
             EMERALD if me else RANK_INK)
        text((bx0, y), r["name"].upper(), font("name", 46),
             EMERALD if me else INK)
        text((bx0, y + 56 * S), f"{r['span'][0]}-{r['span'][1]}",
             font("display", 25), MUTED)

        by = y + 102 * S
        if me:
            # The ghost gets an emerald outline, not just a darker fill. At the
            # 0.29 scale Twitter serves, a fill-only extension of 17 votes is
            # about five pixels of slightly-different dark green and the reader
            # never sees the thing the card exists to show.
            solid, ghost = bar_end(r["votes"]), bar_end(r["proj"])
            k.rectangle([bx0, by, ghost, by + bh], fill=GHOST,
                        outline=EMERALD, width=2 * S)
            k.rectangle([bx0, by, solid, by + bh], fill=EMERALD)
            text((right, by - 6 * S), f"{r['votes']}", font("fig", 52),
                 EMERALD, anchor="ra")
            # The projected figure sits at the END of the ghost, so the eye runs
            # bar-then-number the same way it does on every settled row. That
            # only works while the ghost stops short of the figure column: a
            # LEADER sets the bar scale himself, so his ghost runs to the right
            # edge and the projection overprints his settled total. Bontempelli
            # read "2139.1". When there is no room, the projection moves under
            # the bar and shares the label line instead.
            # There is only room for the projection when the ghost stops short
            # of the figure column, and a LEADER sets the bar scale himself, so
            # his ghost runs to the right edge: Bontempelli's read "2139.1"
            # overprinted. Moving it under the bar does not help either, because
            # the row pitch puts that line on top of the next player's name.
            # Both labels are therefore dropped for a leader. Nothing is lost:
            # the ghost still draws the extension and the footer still states
            # the expected votes in words.
            proj_t = f"{b['proj']:.0f}"
            if ghost + 18 * S + k.textlength(proj_t, font=font("fig", 40)) < right - 90 * S:
                text((ghost + 18 * S, by - 2 * S), proj_t, font("fig", 40), EMERALD)
                text((bx0, by + bh + 14 * S), f"PROJECTED AFTER {PROJ_SEASON}",
                     font("display", 27), GHOST_INK)
        else:
            k.rectangle([bx0, by, bar_end(r["votes"]), by + bh], fill=BAR)
            text((right, by - 6 * S), f"{r['votes']}", font("fig", 52),
                 INK, anchor="ra")
        if b["target"] is not None and r is b["target"]:
            chase_x = (bar_end(r["votes"]), by + bh)

    # The dashed drop from the chased bar's end down through the player's bar.
    # It is the whole argument of the card: without it a reader has to compare
    # two bar lengths three rows apart by eye.
    if chase_x is not None:
        x, y0 = chase_x
        y1 = top + (len(rows) - 1) * rh + 102 * S + bh
        yy = y0
        while yy < y1:
            k.rectangle([x, yy, x + 3 * S, min(yy + 9 * S, y1)], fill=INK)
            yy += 17 * S

    # -- footer ----------------------------------------------------
    k.rectangle([m, 1290 * S, right, 1291 * S], fill=LINE)
    tgt = b["target"]
    lines = [(f"{b['games']} games in {PROJ_SEASON}, {b['exp']:.1f} expected "
              f"votes, {ordinal(b['board_rank'])} on the leaderboard.", INK)]
    if tgt:
        # THE NEAREST RUNG AND THE LANDING SPOT ARE DIFFERENT FACTS. Clearing
        # the man immediately above you moves you exactly one place; the
        # projection may clear several. Newcombe needs 3 to pass Sewell, which
        # is 8th, while his projected 88 also clears Franklin and lands 7th.
        # Welding the two into one sentence stated a rank he does not reach on
        # the vote count named beside it.
        need = tgt["votes"] - b["career"] + 1
        gap = (f"Needs {need} to pass {tgt['name'].split()[-1]} "
               f"({tgt['votes']}).")
        passed = [r for r in b["rows"]
                  if not r["me"] and b["career"] < r["votes"] < b["proj"]]
        if len(passed) <= 1:
            lines.append((f"{gap[:-1]} into {ordinal(b['new_rank'])}.", INK))
        else:
            top = max(passed, key=lambda r: r["votes"])
            lines.append((f"{gap} The projection clears "
                          f"{top['name'].split()[-1]} ({top['votes']}) too, "
                          f"into {ordinal(b['new_rank'])}.", INK))
    lines.append(("Votes polled for this club only. Projection is the model's "
                  "expected total, not awarded votes.", MUTED))
    for i, (t, fill) in enumerate(lines):
        text((m, (1326 + i * 40) * S), t, font("body", 26), fill)

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", player.lower()).strip("_")
    path = os.path.join(OUT_DIR, f"clubvotes_{place:02d}_{slug}.png")
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


def build_rate(player, floor, rows):
    """The rate ladder plus the marked player, and optionally his 2026 line."""
    exp, games26, club, board_rank = projection(player)
    lad, yr0, yr1 = rate_ladder(club, floor)
    me = lad[lad["name"].str.lower() == player.lower()]
    if me.empty:
        raise SystemExit(
            f"{player!r} has no {floor}+ game home-and-away record for {club}. "
            f"Lower --floor or check the spelling.")
    me = me.iloc[0]

    # The top `rows`, and him, whether or not he is in them. A rate card for a
    # player sitting 5th is a legitimate card; one that quietly omits its own
    # subject is not.
    shown = lad.head(rows).copy()
    if player.lower() not in set(shown["name"].str.lower()):
        shown = pd.concat([shown.head(rows - 1), me.to_frame().T],
                          ignore_index=True)
    out = [dict(rank=int(r["rank"]), name=r["name"], rate=float(r["rate"]),
                votes=int(r["votes"]), games=int(r["games"]),
                span=(int(r["first"]), int(r["last"])),
                me=r["name"].lower() == player.lower())
           for _, r in shown.iterrows()]

    return dict(club=club, rows=out, floor=floor, yr0=yr0, yr1=yr1,
                rate=float(me["rate"]), votes=int(me["votes"]),
                games=int(me["games"]), polls=int(me["polls"]),
                cur_rank=int(me["rank"]), n=len(lad), exp=exp,
                games26=games26, board_rank=board_rank)


def draw_rate(player, place, b, preview=False):
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = 56 * S, (W - 56) * S

    def text(xy, t, f, fill, anchor="la"):
        k.text(xy, t, font=f, fill=fill, anchor=anchor)

    def fit(t, role, size, width):
        while size > 20 and k.textlength(t, font=font(role, size)) > width:
            size -= 2
        return font(role, size)

    # -- masthead --------------------------------------------------
    draw_mark(img, m, 44 * S, 29)
    text((right, 44 * S), f"BROWNLOW COUNTDOWN   {ordinal(place).upper()}",
         font("display", 29), MUTED, anchor="ra")
    k.rectangle([m, 100 * S, right, 101 * S], fill=LINE)

    club_t = ABBR.get(b["club"], b["club"].upper())
    text((m, 130 * S), club_t, fit(club_t, "name", 80, right - m), INK)
    scope = ("HIGHEST BROWNLOW VOTE RATE IN CLUB HISTORY"
             if b["yr0"] > VOTES_FROM
             else f"HIGHEST BROWNLOW VOTE RATE SINCE {VOTES_FROM}")
    text((m, 234 * S), scope, fit(scope, "display", 30, right - m), MUTED)
    # Window and floor, in the header at a readable size, because there is no
    # footer to put them in and both are part of the claim.
    text((m, 276 * S),
         f"{b['yr0']}-{b['yr1']}   {b['floor']} GAMES OR MORE   HOME AND AWAY",
         font("display", 30), RANK_INK)
    k.rectangle([m, 330 * S, right, 331 * S], fill=LINE)

    # -- the ladder ------------------------------------------------
    rows = b["rows"]
    top, bot = 376 * S, 1436 * S
    rh = (bot - top) // len(rows)
    bx0 = m + 62 * S
    bx1 = right - 150 * S
    span = bx1 - bx0
    scale = max(r["rate"] for r in rows)
    bh = 30 * S

    def bar_end(v):
        return bx0 + int(span * v / scale)

    for ri, r in enumerate(rows):
        y = top + ri * rh
        if ri:
            k.rectangle([m, y - 22 * S, right, y - 21 * S], fill=LINE)
        me = r["me"]
        if me:
            k.rectangle([m - 14 * S, y - 16 * S, right + 14 * S,
                         y + rh - 40 * S], fill=PANEL)
            k.rectangle([m - 14 * S, y - 16 * S, m - 10 * S,
                         y + rh - 40 * S], fill=EMERALD)
        ink = EMERALD if me else INK
        text((m, y + 2 * S), str(r["rank"]), font("display", 40),
             EMERALD if me else RANK_INK)
        text((bx0, y), r["name"].upper(),
             fit(r["name"].upper(), "name", 44, span), ink)
        # Votes from games under the name. It is the fraction the bar draws, and
        # a rate with its own numerator and denominator beside it cannot be
        # read as anything else.
        text((bx0, y + 52 * S),
             f"{r['span'][0]}-{r['span'][1]}   "
             f"{r['votes']} VOTES FROM {r['games']} GAMES",
             font("display", 24), MUTED)

        by = y + 94 * S
        k.rectangle([bx0, by, bar_end(r["rate"]), by + bh],
                    fill=EMERALD if me else BAR)
        text((right, by - 22 * S), f"{r['rate']:.2f}", font("fig", 52), ink,
             anchor="ra")

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", player.lower()).strip("_")
    path = os.path.join(OUT_DIR, f"clubrate_{place:02d}_{slug}.png")
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


def rate_main(a):
    b = build_rate(a.player, a.floor, a.rows)
    path, prev = draw_rate(a.player, a.place, b, a.preview)
    print(f"OK  wrote {path}")
    if prev:
        print(f"    timeline preview: {prev}")
    print(f"    {b['club']} {b['yr0']}-{b['yr1']}, {b['floor']}+ games, "
          f"home and away: {b['n']} players qualify")
    print(f"    {a.player}: {b['votes']} votes from {b['games']} games, "
          f"{b['polls']} polls, {b['rate']:.3f} a game, "
          f"{ordinal(b['cur_rank'])}")
    print(f"    {PROJ_SEASON} is NOT in the ladder: {b['exp']:.1f} expected "
          f"votes from {b['games26']} games, {ordinal(b['board_rank'])} on the "
          f"board. Copy must say 'through {b['games']} games'.")
    for r in b["rows"]:
        print(f"    {r['rank']:>2}. {r['name']:<22} {r['rate']:.3f}  "
              f"({r['votes']}/{r['games']})" + ("   <- him" if r["me"] else ""))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("player")
    ap.add_argument("place", type=int)
    ap.add_argument("--above", type=int, default=3,
                    help="how many players ahead of him to show (default 3)")
    ap.add_argument("--rate", action="store_true",
                    help="votes per game rather than total votes")
    ap.add_argument("--floor", type=int, default=50,
                    help="rate mode: minimum games for the club (default 50)")
    ap.add_argument("--rows", type=int, default=6,
                    help="rate mode: how many of the ladder to draw")
    ap.add_argument("--font", default="twcen", help=", ".join(FONT_SETS))
    ap.add_argument("--preview", action="store_true",
                    help="also write the 350px version Twitter shows on a phone")
    a = ap.parse_args()
    set_fonts(a.font)
    if a.rate:
        return rate_main(a)
    b = build(a.player, a.above)
    path, prev = draw(a.player, a.place, b, a.preview)
    print(f"OK  wrote {path}")
    if prev:
        print(f"    timeline preview: {prev}")
    print(f"    {b['club']}: career {b['career']} + {b['exp']:.1f} = "
          f"{b['proj']:.1f}, {ordinal(b['cur_rank'])} -> {ordinal(b['new_rank'])}")
    for r in b["rows"]:
        print(f"    {r['rank']:>2}. {r['name']:<20} {r['votes']:>4}"
              + ("   <- him" if r["me"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
