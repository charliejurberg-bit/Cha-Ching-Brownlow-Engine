"""The model's top 10 as a TikTok photo carousel, one slide per player.

    python scripts/tiktok_top10.py                 # all 12 slides
    python scripts/tiktok_top10.py --only 1        # just the leader's slide
    python scripts/tiktok_top10.py --contact       # one sheet of every slide

Writes 1080x1920 PNGs to drafts/tiktok/ (gitignored) plus the draft copy at
drafts/tiktok_top10_<season>.md. It never posts.

THE BOARD IS leaderboard_card.build(), IMPORTED RATHER THAN REBUILT
Rank, the 3-2-1 total, the simulated floor and the ceiling all come from that
one call, so this deck and the Twitter card cannot disagree about a figure.
The ceiling is already max(p90, 3-2-1 total) there, matching the dashboard.

THE SLIDES SAY THIS IS A MODEL, AND THAT SURVIVES A SCREENSHOT
A carousel is reposted one slide at a time, so every slide has to carry the
guard alone rather than relying on slide 1 or on the caption. Two places on
every slide: the masthead reads "2026 MODEL PROJECTION" and the figure's own
label reads "PROJECTED 3-2-1 VOTES". Neither is decoration. A slide cropped to just
the photo and the number is the one artifact here that could pass as the AFL's
own result, and the label is what stops it.

ONE VOTE SCALE ACROSS THE WHOLE DECK
The range band is drawn against a fixed 0 to BAND_MAX axis on every slide, not
rescaled per player. A reader swiping 10 up to 1 then sees the emerald grow,
which is the whole point of a countdown; a per-slide scale would make every
player's band the same length and throw that away.

PHOTOS ARE SOURCED BY EXACT PLAYER NAME AND ARE NOT REQUIRED
ChaChingContent/<Player Name>.<ext> for any extension Pillow opens, which
includes the avif and webp the AFL site serves. A player with no photo still
renders, on the club accent instead, so a missing file costs one slide's art
rather than the run.

UPSCALE IS REPORTED BECAUSE IT CANNOT BE FIXED HERE
Several of these sources are small, and a 465px-wide frame blown up to fill a
1080px panel is soft in a way no sharpening hides. The build prints the factor
per player and flags anything above SOFT_AT, so the fix (a bigger source file)
happens before the post rather than after it.
"""

import argparse
import colorsys
import glob
import os
import re
import sys

import pandas as pd
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import leaderboard_card as lb                                      # noqa: E402
from countdown_card import (                                       # noqa: E402
    BG, EMERALD, INK, MUTED, RANK_INK, GOLD, LINE, S,
    draw_mark, font, ordinal, set_fonts, FONT_SETS,
)
from draft_posts import _display_round                             # noqa: E402

# 9:16, TikTok's native frame. Rendered at S times this and downsampled on save.
W, H = 1080, 1920
M = 64                       # side margin
# TIKTOK CENTRE-CROPS A CAROUSEL IMAGE, SO THE CANVAS IS NOT THE CANVAS
# Measured on a phone rather than assumed: the players' heads were being cut
# off the top. Only a fixed-aspect centre crop can do that, since a phone
# cover-fill would take the sides and leave the top alone. These bounds are the
# 1:1 square, the worst case, so the layout survives whatever aspect TikTok
# picks. Everything a reader must see lives between them; the photograph may
# bleed outside, because losing the top of a blurred backdrop costs nothing.
SAFE_TOP, SAFE_BOT = 420, 1500
PHOTO_BOT = 990              # player slides: sharp photo runs SAFE_TOP to here
COVER_PHOTO_BOT = 1000       # the cover runs slightly deeper
BAR = "#1c2a36"              # the range track, as on the leaderboard card
PANEL = "#0c141c"

PHOTO_DIR = "ChaChingContent"
# The site. Note this is NOT the X handle, which is @ChaChingBrwnlow with no o.
DOMAIN = "chachingbrownlow.com"
SITE_SHOT = os.path.join("ChaChingContent", "_site_hero.jpg")
# The reigning medallist, for the cover's reference point. Verified against
# fitzroy_stats_all.csv rather than taken from the AFL award feed, which serves
# its own predictor between counts and had 2025 as Dawson 32.
PREV = {"name": "Matt Rowell", "season": 2025, "votes": 39}
PREV_FOCUS = (0.50, 0.38)
OUT_DIR = os.path.join("drafts", "tiktok")
CUR_SEASON = 2026
ROWS = 10
BAND_MAX = 50                # the fixed vote axis, see the module docstring
SOFT_AT = 1.8                # upscale beyond this is flagged, not refused

# Copied from dashboard.py's _TEAM_COLOURS rather than imported: dashboard.py is
# a Streamlit app and importing it executes the whole page. Keys are the
# AFLTables spellings that reach Playing.for.
TEAM_COLOURS = {
    'Collingwood': '#4a4a4a', 'Geelong': '#1b3a6b', 'Port Adelaide': '#2e7d7d',
    'Western Bulldogs': '#a33333', 'Brisbane Lions': '#6b1a2f',
    'Brisbane': '#6b1a2f', 'Sydney': '#c0392b', 'Hawthorn': '#8b5e3c',
    'Fremantle': '#6c3483', 'GWS': '#c06a20',
    'Greater Western Sydney': '#c06a20', 'Carlton': '#1a3a5c',
    'Melbourne': '#1a3060', 'Richmond': '#8b7a00', 'West Coast': '#003087',
    'Adelaide': '#c72c41', 'Essendon': '#cc0000', 'St Kilda': '#cc2222',
    'Gold Coast': '#e07000', 'North Melbourne': '#003fa0',
}

# Where the subject sits in each frame, as a fraction of width and height, plus
# an optional zoom, so the crop keeps the head. Tuned by eye against the sources
# in ChaChingContent and only needed where the default is wrong. A celebration
# shot is almost always upper-middle, which is what the default says.
FOCUS_DEFAULT = (0.50, 0.38)
FOCUS = {
    "Bailey Smith": (0.34, 0.40),
    "Jordan Dawson": (0.60, 0.34),
    "Will Ashcroft": (0.56, 0.42),
    # Rankine and Neale both got a bigger source and neither needs an override
    # any more. The entries they used to carry were correcting for a 465x372
    # frame that had the player hard left; the 1200x900 replacement is centred.
    # A wide stadium shot: he fills the height, but the crypto.com boards and
    # the goalposts fill everything else. The zoom pushes them out of frame.
    "Patrick Cripps": (0.50, 0.40, 1.45),
    "Isaac Heeney": (0.50, 0.30),
    "Harry Sheezel": (0.50, 0.28),
}


def accent(team, lift=0.60):
    """The club colour, lifted until it reads as ink on Midnight Turf.

    Half these clubs are navy, maroon or charcoal, which at full saturation is
    invisible against #0a1017. Lifting lightness to a floor keeps each club
    recognisably itself while guaranteeing contrast; picking lighter brand
    colours by hand would not survive a club being added.

    `lift` is lower for a large filled shape than for text. At the 0.60 text
    needs, Adelaide, Brisbane, Sydney and the Bulldogs all converge on the same
    pink, which on the cover's bars costs the whole guess-the-club tease. A bar
    carries its colour over hundreds of pixels and reads at 0.48.
    """
    hexv = TEAM_COLOURS.get(str(team), RANK_INK).lstrip("#")
    r, g, b = (int(hexv[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    # Saturation is only lifted on a colour that HAS a hue. Collingwood is
    # #4a4a4a, a neutral grey whose hue is undefined and reads as 0, so forcing
    # saturation onto it painted the club salmon. Below this threshold the
    # colour is achromatic and stays that way, which is correct for Collingwood.
    s = s if s < 0.12 else max(s, 0.45)
    r, g, b = colorsys.hls_to_rgb(h, max(l, lift), s)
    return "#%02x%02x%02x" % tuple(int(v * 255) for v in (r, g, b))


def find_photo(name):
    """The highest resolution file whose name matches, extension ignored.

    Picking the first match alphabetically meant a replacement had to displace
    the original: dropping a 1200x900 "Izak Rankine.webp" beside the 465x372
    "Izak Rankine.avif" changed nothing, because avif sorts first. Choosing on
    pixel count instead makes upgrading a photo a copy rather than a swap, and
    the old file can stay where it is.
    """
    best, best_px = None, -1
    for p in sorted(glob.glob(os.path.join(PHOTO_DIR, "*"))):
        if os.path.splitext(os.path.basename(p))[0].lower() != str(name).lower():
            continue
        try:
            with Image.open(p) as im:
                px = im.width * im.height
        except Exception:
            continue          # not an image Pillow reads, or truncated
        if px > best_px:
            best, best_px = p, px
    return best


def cover_crop(path, box_w, box_h, focus):
    """Scale to cover the box around a focal point, then crop. Returns the
    image and the upscale factor, which the caller reports.

    focus is (fx, fy) or (fx, fy, zoom). Zoom above 1 crops tighter, for the
    wide stadium shots where the player is a small figure against a stand. It
    costs resolution in exact proportion, so the reported factor carries it and
    the build flags the result like any other soft source.
    """
    im = Image.open(path).convert("RGB")
    zoom = focus[2] if len(focus) > 2 else 1.0
    sc = max(box_w / im.width, box_h / im.height) * zoom
    new = (max(1, round(im.width * sc)), max(1, round(im.height * sc)))
    im = im.resize(new, Image.LANCZOS)
    fx, fy = focus[0], focus[1]
    x = min(max(int(new[0] * fx - box_w / 2), 0), new[0] - box_w)
    y = min(max(int(new[1] * fy - box_h / 2), 0), new[1] - box_h)
    return im.crop((x, y, x + box_w, y + box_h)), sc


def scrim(img, top, bottom, x0=0, x1=None, colour=BG, a0=0, a1=255, power=1.6):
    """A vertical wash from a0 to a1 alpha, eased so the photo does not end on
    a visible line. Composited rather than drawn: a stack of 1px rectangles
    banded visibly on the emerald."""
    x1 = img.width if x1 is None else x1
    h = max(1, bottom - top)
    mask = Image.new("L", (1, h))
    px = mask.load()
    for i in range(h):
        t = (i / (h - 1)) ** power if h > 1 else 1
        px[0, i] = int(a0 + (a1 - a0) * t)
    mask = mask.resize((x1 - x0, h))
    img.paste(Image.new("RGB", (x1 - x0, h), colour), (x0, top), mask)


def fit_font(k, txt, role, size, max_w, floor=28):
    """Largest size at or under `size` whose text fits max_w device px."""
    while size > floor:
        f = font(role, size)
        if k.textlength(txt, font=f) <= max_w:
            return f
        size -= 2
    return font(role, floor)


def build(season=CUR_SEASON, rows=ROWS):
    """The board, plus the per-player detail the slides carry."""
    b = lb.build(season=season, rows=rows)
    g = pd.read_csv(lb.GAME_LEVEL.format(season))
    g["_gkey"] = lb._game_key(g)
    srt = (["_gkey", "Exp_Votes"]
           + [c for c in ("Poll_Prob", "P_3") if c in g.columns]
           + ["Player_Name"])
    g = g.sort_values(srt, ascending=[True, False] + [False] * (len(srt) - 3) + [True])
    g["hard"] = (g.groupby("_gkey").cumcount() + 1).map(
        lb.HARD_VOTE_BY_RANK).fillna(0).astype(int)

    # Whether a rank is shared is counted across EVERY player, not across the
    # ten on the deck. Rank is minimum-on-ties over the 3-2-1 total, so two
    # players tie exactly when that total matches, and the player who makes
    # tenth a tie can easily be the eleventh man and never appear on a slide.
    # Counting within the top ten would print a bare 10TH over a shared rank.
    share = (g.groupby(["Player_Name", "Playing.for"])["hard"].sum()
              .value_counts())

    for r in b["rows"]:
        r["tied"] = bool(share.get(r["hard"], 0) > 1)
        p = g[g.Player_Name == r["Player_Name"]]
        r["n3"] = int((p.hard == 3).sum())
        r["n2"] = int((p.hard == 2).sum())
        r["n1"] = int((p.hard == 1).sum())
        best = p.sort_values("Exp_Votes", ascending=False).iloc[0]
        opp = (best["Away.team"] if best["Playing.for"] == best["Home.team"]
               else best["Home.team"])
        # Round_num is the raw AFLTables number and 2026 opens with an Opening
        # Round, so it runs one ahead of the round the world uses.
        r["best"] = {"round": _display_round(best["Round_num"], season),
                     "opp": opp, "disposals": int(best["Disposals"]),
                     "goals": int(best["Goals"])}
        r["photo"] = find_photo(r["Player_Name"])
    b["creds"] = creds()
    return b


TRAIN_FILE = "fitzroy_stats_all.csv"
FEATURES_PKL = os.path.join("predictions", "features.pkl")
COUNT_DATE = "Monday 21 September"

# Hashtags for clubs whose AFLTables name is not what anyone searches. The rest
# slugify cleanly. #greaterwesternsydney is nobody's tag.
CLUB_TAGS = {
    "Greater Western Sydney": "gwsgiants", "GWS": "gwsgiants",
    "Sydney": "sydneyswans", "Adelaide": "adelaidecrows",
    "Geelong": "geelongcats", "West Coast": "westcoasteagles",
    "Gold Coast": "goldcoastsuns", "Brisbane Lions": "brisbanelions",
}


def _tag(s):
    return "#" + re.sub(r"[^a-z0-9]+", "", str(s).lower())


def caption(b):
    """The post caption, long form and templated.

    LENGTH IS THE POINT, BUT THE FIRST LINE IS THE ONLY GUARANTEED LINE
    TikTok collapses a caption after roughly one line behind a "more", so the
    hook carries the post on its own and everything after it is for the reader
    who already tapped, and for search. Hence the order: hook, method, board,
    how to read it, the honesty, the link, a question.

    The board is spelled out in full even though the carousel reveals it one
    slide at a time. A name in the caption is searchable and a name in a PNG is
    not, and the caption is collapsed by default anyway, so it costs a reveal
    only for the reader who chose to open it.
    """
    s, c = b["season"], b["creds"]
    lead = b["rows"][0]
    n_games = b["n_games"]
    out = [
        f"We scored all {n_games} games. Here is the model's Brownlow top 10.",
        "",
        f"Every home and away game of the {s} season went through the model, "
        "then 3, 2 and 1 were awarded in each one, the way the umpires do it "
        "on the night. Swipe from "
        f"{ordinal(int(b['rows'][-1]['rank']))} up to 1st.",
        "",
    ]
    for r in b["rows"]:
        out.append(f"{rank_text(r['rank'], r['tied']).lower()} "
                   f"{r['Player_Name']}, {r['Playing.for']}, {int(r['hard'])}")
    out += [
        "",
        "The bar under each player is his floor and ceiling across "
        f"{c['sims']:,} simulated seasons. A short bar is a settled case. A "
        "long one is a player whose season could still land either way.",
        "",
        "Two things said plainly. This is a model, not a leak: no "
        f"{s} vote is public until the count on {COUNT_DATE}. And a player's "
        "number here is a ceiling reading, which is what he collects if every "
        "game the model calls his way lands his way.",
        "",
    ]
    if c["seasons"]:
        out += [f"Built on {c['seasons']} seasons of data, {c['first']} to "
                f"{c['last']}, and {c['features']} features per player per "
                "game.", ""]
    out += [
        f"The full board, every player and every game, is at {DOMAIN}. The "
        "site opens on expected votes, which is the average rather than the "
        "3-2-1 total, so the same player reads lower there.",
        "",
        "Who has the model got wrong?",
    ]
    return "\n".join(out)


def hashtags(b):
    """Broad tags first, then the players and clubs actually on the board."""
    base = ["#brownlow", "#brownlowmedal", f"#brownlow{b['season']}", "#afl",
            f"#afl{b['season']}", "#aflfooty", "#footy", "#aussierules",
            "#aflpredictions", "#brownlowpredictions", "#sportsanalytics",
            "#datascience"]
    tags = list(base)
    for r in b["rows"][:6]:
        t = _tag(r["Player_Name"])
        if t not in tags:
            tags.append(t)
    for r in b["rows"]:
        club = str(r["Playing.for"])
        t = "#" + CLUB_TAGS.get(club, re.sub(r"[^a-z0-9]+", "", club.lower()))
        if t not in tags:
            tags.append(t)
    return " ".join(tags)


def creds():
    """The cover's credibility figures, measured rather than asserted.

    Read from the artifacts every run so the cover cannot outlive them: a
    retrain that changes the feature count or extends the training range would
    otherwise leave a stale number on a public asset with nothing to catch it.

    NOTHING HERE IS AN ACCURACY FIGURE, AND THAT IS DELIBERATE
    No MAE, no hit rate, no percentage. The v1 to v4 error figures were all
    measured with a momentum leak in place and none is comparable to the
    current model, so CLAUDE.md refuses them publicly and internally alike.
    Scale is honest and checkable; a performance claim right now is neither.
    """
    import pickle
    out = {"sims": lb.SIMS}
    try:
        with open(FEATURES_PKL, "rb") as fh:
            out["features"] = len(pickle.load(fh))
    except Exception:
        out["features"] = None
    try:
        sn = pd.read_csv(TRAIN_FILE, usecols=["Season"], low_memory=False)["Season"]
        out["first"], out["last"] = int(sn.min()), int(sn.max())
        out["seasons"] = int(sn.nunique())
    except Exception:
        out["first"] = out["last"] = out["seasons"] = None
    return out


def _initials(name):
    return "".join(w[0] for w in str(name).split()[:2]).upper()


def rank_text(rank, tied):
    """5TH, or =7TH where the rank is shared. The flat form, for small type."""
    return ("=" if tied else "") + ordinal(int(rank)).upper()


def draw_rank(k, x, baseline, rank, tied, colour, size=128):
    """The same thing set large, with the suffix raised to the cap line.

    The numeral keeps the weight and the suffix is set at 40% of it, because a
    full size TH doubles the width of the element and starts competing with the
    player's name for the eye. The equals sign gets the same treatment: one
    modifier read at a glance, not a third figure.
    """
    rk = int(rank)
    num = str(rk)
    suf = ordinal(rk)[len(num):].upper()
    big, small = font("fig", size), font("fig", int(size * 0.40))
    # Spaced off the ink, not off the advance width. A 1 is a narrow glyph in a
    # proportional face but still carries a full digit of side bearing, so
    # advancing by textlength left a visible hole between the 1 and the ST.
    if tied:
        eq = font("fig", int(size * 0.60))
        k.text((x, baseline), "=", font=eq, fill=colour, anchor="ls")
        x = k.textbbox((x, baseline), "=", font=eq, anchor="ls")[2] + size * 0.09 * S
    k.text((x, baseline), num, font=big, fill=colour, anchor="ls")
    x = k.textbbox((x, baseline), num, font=big, anchor="ls")[2] + size * 0.07 * S
    k.text((x, baseline - size * 0.48 * S), suf, font=small, fill=colour,
           anchor="ls")
    return k.textbbox((x, baseline), suf, font=small, anchor="ls")[2]


def photo_band(img, path, focus, top, bottom):
    """The photograph, placed so its subject lands inside the safe area.

    THE BAND STARTS AT SAFE_TOP AND THE BACKDROP COVERS THE REST
    A crop cannot move a head downwards. Where a source frames the player with
    his head near the top, cover-cropping to a tall box uses the full height of
    the source and the head lands at the top of the band, which is the part
    TikTok removes. The only fix is to place the photograph lower on the canvas
    and fill the space above it, so that is what this does: the sharp image runs
    from `top`, and above it sits a blurred, darkened enlargement of the same
    frame. Uncropped the slide still reads as full bleed; cropped, the blurred
    part is exactly what gets thrown away.
    """
    band = bottom - top
    back, _ = cover_crop(path, img.width, bottom, focus)
    back = back.filter(ImageFilter.GaussianBlur(28 * S)).point(lambda v: int(v * 0.55))
    img.paste(back, (0, 0))
    sharp, sc = cover_crop(path, img.width, band, focus)
    img.paste(sharp, (0, top))
    return sc / S


def draw_slide(r, season):
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = M * S, (W - M) * S
    acc = accent(r["Playing.for"])
    soft = None

    top, bot = SAFE_TOP * S, PHOTO_BOT * S
    if r["photo"]:
        soft = photo_band(img, r["photo"], FOCUS.get(r["Player_Name"], FOCUS_DEFAULT),
                          top, bot)
    else:
        k.rectangle([0, 0, W * S, bot], fill=PANEL)
        k.text((W * S // 2, (SAFE_TOP + PHOTO_BOT) // 2 * S),
               _initials(r["Player_Name"]), font=font("display", 120),
               fill=acc, anchor="mm")
    scrim(img, top, (SAFE_TOP + 150) * S, a0=200, a1=0, power=0.9)
    scrim(img, int(top + (bot - top) * 0.52), bot, a0=0, a1=255, power=2.4)

    draw_mark(img, m, (SAFE_TOP + 18) * S, 27)
    k.text((right, (SAFE_TOP + 24) * S), f"{season} MODEL PROJECTION",
           font=font("display", 24), fill="#b9c6d1", anchor="ra")

    draw_rank(k, m, (PHOTO_BOT - 44) * S, r["rank"], r["tied"], acc, size=104)

    nm = str(r["Player_Name"]).upper()
    k.text((m, 1024 * S), nm, font=fit_font(k, nm, "name", 68, right - m), fill=INK)
    k.text((m, 1104 * S), str(r["Playing.for"]).upper(),
           font=font("display", 24), fill=acc)

    fig = str(int(r["hard"]))
    k.text((m, 1150 * S), fig, font=font("fig", 108), fill=GOLD)
    fw = k.textlength(fig, font=font("fig", 108))
    k.text((m + fw + 26 * S, 1172 * S), "PROJECTED",
           font=font("display", 26), fill=INK)
    k.text((m + fw + 26 * S, 1208 * S), "3-2-1 VOTES",
           font=font("display", 26), fill=INK)

    by, bh = 1300 * S, 14 * S
    k.rectangle([m, by, right, by + bh], fill=BAR)
    span = right - m
    x0 = m + int(span * min(r["floor"], BAND_MAX) / BAND_MAX)
    x1 = m + int(span * min(r["ceiling"], BAND_MAX) / BAND_MAX)
    k.rectangle([x0, by, max(x1, x0 + 4 * S), by + bh], fill=EMERALD)
    k.text((x0, by + 28 * S), f"{r['floor']:.0f}", font=font("display", 24),
           fill=MUTED, anchor="ma")
    k.text((x1, by + 28 * S), f"{r['ceiling']:.0f}", font=font("display", 24),
           fill=MUTED, anchor="ma")

    cells = [(str(int(r["games"])), "GAMES"),
             (str(r["n3"]), "BEST ON GROUND"),
             (str(r["n2"]), "SECOND BEST")]
    cw = (right - m) / 3
    for i, (v, lab) in enumerate(cells):
        cx = m + cw * i
        k.text((cx, 1392 * S), v, font=font("fig", 50), fill=INK)
        k.text((cx, 1454 * S), lab, font=font("display", 20), fill=MUTED)
    return img, soft


def draw_cover(b):
    """Photo on top, title under it, built like every player slide.

    The reigning medallist is the cover image because he is the only face that
    belongs on a 2026 preview without answering it. He is NOT in this top 10,
    which is why his block leads with the season and the word MEDALLIST: on a
    slide titled TOP 10 PREDICTION an unlabelled face reads as the number one.
    """
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = M * S, (W - M) * S
    soft = None

    top, bot = SAFE_TOP * S, COVER_PHOTO_BOT * S
    photo = find_photo(PREV["name"])
    if photo:
        soft = photo_band(img, photo, PREV_FOCUS, top, bot)
    else:
        k.rectangle([0, 0, W * S, bot], fill=PANEL)
    scrim(img, top, (SAFE_TOP + 150) * S, a0=200, a1=0, power=0.9)
    # Starts higher and eases harder than a player slide's. The identity block
    # sits over a dinner jacket and a lit backdrop rather than over a dark
    # crowd, and at the player-slide setting "2025 MEDALLIST" washed out.
    scrim(img, int(top + (bot - top) * 0.44), bot, a0=0, a1=255, power=1.6)

    draw_mark(img, m, (SAFE_TOP + 18) * S, 27)
    k.text((right, (SAFE_TOP + 24) * S), f"{b['season']} MODEL PROJECTION",
           font=font("display", 24), fill="#b9c6d1", anchor="ra")

    # Spacing is set off the BASELINE of the figure, not its top. Placing the
    # 39 by its top put its cap height straight through the name above it.
    k.text((m, (COVER_PHOTO_BOT - 172) * S), f"{PREV['season']} MEDALLIST",
           font=font("display", 24), fill="#b9c6d1")
    k.text((m, (COVER_PHOTO_BOT - 138) * S), PREV["name"].upper(),
           font=font("display", 44), fill=INK)
    k.text((m, (COVER_PHOTO_BOT - 34) * S), str(PREV["votes"]),
           font=font("fig", 50), fill=GOLD, anchor="ls")
    vw = k.textlength(str(PREV["votes"]), font=font("fig", 50))
    k.text((m + vw + 16 * S, (COVER_PHOTO_BOT - 34) * S), "VOTES",
           font=font("display", 24), fill=MUTED, anchor="ls")

    # Both lines take the size that fits the LONGER of them. Sizing each line
    # to its own width made "2026 BROWNLOW MEDAL" set smaller than the line
    # under it, which reads as a mistake rather than as a hierarchy.
    tl = (f"{b['season']} BROWNLOW MEDAL", "TOP 10 PREDICTION")
    tf = min((fit_font(k, ln, "display", 88, right - m) for ln in tl),
             key=lambda f: f.size)
    for i, ln in enumerate(tl):
        k.text((m, (1052 + i * 100) * S), ln, font=tf, fill=INK)

    # The credentials band. Scale, never accuracy: see creds().
    c = b["creds"]
    cells = [(f"{c['sims']:,}", "SIMULATIONS", "PER SEASON")]
    if c["seasons"]:
        cells.append((str(c["seasons"]), "SEASONS",
                      f"{c['first']} TO {c['last']}"))
    if c["features"]:
        cells.append((str(c["features"]), "FEATURES", "PER PLAYER"))
    k.line([m, 1288 * S, right, 1288 * S], fill=LINE, width=max(1, S))
    k.text((right, 1240 * S), "SWIPE", font=font("display", 32), fill=EMERALD,
           anchor="ra")
    cw = (right - m) / max(len(cells), 1)
    for i, (v, l1, l2) in enumerate(cells):
        cx = m + cw * i
        k.text((cx, 1326 * S), v,
               font=fit_font(k, v, "fig", 54, cw - 24 * S), fill=INK)
        k.text((cx, 1396 * S), l1, font=font("display", 22), fill=MUTED)
        k.text((cx, 1426 * S), l2, font=font("display", 19), fill=RANK_INK)
    return img, soft


def draw_closer(b):
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = M * S, (W - M) * S
    draw_mark(img, m, (SAFE_TOP + 18) * S, 27)
    k.text((right, (SAFE_TOP + 24) * S), f"{b['season']} MODEL PROJECTION",
           font=font("display", 24), fill=MUTED, anchor="ra")
    k.line([m, (SAFE_TOP + 74) * S, right, (SAFE_TOP + 74) * S], fill=LINE,
           width=max(1, S))

    # WHICH BOARD THIS IS, because the site defaults to the other one.
    # A reader who follows the link lands on the decimal board, where the
    # leader reads 39.6 against the 48 he just swiped past. Saying so here is
    # cheaper than the reply, and it is the one piece of prose on the deck.
    for i, ln in enumerate(("THIS TOP 10 AWARDS 3, 2 AND 1",
                            "IN EVERY GAME OF THE SEASON.",
                            "FOR THE BOARD BUILT ON AVERAGE",
                            "VOTES, SEE THE SITE.")):
        k.text((m, (SAFE_TOP + 116 + i * 48) * S), ln,
               font=font("display", 34), fill=INK)

    # The site itself, in a browser frame. The frame is not decoration: the
    # page is Midnight Turf on Midnight Turf, so without a border and a chrome
    # bar the screenshot reads as more slide rather than as a website.
    fx0, fy0, fw = m, 748 * S, right - m
    if os.path.exists(SITE_SHOT):
        # Cropped to a tall window rather than scaled to fit. The capture is a
        # 16:9 desktop viewport, and fitted whole it sat as a letterbox strip
        # with the slide empty under it while its own type shrank to nothing.
        sh = 520 * S
        shot = Image.open(SITE_SHOT).convert("RGB")
        sc = max(fw / shot.width, sh / shot.height)
        nw, nh = round(shot.width * sc), round(shot.height * sc)
        shot = shot.resize((nw, nh), Image.LANCZOS)
        cx = min(max(int(nw * 0.50 - fw / 2), 0), nw - fw)
        cy = min(max(int(nh * 0.44 - sh / 2), 0), nh - sh)
        shot = shot.crop((cx, cy, cx + fw, cy + sh))
        bar = 46 * S
        k.rectangle([fx0, fy0, fx0 + fw, fy0 + bar + sh], fill=PANEL,
                    outline=LINE, width=max(1, 2 * S))
        for d in range(3):
            ccx = fx0 + (24 + d * 24) * S
            k.ellipse([ccx - 5 * S, fy0 + bar // 2 - 5 * S,
                       ccx + 5 * S, fy0 + bar // 2 + 5 * S], fill=LINE)
        k.text((fx0 + fw // 2, fy0 + bar // 2), DOMAIN,
               font=font("body", 22), fill=MUTED, anchor="mm")
        img.paste(shot, (fx0, fy0 + bar))
        k.rectangle([fx0, fy0, fx0 + fw, fy0 + bar + sh], outline=LINE,
                    width=max(1, 2 * S))
        below = fy0 + bar + sh + 62 * S
    else:
        below = fy0

    dom = DOMAIN.upper()
    k.text((m, below), dom, font=fit_font(k, dom, "display", 62, right - m),
           fill=EMERALD)
    return img


def write_copy(b, paths, softs, missing):
    """The caption and the per slide text, as markdown for manual review.

    Templated, like draft_posts.py and for the same reason. The copy rules it
    keeps: no accuracy percentages, no em dashes, no adjectives about
    likelihood, and every round number displayed rather than raw.

    The cautions section is not optional furniture. The slides carry no footer
    text by standing rule, so every qualifier behind a figure has to survive
    here or it is lost between the render and the post.
    """
    s = b["season"]
    lead = b["rows"][0]
    out = [f"# TikTok carousel, the model's top 10, {s}", ""]
    cap = caption(b)
    tags = hashtags(b)
    out += ["## Caption", "", "```", cap, "", tags, "```", "",
            f"{len(cap) + len(tags) + 2} characters including hashtags. "
            "TikTok's limit is 2,200.", "",
            "## Slides", ""]
    out.append("| # | File | Player | Rank | Votes | Range |")
    out.append("|---|---|---|---|---|---|")
    for i, r in enumerate(reversed(b["rows"])):
        out.append(f"| {i + 2} | `{os.path.basename(paths[i + 1])}` | "
                   f"{r['Player_Name']} | {rank_text(r['rank'], r['tied'])} | "
                   f"{int(r['hard'])} | {r['floor']:.0f} to {r['ceiling']:.0f} |")
    out += ["", f"Slide 1 is the cover, slide {len(b['rows']) + 2} is the "
            "closer.", "", "## Cautions before posting", ""]
    out += [
        f"- The {int(lead['hard'])} is a ceiling reading, not an expectation. "
        "It is what a player collects if every game the model calls his way "
        "lands his way, so it sits at or above his own 90th percentile. Do not "
        "let the caption call it a prediction of his total.",
        "- No 2026 Brownlow vote is public until the count. The board is a "
        "model output and every slide says so twice, in the masthead and in "
        "the figure label. Do not crop either off.",
        "- A rank prefixed = is shared, and the next rank down skips "
        "accordingly. Splitting a tie would invent a separation out of a "
        "decimal the slides do not show.",
        "- Round numbers on the slides are the AFL's, one behind the raw "
        "AFLTables number the CSVs carry.",
        f"- Every slide is laid out inside a centred {SAFE_BOT - SAFE_TOP}px "
        f"band, y {SAFE_TOP} to {SAFE_BOT}, because TikTok centre-crops a "
        "carousel image. Anything added outside that band will be cut on a "
        "phone even though it looks fine in the file.",
    ]
    if b.get("chance") is not None:
        out.append(
            f"- If asked about the record: the simulation gives "
            f"{lead['Player_Name']} {b['chance'] * 100:.0f} in 100 of passing "
            f"{lb.RECORD_HOLDER.title()}'s {lb.RECORD_VOTES} from "
            f"{lb.RECORD_SEASON}, and {b['reach'] * 100:.0f} in 100 of reaching "
            f"{int(lead['hard'])} itself. Say the simulation, singular. Note "
            "that 1976 and 1977 awarded double votes, so the raw all time list "
            "is not comparable.")
    for n, sc in softs:
        out.append(f"- {n}'s photo is upscaled {sc:.1f} times and will look "
                   f"soft on a phone. Replace the source in {PHOTO_DIR}/ if "
                   f"there is time.")
    for n in missing:
        out.append(f"- {n} has no photo in {PHOTO_DIR}/ and rendered on the "
                   f"club accent instead.")
    p = os.path.join("drafts", f"tiktok_top10_{s}.md")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    return p


def save(img, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.resize((W, H), Image.LANCZOS).save(path, "PNG", optimize=True)
    return path


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=CUR_SEASON)
    ap.add_argument("--rows", type=int, default=ROWS)
    ap.add_argument("--only", type=int, help="render one rank and stop")
    ap.add_argument("--contact", action="store_true",
                    help="also write a contact sheet of the deck")
    ap.add_argument("--font", default="twcen", help=", ".join(FONT_SETS))
    a = ap.parse_args()
    set_fonts(a.font)

    b = build(a.season, a.rows)
    order = list(reversed(b["rows"]))          # 10 up to 1, the countdown
    made, softs, missing = [], [], []

    if a.only is None:
        cov, csoft = draw_cover(b)
        made.append(save(cov, os.path.join(OUT_DIR, "01_cover.png")))
        if find_photo(PREV["name"]) is None:
            missing.append(PREV["name"])
        elif csoft and csoft > SOFT_AT:
            softs.append((PREV["name"], csoft))
    for i, r in enumerate(order):
        if a.only is not None and int(r["rank"]) != a.only:
            continue
        img, sc = draw_slide(r, a.season)
        n = f"{i + 2:02d}_rank{int(r['rank']):02d}_{slug(r['Player_Name'])}.png"
        made.append(save(img, os.path.join(OUT_DIR, n)))
        if r["photo"] is None:
            missing.append(r["Player_Name"])
        elif sc and sc > SOFT_AT:
            softs.append((r["Player_Name"], sc))
    if a.only is None:
        made.append(save(draw_closer(b),
                         os.path.join(OUT_DIR, f"{len(order) + 2:02d}_closer.png")))

    for p in made:
        print(p)
    if a.only is None:
        print(write_copy(b, made, softs, missing))
    if missing:
        print("\nno photo, rendered on the club accent instead:")
        for n in missing:
            print(f"  {n}")
    if softs:
        print(f"\nsource too small, upscaled past {SOFT_AT}x and will look soft:")
        for n, sc in softs:
            src = find_photo(n)
            print(f"  {n:<22} {sc:.2f}x   {Image.open(src).size} "
                  f"({os.path.basename(src)})")

    if a.contact:
        paths = sorted(glob.glob(os.path.join(OUT_DIR, "0*.png"))
                       + glob.glob(os.path.join(OUT_DIR, "1*.png")))
        cw, ch = 300, 533
        sheet = Image.new("RGB", (cw * len(paths), ch), BG)
        for i, p in enumerate(paths):
            sheet.paste(Image.open(p).resize((cw - 6, ch - 6), Image.LANCZOS),
                        (i * cw + 3, 3))
        cp = os.path.join(OUT_DIR, "_contact.png")
        sheet.save(cp)
        print(f"\n{cp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
