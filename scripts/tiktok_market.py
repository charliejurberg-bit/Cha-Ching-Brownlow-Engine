# -*- coding: utf-8 -*-
"""The 3 Vote Games picks as a TikTok photo carousel, one slide per selection.

    python scripts/tiktok_market.py               # cover + 6 picks + closer
    python scripts/tiktok_market.py --only cripps # one slide, while iterating

Writes 1080x1920 PNGs to `drafts/tiktok_3votes/` (gitignored), copies them to
`OneDrive/Pictures/ChaChing Slides/` so the phone can see them, and writes the
draft copy to `drafts/tiktok_3votes_<season>.md`. It never posts.

EVERY FIGURE IS READ, NONE IS TYPED
Price and model probability come from `data_betting/sb_3vote_board.csv`, which
`sb_3vote_board.py` writes; the per-game stats come from `game_level_2026.csv`
and `data_advanced/score_involvements.csv`. A pick names a player, a round and
which six stats to show, and nothing else. Hand-typing a figure onto a public
card is how a wrong one gets posted.

SCORE INVOLVEMENTS IS THE REAL STAT, NOT THE ENGINEERED COLUMN
`Score_Involvements` in game_level is `Goals + Goal.Assists + Marks.Inside.50 +
Inside.50s`, which double counts and omits the largest real component. It reads
5 for Cripps' round 11 where the real figure is 10. Reader-facing surfaces take
`Score_Involvements_Actual` from the footywire join, which is what `_SI_COL` in
dashboard.py does, and so does the SI key here. Coverage starts in 2015.

THE SIX STAT CELLS DIFFER BY PLAYER, ON PURPOSE
Three are fixed in fixed positions so the grid reads as one object down the
deck: disposals top left, score involvements and coaches votes opening the
second row. The other three are the player's own case. A fixed midfield set
would have put "3 CLEARANCES" on the slide arguing Dempsey should have polled
the 3, which is the slide arguing against itself.

THE VERTICAL BUDGET IS THE WHOLE LAYOUT PROBLEM
TikTok centre-crops a carousel image, so everything a reader must see lives
between y 420 and y 1500. The second stat row is paid for by shortening the
photo band to 546px, never by letting the bottom row drift past 1500.
"""

import argparse
import colorsys
import os
import re
import shutil
import sys

import pandas as pd
from PIL import Image, ImageChops, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from afl_headshots import head                                     # noqa: E402
from countdown_card import (                                       # noqa: E402
    BG, EMERALD, INK, MUTED, RANK_INK, GOLD, LINE, S, draw_mark, font,
)
from tiktok_top10 import (                                         # noqa: E402
    W, H, M, SAFE_TOP, SAFE_BOT, PANEL, BAR, DOMAIN, SITE_SHOT, TEAM_COLOURS,
    accent, fit_font, _initials,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOARD = os.path.join(REPO, "data_betting", "sb_3vote_board.csv")
GAME_LEVEL = os.path.join(REPO, "predictions", "game_level_2026.csv")
SI_PATH = os.path.join(REPO, "data_advanced", "score_involvements.csv")
OUT_DIR = os.path.join(REPO, "drafts", "tiktok_3votes")
# The folder the phone can see. OneDrive syncs Pictures, and the repo's own
# drafts/ is gitignored and local, which is why the first deck never showed up
# in TikTok's picker.
PHONE_DIR = os.path.join(os.path.expanduser("~"), "OneDrive", "Pictures",
                         "ChaChing Slides")
SEASON = 2026
BOOK = "SPORTSBET"
COUNT_DATE = "Monday 21 September"

CUT_TOP, CUT_BOT = 400, 946          # the cutout band, shortened for two stat rows
TIER_COL = {"SAFE": EMERALD, "VALUE": GOLD, "LONGSHOT": None}   # None draws an outline
TIER_LABEL = {"SAFE": "SAFE PICK", "VALUE": "VALUE PICK", "LONGSHOT": "LONGSHOT"}

# THE TIER IS THE PRICE, AND IT IS DERIVED RATHER THAN TYPED
# An earlier rule tiered by the model's chance instead (safe 70%+, value 45 to
# 70%, longshot under 45%). The chance is not on the slide; the price is, in
# gold, at 100px. A reader therefore checks the chip against the only number
# beside it, and a $2.30 runner chipped SAFE reads as an error whatever the
# internal rule was. Deriving from the price cannot drift, which a hand-typed
# tier in PICKS does the moment a price moves between two builds.
#
# The bands hold across BOTH decks, which is why they live here rather than in
# either one. They do not produce the same spread in each, and that is the
# market talking rather than a bug: a 3 votes board runs $1.01 to $34.00, so
# all three tiers are populated, while a to-poll-a-vote board runs $1.09 to
# $7.25 and has no longshot in it at all. Any copy that states the split must
# COUNT it, never assert it.
SAFE_MAX = 2.00          # $2.00 and under
LONGSHOT_MIN = 10.00     # $10.00 and over


def tier_for(odds):
    """SAFE at $2.00 and under, VALUE between, LONGSHOT at $10.00 and over."""
    o = float(odds)
    if o <= SAFE_MAX:
        return "SAFE"
    return "VALUE" if o < LONGSHOT_MIN else "LONGSHOT"


def tier_split(picks):
    """The tier counts, spelled, for a caption that must not assert a split."""
    words = {0: "no", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
             6: "six"}
    n = {t: sum(1 for p in picks if p["tier"] == t) for t in TIER_LABEL}
    parts = [f"{words.get(n[t], n[t])} {TIER_LABEL[t].split()[0].lower()}"
             for t in ("SAFE", "VALUE", "LONGSHOT") if n[t]]
    return ", ".join(parts[:-1]) + (" and " + parts[-1] if len(parts) > 1
                                    else parts[0])


# ODDS-FREE MODE, FOR PLATFORMS THAT PROHIBIT GAMBLING PROMOTION
# TikTok removed the 3 vote and to-poll-a-vote posts under its community
# guidelines on 19 September 2026 and left the top 10 post, which carries no
# prices, untouched. That is the whole diagnosis: the prices are the problem,
# not the model.
#
# REMOVING THE DOLLAR FIGURES IS NOT ENOUGH, and this is the part that is easy
# to get wrong. A classifier reads the frame, not just the number. So this
# mode also drops the bookmaker's name, the implied-probability and edge
# figures, the tier words (SAFE / VALUE PICK / LONGSHOT are betting language
# whatever is beside them), the word BETS in the cover title, and the 18+
# responsible-gambling line. That last one is counterintuitive and deliberate:
# carrying "18+ GAMBLE RESPONSIBLY" on a post with no odds on it is a signal
# TO the classifier that the post is gambling content. It is the right line to
# carry when there are prices and the wrong line to carry when there are not.
#
# What survives is the model: the same selections off the same boards, with
# the model's own probability where the price used to sit. The priced build is
# unchanged and still runs for platforms that permit it.
NO_ODDS = False


def set_no_odds(on=True):
    global NO_ODDS
    NO_ODDS = bool(on)


def add_no_odds_arg(ap):
    ap.add_argument("--no-odds", action="store_true",
                    help="drop every price, the book, the tiers and the 18+ "
                         "line; write to a separate folder")
    return ap


def order_picks(picks):
    """Deck order. Priced, that is the PICKS order, which runs by price.

    Odds-free there is no price, so that order arrives as percentages jumping
    about (70, 82, 65, 44, 22, 17) with nothing on the slide to explain why.
    Sorting by the model's own chance is the only ordering the odds-free deck
    can justify, and it gives the swipe a direction again.
    """
    if not NO_ODDS:
        return list(picks)
    return sorted(picks, key=lambda q: -float(q["model"]))


def slide_stem(p, i):
    """`<n>_<tier>_<key>`, or `<n>_<key>` where there are no tiers."""
    return (f"{i:02d}_{p['key']}" if NO_ODDS
            else f"{i:02d}_{p['tier'].lower()}_{p['key']}")


def odds_paths(out_dir, phone_dir):
    """Where an odds-free build writes. NEVER the priced build's folders.

    Separate because both builds prune their own directory, so sharing one
    would have each delete the other on every run, and because a folder of
    mixed priced and unpriced slides is exactly the picker mistake the prune
    exists to prevent.
    """
    if not NO_ODDS:
        return out_dir, phone_dir
    return out_dir + "_noodds", os.path.join(phone_dir, "No Odds")

# Every stat a slide can show, keyed to where it actually comes from. "adv" is
# the footywire join, "game" is game_level.
STATS = {
    "disp":     ("game", "Disposals", "DISPOSALS", "{:.0f}"),
    "cp":       ("game", "Contested.Possessions", "CONTESTED POSS", "{:.0f}"),
    "clear":    ("game", "Clearances", "CLEARANCES", "{:.0f}"),
    "tackles":  ("game", "Tackles", "TACKLES", "{:.0f}"),
    "goals":    ("game", "Goals", "GOALS", "{:.0f}"),
    "marks":    ("game", "Marks", "MARKS", "{:.0f}"),
    "mi50":     ("game", "Marks.Inside.50", "MARKS INSIDE 50", "{:.0f}"),
    "i50":      ("game", "Inside.50s", "INSIDE 50s", "{:.0f}"),
    "reb":      ("game", "Rebounds", "REBOUND 50s", "{:.0f}"),
    "ga":       ("game", "Goal.Assists", "GOAL ASSISTS", "{:.0f}"),
    "cv":       ("game", "Coaches_Votes", "COACHES VOTES", "{:.0f}"),
    "hitouts":  ("game", "Hit.Outs", "HITOUTS", "{:.0f}"),
    "si":       ("adv", "Score_Involvements_Actual", "SCORE INVOLVEMENTS", "{:.0f}"),
    "metres":   ("adv", "Metres_Gained", "METRES GAINED", "{:.0f}"),
    "int":      ("adv", "Intercepts", "INTERCEPTS", "{:.0f}"),
    "tog":      ("adv", "Time_On_Ground_Pct", "TIME ON GROUND", "{:.0f}%"),
}

# player, RAW AFLTables Round_num (one ahead of the round the world uses in
# 2026), and the six stat cells. Slots 0, 3 and 4 are the fixed anchors. The
# TIER IS NOT DECLARED HERE; tier_for derives it from the price.
#
# TWO PER BAND, AND THE TWO ARE THE TWO BIGGEST EDGES IN IT
# Re-chosen 19 September 2026 off sb_3vote_board.csv, after the tiers moved to
# price bands. The old six were picked by hand and came out one safe, four
# value and one longshot under the new rule, which is a tier scale with nothing
# in most of it. The rule now is mechanical: drop `is_other` and `suspect`,
# require the board's floor of at least a 15% chance and at least +15% on the
# model, then take the top two by edge in each of the three bands. Mechanical
# because the deck's whole claim is the edge, and a hand-picked six invites
# exactly the question the deck cannot answer.
#
# WHAT IT COST, STATED SO IT IS NOT DISCOVERED LATER
# Heeney round 23 (+85%) and Ashcroft round 17 (+61%) leave the deck. Both are
# $2.30, so both are VALUE now, and both are beaten inside that band by Daniel
# (+486%) and Dempsey (+248%). Nothing was dropped that its own band kept.
PICKS = [
    dict(key="balta", name="Noah Balta", rn=9,
         cells=["disp", "cp", "hitouts", "si", "cv", "goals"]),
    dict(key="cripps", name="Patrick Cripps", rn=12,
         cells=["disp", "cp", "clear", "si", "cv", "tackles"]),
    dict(key="daniel", name="Caleb Daniel", rn=5,
         cells=["disp", "marks", "reb", "si", "cv", "metres"]),
    dict(key="dempsey", name="Oliver Dempsey", rn=23,
         cells=["disp", "goals", "mi50", "si", "cv", "tog"]),
    dict(key="papley", name="Tom Papley", rn=5,
         cells=["disp", "goals", "ga", "si", "cv", "mi50"]),
    dict(key="cameron", name="Darcy Cameron", rn=12,
         cells=["disp", "cp", "hitouts", "si", "cv", "clear"]),
]


# ------------------------------------------------------------------ data
def build():
    """Each pick, with its price, its model chance and its six figures."""
    board = pd.read_csv(BOARD)
    g = pd.read_csv(GAME_LEVEL, low_memory=False).drop_duplicates(
        subset=["Game_ID", "Player_Name"])
    adv = pd.read_csv(SI_PATH)
    adv = adv[adv.Season == SEASON]

    out = []
    for p in PICKS:
        row = board[(board.sel == p["name"]) & (board.rn == p["rn"])]
        if len(row) != 1:
            raise SystemExit(f"{p['name']} round {p['rn']}: {len(row)} board rows, "
                             "re-run scripts/sb_3vote_board.py")
        row = row.iloc[0]
        gm = g[(g.Player_Name == p["name"]) & (g.Round_num == p["rn"])]
        if len(gm) != 1:
            raise SystemExit(f"{p['name']} round {p['rn']}: {len(gm)} game_level rows")
        gm = gm.iloc[0]
        av = adv[(adv.Round_num == p["rn"]) & (adv.ID == gm.ID)]
        av = av.iloc[0] if len(av) == 1 else None

        cells = []
        for key in p["cells"]:
            src, col, label, fmt = STATS[key]
            if src == "adv":
                if av is None:
                    raise SystemExit(f"{p['name']} round {p['rn']}: no advanced row "
                                     f"for {label}")
                val = av[col]
            else:
                val = gm[col]
            cells.append((fmt.format(float(val)), label))

        rnd, fix = f"Round {int(row.disp_round)}", f"v {row.opponent}"
        out.append(dict(
            key=p["key"], name=p["name"], club=str(gm["Playing.for"]),
            tier=tier_for(row.odds), round=rnd, fixture=fix,
            price=f"${row.odds:,.2f}",
            fair=f"${row.fair:,.2f}", model=float(row.p),
            implied=1.0 / float(row.odds), cells=cells,
            # The market's wording, carried on the pick so draw_slide and
            # draw_cover serve any market deck. See tiktok_placings.py.
            mast="TO POLL 3 VOTES", lead=rnd, qual=fix,
            note=("TO POLL", "THE 3 VOTES"),
            # Lowercase "v" in the fixture, as everywhere else in the repo.
            # fix is "v Opponent", so upper-casing it whole reads "V ESSENDON".
            cover_label=((f"{rnd.upper()} v {str(row.opponent).upper()}")
                         if NO_ODDS else
                         (f"{TIER_LABEL[tier_for(row.odds)]}  ·  "
                          f"{rnd.upper()} v {str(row.opponent).upper()}")),
        ))
    return out


# ------------------------------------------------------------------ drawing
def wash(img, club, bot):
    """The club colour, bleeding off the top of the frame, with a soft light.

    Bleeds rather than starting at SAFE_TOP because the top of the frame is the
    part TikTok crops: losing the empty head of a gradient costs nothing, and
    uncropped the slide still reads as full bleed.
    """
    acc = accent(club, lift=0.30).lstrip("#")
    r, g, b = (int(acc[i:i + 2], 16) for i in (0, 2, 4))
    br, bg_, bb = (int(BG.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    grad = Image.new("RGB", (1, bot))
    px = grad.load()
    for i in range(bot):
        t = (i / (bot - 1)) ** 1.5
        px[0, i] = (int(r + (br - r) * t), int(g + (bg_ - g) * t), int(b + (bb - b) * t))
    img.paste(grad.resize((img.width, bot)), (0, 0))
    glow = Image.new("L", (img.width, bot), 0)
    ImageDraw.Draw(glow).ellipse([img.width * 0.12, bot * 0.20,
                                  img.width * 0.88, bot * 1.05], fill=110)
    img.paste(Image.new("RGB", (img.width, bot), accent(club, lift=0.52)), (0, 0),
              glow.filter(ImageFilter.GaussianBlur(70 * S)))


def place_cut(img, path, top, bot, headroom=0.94):
    """Bottom-aligned cutout, trimmed to its own alpha before scaling.

    The source is a 1080 square with the figure floating in it, so scaling the
    file rather than its content leaves the player small and high. getbbox on
    the alpha channel is what makes every player fill the band identically.
    """
    im = Image.open(path).convert("RGBA")
    im = im.crop(im.split()[-1].getbbox() or (0, 0, im.width, im.height))
    band = int((bot - top) * headroom)
    im = im.resize((max(1, round(im.width * band / im.height)), band), Image.LANCZOS)
    img.paste(im, ((img.width - im.width) // 2, bot - band), im)


def _rgb(h):
    h = str(h).lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def trim_cut(name, height):
    """The AFL cutout for a player, trimmed to its own alpha and scaled.

    The same trim place_cut does, returned rather than pasted, for the callers
    that need to position, dim, silhouette or fade the figure themselves.
    """
    path = head(name)
    if not path:
        return None
    im = Image.open(path).convert("RGBA")
    im = im.crop(im.getchannel("A").getbbox() or (0, 0, im.width, im.height))
    sc = height / im.height
    return im.resize((max(1, round(im.width * sc)), height), Image.LANCZOS)


def fade_alpha(cut, keep=0.80):
    """Ramp a cutout's own alpha to nothing over its last stretch.

    A cutout is square-cropped at the chest, so a figure that ends above the
    frame ends on a straight line. Painting a gradient OVER it does not fix
    that: the gradient does not know where the shoulders are, and what shows
    is the rectangle. Fading the alpha itself is what makes it end in air.
    """
    h = cut.height
    ramp = Image.new("L", (1, h))
    px, k0 = ramp.load(), int(h * keep)
    for i in range(h):
        px[0, i] = 255 if i < k0 else max(0, int(255 * (1 - (i - k0) / (h - k0))))
    return Image.merge("RGBA", (*cut.split()[:3],
                                ImageChops.multiply(cut.getchannel("A"),
                                                    ramp.resize((cut.width, h)))))


def soft_glow(img, cx, cy, rx, ry, colour, alpha=140, blur=90):
    """A blurred elliptical wash, composited under whatever is drawn next."""
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=alpha)
    img.paste(Image.new("RGB", img.size, colour), (0, 0),
              mask.filter(ImageFilter.GaussianBlur(blur)))


def cut_shadow(img, cut, x, y, spread=26, alpha=170):
    """A dark halo behind a cutout, so a figure separates from its field."""
    a = cut.getchannel("A").filter(ImageFilter.GaussianBlur(spread))
    img.paste(Image.new("RGB", cut.size, "#04070b"), (x, y + spread // 2),
              a.point(lambda v: int(v * alpha / 255)))


def vgrad(img, top, bottom, colour, a0, a1, power=1.0):
    """A vertical wash from a0 to a1 alpha, eased. Composited rather than
    drawn: a stack of 1px rectangles bands visibly on the emerald."""
    h = max(1, bottom - top)
    mask = Image.new("L", (1, h))
    px = mask.load()
    for i in range(h):
        t = (i / (h - 1)) ** power if h > 1 else 1
        px[0, i] = int(a0 + (a1 - a0) * t)
    img.paste(Image.new("RGB", (img.width, h), colour), (0, top),
              mask.resize((img.width, h)))


def backdrop(img, cx, cy, tint="#14332c"):
    """Light the whole frame, so no region of it is left flat.

    TikTok centre-crops a carousel image, which is why every layout here keeps
    what a reader must see between SAFE_TOP and SAFE_BOT. The covers used to
    answer that by leaving the 420px above and below as bare #0a1017, which
    uncropped reads as a band of content floating in a black rectangle. Tone
    costs nothing when it is cropped away and saves the slide when it is not.

    GOLD IS A TOKEN FOR FIGURES, NOT A WASH. A gold-tinted field was tried
    first, on the reasoning that gold is the Betting Hub's colour. Spread over
    a whole frame at any alpha that registers, #f0b429 reads as brown and
    takes the palette with it.
    """
    soft_glow(img, cx, cy, int(W * 0.66 * S), int(H * 0.32 * S), tint, 140, 140 * S)
    soft_glow(img, cx, cy - 80 * S, 300 * S, 320 * S, _rgb(EMERALD), 30, 180 * S)
    vgrad(img, int(H * 0.74 * S), H * S, "#05090e", 0, 215, 1.5)
    vgrad(img, 0, int(H * 0.22 * S), "#05090e", 195, 0, 0.8)


def blur_text(img, xy, txt, fnt, fill, radius, anchor="la", gain=2.1):
    """Text rendered and then blurred out, for a cover that carries a row
    without naming it.

    Drawn into a tile the size of its own bbox rather than onto a full canvas
    layer, because the canvas is 2160x3840 and this runs once per row.

    `gain` lifts the alpha back after the blur. Without it a blurred glyph is
    not an obscured name, it is a faint one: Gaussian spreads the same ink
    over a larger area, so the peak drops and the row reads as washed out
    rather than as deliberately hidden.
    """
    k = ImageDraw.Draw(img)
    box = k.textbbox(xy, txt, font=fnt, anchor=anchor)
    pad = int(radius * 3)
    x0, y0 = int(box[0]) - pad, int(box[1]) - pad
    w, h = int(box[2] - box[0]) + pad * 2, int(box[3] - box[1]) + pad * 2
    if w <= 0 or h <= 0:
        return
    tile = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(tile).text((xy[0] - x0, xy[1] - y0), txt, font=fnt, fill=fill,
                              anchor=anchor)
    tile = tile.filter(ImageFilter.GaussianBlur(radius))
    a = tile.getchannel("A").point(lambda v: min(255, int(v * gain)))
    tile.putalpha(a)
    img.paste(tile, (x0, y0), tile)


def prob_bar(k, x0, x1, y, model, implied, h=12):
    """The model's chance filled, the price's chance as a gold tick.

    The tick sits INSIDE the emerald fill whenever the model is ahead of the
    price, which is every pick that makes a deck, so it carries a dark outline
    or it disappears into the thing it is meant to be measured against.
    """
    k.rectangle([x0, y, x1, y + h * S], fill=BAR)
    k.rectangle([x0, y, x0 + int((x1 - x0) * model), y + h * S], fill=EMERALD)
    if NO_ODDS:
        return          # the tick IS the price; odds-free there is none
    t = x0 + int((x1 - x0) * implied)
    k.rectangle([t - 4 * S, y - 7 * S, t + 4 * S, y + h * S + 7 * S], fill=BG)
    k.rectangle([t - 2 * S, y - 5 * S, t + 2 * S, y + h * S + 5 * S], fill=GOLD)


def rg_line(k, x, y):
    """The 18+ line, on the COVER and not only on the closer.

    The closer is the slide a follower reaches; the cover is the slide that
    reaches everyone else, and it is the one carrying six dollar figures.
    """
    k.text((x, y), "18+  GAMBLE RESPONSIBLY", font=font("display", 20), fill=MUTED)


def pill(k, x, y, txt, colour, size=24, padx=16, pady=10):
    """Filled for safe and value, gold outline for the longshot.

    Midnight Turf has emerald and gold and nothing else that is not a loss, so
    the third tier gets a different treatment rather than a third hue.
    """
    f = font("display", size)
    w = k.textlength(txt, font=f)
    box = [x, y, x + w + padx * 2 * S, y + size * S * 1.15 + pady * 2 * S]
    if colour is None:
        k.rounded_rectangle(box, radius=int(6 * S), outline=GOLD, width=max(2, 2 * S))
        k.text((x + padx * S, y + pady * S), txt, font=f, fill=GOLD)
    else:
        k.rounded_rectangle(box, radius=int(6 * S), fill=colour)
        k.text((x + padx * S, y + pady * S), txt, font=f, fill=BG)


def masthead(img, k, m, right, label):
    draw_mark(img, m, (SAFE_TOP + 18) * S, 27)
    k.text((right, (SAFE_TOP + 24) * S), label, font=font("display", 24),
           fill="#dce4ea", anchor="ra")


def stat_grid(k, m, right, y, cells, row_gap=92, vsize=46):
    """Two rows of three, one grid, so the columns line up down the whole deck."""
    cw = (right - m) / 3
    for i, (val, label) in enumerate(cells):
        cx = m + cw * (i % 3)
        yy = y + (i // 3) * row_gap * S
        k.text((cx, yy), val, font=font("fig", vsize), fill=INK)
        k.text((cx, yy + 54 * S), label, font=font("display", 18), fill=MUTED)


def _fixture_upper(t):
    """Upper-case, but keep a leading fixture "v" lower.

    `qual` is "v Essendon" on a market slide and "MODEL RANK 19TH" on a
    placings one, so this runs on both. Upper-casing the whole string gives
    "V ESSENDON", which is not how a fixture is written anywhere else in the
    repo, and since the cover now sets the same fixture properly the two
    disagreed on one deck.
    """
    t = str(t)
    return "v " + t[2:].upper() if t[:2] == "v " else t.upper()


def draw_slide(p):
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = M * S, (W - M) * S
    acc = accent(p["club"])
    soft = None

    wash(img, p["club"], CUT_BOT * S)
    photo = head(p["name"])
    if photo:
        with Image.open(photo) as im:
            soft = (CUT_BOT - CUT_TOP) * S * 0.94 / im.height / S
        place_cut(img, photo, CUT_TOP * S, CUT_BOT * S)
    else:
        k.text((W * S // 2, (CUT_TOP + CUT_BOT) // 2 * S), _initials(p["name"]),
               font=font("display", 120), fill=INK, anchor="mm")
    k.line([0, CUT_BOT * S, W * S, CUT_BOT * S], fill=LINE, width=max(1, S))

    masthead(img, k, m, right, p["mast"])
    # The tier is betting language, so odds-free the chip carries the model's
    # own chance instead. It keeps the slide's shape and says something true.
    if NO_ODDS:
        pill(k, m, (CUT_BOT - 74) * S, "MODEL %.0f%%" % (p["model"] * 100),
             EMERALD)
    else:
        pill(k, m, (CUT_BOT - 74) * S, TIER_LABEL[p["tier"]], TIER_COL[p["tier"]])

    nm = p["name"].upper()
    k.text((m, 978 * S), nm, font=fit_font(k, nm, "name", 66, right - m), fill=INK)

    # THE ROUND LEADS THE FIXTURE LINE. A carousel slide is read out of order and
    # out of context, so which game this is has to survive alone; the opponent is
    # the qualifier behind it, and the club is on the jumper and in the wash.
    # On a placings slide the board leads instead, for the same reason.
    rf = font("display", 38)
    k.text((m, 1052 * S), p["lead"].upper(), font=rf, fill=INK)
    rw = k.textlength(p["lead"].upper(), font=rf)
    k.text((m + rw + 20 * S, 1062 * S), _fixture_upper(p["qual"]),
           font=font("display", 24), fill=acc)

    # THE HERO FIGURE IS THE PRICE, OR THE MODEL'S CHANCE WHERE THERE IS NONE.
    # Emerald rather than gold odds-free: gold is the Betting Hub's token and
    # a big gold figure reads as a price even when it carries a % sign.
    hero = ("%.0f%%" % (p["model"] * 100)) if NO_ODDS else p["price"]
    k.text((m, 1112 * S), hero, font=font("fig", 100),
           fill=EMERALD if NO_ODDS else GOLD)
    fw = k.textlength(hero, font=font("fig", 100))
    for i, ln in enumerate(p["note"]):
        k.text((m + fw + 24 * S, (1132 + i * 34) * S), ln, font=font("display", 25),
               fill=INK)

    y, bh = 1248 * S, 16 * S
    k.rectangle([m, y, right, y + bh], fill=BAR)
    span = right - m
    k.rectangle([m, y, m + int(span * p["model"]), y + bh], fill=EMERALD)
    if NO_ODDS:
        # No tick and no second label: the tick IS the price, and the whole
        # point of the mode is that the market is not on the slide.
        k.text((m, y + bh + 12 * S), "MODEL CHANCE",
               font=font("display", 23), fill=EMERALD)
    else:
        tick = m + int(span * p["implied"])
        k.rectangle([tick - 2 * S, y - 8 * S, tick + 2 * S, y + bh + 8 * S],
                    fill=GOLD)
        k.text((m, y + bh + 12 * S), "MODEL %.0f%%" % (p["model"] * 100),
               font=font("display", 23), fill=EMERALD)
        k.text((right, y + bh + 12 * S),
               "PRICE IMPLIES %.0f%%" % (p["implied"] * 100),
               font=font("display", 23), fill=GOLD, anchor="ra")

    stat_grid(k, m, right, 1336 * S, p["cells"])
    return img, soft


# THE COVER NAMES NOBODY, AND THAT IS THE WHOLE DESIGN
# A slip: one row per pick carrying the club colour, the game, the price and
# the model-against-market bar, with the NAME BLURRED OUT of every one. A
# cover that lists the six answers the deck before it is swiped, and the names
# are the only thing on it a reader cannot work out for himself.
#
# It also solves what the old cover was avoiding rather than answering. That
# one carried no face at all, on the reasoning that a market deck opening on
# one man reads as a tip on that man, and paid for it with a blurred gradient
# over six bare prices. A blurred slip keeps the reason and loses the price
# grid: nobody is being tipped, because nobody is named.
COVER_TITLE_1, COVER_TITLE_1_CLEAN = "BROWNLOW BETS", "THE BROWNLOW MODEL"
# 0.30 of the cap height. Below about 0.22 a name is still readable at full
# size, which defeats the point on the one surface that gets screenshotted.
# The gain is the alpha lifted back after the blur: under about 2 the row
# reads as faded rather than hidden, and by 3.2 it has flattened into a solid
# bar and stopped reading as a name at all.
NAME_BLUR, NAME_BLUR_GAIN = 0.30, 2.6


def draw_cover(picks, sub="TO POLL 3 VOTES"):
    """The six as a slip, with every name blurred out.

    Shared with tiktok_placings.py, which passes its own `sub` and puts its own
    wording in each pick's `cover_label`. Nothing here is market specific.
    """
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = M * S, (W - M) * S

    backdrop(img, int(W * 0.30 * S), 820 * S)

    # One figure behind the slip, as a silhouette rather than a face: this
    # cover withholds identity, and a readable face on it contradicts six
    # blurred names. Faded LATE, because the slip's own top edge already cuts
    # the figure at the chest and an early fade left a head with no shoulders.
    c = trim_cut(picks[-1]["name"], 560 * S) if picks else None
    if c:
        c = fade_alpha(c, 0.88)
        a = c.getchannel("A")
        x, y = int(W * 0.76 * S) - c.width // 2, 430 * S
        img.paste(Image.new("RGB", c.size, GOLD), (x, y),
                  a.filter(ImageFilter.GaussianBlur(11 * S))
                   .point(lambda v: int(v * 0.30)))
        img.paste(Image.new("RGB", c.size, "#0c1620"), (x, y), a)

    masthead(img, k, m, right, f"{SEASON} MODEL")
    title = COVER_TITLE_1_CLEAN if NO_ODDS else COVER_TITLE_1
    tf = min((fit_font(k, ln, "display", 76, int(W * 0.56 * S) - m)
              for ln in (title, sub)), key=lambda f: f.size)
    k.text((m, (SAFE_TOP + 58) * S), title, font=tf, fill=INK)
    k.text((m, (SAFE_TOP + 138) * S), sub, font=tf,
           fill=EMERALD if NO_ODDS else GOLD)

    # The slip. Cha Ching's card and not a bookmaker's: the book is named as
    # the price source in the footer, exactly as the slides name it.
    x0, y0, x1, y1 = m, 764 * S, right, 1432 * S
    k.rectangle([x0, y0, x1, y1], fill="#0c141c", outline=LINE, width=max(1, 2 * S))
    k.rectangle([x0, y0, x1, y0 + 54 * S], fill="#121d28")
    k.text((x0 + 22 * S, y0 + 27 * S), "SELECTION", font=font("display", 22),
           fill=MUTED, anchor="lm")
    k.text((x1 - 22 * S, y0 + 27 * S),
           "MODEL CHANCE" if NO_ODDS else "PRICE  ·  MODEL v MARKET",
           font=font("display", 22), fill=MUTED, anchor="rm")

    ry, pitch = y0 + 54 * S, 92 * S
    for i, p in enumerate(picks):
        y = ry + i * pitch
        if i:
            k.line([x0 + 18 * S, y, x1 - 18 * S, y], fill=LINE, width=max(1, S))
        k.rectangle([x0, y + 20 * S, x0 + 5 * S, y + 62 * S], fill=accent(p["club"]))
        nm = p["name"].upper()
        nf = fit_font(k, nm, "display", 28, 330 * S)
        blur_text(img, (x0 + 26 * S, y + 22 * S), nm, nf, INK,
                  max(2, round(nf.size * NAME_BLUR)), gain=NAME_BLUR_GAIN)
        lab = p["cover_label"]
        k.text((x0 + 26 * S, y + 58 * S), lab,
               font=fit_font(k, lab, "display", 19, 420 * S), fill=MUTED)
        fig = ("%.0f%%" % (p["model"] * 100)) if NO_ODDS else p["price"]
        k.text((x1 - 22 * S, y + 20 * S), fig, font=font("fig", 40),
               fill=EMERALD if NO_ODDS else GOLD, anchor="ra")
        prob_bar(k, x1 - 272 * S, x1 - 22 * S, y + 70 * S, p["model"],
                 p["implied"], h=9)

    k.text((x0 + 22 * S, y1 - 34 * S),
           f"{SEASON} MODEL PROJECTION" if NO_ODDS else f"PRICES {BOOK}",
           font=font("display", 19), fill=MUTED, anchor="lm")
    k.text((x1 - 22 * S, y1 - 34 * S), "SWIPE FOR THE NAMES",
           font=font("display", 19), fill=EMERALD, anchor="rm")

    if not NO_ODDS:
        rg_line(k, m, 1466 * S)
    k.text((right, 1466 * S), "SWIPE", font=font("display", 26), fill=EMERALD,
           anchor="ra")
    return img


CLOSER_LINES = ("THE MODEL SCORED ALL 207",
                "GAMES, THEN PRICED EVERY",
                "RUNNER AGAINST THE BOOK.",
                "NO 2026 VOTE IS PUBLIC",
                f"UNTIL THE COUNT ON {COUNT_DATE.split()[-2].upper()} "
                f"{COUNT_DATE.split()[-1].upper()}.")
CLOSER_LINES_CLEAN = ("THE MODEL SCORED ALL 207",
                      "GAMES OF THE SEASON, THEN",
                      "RANKED EVERY PLAYER IN THEM.",
                      "NO 2026 VOTE IS PUBLIC",
                      f"UNTIL THE COUNT ON {COUNT_DATE.split()[-2].upper()} "
                      f"{COUNT_DATE.split()[-1].upper()}.")


def draw_closer(lines=CLOSER_LINES):
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = M * S, (W - M) * S
    masthead(img, k, m, right, f"{SEASON} MODEL")
    k.line([m, (SAFE_TOP + 74) * S, right, (SAFE_TOP + 74) * S], fill=LINE,
           width=max(1, S))

    # WHAT THESE PRICES ARE AND ARE NOT. The slides carry a dollar figure, so
    # the one piece of prose on the deck has to say where it came from and that
    # no vote is public yet.
    for i, ln in enumerate(lines):
        k.text((m, (SAFE_TOP + 116 + i * 48) * S), ln, font=font("display", 32),
               fill=INK)

    fx0, fy0, fw = m, 792 * S, right - m
    # Without the screenshot the domain would sit straight under the prose and
    # leave the bottom two thirds of the frame empty. Place it where the frame
    # would have ended so the slide keeps its balance.
    below = fy0 if not NO_ODDS else 1290 * S
    # THE SITE SCREENSHOT IS ITSELF ODDS. _site_hero.jpg captures the landing
    # page, and the landing page carries a BEST ODDS figure and a price ticker.
    # Removing every dollar sign from the layout and then pasting a photograph
    # of one in the middle of it is the kind of miss that only shows up by
    # looking at the rendered slide, which is how this one was caught.
    if os.path.exists(SITE_SHOT) and not NO_ODDS:
        sh = 470 * S
        shot = Image.open(SITE_SHOT).convert("RGB")
        sc = max(fw / shot.width, sh / shot.height)
        nw, nh = round(shot.width * sc), round(shot.height * sc)
        shot = shot.resize((nw, nh), Image.LANCZOS)
        cx = min(max(int(nw * 0.50 - fw / 2), 0), nw - fw)
        cy = min(max(int(nh * 0.44 - sh / 2), 0), nh - sh)
        shot = shot.crop((cx, cy, cx + fw, cy + sh))
        bar = 46 * S
        k.rectangle([fx0, fy0, fx0 + fw, fy0 + bar + sh], fill=PANEL, outline=LINE,
                    width=max(1, 2 * S))
        for d in range(3):
            ccx = fx0 + (24 + d * 24) * S
            k.ellipse([ccx - 5 * S, fy0 + bar // 2 - 5 * S,
                       ccx + 5 * S, fy0 + bar // 2 + 5 * S], fill=LINE)
        k.text((fx0 + fw // 2, fy0 + bar // 2), DOMAIN, font=font("body", 22),
               fill=MUTED, anchor="mm")
        img.paste(shot, (fx0, fy0 + bar))
        k.rectangle([fx0, fy0, fx0 + fw, fy0 + bar + sh], outline=LINE,
                    width=max(1, 2 * S))
        below = fy0 + bar + sh + 56 * S

    dom = DOMAIN.upper()
    k.text((m, below), dom, font=fit_font(k, dom, "display", 58, right - m),
           fill=EMERALD)
    # Not ours to drop on a deck carrying prices, and wrong to carry on one
    # that is not: see NO_ODDS.
    if not NO_ODDS:
        k.text((m, (SAFE_BOT - 34) * S), "18+  GAMBLE RESPONSIBLY",
               font=font("display", 24), fill=MUTED)
    return img


# ------------------------------------------------------------------ copy
def caption(picks):
    """Templated, like every other draft in this repo, and for the same reason:
    a templated post cannot invent an accuracy claim under time pressure."""
    if NO_ODDS:
        out = [
            f"The model scored all 207 games of the {SEASON} season. These "
            f"{len(picks)} had the best chance of the 3 votes.",
            "",
            "Every home and away game went through the model, which then "
            "gave each player in each one his chance of polling the 3.",
            "",
        ]
        # No tier prefix: SAFE and LONGSHOT are betting words. Ordered as the
        # deck is, so the caption and the swipe agree.
        for p in picks:
            out.append(f"{p['name']}, {p['round'].lower()} {p['fixture']}, "
                       f"{p['model'] * 100:.0f}%")
        out += [""]
    else:
        out = [
            "The model priced all 207 games. Here are six runners to poll "
            "the 3 votes.",
            "",
            f"{tier_split(picks).capitalize()}. Every home and away game of "
            f"the {SEASON} season went through the model, then each runner's "
            "chance of the 3 was set against what the book is paying.",
            "",
        ]
        for p in picks:
            out.append(f"{TIER_LABEL[p['tier']].lower()}: {p['name']}, "
                       f"{p['round'].lower()} {p['fixture']}, {p['price']} "
                       f"({BOOK.title()}), model {p['model'] * 100:.0f}%")
        out += [""]
    if NO_ODDS:
        # No responsible-gambling block, and that is deliberate rather than an
        # omission: on a post with no market on it, the 18+ line is a signal
        # that the post is about betting. See NO_ODDS.
        out += [
            "The bar on each slide is the model's chance of the 3 votes in "
            "that game, from the same simulation.",
            "",
            "This is a model, not a leak: no "
            f"{SEASON} vote is public until the count on {COUNT_DATE}.",
            "",
            f"The full board, every player and every game, is at {DOMAIN}.",
            "",
            "Which one has the model got wrong?",
        ]
        return "\n".join(out)
    out += [
        "The bar on each slide is the model's chance against the chance the "
        "price implies. The gap between them is the whole reason the pick is "
        "on the list.",
        "",
        "Two things said plainly. This is a model, not a leak: no "
        f"{SEASON} vote is public until the count on {COUNT_DATE}. And prices "
        "move, so check the current one before you act on any of this.",
        "",
        f"The full board, every player and every game, is at {DOMAIN}.",
        "",
        "18+. Gamble responsibly. Set a deposit limit. Think. Is this a bet "
        "you really want to place? For free and confidential support call "
        "1800 858 858 or visit gamblinghelponline.org.au.",
        "",
        "Which one is the model wrong about?",
    ]
    return "\n".join(out)


def hashtags(picks):
    base = ["#brownlow", "#brownlowmedal", f"#brownlow{SEASON}", "#afl",
            f"#afl{SEASON}", "#aflfooty", "#footy", "#aussierules",
            "#aflpredictions", "#brownlowpredictions", "#sportsanalytics"]
    tags = list(base)
    for p in picks:
        t = "#" + "".join(ch for ch in p["name"].lower() if ch.isalnum())
        if t not in tags:
            tags.append(t)
    return " ".join(tags)


def write_copy(picks, paths, softs):
    cap, tags = caption(picks), hashtags(picks)
    out = [f"# TikTok carousel, to poll the 3 votes, {SEASON}", "",
           "## Caption", "", "```", cap, "", tags, "```", "",
           f"{caption_len(cap, tags)} characters including hashtags. "
           "TikTok's limit is 2,200.", "", "## Slides", "",
           "| # | File | Player | Round | Price | Model | Fair |",
           "|---|---|---|---|---|---|---|"]
    for i, p in enumerate(picks):
        out.append(f"| {i + 2} | `{os.path.basename(paths[i + 1])}` | {p['name']} | "
                   f"{p['round']} {p['fixture']} | {p['price']} | "
                   f"{p['model'] * 100:.0f}% | {p['fair']} |")
    out += ["", f"Slide 1 is the cover, slide {len(picks) + 2} is the closer.", "",
            "## Before posting", "",
            f"- **Re-check the prices.** They were read off {BOOK.title()} when "
            "`sb_3vote_board.py` last ran, and 101 of 1,150 selections moved in "
            "the 24 hours before this deck was first built. A card showing a "
            "price the book is no longer offering is the one error here that "
            "cannot be walked back after posting.",
            "- **No 2026 Brownlow vote is public until the count.** Every slide "
            "carries the model label in the masthead; do not crop it off.",
            "- **This is the first Cha Ching post carrying prices.** The closer "
            "carries the 18+ line and the caption carries the help line. TikTok "
            "may restrict reach on the post regardless.",
            "- **The model chance is the within-game fitted P(3).** It is the "
            "one Brownlow market that needed no calibration layer in the "
            "backtest. It is still a model output and it shares the model's "
            "errors; the deck claims no accuracy figure and must not start.",
            "- Round numbers on the slides are the AFL's, one behind the raw "
            "AFLTables number the CSVs carry.",
            f"- Everything a reader must see sits between y {SAFE_TOP} and "
            f"y {SAFE_BOT}, because TikTok centre-crops a carousel image."]
    for n, sc in softs:
        out.append(f"- {n}'s headshot is upscaled {sc:.1f} times and will look "
                   f"soft on a phone.")
    path = os.path.join(REPO, "drafts", f"tiktok_3votes_{SEASON}{'_noodds' if NO_ODDS else ''}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    return path


SLIDE_RE = r"^\d{2}_.+\.png$"


TIKTOK_CAPTION_MAX = 2200


def caption_len(cap, tags):
    """Length including hashtags, and a LOUD warning when it will not fit.

    Every deck printed this number and none of them checked it. The placings
    deck went to nine picks and the caption to 2,562, and the draft file
    reported the figure beside the limit in the same calm sentence it always
    had. TikTok truncates rather than refusing, so the part that gets cut is
    the end: the responsible-gambling line and the help number.
    """
    n = len(cap) + len(tags) + 2
    if n > TIKTOK_CAPTION_MAX:
        print(f"  WARNING: caption is {n} characters against TikTok's "
              f"{TIKTOK_CAPTION_MAX}. It will be TRUNCATED, and the 18+ and "
              f"help lines are at the end. Cut {n - TIKTOK_CAPTION_MAX}.")
    return n


def prune(dirs, keep, pattern=SLIDE_RE):
    r"""Remove slide files that this build did not just write.

    THE TIER IS IN THE FILENAME AND THE TIER NOW MOVES. A slide is written as
    `<n>_<tier>_<key>.png`, so a price crossing a band renames it and a
    re-picked leg renumbers every slide after it. Nothing removed the old
    file, so one re-pick left five stale slides sitting in the phone's picker
    beside the six real ones, all of them looking equally current. Posting
    yesterday's price is the one mistake on a priced deck that cannot be
    walked back afterwards.

    `keep` is the set of basenames this build wrote. Only files matching the
    deck's own numbered pattern, in the deck's own folder, are considered, so
    a sibling deck's files and anything a human put there are never touched.
    The poll deck shares PHONE_DIR with this one and is told apart by its
    `poll_` prefix, which is why the pattern is a parameter: `^\d{2}_` does
    not match `poll_02_...`, and the prefixed pattern does not match this
    deck's.

    NEVER CALL THIS AFTER A PARTIAL BUILD. `--only` renders a single slide,
    and pruning against that would delete the whole rest of the deck.
    """
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for b in sorted(os.listdir(d)):
            if b in keep or not re.match(pattern, b):
                continue
            os.remove(os.path.join(d, b))
            print(f"  pruned stale slide: {os.path.join(os.path.basename(d), b)}")


def save(img, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.resize((W, H), Image.LANCZOS).save(path, "PNG", optimize=True)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="render one pick by key, or 'cover' / 'closer'")
    ap.add_argument("--no-phone", action="store_true",
                    help="skip the copy into the OneDrive folder")
    add_no_odds_arg(ap)
    a = ap.parse_args()
    os.chdir(REPO)

    set_no_odds(a.no_odds)
    out_dir, phone_dir = odds_paths(OUT_DIR, PHONE_DIR)
    picks = order_picks(build())
    paths, softs = [], []

    if a.only:
        one = [p for p in picks if p["key"] == a.only]
        if a.only == "cover":
            print(save(draw_cover(picks), os.path.join(out_dir, "01_cover.png")))
        elif a.only == "closer":
            print(save(draw_closer(CLOSER_LINES_CLEAN if NO_ODDS else CLOSER_LINES), os.path.join(out_dir, "99_closer.png")))
        elif one:
            img, _ = draw_slide(one[0])
            print(save(img, os.path.join(out_dir, f"only_{a.only}.png")))
        else:
            raise SystemExit(f"no pick keyed {a.only!r}; "
                             f"have {[p['key'] for p in picks]}")
        return

    paths.append(save(draw_cover(picks), os.path.join(out_dir, "01_cover.png")))
    for i, p in enumerate(picks):
        img, soft = draw_slide(p)
        paths.append(save(img, os.path.join(
            out_dir, slide_stem(p, i + 2) + ".png")))
        if soft and soft > 1.8:
            softs.append((p["name"], soft))
    paths.append(save(draw_closer(CLOSER_LINES_CLEAN if NO_ODDS else CLOSER_LINES), os.path.join(out_dir, f"{len(picks) + 2:02d}_closer.png")))

    copy = write_copy(picks, paths, softs)
    keep = {os.path.basename(x) for x in paths}
    prune([out_dir], keep)
    print(f"  {len(paths)} slides to {out_dir}")
    print(f"  copy: {copy}")

    if not a.no_phone:
        os.makedirs(phone_dir, exist_ok=True)
        for p in paths:
            shutil.copy2(p, os.path.join(phone_dir, os.path.basename(p)))
        prune([phone_dir], keep)
        print(f"  copied to {phone_dir}")


if __name__ == "__main__":
    main()
