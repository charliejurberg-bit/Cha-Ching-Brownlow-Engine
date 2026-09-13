"""All-time career Brownlow vote ladder, with 2026 projected on every bar.

    python scripts/career_votes_card.py "Lachie Neale" 7
    python scripts/career_votes_card.py "Lachie Neale" 7 --above 4 --preview

Writes a PNG to drafts/ (gitignored). Portrait 1200x1500 at S=2, downsampled
once to Twitter's 2048 long edge, same as the other countdown cards. Fonts,
colours and the CHA CHING mark are imported from countdown_card rather than
restated. No footer text, by standing rule: the window and the legend are in
the header, where they are set at a size that survives a timeline.

WHY THIS IS A SEPARATE CARD FROM club_votes_card.py
That one is scoped to a club and cannot reach past 1984, because the file that
goes back to 1924 carries season totals with no club attribution. This ladder
needs no club attribution, so the whole vote record is available and the claim
is the strongest one a countdown can make about a player: where he sits on the
list of everyone who has ever polled.

THE LADDER IS vote_milestones.career_table(), IMPORTED RATHER THAN REBUILT
That module already solves the seam. Per-game votes exist from 1984; before it
only season totals, keyed on a name with no fitzRoy ID. So a pre-1984 total is
attached to a modern career only where exactly ONE career carries the name and
reaches the boundary, which is what keeps Gary Ablett senior's votes off Gary
Ablett junior's total. Rebuilding that here would be a second implementation of
a join that has already been got right once.

EVERY ACTIVE PLAYER GETS A GHOST, NOT JUST THE SUBJECT
The settled figure is votes to the end of 2025, and the marked player is not
the only one still adding to it: Dangerfield and Pendlebury both played 2026
and both sit inside Neale's top five. Drawing a projection on his bar alone
would show him closing a gap that is also moving, so every row carries its own
2026 expectation. Theirs are small (2.6 and 4.0 against his 21.8) and that is
the point: the card shows the one man moving rather than asserting it.

Only the subject's ghost is labelled with a figure. The others end well inside
the figure column and a number there would collide with the settled total
beside it; the header legend says what an outline means, and the exact figures
print on stdout for the copy.

THE DASHED LINE MARKS THE RUNG THE PROJECTION LANDS ON
club_votes_card drops its line from the NEAREST rung above, which is right for
a player whose projection clears one place. This one drops from the HIGHEST bar
the projection clears, because that is the rung the claim rests on: Neale needs
3 votes to pass Sam Mitchell and 22 to pass Gary Dempsey, and only the second
is worth a card. If the projection clears nothing the line falls back to the
nearest rung above, so the card still shows what he is chasing.

WHAT THE LADDER MIXES, AND WHY IT IS STILL ONE LADDER
Votes were a single vote a game from 1924 to 1930 and 3-2-1 from 1931, and a
season has run anywhere from 16 to 23 games. A career total therefore rewards
the modern era, and no card can subtract that. It is a real ladder of a real
quantity and the copy has to carry the era caveat rather than the graphic.
"""

import argparse
import os
import re
import sys

import pandas as pd
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import vote_milestones as vm  # noqa: E402  the career table and its 1984 seam
from countdown_card import (  # noqa: E402
    BG, INK, MUTED, RANK_INK, EMERALD, LINE,
    W, H, S, draw_mark, font, ordinal, set_fonts, FONT_SETS,
)
from club_votes_card import BAR, GHOST, GHOST_INK  # noqa: E402

OUT_DIR = "drafts"
SEASON_2026 = "predictions/season_2026.csv"
STATS_CUR = "data_2026/afltables_2026.csv"
PROJ_SEASON = 2026
VOTES_FROM = 1924          # the first Brownlow
# A ghost on a settled bar. Slate rather than the emerald GHOST, because one
# accent is the rule and the accent belongs to the subject.
BAR_GHOST = "#243240"


def career_spans():
    """True first and last season played, by fitzRoy ID, from the stats files.

    NOT the first and last season a player POLLED. The vote table knows only
    the seasons a player appears in the vote record, so reading a span off it
    would print 1968-1984 for Gary Dempsey (who debuted in 1967) and 1984-1984
    for the same man on the pre-1984 side of the seam. The stats archives reach
    1965, which covers every player this card can draw except one who finished
    before then; those fall back to their polled seasons and the caller says so.
    """
    cols = ["Season", "ID"]
    frames = [pd.read_csv(p, low_memory=False, usecols=cols)
              for p in (vm.OLD, vm.NEW, STATS_CUR)]
    s = pd.concat(frames, ignore_index=True)
    s["Season"] = pd.to_numeric(s["Season"], errors="coerce")
    s = s[s["ID"].notna() & s["Season"].notna()]
    g = s.groupby("ID")["Season"].agg(["min", "max"])
    return {int(i): (int(r["min"]), int(r["max"])) for i, r in g.iterrows()}


def expected_2026():
    """Player name -> (expected votes, games) for the current season."""
    s = pd.read_csv(SEASON_2026)
    s["_bare"] = s["Player_Name"].map(
        lambda v: re.sub(r"\s*\([^)]*\)\s*$", "", str(v)).strip())
    return {r["_bare"]: (float(r["Exp_Total_Votes"]), int(r["Games"]))
            for _, r in s.iterrows()}


def build(player, n_above=4):
    a = vm.modern()
    car, ambiguous = vm.career_table(a)
    car["rank"] = car["votes"].rank(method="min", ascending=False).astype(int)

    me = car[car["name"] == player]
    if me.empty:
        raise SystemExit(f"{player!r} has no career votes in the archive")
    if len(me) > 1:
        me = me[me["last"] >= 2020]
        if len(me) != 1:
            raise SystemExit(f"{player!r} is ambiguous across {len(me)} careers")
    me = me.iloc[0]
    career = float(me["votes"])

    spans, exp26 = career_spans(), expected_2026()
    exp, games26 = exp26.get(player, (0.0, 0))
    proj = career + exp

    def row(r, mine=False):
        pid = int(r["ID"])
        e, _g = exp26.get(r["name"], (0.0, 0))
        span = spans.get(pid)
        if span is None:                       # finished before 1965
            span = (int(r["first"]), int(r["last"]))
        return dict(rank=int(r["rank"]), name=r["name"], votes=float(r["votes"]),
                    exp=e, proj=float(r["votes"]) + e, span=span, me=mine,
                    span_is_polled=spans.get(pid) is None)

    # The nearest players ABOVE him, then him, then anyone level with him. A
    # ladder card that shows four names above a man on 225 and omits the other
    # man on 225 has not lied about his rank, but it has let the reader infer
    # he holds the place alone.
    above = (car[car["votes"] > career]
             .nsmallest(n_above, "votes")
             .sort_values("votes", ascending=False))
    tied = car[(car["votes"] == career) & (car["ID"] != me["ID"])]
    rows = ([row(r) for _, r in above.iterrows()] + [row(me, mine=True)]
            + [row(r) for _, r in tied.iterrows()])

    # The rung the projection lands on, which is the one the claim rests on.
    crossed = [r for r in rows if not r["me"] and career < r["votes"] < proj]
    if crossed:
        target = max(crossed, key=lambda r: r["votes"])
    else:
        ahead = [r for r in rows if not r["me"] and r["votes"] > career]
        target = min(ahead, key=lambda r: r["votes"]) if ahead else None

    new_rank = int((car["votes"] > proj).sum()) + 1
    return dict(rows=rows, career=career, exp=exp, proj=proj, games26=games26,
                cur_rank=int(me["rank"]), new_rank=new_rank, target=target,
                n=len(car), ambiguous=ambiguous,
                board_rank=int((pd.read_csv(SEASON_2026)["Exp_Total_Votes"]
                                > exp).sum()) + 1)


def draw(player, place, b, preview=False):
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

    head = "MOST BROWNLOW VOTES"
    text((m, 130 * S), head, fit(head, "name", 80, right - m), INK)
    text((m, 234 * S), f"EVERY PLAYER, {VOTES_FROM} TO {PROJ_SEASON - 1}",
         font("display", 30), MUTED)
    legend = f"OUTLINE: {PROJ_SEASON} PROJECTED, NOT AWARDED"
    text((m, 276 * S), legend, fit(legend, "display", 30, right - m), RANK_INK)
    k.rectangle([m, 330 * S, right, 331 * S], fill=LINE)

    # -- the ladder ------------------------------------------------
    rows = b["rows"]
    top, bot = 376 * S, 1436 * S
    rh = (bot - top) // len(rows)
    bx0 = m + 62 * S                      # bars start clear of the rank numeral
    bx1 = right - 150 * S                 # and stop clear of the figure
    span = bx1 - bx0
    scale = max(max(r["proj"] for r in rows), b["proj"])
    bh = 30 * S

    def bar_end(v):
        return bx0 + int(span * v / scale)

    chase = None
    for ri, r in enumerate(rows):
        y = top + ri * rh
        if ri:
            k.rectangle([m, y - 22 * S, right, y - 21 * S], fill=LINE)
        me = r["me"]
        ink = EMERALD if me else INK
        text((m, y + 2 * S), str(r["rank"]), font("display", 40),
             EMERALD if me else RANK_INK)
        text((bx0, y), r["name"].upper(),
             fit(r["name"].upper(), "name", 46, span), ink)
        text((bx0, y + 54 * S), f"{r['span'][0]}-{r['span'][1]}",
             font("display", 25), MUTED)

        by = y + 96 * S
        solid, ghost = bar_end(r["votes"]), bar_end(r["proj"])
        if me:
            # The ghost gets an emerald outline, not just a darker fill. At the
            # 0.29 scale Twitter serves, a fill-only extension is a few pixels
            # of slightly-different dark green and the reader never sees the
            # thing the card exists to show.
            k.rectangle([bx0, by, ghost, by + bh], fill=GHOST,
                        outline=EMERALD, width=2 * S)
            k.rectangle([bx0, by, solid, by + bh], fill=EMERALD)
            # The projected total is the card's point and has to survive the
            # timeline downscale, so it is set only a little under the settled
            # figures rather than as an annotation.
            text((ghost + 16 * S, by - 8 * S), f"{r['proj']:.0f}",
                 font("fig", 44), GHOST_INK)
        else:
            if ghost > solid:
                k.rectangle([bx0, by, ghost, by + bh], fill=BAR_GHOST,
                            outline=BAR, width=2 * S)
            k.rectangle([bx0, by, solid, by + bh], fill=BAR)
        text((right, by - 22 * S), f"{r['votes']:.0f}", font("fig", 52), ink,
             anchor="ra")
        if b["target"] is not None and r is b["target"]:
            chase = (solid, by + bh)

    # The dashed drop from the chased bar's end down through his own bar. It is
    # the whole argument of the card: without it a reader compares two bar
    # lengths several rows apart by eye.
    if chase is not None:
        x, y0 = chase
        mine = next(i for i, r in enumerate(rows) if r["me"])
        y1 = top + mine * rh + 96 * S + bh
        yy = y0
        while yy < y1:
            k.rectangle([x, yy, x + 3 * S, min(yy + 9 * S, y1)], fill=INK)
            yy += 17 * S

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", player.lower()).strip("_")
    path = os.path.join(OUT_DIR, f"careervotes_{place:02d}_{slug}.png")
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
    ap.add_argument("--above", type=int, default=4,
                    help="how many players ahead of him to show (default 4)")
    ap.add_argument("--font", default="twcen", help=", ".join(FONT_SETS))
    ap.add_argument("--preview", action="store_true",
                    help="also write the 350px version Twitter shows on a phone")
    a = ap.parse_args()
    set_fonts(a.font)
    b = build(a.player, a.above)
    path, prev = draw(a.player, a.place, b, a.preview)
    print(f"OK  wrote {path}")
    if prev:
        print(f"    timeline preview: {prev}")
    print(f"    {a.player}: {b['career']:.0f} career votes, "
          f"{ordinal(b['cur_rank'])} of {b['n']} players all time")
    print(f"    + {b['exp']:.1f} expected from {b['games26']} games in "
          f"{PROJ_SEASON} = {b['proj']:.1f}, {ordinal(b['new_rank'])}, "
          f"{ordinal(b['board_rank'])} on the board")
    if b["target"] is not None:
        t = b["target"]
        print(f"    needs {t['votes'] - b['career'] + 1:.0f} to pass "
              f"{t['name']} ({t['votes']:.0f})")
    for r in b["rows"]:
        tail = f" + {r['exp']:.1f} = {r['proj']:.1f}" if r["exp"] else ""
        print(f"    {r['rank']:>2}. {r['name']:<22}{r['votes']:>6.0f}{tail}"
              + ("   <- him" if r["me"] else "")
              + ("   (span is polled seasons only)" if r["span_is_polled"] else ""))
    if b["ambiguous"]:
        print("    pre-1984 names left unmerged (two careers share them): "
              + ", ".join(b["ambiguous"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
