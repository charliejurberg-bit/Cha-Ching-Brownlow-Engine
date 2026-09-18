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
import shutil
import sys

import pandas as pd
from PIL import Image, ImageDraw, ImageFilter

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
    "si":       ("adv", "Score_Involvements_Actual", "SCORE INVOLVEMENTS", "{:.0f}"),
    "metres":   ("adv", "Metres_Gained", "METRES GAINED", "{:.0f}"),
    "int":      ("adv", "Intercepts", "INTERCEPTS", "{:.0f}"),
    "tog":      ("adv", "Time_On_Ground_Pct", "TIME ON GROUND", "{:.0f}%"),
}

# player, RAW AFLTables Round_num (one ahead of the round the world uses in
# 2026), tier, and the six stat cells. Slots 0, 3 and 4 are the fixed anchors.
PICKS = [
    dict(key="heeney", name="Isaac Heeney", rn=24, tier="SAFE",
         cells=["disp", "cp", "clear", "si", "cv", "goals"]),
    dict(key="cripps", name="Patrick Cripps", rn=12, tier="SAFE",
         cells=["disp", "cp", "clear", "si", "cv", "tackles"]),
    dict(key="ashcroft", name="Will Ashcroft", rn=18, tier="SAFE",
         cells=["disp", "cp", "clear", "si", "cv", "metres"]),
    dict(key="daniel", name="Caleb Daniel", rn=5, tier="VALUE",
         cells=["disp", "marks", "reb", "si", "cv", "metres"]),
    dict(key="dempsey", name="Oliver Dempsey", rn=23, tier="VALUE",
         cells=["disp", "goals", "mi50", "si", "cv", "tog"]),
    dict(key="papley", name="Tom Papley", rn=5, tier="LONGSHOT",
         cells=["disp", "goals", "ga", "si", "cv", "mi50"]),
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
            tier=p["tier"], round=rnd, fixture=fix, price=f"${row.odds:,.2f}",
            fair=f"${row.fair:,.2f}", model=float(row.p),
            implied=1.0 / float(row.odds), cells=cells,
            # The market's wording, carried on the pick so draw_slide and
            # draw_cover serve any market deck. See tiktok_placings.py.
            mast="TO POLL 3 VOTES", lead=rnd, qual=fix,
            note=("TO POLL", "THE 3 VOTES"), cover_label=TIER_LABEL[p["tier"]],
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
    k.text((m + rw + 20 * S, 1062 * S), p["qual"].upper(),
           font=font("display", 24), fill=acc)

    k.text((m, 1112 * S), p["price"], font=font("fig", 100), fill=GOLD)
    fw = k.textlength(p["price"], font=font("fig", 100))
    for i, ln in enumerate(p["note"]):
        k.text((m + fw + 24 * S, (1132 + i * 34) * S), ln, font=font("display", 25),
               fill=INK)

    y, bh = 1248 * S, 16 * S
    k.rectangle([m, y, right, y + bh], fill=BAR)
    span = right - m
    k.rectangle([m, y, m + int(span * p["model"]), y + bh], fill=EMERALD)
    tick = m + int(span * p["implied"])
    k.rectangle([tick - 2 * S, y - 8 * S, tick + 2 * S, y + bh + 8 * S], fill=GOLD)
    k.text((m, y + bh + 12 * S), "MODEL %.0f%%" % (p["model"] * 100),
           font=font("display", 23), fill=EMERALD)
    k.text((right, y + bh + 12 * S), "PRICE IMPLIES %.0f%%" % (p["implied"] * 100),
           font=font("display", 23), fill=GOLD, anchor="ra")

    stat_grid(k, m, right, 1336 * S, p["cells"])
    return img, soft


def draw_cover(picks, sub="TO POLL 3 VOTES"):
    """What the deck is, then the six prices, and nothing else.

    No single player's face: a market deck that opens on one man reads as a tip
    on that man. The prices give the thumbnail something numeric instead. The
    model's credentials (207 games, 19 seasons, 93 features) used to sit under
    the prices and made the cover too much to take in at a glance; they live in
    the caption and on the closer.
    """
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = M * S, (W - M) * S
    rule = 812
    # The wash stops exactly on the rule under the title. The glow inside it is
    # clipped at the same line, so the one hard edge on the slide lands on a
    # drawn rule and reads as the layout rather than as a seam. "Cha Ching" is
    # not a club, so accent() falls back to its neutral.
    wash(img, "Cha Ching", rule * S)
    masthead(img, k, m, right, f"{SEASON} MODEL")

    lines = ("BEST PICKS FOR", "THE BROWNLOW")
    tf = min((fit_font(k, ln, "display", 96, right - m) for ln in lines),
             key=lambda f: f.size)
    for i, ln in enumerate(lines):
        k.text((m, (500 + i * 104) * S), ln, font=tf, fill=INK)
    k.text((m, 722 * S), sub, font=fit_font(k, sub, "display", 52, right - m),
           fill=EMERALD)
    k.line([m, rule * S, right, rule * S], fill=LINE, width=max(1, S))

    cw = (right - m) / 3
    for i, p in enumerate(picks):
        cx = m + cw * (i % 3)
        yy = (866 + (i // 3) * 206) * S
        k.text((cx, yy), p["price"], font=fit_font(k, p["price"], "fig", 72, cw - 24 * S),
               fill=GOLD)
        k.text((cx, yy + 92 * S), p["cover_label"], font=font("display", 22),
               fill=MUTED)

    k.text((right, 1296 * S), "SWIPE", font=font("display", 32), fill=EMERALD,
           anchor="ra")
    return img


CLOSER_LINES = ("THE MODEL SCORED ALL 207",
                "GAMES, THEN PRICED EVERY",
                "RUNNER AGAINST THE BOOK.",
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
    below = fy0
    if os.path.exists(SITE_SHOT):
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
    # The one line on the deck that is not ours to drop. This is the first Cha
    # Ching post carrying prices.
    k.text((m, (SAFE_BOT - 34) * S), "18+  GAMBLE RESPONSIBLY",
           font=font("display", 24), fill=MUTED)
    return img


# ------------------------------------------------------------------ copy
def caption(picks):
    """Templated, like every other draft in this repo, and for the same reason:
    a templated post cannot invent an accuracy claim under time pressure."""
    out = [
        "The model priced all 207 games. Here are six runners to poll the 3 votes.",
        "",
        "Three safe, two value, one longshot. Every home and away game of the "
        f"{SEASON} season went through the model, then each runner's chance of "
        "the 3 was set against what the book is paying.",
        "",
    ]
    for p in picks:
        out.append(f"{TIER_LABEL[p['tier']].lower()}: {p['name']}, {p['round'].lower()} "
                   f"{p['fixture']}, {p['price']} ({BOOK.title()}), model "
                   f"{p['model'] * 100:.0f}%")
    out += [
        "",
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
           f"{len(cap) + len(tags) + 2} characters including hashtags. "
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
    path = os.path.join(REPO, "drafts", f"tiktok_3votes_{SEASON}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    return path


def save(img, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.resize((W, H), Image.LANCZOS).save(path, "PNG", optimize=True)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="render one pick by key, or 'cover' / 'closer'")
    ap.add_argument("--no-phone", action="store_true",
                    help="skip the copy into the OneDrive folder")
    a = ap.parse_args()
    os.chdir(REPO)

    picks = build()
    paths, softs = [], []

    if a.only:
        one = [p for p in picks if p["key"] == a.only]
        if a.only == "cover":
            print(save(draw_cover(picks), os.path.join(OUT_DIR, "01_cover.png")))
        elif a.only == "closer":
            print(save(draw_closer(), os.path.join(OUT_DIR, "99_closer.png")))
        elif one:
            img, _ = draw_slide(one[0])
            print(save(img, os.path.join(OUT_DIR, f"only_{a.only}.png")))
        else:
            raise SystemExit(f"no pick keyed {a.only!r}; "
                             f"have {[p['key'] for p in picks]}")
        return

    paths.append(save(draw_cover(picks), os.path.join(OUT_DIR, "01_cover.png")))
    for i, p in enumerate(picks):
        img, soft = draw_slide(p)
        paths.append(save(img, os.path.join(
            OUT_DIR, f"{i + 2:02d}_{p['tier'].lower()}_{p['key']}.png")))
        if soft and soft > 1.8:
            softs.append((p["name"], soft))
    paths.append(save(draw_closer(), os.path.join(OUT_DIR, f"{len(picks) + 2:02d}_closer.png")))

    copy = write_copy(picks, paths, softs)
    print(f"  {len(paths)} slides to {OUT_DIR}")
    print(f"  copy: {copy}")

    if not a.no_phone:
        os.makedirs(PHONE_DIR, exist_ok=True)
        for p in paths:
            shutil.copy2(p, os.path.join(PHONE_DIR, os.path.basename(p)))
        print(f"  copied to {PHONE_DIR}")


if __name__ == "__main__":
    main()
