"""The site's Polling DNA panel, redrawn at tweet size.

    python scripts/dna_card.py "Jason Horne-Francis" 13
    python scripts/dna_card.py "Jason Horne-Francis" 13 --stat Disposals --line 25 --preview

This is a REPLICA, not a new design. It reproduces the Player Profile > DNA tab
as dashboard.py renders it: the threshold mini-head and slider, the gold poll
rate, the generated sentence, the three-cell strip, and the Vote Distribution
stacked bar with its legend. A reader who clicks through from the tweet should
land on the thing they just saw.

WHAT IS COPIED FROM THE PAGE RATHER THAN CHOSEN HERE

- Monospace for every label and figure. countdown_card.py's docstring bans this
  and is right for that card, but the site sets .dna-find-val, .dfs-v, .dfs-l
  and .dna-vleg in IBM Plex Mono, so matching the page means matching the mono.
  Consolas stands in: IBM Plex Mono is a webfont and is not installed here, so a
  browser on this machine already falls back to Consolas and the screenshot the
  card is copying is Consolas too.
- Gold for the poll rate. .dna-find-val is var(--gold), and gold leads the vote
  distribution bar as well. CLAUDE.md reserves gold for the Betting Hub, and the
  DNA tab is the standing exception on the Brownlow side; this card inherits the
  exception rather than reopening it.
- The current season is excluded. The page drops any season whose votes are not
  yet in, because a game that structurally cannot poll is not evidence that he
  failed to poll.

THE ONE DELIBERATE DEPARTURE FROM THE PAGE
The distribution bar is the THRESHOLD SUBSET, where the page draws the player's
whole career. On the page that is right, because the bar sits below both halves
of the tab and describes the player. On a card built around one line it is not:
a bar of 75 games under a panel of 15 invites the reader to divide the wrong
numbers, and 72% of its width is games the card is not talking about.

Scoped to the 15, every figure on the card reconciles against the bar. The three
polled segments are 7 + 2 + 3, which is the 80% poll rate; the gold segment is
7 of 15, which is the 46.7%; and 7x3 + 2x2 + 3x1 over 15 is the 1.87 average.
Nothing on the card can now be checked against the bar and disagree with it.

Because the numbers no longer match what the same-looking panel shows on the
site, the section header carries the threshold. An unlabelled "Vote
Distribution" reading 15 games where the page reads 75 is the kind of quiet
mismatch a reader finds and cannot explain.

Finals carry a string round, coerce to NaN and drop out, so no game that could
not have polled reaches a denominator.
"""

import argparse
import math
import os
import re
import sys

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from countdown_card import BG, W, H, S, draw_mark, ordinal  # noqa: E402

OUT_DIR = "drafts"
STATS_HIST = "data_history/fitzroy_stats_1965_2006.csv.gz"
STATS_ALL = "fitzroy_stats_all.csv"
CUR_SEASON = 2026

# theme.py tokens, and the two rgba fills composited onto --surface #101a24
# because PIL has no alpha compositing in a flat draw. muted-fill is
# rgba(159,176,191,.22) and the 1-vote grey is rgba(159,176,191,.55).
INK = "#e9eef3"
MUTED = "#7e8c99"
STEEL = "#9fb0bf"
GOLD = "#f0b429"
EMERALD = "#34d399"
LINE = "#1a2632"
HEADER_INK = "#4a5a6a"          # .section-header colour
EMERALD_PACK = "#1d6852"        # rgba(52,211,153,.45) on surface
GREY_1V = "#5f6d79"             # rgba(159,176,191,.55) on surface
MUTED_FILL = "#2f3a46"          # rgba(159,176,191,.22) on surface
HAIRLINE_STRONG = "#2b3640"

# The page's threshold sliders, from _THRESH_STATS in dashboard.py. The slider
# graphic is only honest if its endpoints are the ones the page actually offers.
THRESH_STATS = {
    "Disposals": ("Disposals", 10, 50, 20),
    "Goals": ("Goals", 0, 10, 2),
    "Coaches Votes": ("Coaches_Votes", 0, 10, 5),
}

FDIR = r"C:\Windows\Fonts"
MONO, MONO_B = "consola.ttf", "consolab.ttf"
SANS, SANS_B = "segoeui.ttf", "seguisb.ttf"


def f(name, size):
    return ImageFont.truetype(os.path.join(FDIR, name), int(size * S))


def tracked_width(k, txt, fnt, track):
    return sum(k.textlength(c, font=fnt) for c in txt) + track * max(0, len(txt) - 1)


def tracked(k, xy, txt, fnt, fill, track):
    """Letter-spaced text. The page's mini-heads run .14em to .16em and the
    spacing is most of what makes them read as labels rather than as prose."""
    x, y = xy
    for c in txt:
        k.text((x, y), c, font=fnt, fill=fill)
        x += k.textlength(c, font=fnt) + track
    return x - xy[0]


def wrap(k, txt, fnt, width):
    lines, cur = [], ""
    for word in txt.split():
        trial = f"{cur} {word}".strip()
        if k.textlength(trial, font=fnt) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _name(d):
    return (d["First.name"].astype(str).str.strip() + " "
            + d["Surname"].astype(str).str.strip())


def gather(player, stat_label, line):
    col, smin, smax, _ = THRESH_STATS[stat_label]
    frames, voted = [], set()
    for path in (STATS_HIST, STATS_ALL):
        d = pd.read_csv(path, low_memory=False)
        d = d[pd.to_numeric(d["Round"], errors="coerce").notna()]
        # WHICH SEASONS COUNT IS A LEAGUE QUESTION, NOT A PLAYER ONE. The page
        # takes it from the whole game frame, so a season is kept when ANY
        # player polled in it, meaning the count has happened. Grouping the
        # PLAYER's own rows instead silently deletes every season he failed to
        # poll in: it cut Horne-Francis' voteless 2022 and read 58 career games
        # where the page reads 75, dragging the zero-vote bar with it.
        voted |= set(d.groupby("Season")["Brownlow.Votes"].sum()
                     .loc[lambda s: s > 0].index)
        mine = d[_name(d) == player]
        if not mine.empty:
            frames.append(mine)
    if not frames:
        raise SystemExit(f"{player!r} not found in the archives")
    g = pd.concat(frames, ignore_index=True)
    g = g[g["Season"].isin(voted)]
    sub = g[g[col] >= line]
    if sub.empty:
        raise SystemExit(f"{player!r} has no games with {col} >= {line}")
    # The bar describes the games over the line, not the career. See the
    # docstring: this is the one place the card departs from the page.
    vc = sub["Brownlow.Votes"].value_counts()
    return dict(
        n_sub=len(sub), n_tot=len(g),
        poll=(sub["Brownlow.Votes"] > 0).mean(),
        avg=sub["Brownlow.Votes"].mean(),
        three=(sub["Brownlow.Votes"] == 3).mean(),
        dist={v: int(vc.get(v, 0)) for v in (3, 2, 1, 0)},
        yr0=int(g["Season"].min()), yr1=int(g["Season"].max()),
        smin=smin, smax=smax,
    )


def draw(player, place, stat_label, line, b, preview=False):
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = 56 * S, (W - 56) * S
    noun = stat_label.lower()

    def hair(y, colour=LINE):
        k.rectangle([m, y, right, y + 1 * S], fill=colour)

    def section(y, label):
        """.section-header: 11px Sora, .1em tracking, uppercase, hairline under."""
        tracked(k, (m, y), label.upper(), f(SANS_B, 24), HEADER_INK, 2.6 * S)
        hair(y + 40 * S)

    # -- masthead --------------------------------------------------
    draw_mark(img, m, 44 * S, 29)
    k.text((right, 46 * S), f"BROWNLOW COUNTDOWN   {ordinal(place).upper()}",
           font=f(SANS_B, 27), fill=MUTED, anchor="ra")
    hair(100 * S)

    size = 66
    while k.textlength(player, font=f(SANS_B, size)) > right - m and size > 30:
        size -= 2
    k.text((m, 128 * S), player, font=f(SANS_B, size), fill=INK)

    section(240 * S, "Polling DNA")

    # -- the slider ------------------------------------------------
    # The page's "<Stat> Threshold" mini-head above this is deliberately NOT
    # drawn. On the page it names a control the reader is about to move; on a
    # static card it labels a slider that cannot move, directly above a slider
    # already labelled "Min disposals" and a caption already reading "at 25+
    # disposals". Three sayings of one thing before the reader reaches a number.
    k.text((m, 330 * S), f"Min {noun}", font=f(SANS, 32), fill=STEEL)

    ty = 456 * S
    frac = (line - b["smin"]) / float(b["smax"] - b["smin"])
    tx = m + int((right - m) * frac)
    k.rounded_rectangle([m, ty, right, ty + 7 * S], radius=4 * S, fill=MUTED_FILL)
    k.rounded_rectangle([m, ty, tx, ty + 7 * S], radius=4 * S, fill=EMERALD)
    r = 19 * S
    cy = ty + 3 * S
    k.ellipse([tx - r, cy - r, tx + r, cy + r], fill=BG, outline=EMERALD, width=6 * S)
    lab = str(line)
    k.text((tx - k.textlength(lab, font=f(SANS, 32)) / 2, 404 * S), lab,
           font=f(SANS, 32), fill=STEEL)
    k.text((m, 496 * S), str(b["smin"]), font=f(SANS, 30), fill=MUTED)
    k.text((right, 496 * S), str(b["smax"]), font=f(SANS, 30), fill=MUTED,
           anchor="ra")

    # -- the hero rate ---------------------------------------------
    k.text((m, 572 * S), f"{b['poll']*100:.1f}%", font=f(MONO_B, 116), fill=GOLD)
    tracked(k, (m, 736 * S), f"poll rate at {line}+ {noun}", f(MONO, 27),
            MUTED, 0.8 * S)

    # -- the generated sentence, verbatim from the page's own logic --
    ln = player.split()[-1]
    if b["poll"] == 1.0:
        s = f"When {ln} reaches {line}+ {noun} he polls every time"
        s += (" and every one was a 3-vote game." if b["three"] == 1.0
              else f", averaging {b['avg']:.2f} votes.")
    else:
        s = (f"At {line}+ {noun} {ln} polls {b['poll']*100:.0f}% of the time, "
             f"averaging {b['avg']:.2f} votes.")
    sf = f(SANS, 34)
    # The page sets .dna-find-sentence to max-width:46ch, so it breaks well
    # short of the column. At full width this sentence drops "votes." alone on
    # line two; the narrower measure breaks it after "time," instead.
    for i, ln_txt in enumerate(wrap(k, s, sf, int((right - m) * 0.80))):
        k.text((m, (800 + i * 46) * S), ln_txt, font=sf, fill=INK)

    # -- the three-cell strip --------------------------------------
    cells = [(f"{b['n_sub']} of {b['n_tot']}", "Games"),
             (f"{b['avg']:.2f}", "Avg votes polled"),
             (f"{b['three']*100:.1f}%", "3-Vote Rate")]
    cw = (right - m) // 3
    sy = 950 * S
    for i, (val, lab_t) in enumerate(cells):
        x = m + i * cw
        if i:
            k.rectangle([x - 22 * S, sy, x - 21 * S, sy + 92 * S],
                        fill=HAIRLINE_STRONG)
        k.text((x, sy), val, font=f(MONO_B, 42), fill=STEEL)
        tracked(k, (x, sy + 62 * S), lab_t.upper(), f(MONO, 23), MUTED, 3.0 * S)

    # -- vote distribution -----------------------------------------
    section(1126 * S, f"Vote Distribution at {line}+ {noun}")
    d, tot = b["dist"], b["n_sub"]
    bar_y, bar_h = 1206 * S, 76 * S
    seg = [(d[3], GOLD), (d[2], EMERALD_PACK), (d[1], GREY_1V), (d[0], MUTED_FILL)]
    strip = Image.new("RGB", (right - m, bar_h), MUTED_FILL)
    sk = ImageDraw.Draw(strip)
    x = 0
    for n, col in seg:
        w = int(round((right - m) * n / tot))
        sk.rectangle([x, 0, x + w, bar_h], fill=col)
        x += w
    mask = Image.new("L", strip.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, strip.size[0] - 1, bar_h - 1],
                                          radius=12 * S, fill=255)
    img.paste(strip, (m, bar_y), mask)

    # The footnote block that sat here is gone on purpose. Its three lines were
    # the smallest type on the card and the first thing Twitter's downscale ate,
    # and the two facts worth keeping are already load-bearing elsewhere: the
    # sample is the "15 of 75 GAMES" cell, and the scope is in this section
    # header. Only the count-night caveat is genuinely lost, and the tweet it
    # ships inside carries it.
    lx = m
    for (n, col), lab_t in zip(seg, ("3 votes", "2 votes", "1 vote", "0 votes")):
        k.rounded_rectangle([lx, 1326 * S, lx + 21 * S, 1347 * S],
                            radius=4 * S, fill=col)
        t = f"{lab_t} \u00b7 {n}"
        k.text((lx + 34 * S, 1320 * S), t, font=f(MONO, 29), fill=STEEL)
        lx += 34 * S + k.textlength(t, font=f(MONO, 29)) + 40 * S

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", player.lower()).strip("_")
    path = os.path.join(OUT_DIR, f"dna_{place:02d}_{slug}_{noun.replace(' ','_')}_{line}.png")
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
    ap.add_argument("--stat", default="Disposals", choices=list(THRESH_STATS))
    ap.add_argument("--line", type=int, default=25)
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()
    b = gather(a.player, a.stat, a.line)
    path, prev = draw(a.player, a.place, a.stat, a.line, b, a.preview)
    print(f"OK  wrote {path}")
    if prev:
        print(f"    timeline preview: {prev}")
    print(f"    {a.line}+ {a.stat}: {b['n_sub']} of {b['n_tot']} games, "
          f"poll {b['poll']*100:.1f}%, avg {b['avg']:.2f}, "
          f"3-vote {b['three']*100:.1f}%")
    print(f"    distribution over the line 3/2/1/0: "
          f"{[b['dist'][v] for v in (3, 2, 1, 0)]}  ({b['yr0']}-{b['yr1']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
