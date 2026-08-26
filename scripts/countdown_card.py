"""Three-season progression card for the Brownlow leaderboard countdown.

    python scripts/countdown_card.py "Clayton Oliver" 20
    python scripts/countdown_card.py "Clayton Oliver" 20 --tagline "Back to his best"

Writes a PNG to drafts/ (gitignored), sized 1600x900 for a tweet, rendered at
2x and downsampled so the type stays crisp.

Every figure is computed from this repo, never typed in. 2024 and 2025 come
from fitzroy_stats_all.csv, 2026 from data_2026/afltables_2026.csv, coaches
votes from coaches_votes_all.csv plus data_2026/coaches_votes_2026.csv, and the
expected-vote total from predictions/season_2026.csv.

RANK QUALIFICATION
Ranks are among players with at least MIN_GAMES (12) in that season, half of a
23-game home-and-away season. The threshold matters and is not cosmetic: with
no threshold a player who managed three big games outranks a player who was
excellent for six months, and Oliver's 2026 disposal rank moves between 4th and
5th on that choice alone. State the threshold on the card, which the footer
does, rather than leaving a reader to assume.

Finals are excluded everywhere. The archive labels them with a string round
(QF, EF, SF, PF, GF), so coercing Round to a number and dropping the nulls is
the whole filter.

WHAT IS NOT RANKED
Brownlow votes. A vote count is not a per-game rate and the countdown's whole
point is the vote tally, so a league rank beside it reads as a second, competing
ranking. 2026 shows expected votes, which is a model output and is labelled as
one.
"""

import argparse
import os
import re
import sys

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

MIN_GAMES = 12
OUT_DIR = "drafts"
# 4:5 portrait, not 16:9. Twitter renders an in-timeline image at roughly 350px
# wide on a phone WHATEVER its aspect, so horizontal resolution is fixed and the
# only real lever is how much you put across that width. The first version was
# 1600 wide: at 0.219 scale its 18px rank text displayed at 3.9px and the row
# labels at 5.0px, i.e. everything except the player's name was illegible in the
# timeline. 1200 wide scales to 0.292, and portrait buys the vertical room to
# set the type at the sizes that survive it. Check any change with --preview,
# which writes the 350px version Twitter actually shows.
# S is the output multiplier, not a supersample: the card is drawn and SAVED at
# W*S by H*S (2400x3000). X accepts up to 4096 a side.
W, H, S = 1200, 1500, 2

# Midnight Turf, from CLAUDE.md. Never change these.
#
# ONE accent, and it is emerald. An earlier pass spent boldness in four places
# at once (filled emerald rank pills, a green panel, a gold masthead, emerald
# figures) and the card read as a betting app rather than a stats graphic. Gold
# is the Betting Hub's token and has no business on the free Brownlow side
# anyway. The current season is marked by colour and a hairline, nothing filled.
BG = "#0a1017"
INK, MUTED = "#e9eef3", "#7e8c99"
RANK_INK = "#93a3b1"            # light enough to survive Twitter's downscale
EMERALD = "#34d399"
LINE = "#1a2632"
PANEL = "#0c141c"               # barely-there lift, not a green block

F = r"C:\Windows\Fonts"
def font(role, size):
    """role is display / name / fig / body, resolved through the active set."""
    fs = FONTS
    return ImageFont.truetype(os.path.join(F, fs[role]),
                              int(size * S * fs["scale"]))

# Type pairings, switchable with --font, because this is a judgement call that
# is faster to make by looking than by arguing. Each set carries a size scale:
# the families differ a lot at the same nominal px (Franklin runs small, Georgia
# runs large), so a single size table would flatter one and break another.
#
# Never a monospace for the figures. Consolas did them originally and its
# slashed zero and typewriter rhythm read as a console dump.
FONT_SETS = {
    # DIN. What broadcast stats graphics have always been set in. Clean, neutral.
    "bahnschrift": dict(display="bahnschrift.ttf", name="bahnschrift.ttf",
                        fig="bahnschrift.ttf", body="segoeui.ttf", scale=1.00),
    # The newspaper sports page. Authoritative, a little editorial, not neutral.
    "franklin":    dict(display="framd.ttf", name="framdcn.ttf",
                        fig="framd.ttf", body="segoeui.ttf", scale=0.96),
    # Slab serif. Athletic and slightly vintage; the figures have real presence.
    "rockwell":    dict(display="ROCKB.TTF", name="ROCKB.TTF",
                        fig="ROCKB.TTF", body="segoeui.ttf", scale=0.92),
    # Broadsheet. Serif figures read as considered rather than sporty.
    "georgia":     dict(display="georgiab.ttf", name="georgiab.ttf",
                        fig="georgiab.ttf", body="georgia.ttf", scale=0.88),
    # Geometric sans, wide and calm. The quietest of the five.
    "twcen":       dict(display="TCB_____.TTF", name="TCB_____.TTF",
                        fig="TCB_____.TTF", body="segoeui.ttf", scale=1.02),
}
FONTS = dict(FONT_SETS["twcen"])


def set_fonts(name):
    global FONTS
    if name not in FONT_SETS:
        raise SystemExit(f"--font must be one of {', '.join(FONT_SETS)}")
    FONTS = dict(FONT_SETS[name])

# Labels are lines, not strings: at a legible size "CONTESTED POSSESSIONS" does
# not fit one line beside three number columns, and shortening it to "CONTESTED"
# loses what the stat is.
ROWS = [(["DISPOSALS"], "disp", "{:.1f}"),
        (["CONTESTED", "POSSESSIONS"], "cp", "{:.1f}"),
        (["CLEARANCES"], "clr", "{:.1f}"),
        (["COACHES", "VOTES"], "cv", "{:.0f}"),
        (["BROWNLOW", "VOTES"], "bv", "{:.0f}")]


def ordinal(n):
    n = int(n)
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def _strip_club(s):
    return re.sub(r"\s*\([^)]*\)\s*$", "", str(s)).strip()


def gather(player):
    """Three seasons of figures and league ranks for one player."""
    first, sur = player.split(" ", 1)

    hist = pd.read_csv("fitzroy_stats_all.csv", low_memory=False)
    hist["Season"] = pd.to_numeric(hist["Season"], errors="coerce")
    hist["Round_num"] = pd.to_numeric(hist["Round"], errors="coerce")
    hist = hist[hist["Round_num"].notna()]

    cur = pd.read_csv("data_2026/afltables_2026.csv", low_memory=False)
    cur["Round_num"] = pd.to_numeric(cur["Round"], errors="coerce")
    cur = cur[cur["Round_num"].notna()]

    cvh = pd.read_csv("coaches_votes_all.csv", low_memory=False)
    cv26 = pd.read_csv("data_2026/coaches_votes_2026.csv")
    cvh["p"] = cvh["Player.Name"].map(_strip_club)
    cv26["p"] = cv26["Player.Name"].map(_strip_club)
    CV = pd.concat([cvh[["Season", "p", "Coaches.Votes"]],
                    cv26[["Season", "p", "Coaches.Votes"]]])

    out = {}
    for yr, src in ((2024, hist[hist.Season == 2024]),
                    (2025, hist[hist.Season == 2025]),
                    (2026, cur)):
        agg = {"sur": ("Surname", "first"), "fn": ("First.name", "first"),
               "team": ("Playing.for", "last"), "games": ("Round_num", "size"),
               "disp": ("Disposals", "mean"), "cp": ("Contested.Possessions", "mean"),
               "clr": ("Clearances", "mean")}
        if "Brownlow.Votes" in src.columns:
            agg["bv"] = ("Brownlow.Votes", "sum")
        g = src.groupby("ID").agg(**agg)
        hit = g[(g.sur == sur) & (g.fn == first)]
        if hit.empty:
            raise SystemExit(f"{player} has no {yr} home-and-away games in the archive.")
        pid = hit.index[0]
        q = g[g.games >= MIN_GAMES]
        r = {c: int(q[c].rank(ascending=False, method="min")[pid]) for c in
             ("disp", "cp", "clr")}
        row = g.loc[pid]

        cy = CV[CV.Season == yr].groupby("p")["Coaches.Votes"].sum()
        cvt = float(cy.get(player, 0))
        rec = {"team": str(row.team), "games": int(row.games), "qualified": len(q),
               "disp": float(row.disp), "disp_r": r["disp"],
               "cp": float(row.cp), "cp_r": r["cp"],
               "clr": float(row.clr), "clr_r": r["clr"],
               "cv": cvt, "cv_r": int((cy > cvt).sum()) + 1}
        if yr < 2026:
            rec["bv"] = float(row.bv)
            rec["bv_r"] = None
        else:
            proj = pd.read_csv("predictions/season_2026.csv")
            m = proj[proj.Player_Name == player]
            rec["bv"] = float(m.Exp_Total_Votes.iloc[0]) if len(m) else 0.0
            rec["bv_r"] = None
            rec["bv_exp"] = True
        out[yr] = rec
    return out


ABBR = {"Greater Western Sydney": "GWS", "Western Bulldogs": "WESTERN BULLDOGS",
        "Brisbane Lions": "BRISBANE", "North Melbourne": "NTH MELBOURNE",
        "Port Adelaide": "PORT ADELAIDE", "West Coast": "WEST COAST",
        "Gold Coast": "GOLD COAST", "St Kilda": "ST KILDA"}


def draw(player, place, tagline, d):
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m = 56 * S
    right = (W - 56) * S
    years = [2024, 2025, 2026]

    lab_w = 320 * S
    col_x0 = m + lab_w
    col_w = (right - col_x0) // 3
    centre = [col_x0 + col_w * i + col_w // 2 for i in range(3)]

    def text(xy, t, f, fill, anchor="la"):
        k.text(xy, t, font=f, fill=fill, anchor=anchor)

    # The current season is a faint lift and a hairline above it. No fill, no
    # border, no pill anywhere on the card: at timeline size the emerald figures
    # already carry the eye, and boxing them as well is what made it shout.
    cx0 = col_x0 + col_w * 2
    PANEL_TOP, PANEL_BOT = 282 * S, 1372 * S
    k.rectangle([cx0, PANEL_TOP, right, PANEL_BOT], fill=PANEL)
    k.rectangle([cx0, PANEL_TOP, right, PANEL_TOP + 3 * S], fill=EMERALD)

    text((m, 44 * S), "CHA CHING", font("display", 29), EMERALD)
    text((right, 44 * S), f"BROWNLOW COUNTDOWN   {ordinal(place).upper()}",
         font("display", 29), MUTED, anchor="ra")
    k.rectangle([m, 100 * S, right, 101 * S], fill=LINE)

    text((m, 132 * S), player.upper(), font("name", 80), INK)
    text((m, 234 * S), tagline, font("body", 33), MUTED)

    for i, yr in enumerate(years):
        cur = yr == 2026
        text((centre[i], 302 * S), str(yr), font("display", 45),
             EMERALD if cur else INK, anchor="ma")
        club = ABBR.get(d[yr]["team"], d[yr]["team"].upper())
        text((centre[i], 360 * S), club, font("display", 25), MUTED, anchor="ma")
        text((centre[i], 392 * S), f"{d[yr]['games']} GAMES", font("display", 23),
             MUTED, anchor="ma")
    k.rectangle([m, 430 * S, right, 431 * S], fill=LINE)

    top, rh = 450 * S, 184 * S
    for ri, (lines, key, fmt) in enumerate(ROWS):
        y = top + ri * rh
        if ri:
            k.rectangle([m, y - 12 * S, right, y - 11 * S], fill=LINE)
        ly = y + (46 if len(lines) == 1 else 24) * S
        for li, ln in enumerate(lines):
            text((m, ly + li * 44 * S), ln, font("display", 37), INK)
        for i, yr in enumerate(years):
            cur = yr == 2026
            rec = d[yr]
            val = f"{rec['bv']:.1f}" if (key == "bv" and cur) else fmt.format(rec[key])
            text((centre[i], y + 16 * S), val, font("fig", 78),
                 EMERALD if cur else INK, anchor="ma")
            # Rank rides under the figure as plain text. Legibility comes from
            # size and a light enough ink, not from a box: 38px is 11px once
            # Twitter has scaled the card, and RANK_INK holds ~6:1 on this
            # ground. The pills these replaced were the tacky part.
            rk = rec.get(key + "_r")
            if rk:
                text((centre[i], y + 112 * S), ordinal(rk), font("display", 38),
                     EMERALD if cur else RANK_INK, anchor="ma")
            elif key == "bv" and cur:
                text((centre[i], y + 112 * S), "EXPECTED", font("display", 30),
                     EMERALD, anchor="ma")
    k.rectangle([m, PANEL_BOT + 14 * S, right, PANEL_BOT + 15 * S], fill=LINE)

    pool = " / ".join(str(d[y]["qualified"]) for y in years)
    text((m, 1404 * S),
         f"Ranks among players with {MIN_GAMES}+ home-and-away games that season",
         font("body", 25), MUTED)
    text((m, 1440 * S),
         f"({pool} qualified).  Brownlow votes unranked.  2026 = expected votes.",
         font("body", 25), MUTED)

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", player.lower()).strip("_")
    path = os.path.join(OUT_DIR, f"countdown_{place:02d}_{slug}.png")
    # Save the FULL canvas, W*S by H*S. This used to downsample to W by H first,
    # which threw the resolution away for nothing: the card was drawn at 2400x3000
    # and saved at 1200x1500, so it went soft the moment anyone tapped it to
    # full-screen (an iPad needs ~1668px across, a desktop ~1800). PIL renders the
    # type antialiased at the real size, so there is no quality argument for the
    # downsample either.
    #
    # It stays a PNG on X at this size: 2400x3000 comes to ~260KB, under the
    # ~900KB above which X re-encodes to JPEG, and JPEG on small text over a dark
    # ground is exactly where ringing artefacts show. Do not add a quantise step
    # to shrink it further; there is no need and it would chew the type edges.
    img.save(path, "PNG", optimize=True)
    prev = os.path.join(OUT_DIR, f"countdown_{place:02d}_{slug}_timeline.png")
    img.resize((350, int(350 * H / W)), Image.LANCZOS).save(prev, "PNG")
    return path, prev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("player")
    ap.add_argument("place", type=int)
    ap.add_argument("--tagline", default="")
    ap.add_argument("--font", default="twcen",
                    help=", ".join(FONT_SETS))
    a = ap.parse_args()
    set_fonts(a.font)
    d = gather(a.player)
    p, prev = draw(a.player, a.place, a.tagline, d)
    print(f"OK  wrote {p}")
    print(f"    timeline preview (what Twitter shows on a phone): {prev}")
    for yr in (2024, 2025, 2026):
        r = d[yr]
        print(f"    {yr} {r['team'][:22]:<23} {r['games']:>2}g  "
              f"disp {r['disp']:>5.1f} ({ordinal(r['disp_r']):>5})  "
              f"cp {r['cp']:>5.1f} ({ordinal(r['cp_r']):>5})  "
              f"clr {r['clr']:>4.1f} ({ordinal(r['clr_r']):>5})  "
              f"cv {r['cv']:>3.0f} ({ordinal(r['cv_r']):>5})  bv {r['bv']:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
