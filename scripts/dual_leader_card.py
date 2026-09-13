"""Two stats, every qualified player, one marked. For a player who tops both.

    python scripts/dual_leader_card.py "Bailey Smith" 2 \
        --x Metres_Gained --y Inside.50s --preview

Writes a PNG to drafts/ (gitignored). Portrait 1200x1500 at S=2, downsampled
once to Twitter's 2048 long edge, same as the other countdown cards. Fonts,
colours and the CHA CHING mark are imported from countdown_card rather than
restated. No footer text, by standing rule.

WHY A SCATTER AND NOT TWO LADDERS
The claim is an INTERSECTION: Bailey Smith led the AFL for metres gained and for
inside 50s in the same season. Two stacked ladders would show him at the top of
each and leave the reader to hold both in their head, which is the one thing a
graphic should never ask. A scatter puts the whole field on one page and the
claim becomes a position: he is alone in the top right corner and nobody has to
be told, because the nearest player on one axis (Wanganeen-Milera, 630 metres)
sits two thirds of the way down the other.

It is also the honest shape. A ladder hides how close second place was; a
scatter cannot, because second place is drawn.

THE FIELD IS DRAWN, NOT SUMMARISED
All 408 qualified players are plotted. A card showing the top ten of each would
be making the same claim on a tenth of the evidence and would look identical, so
the dots are the argument. MIN_GAMES is countdown_card's 12 and the header says
so, because the corner is exactly where a 5-game cameo would land if the floor
were dropped.

METRES GAINED STARTS IN 2015 AND THIS CARD DOES NOT CARE
The scatter is one season against itself, so the advanced-stats floor is
irrelevant to the graphic. It is only relevant to the historical line that goes
with it ("the fourth season since 2015 to lead both"), which lives in the draft
copy where the window can be stated. Do not put a since-2015 claim on this card.
"""

import argparse
import math
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
    SI_PATH, ADV_COLS, CATALOGUE,
)

OUT_DIR = "drafts"
STATS_CUR = "data_2026/afltables_2026.csv"
CUR_SEASON = 2026
DOT = "#31404e"          # the field, quiet enough that 400 of them stay a cloud
DOT_NEAR = "#5b7185"     # the handful worth naming


def label_for(col):
    for words, name, _fmt in CATALOGUE:
        if name == col:
            return " ".join(words)
    return col.replace(".", " ").replace("_", " ").upper()


def fmt_for(col):
    for _words, name, f in CATALOGUE:
        if name == col:
            return f
    return "{:.1f}"


def gather(season, x, y):
    cur = pd.read_csv(STATS_CUR, low_memory=False)
    cur["Player"] = (cur["First.name"].str.strip() + " "
                     + cur["Surname"].str.strip())
    cur["Round_num"] = pd.to_numeric(cur["Round"], errors="coerce")
    cur = cur[cur["Round_num"].notna()]
    cur["Season"] = season

    need = [c for c in (x, y) if c in ADV_COLS]
    if need:
        adv = pd.read_csv(SI_PATH,
                          usecols=["Season", "Round_num", "ID"] + ADV_COLS)
        # Deduped before the merge: a repeated key on the RIGHT of a left join
        # multiplies the left row rather than annotating it.
        adv = adv.drop_duplicates(["Season", "Round_num", "ID"])
        cur = cur.merge(adv, on=["Season", "Round_num", "ID"], how="left")

    for c in (x, y):
        if c not in cur.columns:
            raise SystemExit(f"{c!r} is not a column this card can plot")
    g = cur.groupby(["ID", "Player", "Playing.for"], as_index=False).agg(
        n=("Round_num", "size"), x=(x, "mean"), y=(y, "mean"))
    g = g[(g["n"] >= MIN_GAMES) & g["x"].notna() & g["y"].notna()]
    return g.reset_index(drop=True)


def build(player, season, x, y):
    g = gather(season, x, y)
    me = g[g["Player"] == player]
    if me.empty:
        raise SystemExit(f"{player!r} has no qualifying {season} season")
    me = me.iloc[0]
    g["rx"] = g["x"].rank(ascending=False, method="min").astype(int)
    g["ry"] = g["y"].rank(ascending=False, method="min").astype(int)
    me = g[g["Player"] == player].iloc[0]
    # Worth naming: whoever is second on either axis, so the reader can see how
    # far the gap is on each without reading a table.
    near = pd.concat([g[(g.rx <= 3) | (g.ry <= 3)]]).drop_duplicates("ID")
    near = near[near["Player"] != player]
    return dict(field=g, me=me, near=near, xcol=x, ycol=y, season=season,
                n=len(g))


def draw(player, place, b, preview=False):
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = 56 * S, (W - 56) * S

    def text(xy, t, f, fill, anchor="la"):
        k.text(xy, t, font=f, fill=fill, anchor=anchor)

    def fit(t, role, size, width):
        while size > 16 and k.textlength(t, font=font(role, size)) > width:
            size -= 2
        return font(role, size)

    g, me = b["field"], b["me"]
    xl, yl = label_for(b["xcol"]), label_for(b["ycol"])
    xf, yf = fmt_for(b["xcol"]), fmt_for(b["ycol"])

    draw_mark(img, m, 44 * S, 29)
    text((right, 44 * S), f"BROWNLOW COUNTDOWN   {ordinal(place).upper()}",
         font("display", 29), MUTED, anchor="ra")
    k.rectangle([m, 100 * S, right, 101 * S], fill=LINE)

    head = "FIRST FOR BOTH" if (me.rx == 1 and me.ry == 1) else player.upper()
    text((m, 128 * S), head, fit(head, "name", 80, right - m), INK)
    l1 = f"{player.upper()}, {b['season']}"
    text((m, 232 * S), l1, fit(l1, "display", 30, right - m), MUTED)
    l2 = f"EVERY PLAYER WITH {MIN_GAMES}+ HOME AND AWAY GAMES   ({b['n']})"
    text((m, 274 * S), l2, fit(l2, "display", 30, right - m), RANK_INK)
    k.rectangle([m, 328 * S, right, 329 * S], fill=LINE)

    # -- the plot ---------------------------------------------------
    # Axis label above the plot rather than rotated down its side: PIL rotation
    # means compositing a second image, and at the size Twitter serves a
    # sideways label is unread anyway.
    text((m, 366 * S), yl, font("display", 27), RANK_INK)
    px0, px1 = m + 8 * S, right
    py0, py1 = 410 * S, 1176 * S

    xs, ys = g["x"].to_numpy(float), g["y"].to_numpy(float)
    xlo, xhi = xs.min(), xs.max()
    ylo, yhi = ys.min(), ys.max()
    xpad, ypad = (xhi - xlo) * 0.06, (yhi - ylo) * 0.08
    xlo, xhi = xlo - xpad, xhi + xpad
    ylo, yhi = max(0.0, ylo - ypad), yhi + ypad

    def px(v):
        return px0 + (px1 - px0) * (v - xlo) / (xhi - xlo)

    def py(v):
        return py1 - (py1 - py0) * (v - ylo) / (yhi - ylo)

    k.rectangle([px0, py1, px1, py1 + 2 * S], fill=LINE)

    r = 5 * S
    near_ids = set(b["near"]["ID"])
    for _, row in g.iterrows():
        if row["Player"] == player:
            continue
        c = DOT_NEAR if row["ID"] in near_ids else DOT
        cx, cy = px(row["x"]), py(row["y"])
        k.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)

    placed = []

    def free(box):
        return not any(box[0] < q[2] and q[0] < box[2]
                       and box[1] < q[3] and q[1] < box[3] for q in placed)

    cx, cy = px(me.x), py(me.y)
    k.ellipse([cx - 13 * S, cy - 13 * S, cx + 13 * S, cy + 13 * S], fill=EMERALD)
    _mw = k.textlength(player.upper(), font=font("name", 34))
    nm = player.upper()
    # The subject's label goes left of his dot when he is at the right edge,
    # which he is whenever this card is the right card to be drawing.
    at_right = cx > (px0 + px1) / 2
    text((cx - 24 * S if at_right else cx + 24 * S, cy), nm,
         font("name", 34), EMERALD, anchor="rm" if at_right else "lm")
    placed.append((cx - 24 * S - _mw, cy - 22 * S, cx + 24 * S, cy + 22 * S)
                  if at_right else
                  (cx - 24 * S, cy - 22 * S, cx + 24 * S + _mw, cy + 22 * S))


    # Named dots need collision avoidance, not just an offset. Warner and
    # Richards sit 0.00 apart on inside 50s and 42 metres apart on the other
    # axis, so a fixed "above the dot" placement printed them over each other as
    # WARNERCHARDS. Four candidate positions, first one that does not overlap an
    # already-placed box; a name that fits nowhere is dropped rather than
    # stacked, because an unreadable label is worse than no label.
    lf = font("display", 22)
    for _, row in b["near"].iterrows():
        cx, cy = px(row["x"]), py(row["y"])
        nm = row["Player"].split(" ", 1)[1].upper()
        tw, th = k.textlength(nm, font=lf), 24 * S
        pad = 18 * S
        for ax, ay, anchor in (("m", "d", "md"), ("m", "u", "ma"),
                               ("r", "m", "rm"), ("l", "m", "lm")):
            if ax == "m":
                x0, x1 = cx - tw / 2, cx + tw / 2
                y0, y1 = ((cy - pad - th, cy - pad) if ay == "d"
                          else (cy + pad, cy + pad + th))
                tx, ty = cx, (cy - pad if ay == "d" else cy + pad)
            else:
                y0, y1 = cy - th / 2, cy + th / 2
                x0, x1 = ((cx - pad - tw, cx - pad) if ax == "r"
                          else (cx + pad, cx + pad + tw))
                tx, ty = (cx - pad if ax == "r" else cx + pad), cy
            if x0 < m or x1 > right or y0 < py0 or y1 > py1:
                continue
            if free((x0, y0, x1, y1)):
                text((tx, ty), nm, lf, DOT_NEAR, anchor=anchor)
                placed.append((x0, y0, x1, y1))
                break

    text((px1, py1 + 16 * S), xl, font("display", 27), RANK_INK, anchor="ra")

    # -- the two ranks ----------------------------------------------
    k.rectangle([m, 1252 * S, right, 1253 * S], fill=LINE)
    half = m + (right - m) // 2
    pairs = [(m, xf.format(me.x), f"{ordinal(int(me.rx)).upper()} FOR {xl}"),
             (half, yf.format(me.y), f"{ordinal(int(me.ry)).upper()} FOR {yl}")]
    for x_, big, lab in pairs:
        text((x_, 1290 * S), big, font("fig", 88), EMERALD)
        text((x_, 1400 * S), lab, fit(lab, "display", 27,
                                      (right - m) // 2 - 20 * S), INK)

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", player.lower()).strip("_")
    path = os.path.join(OUT_DIR, f"dual_{place:02d}_{slug}.png")
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
    ap.add_argument("--x", default="Metres_Gained")
    ap.add_argument("--y", default="Inside.50s")
    ap.add_argument("--season", type=int, default=CUR_SEASON)
    ap.add_argument("--font", default="twcen", help=", ".join(FONT_SETS))
    ap.add_argument("--preview", action="store_true",
                    help="also write the 350px version Twitter shows on a phone")
    a = ap.parse_args()
    set_fonts(a.font)
    b = build(a.player, a.season, a.x, a.y)
    path, prev = draw(a.player, a.place, b, a.preview)
    me, g = b["me"], b["field"]
    print(f"OK  wrote {path}")
    if prev:
        print(f"    timeline preview: {prev}")
    print(f"    field: {b['n']} players with {MIN_GAMES}+ games in {a.season}")
    print(f"    {a.player}: {a.x} {me.x:.2f} ({ordinal(int(me.rx))}), "
          f"{a.y} {me.y:.2f} ({ordinal(int(me.ry))})")
    for col, rk, lab in (("x", "rx", a.x), ("y", "ry", a.y)):
        top = g.nsmallest(4, rk)
        print(f"    top 4 for {lab}:")
        for _, r in top.iterrows():
            print(f"      {int(r[rk]):>2}. {r['Player']:<24}{r[col]:>8.2f}"
                  + ("   <- him" if r["Player"] == a.player else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
