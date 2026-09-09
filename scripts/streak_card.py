"""A season's games in order, with a run over a stat line marked.

    python scripts/streak_card.py "Will Ashcroft" 4 --stat Disposals --line 30
    python scripts/streak_card.py "Will Ashcroft" 4 --line 30 --club "Brisbane Lions" \
        --club-alias "Brisbane Bears" --preview

Writes a PNG to drafts/ (gitignored). Portrait 1200x1500 at S=2, downsampled
once to Twitter's 2048 long edge, same as the other countdown cards. Fonts,
colours and the CHA CHING mark are imported from countdown_card rather than
restated. No footer text, by standing rule.

WHY THIS CARD EXISTS
Every other card in the set is a ladder or a two-season table, and neither can
show a RUN. A ladder of streak lengths would put Ashcroft's 9 above Rockliff's 6
and say nothing about what a 9-game run looks like or where in the season it
happened; the whole point of a streak is that it is consecutive and late. One
column per game, in order, with the line drawn across, makes the shape the
graphic: the last nine columns all clear it and the reader counts them without
being told.

HOME AND AWAY ONLY, AND THE SUBTITLE SAYS SO RATHER THAN SAYING "EVERY GAME"
It first read EVERY GAME HE PLAYED, which was wrong the moment finals started:
afl.com.au had Ashcroft on 24 games while this file holds 23, because
data_2026/afltables_2026.csv carries no finals rows. The two reconcile exactly
(174 score involvements here against the AFL's 180, over 24 games rather than
23), so neither is broken, but a card claiming EVERY GAME while showing 23 of 24
is a card a reader can catch.

THE X AXIS IS GAMES PLAYED, NOT ROUNDS, AND THE SUBTITLE SAYS SO
Ashcroft's run covers AFL rounds 14 and 16 to 23; he did not play round 15. A
streak is conventionally consecutive games, so plotting rounds would open a gap
the claim does not have, and plotting games and calling them rounds would be
wrong. Games, labelled as games, with the first and last round of the run named
underneath.

ROUND LABELS ARE THE AFL'S, NOT AFLTABLES'
display_round is imported from countdown_card, which carries the season-gated
subtraction: from 2024 AFLTables counts Opening Round as round 1, so its numbers
run one ahead. Ashcroft's run is raw 15 and 17-24, which is the AFL's 14 and
16-23.

THE CLUB LADDER IS COMPUTED, NOT ASSERTED
--club turns the figure band's second cell into a club record claim, and the
comparison is computed on each run from the same archive as the chart. Bears and
Lions are one club here and Fitzroy is not folded in, per the Neale card and the
archive's own Team column; --club-alias is how that is expressed rather than
being hardcoded, so the same flag serves a Sydney/South Melbourne or a
Footscray/Western Bulldogs card without an edit.
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
    W, H, S, draw_mark, font, ordinal, set_fonts, FONT_SETS, display_round,
)
from club_votes_card import BAR  # noqa: E402

OUT_DIR = "drafts"
STATS_HIST = "data_history/fitzroy_stats_1965_2006.csv.gz"
STATS_ALL = "fitzroy_stats_all.csv"
STATS_CUR = "data_2026/afltables_2026.csv"
CUR_SEASON = 2026


def _name(d):
    return (d["First.name"].astype(str).str.strip() + " "
            + d["Surname"].astype(str).str.strip())


def load(cols):
    """Every archive, 1965 on, home and away rows only, with a real Date."""
    frames = []
    for path in (STATS_HIST, STATS_ALL):
        d = pd.read_csv(path, low_memory=False)
        frames.append(d[cols])
    cur = pd.read_csv(STATS_CUR, low_memory=False)
    cur["Player"] = _name(cur)
    cur["Season"] = CUR_SEASON
    frames.append(cur[cols])
    d = pd.concat(frames, ignore_index=True)
    d["Round_num"] = pd.to_numeric(d["Round"], errors="coerce")
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
    # Finals carry a string round and coerce to NaN. Dropped here rather than
    # kept, so the chart and the club ladder measure the same thing, and because
    # every countdown figure is home and away.
    return d[d["Round_num"].notna()]


def runs(frame, stat, line):
    """Every run of consecutive GAMES clearing the line, per player."""
    out = []
    for pid, g in frame.groupby("ID"):
        g = g.sort_values(["Date", "Season", "Round_num"]).reset_index(drop=True)
        over = (g[stat] >= line).to_numpy()
        n = start = 0
        for i, o in enumerate(over):
            if not o:
                n = 0
                continue
            if n == 0:
                start = i
            n += 1
            if i == len(over) - 1 or not over[i + 1]:
                out.append(dict(player=str(g["Player"].iloc[0]), length=n,
                                s0=int(g["Season"].iloc[start]),
                                r0=int(g["Round_num"].iloc[start]),
                                s1=int(g["Season"].iloc[i]),
                                r1=int(g["Round_num"].iloc[i])))
                n = 0
    return pd.DataFrame(out)


def build(player, stat, line, season, club=None, aliases=()):
    cols = ["Season", "Round", "Date", "Player", "ID", "Playing.for", stat]
    d = load(cols)
    d = d[d[stat].notna()]

    me = d[(d["Player"] == player) & (d["Season"] == season)]
    if me.empty:
        raise SystemExit(f"{player!r} has no {season} home-and-away games")
    me = me.sort_values(["Date", "Round_num"]).reset_index(drop=True)

    mine = runs(d[d["Player"] == player], stat, line)
    best = mine[(mine.s1 == season)].nlargest(1, "length")
    if best.empty:
        raise SystemExit(f"{player!r} has no run over {line} {stat} ending in {season}")
    best = best.iloc[0]

    # Which of his season's games belong to the run. Found by walking back from
    # the last game clearing the line rather than by round number, because the
    # run is consecutive GAMES and a missed round must not break it.
    over = (me[stat] >= line).to_numpy()
    idx = [i for i, o in enumerate(over) if o]
    end = max(i for i in idx
              if int(me["Round_num"].iloc[i]) == int(best.r1))
    span = list(range(end - int(best.length) + 1, end + 1))

    ladder = None
    if club:
        pool = [club] + list(aliases)
        cl = runs(d[d["Playing.for"].isin(pool)], stat, line)
        cl = cl.nlargest(6, "length").reset_index(drop=True)
        ladder = cl
    n_over = int(over.sum())
    return dict(games=me, stat=stat, line=line, season=season, span=span,
                length=int(best.length), n_over=n_over, ladder=ladder,
                club=club, all_runs=runs(d, stat, line))


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

    g, stat, line = b["games"], b["stat"], b["line"]
    span, season = b["span"], b["season"]
    # 30 rather than 30.0 wherever the line is shown. It arrives as a float
    # because --line takes halves (5.5 tackles, 17.5 kicks) and a card that
    # says "30.0+ DISPOSALS" reads as a spreadsheet rather than a stat.
    ltxt = f"{line:g}"

    draw_mark(img, m, 44 * S, 29)
    text((right, 44 * S), f"BROWNLOW COUNTDOWN   {ordinal(place).upper()}",
         font("display", 29), MUTED, anchor="ra")
    k.rectangle([m, 100 * S, right, 101 * S], fill=LINE)

    words = {1: "ONE", 2: "TWO", 3: "THREE", 4: "FOUR", 5: "FIVE", 6: "SIX",
             7: "SEVEN", 8: "EIGHT", 9: "NINE", 10: "TEN", 11: "ELEVEN",
             12: "TWELVE"}
    head = f"{words.get(b['length'], str(b['length']))} IN A ROW"
    text((m, 128 * S), head, fit(head, "name", 80, right - m), INK)
    lab = stat.replace(".", " ").upper()
    head2 = f"{player.upper()}, {ltxt}+ {lab}, {season}"
    text((m, 232 * S), head2, fit(head2, "display", 30, right - m), MUTED)
    sub = "EVERY HOME AND AWAY GAME, IN ORDER"
    text((m, 274 * S), sub, font("display", 30), RANK_INK)
    k.rectangle([m, 328 * S, right, 329 * S], fill=LINE)

    # -- the season, one column per game ---------------------------
    top, base = 392 * S, 1176 * S
    n = len(g)
    slot = (right - m) / n
    bw = int(slot * 0.74)
    peak = float(g[stat].max())
    scale = (base - top) / (peak * 1.06)

    # The line first, behind the columns, so a column reads as crossing it.
    ly = base - int(line * scale)
    x = m
    while x < right:
        k.rectangle([x, ly, min(x + 10 * S, right), ly + 2 * S], fill="#3d4d5c")
        x += 20 * S
    text((right, ly - 40 * S), ltxt, font("fig", 30), RANK_INK, anchor="ra")

    for i, v in enumerate(g[stat].to_numpy(dtype=float)):
        x0 = m + int(i * slot) + int((slot - bw) / 2)
        y0 = base - int(v * scale)
        run = i in span
        k.rectangle([x0, y0, x0 + bw, base], fill=EMERALD if run else BAR)
        if run:
            text((x0 + bw / 2, y0 - 34 * S), f"{v:.0f}", font("fig", 27),
                 EMERALD, anchor="ma")

    k.rectangle([m, base, right, base + 2 * S], fill=LINE)

    # The run's bracket, under the columns it covers. Rounds are named at the
    # ends only: 23 labels do not survive the timeline downscale and the two
    # that carry the claim do.
    x0 = m + int(span[0] * slot)
    x1 = m + int((span[-1] + 1) * slot)
    k.rectangle([x0 + 4 * S, base + 14 * S, x1 - 4 * S, base + 19 * S],
                fill=EMERALD)
    r0 = display_round(int(g["Round_num"].iloc[span[0]]), season)
    r1 = display_round(int(g["Round_num"].iloc[span[-1]]), season)
    text((x0 + 4 * S, base + 30 * S), f"R{r0}", font("display", 27), EMERALD)
    text((x1 - 4 * S, base + 30 * S), f"R{r1}", font("display", 27), EMERALD,
         anchor="ra")

    # -- the two figures -------------------------------------------
    k.rectangle([m, 1284 * S, right, 1285 * S], fill=LINE)
    half = m + (right - m) // 2
    lad = b["ladder"]
    if lad is not None and len(lad) > 1:
        nxt = lad[lad.player != player]
        nxt = nxt.iloc[0] if len(nxt) else None
        rec = "CLUB RECORD" if int(lad.length.iloc[0]) == b["length"] else "CLUB"
        sub2 = (f"NEXT BEST {int(nxt.length)}, {nxt.player.upper()}"
                if nxt is not None else "")
    else:
        rec, sub2 = "IN A ROW", ""
    pairs = [
        (m, str(b["length"]), EMERALD, rec, sub2),
        (half, str(b["n_over"]), INK, f"GAMES OF {ltxt}+ IN {season}",
         f"FROM {len(g)} PLAYED"),
    ]
    for x, big, col, l1, l2 in pairs:
        text((x, 1312 * S), big, font("fig", 88), col)
        text((x, 1410 * S), l1, fit(l1, "display", 27, (right - m) // 2 - 20 * S), INK)
        text((x, 1446 * S), l2, fit(l2, "display", 25, (right - m) // 2 - 20 * S),
             MUTED)

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", player.lower()).strip("_")
    path = os.path.join(OUT_DIR,
                        f"streak_{place:02d}_{slug}_{stat.lower()}_{ltxt}.png")
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
    ap.add_argument("--stat", default="Disposals")
    ap.add_argument("--line", type=float, default=30)
    ap.add_argument("--season", type=int, default=CUR_SEASON)
    ap.add_argument("--club", help="club to compute the record ladder against")
    ap.add_argument("--club-alias", action="append", default=[],
                    help="another Team spelling counting as the same club")
    ap.add_argument("--font", default="twcen", help=", ".join(FONT_SETS))
    ap.add_argument("--preview", action="store_true",
                    help="also write the 350px version Twitter shows on a phone")
    a = ap.parse_args()
    set_fonts(a.font)
    b = build(a.player, a.stat, a.line, a.season, a.club, a.club_alias)
    path, prev = draw(a.player, a.place, b, a.preview)
    g = b["games"]
    print(f"OK  wrote {path}")
    if prev:
        print(f"    timeline preview: {prev}")
    print(f"    {a.player} {a.season}: {b['n_over']} of {len(g)} games at "
          f"{a.line:.0f}+ {a.stat}, longest run {b['length']}")
    rounds = [display_round(int(g['Round_num'].iloc[i]), a.season) for i in b["span"]]
    print(f"    the run, AFL rounds: {', '.join(rounds)}")
    if b["ladder"] is not None:
        print(f"    {a.club} ladder (with aliases {a.club_alias or 'none'}):")
        for _, r in b["ladder"].iterrows():
            print(f"      {int(r.length):>2}  {r.player:<20} "
                  f"{r.s0} r{r.r0} to {r.s1} r{r.r1}")
    allr = b["all_runs"]
    at = allr[allr.length >= b["length"]]
    print(f"    league wide, 1965-{a.season}: {len(at)} runs of {b['length']}+ "
          f"by {at.player.nunique()} players")
    print("    longest anywhere:")
    for _, r in allr.nlargest(5, "length").iterrows():
        print(f"      {int(r.length):>2}  {r.player:<20} {r.s0} r{r.r0} to {r.s1} r{r.r1}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
