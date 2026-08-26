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
SI_PATH = "data_advanced/score_involvements.csv"
SI_COL = "Score_Involvements_Actual"
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

# Every candidate stat, with the label split into lines because at a legible
# size "CONTESTED POSSESSIONS" will not fit one line beside the number columns.
# Which of these a card shows is CHOSEN PER PLAYER, see pick_stats: a fixed five
# rows says the same thing about a tagger, a ruck and a small forward, and
# usually says the wrong thing about two of them.
CATALOGUE = [
    (["DISPOSALS"],              "Disposals",               "{:.1f}"),
    (["CONTESTED", "POSSESSIONS"], "Contested.Possessions", "{:.1f}"),
    (["CLEARANCES"],             "Clearances",              "{:.1f}"),
    (["TACKLES"],                "Tackles",                 "{:.1f}"),
    (["GOALS"],                  "Goals",                   "{:.1f}"),
    (["MARKS"],                  "Marks",                   "{:.1f}"),
    (["INSIDE 50s"],             "Inside.50s",              "{:.1f}"),
    (["KICKS"],                  "Kicks",                   "{:.1f}"),
    (["HANDBALLS"],              "Handballs",               "{:.1f}"),
    (["MARKS", "INSIDE 50"],     "Marks.Inside.50",         "{:.1f}"),
    (["CONTESTED", "MARKS"],     "Contested.Marks",         "{:.1f}"),
    (["GOAL", "ASSISTS"],        "Goal.Assists",            "{:.1f}"),
    (["REBOUND 50s"],            "Rebounds",                "{:.1f}"),
    (["ONE", "PERCENTERS"],      "One.Percenters",          "{:.1f}"),
    (["HIT-OUTS"],               "Hit.Outs",                "{:.1f}"),
    # The REAL AFL stat, joined from data_advanced/score_involvements.csv.
    # NOT features.py's `Score_Involvements`, which is a model feature defined as
    # Goals + Goal.Assists + Marks.Inside.50 + Inside.50s: it double counts a
    # marked goal, omits every possession in a scoring chain, and lands in the
    # same 6-to-9 range for a midfielder, so the wrong number looks right. Never
    # show that one to a reader as a score involvement. Coverage starts 2015,
    # which covers every season a countdown card compares.
    (["SCORE", "INVOLVEMENTS"],  "Score_Involvements_Actual", "{:.1f}"),
]
# Always shown, in this order, after the chosen stats. Coaches votes are an
# independent read on the same season and Brownlow votes are the whole point of
# the countdown, so neither competes for a slot.
ALWAYS = [(["COACHES", "VOTES"], "cv", "{:.0f}"),
          (["BROWNLOW", "VOTES"], "bv", "{:.0f}")]
N_PICK = 4


def ordinal(n):
    n = int(n)
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def _strip_club(s):
    return re.sub(r"\s*\([^)]*\)\s*$", "", str(s)).strip()


def gather(player, seasons):
    """Per-game averages and league ranks for every catalogue stat, per season."""
    first, sur = player.split(" ", 1)
    cols = [c for _, c, _ in CATALOGUE]

    hist = pd.read_csv("fitzroy_stats_all.csv", low_memory=False)
    hist["Season"] = pd.to_numeric(hist["Season"], errors="coerce")
    hist["Round_num"] = pd.to_numeric(hist["Round"], errors="coerce")
    hist = hist[hist["Round_num"].notna()]

    cur = pd.read_csv("data_2026/afltables_2026.csv", low_memory=False)
    cur["Round_num"] = pd.to_numeric(cur["Round"], errors="coerce")
    cur = cur[cur["Round_num"].notna()]
    cur["Season"] = 2026

    # Real score involvements ride in on Season + Round_num + ID. Deduped before
    # the merge: a repeated key on the RIGHT of a left join multiplies the left
    # row instead of annotating it. Absent seasons simply lose the stat, and
    # pick_stats skips a column it cannot rank.
    _si = pd.read_csv(SI_PATH, usecols=["Season", "Round_num", "ID", SI_COL])
    _si = _si.drop_duplicates(["Season", "Round_num", "ID"])
    hist = hist.merge(_si, on=["Season", "Round_num", "ID"], how="left")
    cur = cur.merge(_si, on=["Season", "Round_num", "ID"], how="left")

    cvh = pd.read_csv("coaches_votes_all.csv", low_memory=False)
    cv26 = pd.read_csv("data_2026/coaches_votes_2026.csv")
    cvh["p"] = cvh["Player.Name"].map(_strip_club)
    cv26["p"] = cv26["Player.Name"].map(_strip_club)
    CV = pd.concat([cvh[["Season", "p", "Coaches.Votes"]],
                    cv26[["Season", "p", "Coaches.Votes"]]])

    out = {}
    for yr in seasons:
        src = cur if yr == 2026 else hist[hist.Season == yr]
        agg = {"sur": ("Surname", "first"), "fn": ("First.name", "first"),
               "team": ("Playing.for", "last"), "games": ("Round_num", "size")}
        agg.update({c: (c, "mean") for c in cols if c in src.columns})
        if "Brownlow.Votes" in src.columns:
            agg["bv"] = ("Brownlow.Votes", "sum")
        g = src.groupby("ID").agg(**agg)
        hit = g[(g.sur == sur) & (g.fn == first)]
        if hit.empty:
            raise SystemExit(f"{player} has no {yr} home-and-away games in the archive.")
        pid = hit.index[0]
        q = g[g.games >= MIN_GAMES]
        row = g.loc[pid]

        cy = CV[CV.Season == yr].groupby("p")["Coaches.Votes"].sum()
        cvt = float(cy.get(player, 0))
        rec = {"team": str(row.team), "games": int(row.games), "qualified": len(q),
               "val": {}, "rank": {},
               "cv": cvt, "cv_r": int((cy > cvt).sum()) + 1}
        for c in cols:
            if c in g.columns:
                rec["val"][c] = float(row[c])
                rec["rank"][c] = int(q[c].rank(ascending=False, method="min")[pid])
        if yr < 2026:
            rec["bv"] = float(row.bv)
            rec["bv_r"] = None
        else:
            proj = pd.read_csv("predictions/season_2026.csv")
            m = proj[proj.Player_Name == player]
            rec["bv"] = float(m.Exp_Total_Votes.iloc[0]) if len(m) else 0.0
            rec["bv_r"] = None
        out[yr] = rec
    return out


# A stat earns its slot by being one this player is actually GOOD at, then by
# how far he moved. Strength gates and improvement ranks, in that order: a stat
# he improved at while staying ordinary says nothing worth a row, and a stat he
# is elite at says plenty even if it did not move (Clayton Oliver leading the
# league for contested ball is the case). ELIGIBLE is the gate in percentile
# terms, so it means the same thing in a 408-player field as a 433-player one.
#
# STRENGTH IS CUBED, and that is the whole fix. Linear strength barely separates
# 10th from 79th in a 408-man field (0.98 against 0.81), so a big climb through
# the pack outscored genuine quality: Shai Bolton's tackles went 193rd to 79th
# and beat his being 10th in the AFL for score involvements onto the card.
# Cubing spreads the top end (0.94 against 0.53) so improvement decides between
# strong stats rather than dragging a mediocre one in.
# The gate is top 12%, roughly top 50 in a 408-man field, because a row has to
# earn its space. Bolton's handballs at 53rd cleared an 18% gate and said
# nothing: his real story is 3rd, 5th and 10th in the AFL, and a fourth row of
# "53rd" only diluted it. Cards therefore show 3 or 4 stats, not always 4.
ELIGIBLE = 0.12
MIN_PICK = 3                     # relax the gate rather than ship a sparse card
W_STRENGTH, W_IMPROVE = 0.55, 0.45


def pick_stats(d, seasons):
    prev, cur = seasons[-2], seasons[-1]
    n = d[cur]["qualified"]
    scored = []
    for lines, col, fmt in CATALOGUE:
        rc = d[cur]["rank"].get(col)
        if rc is None or rc > n * ELIGIBLE:
            continue
        rp = d[prev]["rank"].get(col)
        strength = (1 - (rc - 1) / n) ** 3
        improve = max((rp - rc) / d[prev]["qualified"], 0) if rp else 0.0
        scored.append((W_STRENGTH * strength + W_IMPROVE * improve,
                       lines, col, fmt))
    scored.sort(key=lambda x: -x[0])
    picked = [(l, c, f) for _, l, c, f in scored[:N_PICK]]
    if len(picked) < MIN_PICK:
        # Too few cleared the gate. Fall back to the best available by rank
        # alone, so a card never renders with one row, but keep the order.
        have = {c for _, c, _ in picked}
        rest = sorted(((d[cur]["rank"].get(c, 10 ** 6), l, c, f)
                       for l, c, f in CATALOGUE if c not in have
                       and c in d[cur]["rank"]))
        picked += [(l, c, f) for _, l, c, f in rest[:MIN_PICK - len(picked)]]
    return picked


ABBR = {"Greater Western Sydney": "GWS", "Western Bulldogs": "WESTERN BULLDOGS",
        "Brisbane Lions": "BRISBANE", "North Melbourne": "NTH MELBOURNE",
        "Port Adelaide": "PORT ADELAIDE", "West Coast": "WEST COAST",
        "Gold Coast": "GOLD COAST", "St Kilda": "ST KILDA"}


def draw(player, place, tagline, d, seasons, picked):
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = 56 * S, (W - 56) * S
    rows = picked + ALWAYS
    lab_w = 320 * S
    col_x0 = m + lab_w
    ncol = len(seasons)
    col_w = (right - col_x0) // ncol
    centre = [col_x0 + col_w * i + col_w // 2 for i in range(ncol)]

    def text(xy, t, f, fill, anchor="la"):
        k.text(xy, t, font=f, fill=fill, anchor=anchor)

    cur_i = len(seasons) - 1
    cx0 = col_x0 + col_w * cur_i
    PANEL_TOP, PANEL_BOT = 282 * S, 1372 * S
    k.rectangle([cx0, PANEL_TOP, cx0 + col_w, PANEL_BOT], fill=PANEL)
    k.rectangle([cx0, PANEL_TOP, cx0 + col_w, PANEL_TOP + 3 * S], fill=EMERALD)

    text((m, 44 * S), "CHA CHING", font("display", 29), EMERALD)
    text((right, 44 * S), f"BROWNLOW COUNTDOWN   {ordinal(place).upper()}",
         font("display", 29), MUTED, anchor="ra")
    k.rectangle([m, 100 * S, right, 101 * S], fill=LINE)
    text((m, 132 * S), player.upper(), font("name", 80), INK)
    if tagline:
        text((m, 234 * S), tagline, font("body", 33), MUTED)

    for i, yr in enumerate(seasons):
        cur = i == cur_i
        text((centre[i], 302 * S), str(yr), font("display", 45),
             EMERALD if cur else INK, anchor="ma")
        club = ABBR.get(d[yr]["team"], d[yr]["team"].upper())
        text((centre[i], 360 * S), club, font("display", 25), MUTED, anchor="ma")
        text((centre[i], 394 * S), f"{d[yr]['games']} GAMES", font("display", 23),
             MUTED, anchor="ma")
    k.rectangle([m, 430 * S, right, 431 * S], fill=LINE)

    top = 452 * S
    rh = int((1372 * S - top) / len(rows))
    for ri, (lines, key, fmt) in enumerate(rows):
        y = top + ri * rh
        if ri:
            k.rectangle([m, y - 12 * S, right, y - 11 * S], fill=LINE)
        ly = y + (int(rh / S * 0.24) if len(lines) == 1 else int(rh / S * 0.11)) * S
        for li, ln in enumerate(lines):
            text((m, ly + li * 44 * S), ln, font("display", 37), INK)

        def value_of(yr):
            r = d[yr]
            if key in ("cv", "bv"):
                return r[key]
            return r["val"].get(key)

        for i, yr in enumerate(seasons):
            cur = i == cur_i
            v = value_of(yr)
            if v is None:
                continue
            txt = f"{v:.1f}" if (key == "bv" and yr == 2026) else fmt.format(v)
            text((centre[i], y + int(rh / S * 0.10) * S), txt, font("fig", 74),
                 EMERALD if cur else INK, anchor="ma")
            rk = (d[yr]["rank"].get(key) if key not in ("cv", "bv")
                  else (d[yr]["cv_r"] if key == "cv" else None))
            if rk:
                text((centre[i], y + int(rh / S * 0.56) * S), ordinal(rk),
                     font("display", 36), EMERALD if cur else RANK_INK, anchor="ma")
            elif key == "bv" and yr == 2026:
                text((centre[i], y + int(rh / S * 0.56) * S), "EXPECTED",
                     font("display", 29), EMERALD, anchor="ma")

    k.rectangle([m, PANEL_BOT + 14 * S, right, PANEL_BOT + 15 * S], fill=LINE)
    pool = " / ".join(str(d[y]["qualified"]) for y in seasons)
    text((m, 1404 * S),
         f"Ranks among players with {MIN_GAMES}+ home-and-away games that season",
         font("body", 25), MUTED)
    text((m, 1440 * S),
         f"({pool} qualified).  Brownlow votes unranked.  2026 = expected votes.",
         font("body", 25), MUTED)

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", player.lower()).strip("_")
    path = os.path.join(OUT_DIR, f"countdown_{place:02d}_{slug}.png")
    img.save(path, "PNG", optimize=True)
    prev = os.path.join(OUT_DIR, f"countdown_{place:02d}_{slug}_timeline.png")
    img.resize((350, int(350 * H / W)), Image.LANCZOS).save(prev, "PNG")
    return path, prev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("player")
    ap.add_argument("place", type=int)
    ap.add_argument("--tagline", default="")
    ap.add_argument("--font", default="twcen", help=", ".join(FONT_SETS))
    ap.add_argument("--seasons", type=int, default=2, choices=(2, 3),
                    help="2 = 2025 v 2026 (default), 3 = adds 2024")
    a = ap.parse_args()
    set_fonts(a.font)
    seasons = [2024, 2025, 2026][-a.seasons:]
    d = gather(a.player, seasons)
    picked = pick_stats(d, seasons)
    p, prev = draw(a.player, a.place, a.tagline, d, seasons, picked)
    print(f"OK  wrote {p}")
    print(f"    timeline preview (what Twitter shows on a phone): {prev}")
    print("    chosen: " + ", ".join(" ".join(l) for l, _, _ in picked))
    for yr in seasons:
        r = d[yr]
        bits = [f"{c.split('.')[0][:9]} {r['val'][c]:.1f}({ordinal(r['rank'][c])})"
                for _, c, _ in picked if c in r["val"]]
        print(f"    {yr} {r['team'][:20]:<21}{r['games']:>2}g  " + "  ".join(bits)
              + f"  cv {r['cv']:.0f}({ordinal(r['cv_r'])})  bv {r['bv']:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
