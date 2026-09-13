"""Leaderboard card for a stat inside a QUALIFIED pool, one row per player.

    python scripts/pool_leader_card.py "Kysaiah Pickett" 12
    python scripts/pool_leader_card.py "Kysaiah Pickett" 12 --stat xScore \
        --pool-stat CentreBounceAttendancePercentage --pool-min 60 --preview

Writes a PNG to drafts/ (gitignored). Portrait 1200x1500 at S=2, downsampled
once to Twitter's 2048 long edge, same as the other countdown cards.

THE QUALIFICATION IS ON THE CARD, IN THE HEADER, NOT IN A FOOTNOTE
This card exists to make a claim of the form "nobody in group X did more of Y",
and every such claim lives or dies on how X was drawn. Pickett leads expected
score among midfielders at a 60% centre-bounce cut and is SECOND at 55%, because
Chad Warner sits at 58.9% and drops out of the pool. That is not a reason to
avoid the claim, it is a reason to print the cut where the reader sees it before
the number: a stated threshold is ordinary practice, an unstated one is the
thing that gets a graphic taken apart. The subtitle carries the pool rule and
the qualified count, and the CBA column shows every listed player's own figure
so a reader can see who was near the line.

For the same reason the card never says "in the AFL". It says what the pool is.

PER GAME IS NOT THE SAME RANKING AND THE CARD SAYS SO
The bars are season totals, which reward availability: Pickett played 23 games
to Heeney's 20 and leads on total while trailing 8.49 to 8.62 per game. The
per-game figure is printed beside every bar rather than hidden, so the card
cannot be read as a claim about rate.
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
    BG, INK, MUTED, RANK_INK, EMERALD, LINE,
    W, H, S, draw_mark, font, ordinal, set_fonts, FONT_SETS, MIN_GAMES,
)

OUT_DIR = "drafts"
WHEELO = "data_wheelo/wheelo_2026.csv"
SEASON = 2026
BAR = "#31404e"

# Labels for the columns this card knows how to draw. A stat not listed here
# still works; it just gets its raw column name as the heading.
LABELS = {
    "xScore": ("EXPECTED SCORE", "EXPECTED SCORE FROM HIS OWN SHOTS AT GOAL"),
    "Goals": ("GOALS", "GOALS"),
    "GoalAssists": ("GOAL ASSISTS", "GOAL ASSISTS"),
    "ScoreInvolvements": ("SCORE INVOLVEMENTS", "SCORE INVOLVEMENTS"),
    "MetresGained": ("METRES GAINED", "METRES GAINED"),
    "Inside50s": ("INSIDE 50s", "INSIDE 50s"),
}
POOL_LABELS = {
    "CentreBounceAttendancePercentage": ("CBA%", "CENTRE BOUNCE ATTENDANCE"),
}


def gather(player, stat, pool_stat, pool_min, top):
    w = pd.read_csv(WHEELO, low_memory=False)
    n = w.groupby("Player").size()
    w = w[w["Player"].isin(n[n >= MIN_GAMES].index)]
    g = w.groupby("Player")
    games = g.size()
    # The pool metric is a per-game percentage, so it is a mean. Checked against
    # a bounce-weighted denominator (a match holds goals + 4 centre bounces) for
    # Pickett's 2026: 74.96 as a mean, 74.82 weighted. 0.14 of a point.
    poolval = g[pool_stat].mean()
    pool = poolval[poolval >= pool_min].index
    if player not in pool:
        raise SystemExit(
            f"{player!r} is not in the pool: {pool_stat} = "
            f"{poolval.get(player, float('nan')):.1f}, cut is {pool_min}")
    tot = g[stat].sum().loc[pool].sort_values(ascending=False)
    rows = [dict(name=nm, val=float(v), per=float(v) / int(games[nm]),
                 games=int(games[nm]), pool=float(poolval[nm]),
                 me=(nm == player))
            for nm, v in tot.head(top).items()]
    if not any(r["me"] for r in rows):
        r = int((tot > tot[player]).sum()) + 1
        rows[-1] = dict(name=player, val=float(tot[player]),
                        per=float(tot[player]) / int(games[player]),
                        games=int(games[player]), pool=float(poolval[player]),
                        me=True, rank=r)
    per = (g[stat].sum() / games).loc[pool]
    return dict(rows=rows, n_pool=len(pool),
                rank=int((tot > tot[player]).sum()) + 1,
                per_rank=int((per > per[player]).sum()) + 1,
                per_leader=per.idxmax())


def draw(player, place, stat, pool_stat, pool_min, b, preview=False):
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = 56 * S, (W - 56) * S
    col_head, sub_head = LABELS.get(stat, (stat.upper(), stat.upper()))
    pool_head, pool_full = POOL_LABELS.get(
        pool_stat, (pool_stat[:6].upper(), pool_stat.upper()))

    def text(xy, t, f, fill, anchor="la"):
        k.text(xy, t, font=f, fill=fill, anchor=anchor)

    def fit(t, role, size, width):
        while size > 18 and k.textlength(t, font=font(role, size)) > width:
            size -= 2
        return font(role, size)

    # -- masthead --------------------------------------------------
    draw_mark(img, m, 44 * S, 29)
    text((right, 44 * S), f"BROWNLOW COUNTDOWN   {ordinal(place).upper()}",
         font("display", 29), MUTED, anchor="ra")
    k.rectangle([m, 100 * S, right, 101 * S], fill=LINE)

    text((m, 130 * S), player.upper(),
         fit(player.upper(), "name", 76, right - m), INK)
    text((m, 232 * S), sub_head, font("display", 30), MUTED)
    # The pool rule, above the numbers rather than under them. See the docstring.
    text((m, 276 * S),
         f"{pool_full} {pool_min}%+   {MIN_GAMES}+ GAMES   "
         f"{b['n_pool']} QUALIFIED",
         font("display", 26), RANK_INK)
    k.rectangle([m, 330 * S, right, 331 * S], fill=LINE)

    # -- column heads ----------------------------------------------
    x_val, x_pool = right - 132 * S, right
    text((x_val, 356 * S), col_head.split()[0] if len(col_head) > 12 else col_head,
         font("display", 23), MUTED, anchor="ra")
    text((x_pool, 356 * S), pool_head, font("display", 23), MUTED, anchor="ra")

    rows = b["rows"]
    top, bot = 404 * S, 1226 * S
    rh = (bot - top) // len(rows)
    bx0 = m + 52 * S
    bx1 = right - 296 * S
    span = bx1 - bx0
    scale = max(r["val"] for r in rows)
    bh = 26 * S

    for i, r in enumerate(rows):
        y = top + i * rh
        me = r["me"]
        rk = r.get("rank", i + 1)
        text((m, y + 2 * S), str(rk), font("display", 36),
             EMERALD if me else RANK_INK)
        nm = fit(r["name"].upper(), "name", 38, bx1 - bx0)
        text((bx0, y), r["name"].upper(), nm, EMERALD if me else INK)
        by = y + 54 * S
        k.rectangle([bx0, by, bx0 + int(span * r["val"] / scale), by + bh],
                    fill=EMERALD if me else BAR)
        # Season total large, per game beside it small. Both, always: the bars
        # are totals and a total rewards playing every week.
        text((x_val, y + 4 * S), f"{r['val']:.1f}", font("fig", 40),
             EMERALD if me else INK, anchor="ra")
        text((x_val, y + 58 * S), f"{r['per']:.2f}/g   {r['games']}g",
             font("display", 22), MUTED, anchor="ra")
        text((x_pool, y + 4 * S), f"{r['pool']:.0f}", font("fig", 40),
             EMERALD if me else RANK_INK, anchor="ra")

    # -- footer ----------------------------------------------------
    k.rectangle([m, 1268 * S, right, 1269 * S], fill=LINE)
    lead = b["per_leader"]
    foot = [f"Bars are {SEASON} home-and-away totals. Per game beside each.",
            f"Per game the order changes: {lead.split()[-1]} leads, "
            f"{player.split()[-1]} is {ordinal(b['per_rank'])}."
            if b["per_rank"] != 1 else
            f"{player.split()[-1]} leads per game as well."]
    for i, t in enumerate(foot):
        text((m, (1304 + i * 40) * S), t, font("body", 26), MUTED)

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", player.lower()).strip("_")
    path = os.path.join(OUT_DIR, f"pool_{place:02d}_{slug}_{stat.lower()}.png")
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
    ap.add_argument("--stat", default="xScore")
    ap.add_argument("--pool-stat", default="CentreBounceAttendancePercentage")
    ap.add_argument("--pool-min", type=float, default=60)
    ap.add_argument("--top", type=int, default=7)
    ap.add_argument("--font", default="twcen", help=", ".join(FONT_SETS))
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()
    set_fonts(a.font)
    b = gather(a.player, a.stat, a.pool_stat, a.pool_min, a.top)
    path, prev = draw(a.player, a.place, a.stat, a.pool_stat, a.pool_min,
                      b, a.preview)
    print(f"OK  wrote {path}")
    if prev:
        print(f"    timeline preview: {prev}")
    print(f"    pool {b['n_pool']} players, {a.pool_stat} >= {a.pool_min}")
    print(f"    {a.player}: {ordinal(b['rank'])} on total, "
          f"{ordinal(b['per_rank'])} per game ({b['per_leader']} leads)")
    for i, r in enumerate(b["rows"], 1):
        print(f"    {r.get('rank', i):>2}. {r['name']:<24} {r['val']:7.1f}"
              f"  {r['per']:5.2f}/g  pool {r['pool']:5.1f}"
              + ("   <- him" if r["me"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
