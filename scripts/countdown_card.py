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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import features as feat  # noqa: E402  the repo's own feed-name resolver

MIN_GAMES = 12
SI_PATH = "data_advanced/score_involvements.csv"
SI_COL = "Score_Involvements_Actual"
# Everything data_advanced carries that is a performance stat. Time_On_Ground_Pct
# is deliberately NOT here: a high TOG is a role, not an achievement, and ranking
# by it would put players who never leave the ground above players who are good.
ADV_COLS = [SI_COL, "Metres_Gained", "Intercepts"]

# Wheelo, 2015 onward. Only columns the other two sources do NOT already carry:
# Intercepts, MetresGained and ScoreInvolvements are all in data_advanced and
# agree with Wheelo exactly (154 / 7.00 for Ed Richards from both), so taking
# them twice would only create a chance for the two to drift.
#
# Score involvement PERCENTAGE is derived here rather than read: it is the
# player's score involvements over his TEAM's score launches, which is how
# Wheelo publishes it. Against team scoring shots instead it reads 33.8% for
# Richards where Wheelo says 31.0, and the rank is the same either way, so the
# denominator is the whole difference.
WHEELO_2026 = "data_wheelo/wheelo_2026.csv"
WHEELO_ALL = "data_wheelo/wheelo_all_seasons.csv"
WHEELO_COLS = ["PressureActs", "InterceptMarks", "GroundBallGets",
               "ScoreLaunches", "FirstPossessions", "xScore",
               "DisposalEfficiency", "ScoreInvolvements"]
SI_PCT = "ScoreInvolvementPct"

# A PERCENTAGE CANNOT BE AVERAGED PER GAME. Every other stat here is a per-game
# mean, which is right for a count; for a ratio it is not. Ed Richards' score
# involvement percentage is 30.5 as the mean of his per-game figures and 31.2 as
# season involvements over season team launches, and Wheelo publishes 31.0. Each
# entry is (numerator, denominator) and the season figure is the ratio of the
# two sums, weighting every game by how much of the denominator it carried.
RATIO_STATS = {
    SI_PCT: ("ScoreInvolvements", "_team_sl"),
    "DisposalEfficiency": ("_eff_disposals", "Disposals"),
}
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
GOLD = "#f0b429"                 # results, and the tail of the CHING gradient
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
    # Also from data_advanced, 2015 onward. Metres gained runs in the hundreds
    # so it formats without a decimal.
    (["METRES", "GAINED"],       "Metres_Gained",           "{:.0f}"),
    (["INTERCEPTS"],             "Intercepts",              "{:.1f}"),
    # Wheelo. Percentages format without a decimal place, counts with one.
    (["PRESSURE", "ACTS"],       "PressureActs",            "{:.1f}"),
    (["INTERCEPT", "MARKS"],     "InterceptMarks",          "{:.1f}"),
    (["GROUND BALL", "GETS"],    "GroundBallGets",          "{:.1f}"),
    (["SCORE", "LAUNCHES"],      "ScoreLaunches",           "{:.1f}"),
    (["FIRST", "POSSESSIONS"],   "FirstPossessions",        "{:.1f}"),
    (["EXPECTED", "SCORE"],      "xScore",                  "{:.1f}"),
    (["DISPOSAL", "EFFICIENCY"], "DisposalEfficiency",      "{:.0f}"),
    (["SCORE", "INVOLVEMENT %"], SI_PCT,                   "{:.0f}"),
]
# Always shown, in this order, after the chosen stats. Coaches votes are an
# independent read on the same season and Brownlow votes are the whole point of
# the countdown, so neither competes for a slot.
ALWAYS = [(["COACHES", "VOTES"], "cv", "{:.0f}"),
          (["BROWNLOW", "VOTES"], "bv", "{:.0f}")]
N_PICK = 4


# ── the CHA CHING mark ────────────────────────────────────────
# Lifted from dashboard.py's .ccb-mark: CHA is a vertical silver gradient and
# CHING runs emerald to lime to gold on a diagonal. Flat emerald text was not
# the logo, it was just the accent colour spelling the name.
CHA_STOPS = [(0.0, (233, 238, 243)), (1.0, (138, 154, 169))]
CHING_STOPS = [(0.0, (52, 211, 153)), (0.52, (142, 201, 74)), (1.0, (240, 180, 41))]


def _lerp(stops, t):
    t = min(max(t, 0.0), 1.0)
    for i in range(len(stops) - 1):
        p0, c0 = stops[i]
        p1, c1 = stops[i + 1]
        if p0 <= t <= p1:
            f = 0.0 if p1 == p0 else (t - p0) / (p1 - p0)
            return tuple(int(round(c0[j] + (c1[j] - c0[j]) * f)) for j in range(3))
    return stops[-1][1]


def gradient_text(img, xy, txt, fnt, stops, angle):
    """Draw txt filled with a linear gradient. angle 180 = top to bottom."""
    xy = (int(xy[0]), int(xy[1]))
    box = tuple(int(v) for v in ImageDraw.Draw(img).textbbox(xy, txt, font=fnt))
    w, h = max(1, box[2] - box[0]), max(1, box[3] - box[1])
    pad = 4
    w, h = w + pad * 2, h + pad * 2
    import math
    rad = math.radians(angle - 90)
    dx, dy = math.cos(rad), math.sin(rad)
    denom = abs(dx) * w + abs(dy) * h or 1
    px = []
    for y in range(h):
        for x in range(w):
            t = ((x if dx >= 0 else w - x) * abs(dx)
                 + (y if dy >= 0 else h - y) * abs(dy)) / denom
            px.append(_lerp(stops, t))
    grad = Image.new("RGB", (w, h))
    grad.putdata(px)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text((pad - (box[0] - xy[0]), pad - (box[1] - xy[1])),
                              txt, font=fnt, fill=255)
    img.paste(grad, (box[0] - pad, box[1] - pad), mask)
    return box[2] - box[0]


def draw_mark(img, x, y, size):
    """CHA CHING, in the site's own gradients."""
    f = font("display", size)
    w = gradient_text(img, (x, y), "CHA", f, CHA_STOPS, 180)
    sp = int(ImageDraw.Draw(img).textlength(" ", font=f))
    gradient_text(img, (x + w + sp, y), "CHING", f, CHING_STOPS, 120)


def ordinal(n):
    n = int(n)
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def _strip_club(s):
    return re.sub(r"\s*\([^)]*\)\s*$", "", str(s)).strip()


def _wheelo(seasons, targets):
    """Wheelo stats keyed to the AFLTables spelling, one frame per season.

    Names are resolved with features.resolve_feed_names, the repo's own three
    layer matcher, rather than a join on the raw strings. A raw join reaches
    91%: Wheelo writes O'Sullivan, D'Ambrosio, Bailey J. Williams and Thomas
    Edwards where AFLTables writes OSullivan, DAmbrosio, Bailey Williams and Tom
    Edwards. The resolver reaches 99.98% with nothing unmatched, and it keeps
    team in the key at every layer so the two Bailey Williamses cannot swap.
    """
    out = []
    allw = None
    for yr in seasons:
        if yr == 2026:
            w = pd.read_csv(WHEELO_2026, low_memory=False)
        else:
            if allw is None:
                allw = pd.read_csv(WHEELO_ALL, low_memory=False)
            w = allw[allw.Season == yr].copy()
        if w.empty:
            continue
        w["Team"] = w["Team"].replace(feat.WHEELO_TEAM_FIXES)
        # Team score launches, for the percentage. Computed BEFORE the name
        # resolution, which does not touch team or round.
        tl = w.groupby(["Round", "Team"])["ScoreLaunches"].sum().rename("_team_sl")
        w = w.merge(tl, on=["Round", "Team"], how="left")
        # Effective disposals, reconstructed so efficiency can be re-weighted.
        w["_eff_disposals"] = w["DisposalEfficiency"] / 100.0 * w["Disposals"]
        res, _ = feat.resolve_feed_names(w, targets[yr], "Player", "Team", "Round",
                                         label=f"wheelo {yr}", verbose=False)
        res = res.rename(columns={"Player": "Player_Name", "Team": "Playing.for",
                                  "Round": "Round_num"})
        keep = (["Player_Name", "Playing.for", "Round_num"] + WHEELO_COLS
                + ["_team_sl", "_eff_disposals"])
        r = res[[c for c in keep if c in res.columns]].copy()
        r["Season"] = yr
        # Unique on the merge key or the merge multiplies the left row instead
        # of annotating it. Wheelo's 2025 carries 41 duplicate keys, every one a
        # Gold Coast round 25 row, which inflated the qualified pool from 420 to
        # 421 and would have shifted every 2025 rank by a place. It is the same
        # 2025 round 24/25 duplication already found in game_level_2025.csv (78
        # rows) and backtest_game_level.csv (41), so this is a defect in the
        # season rather than in any one feed, and every consumer has to defend
        # itself.
        r = r.drop_duplicates(["Season", "Round_num", "Player_Name", "Playing.for"])
        out.append(r)
    return pd.concat(out, ignore_index=True) if out else None


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
    _si = pd.read_csv(SI_PATH,
                      usecols=["Season", "Round_num", "ID"] + ADV_COLS)
    _si = _si.drop_duplicates(["Season", "Round_num", "ID"])
    hist = hist.merge(_si, on=["Season", "Round_num", "ID"], how="left")
    cur = cur.merge(_si, on=["Season", "Round_num", "ID"], how="left")

    cvh = pd.read_csv("coaches_votes_all.csv", low_memory=False)
    cv26 = pd.read_csv("data_2026/coaches_votes_2026.csv")
    cvh["p"] = cvh["Player.Name"].map(_strip_club)
    cv26["p"] = cv26["Player.Name"].map(_strip_club)
    CV = pd.concat([cvh[["Season", "p", "Coaches.Votes"]],
                    cv26[["Season", "p", "Coaches.Votes"]]])

    # Wheelo needs a per-season target frame carrying the AFLTables spelling.
    hist["Player_Name"] = (hist["First.name"].str.strip() + " "
                           + hist["Surname"].str.strip())
    cur["Player_Name"] = (cur["First.name"].str.strip() + " "
                          + cur["Surname"].str.strip())
    targets = {yr: (cur if yr == 2026 else hist[hist.Season == yr])
               for yr in seasons}
    wh = _wheelo(seasons, targets)
    if wh is not None:
        key = ["Season", "Round_num", "Player_Name", "Playing.for"]
        hist = hist.merge(wh, on=key, how="left")
        cur = cur.merge(wh[wh.Season == 2026], on=key, how="left")

    out = {}
    for yr in seasons:
        src = cur if yr == 2026 else hist[hist.Season == yr]
        agg = {"sur": ("Surname", "first"), "fn": ("First.name", "first"),
               "team": ("Playing.for", "last"), "games": ("Round_num", "size")}
        agg.update({c: (c, "mean") for c in cols
                    if c in src.columns and c not in RATIO_STATS})
        for _stat, (_num, _den) in RATIO_STATS.items():
            if _num in src.columns and _den in src.columns:
                agg[f"_n_{_stat}"] = (_num, "sum")
                agg[f"_d_{_stat}"] = (_den, "sum")
        if "Brownlow.Votes" in src.columns:
            agg["bv"] = ("Brownlow.Votes", "sum")
        g = src.groupby("ID").agg(**agg)
        for _stat in RATIO_STATS:
            if f"_n_{_stat}" in g.columns:
                g[_stat] = (g[f"_n_{_stat}"] / g[f"_d_{_stat}"]).replace(
                    [float("inf"), -float("inf")], pd.NA) * 100
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


def force_stats(spec):
    """Resolve --stats into CATALOGUE rows, in the order given.

    pick_stats scores a player's stats against the field and takes the best
    four, which is right by default and is why the automatic path stays the
    default. It optimises for "which numbers flatter him", though, and that is
    not always the same question as "which numbers show what happened". On the
    2024-2026 Pickett card it chose TACKLES, 3.6 / 3.6 / 4.6, flat across the
    first step of a three-season arc, over CLEARANCES, 1.6 / 3.3 / 4.5, which
    rises at both steps and nearly triples. Both are true; only one is the
    story. This exists for that case and should stay the exception.
    """
    by_col = {col.lower(): (lines, col, fmt) for lines, col, fmt in CATALOGUE}
    out = []
    for raw in [s.strip() for s in spec.split(",") if s.strip()]:
        hit = by_col.get(raw.lower())
        if hit is None:
            raise SystemExit(
                f"--stats: no catalogue column {raw!r}.\nValid columns:\n  "
                + "\n  ".join(sorted(c for _, c, _ in CATALOGUE)))
        if hit in out:
            raise SystemExit(f"--stats: {raw!r} given twice")
        out.append(hit)
    if not 2 <= len(out) <= 5:
        raise SystemExit("--stats takes between 2 and 5 columns "
                         "(the two always-shown vote rows are added after)")
    return out


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


# A game earns a block by having produced at least one figure inside the
# league's top NOTABLE for the season. Below that it is just a game he played:
# Wanganeen-Milera's third-rated game was 20 kicks and 28 disposals, nothing
# flagged, and it made a card whose rows visibly tailed off. Trailing games are
# dropped rather than the middle ones, and never below MIN_BLOCKS.
NOTABLE = 25
MIN_BLOCKS = 2


def top_games(player, picked, season=2026, n=3, per_game=3, force=None):
    """The player's biggest games, each described by ITS OWN best stats.

    Games are ranked by Exp_Votes rather than by any single stat, because this
    is a Brownlow countdown: the question is which games the model thought were
    vote-winning, not which produced the largest number. For Nasiah
    Wanganeen-Milera that puts a 28-disposal win over Port Adelaide third, ahead
    of a 44-disposal loss, which is the point.

    WITHIN a game the stats are chosen per game, not carried across from the
    season card. Showing the same three every time buries what actually happened:
    his round 20 was the highest-kicking AND furthest-gaining single game any
    player managed all season, and he also kicked four goals from defence, none
    of which a fixed set would have surfaced. Each stat is ranked against every
    player-game in the season, so "league best" means best of ~9,500 and a
    figure that is merely large for him does not get a row.
    """
    g = pd.read_csv(f"predictions/game_level_{season}.csv").drop_duplicates(
        ["Round_num", "ID"], keep="first")
    adv = pd.read_csv(SI_PATH, usecols=["Season", "Round_num", "ID"] + ADV_COLS)
    adv = adv[adv.Season == season].drop(columns="Season").drop_duplicates(
        ["Round_num", "ID"])
    g = g.merge(adv, on=["Round_num", "ID"], how="left")

    label = {c: l for l, c, _ in CATALOGUE}
    cols = [c for _, c, _ in CATALOGUE if c in g.columns]
    me = g[g.Player_Name == player]
    if me.empty:
        raise SystemExit(f"{player} has no {season} games.")

    chosen = me.nlargest(n, "Exp_Votes")
    ranks = {}                       # (round, col) -> league rank of that figure
    for _, r in chosen.iterrows():
        for c in cols:
            v = r.get(c)
            if pd.isna(v):
                continue
            ranks[(int(r.Round_num), c)] = int((g[c] > v).sum()) + 1

    # ONE set of columns for all three games, so a reader can compare down the
    # card instead of re-reading the labels on every row. The columns are still
    # chosen from these games rather than from the season: take each stat's BEST
    # rank across the three and keep the strongest few. For Wanganeen-Milera
    # that is kicks, metres gained and disposals, which is what his round 20 was
    # made of; tackles reached the old per-game list only because round 5 had
    # nothing better, and it told a reader nothing.
    #
    # `force` overrides the pick, because best-rank alone can seat a column that
    # is strong in one game and empty in the others. Rankine's two biggest games
    # of 2026 drew goal assists on a best rank of 21st, which put "1" in a cell
    # of his round 22; metres gained missed the cut at 26th and was 795 and 845
    # in the two games, 42nd and 26th of ~9,500. Read the printed per-game ranks
    # before overriding, and only override to a column that is strong in EVERY
    # block, never to one that flatters a single game.
    if force:
        bad = [c for c in force if c not in cols]
        if bad:
            raise SystemExit(f"--game-stats: not in this season's data: "
                             f"{', '.join(bad)}")
        order = list(force)
    else:
        best_rank = {}
        for (rn, c), rk in ranks.items():
            v = chosen.loc[chosen.Round_num == rn, c].iloc[0]
            if pd.notna(v) and v > 0:
                best_rank[c] = min(best_rank.get(c, 10 ** 9), rk)
        order = [c for c, _ in sorted(best_rank.items(), key=lambda x: x[1])][:per_game]

    # Trim from the end while the last block has nothing worth flagging.
    keep = list(chosen.Round_num.astype(int))
    while len(keep) > MIN_BLOCKS:
        rn = keep[-1]
        if min((ranks.get((rn, c), 10 ** 9) for c in order), default=10 ** 9) <= NOTABLE:
            break
        keep.pop()
    chosen = chosen[chosen.Round_num.astype(int).isin(keep)]

    out = []
    for _, r in chosen.iterrows():
        opp = r["Away.team"] if r["Playing.for"] == r["Home.team"] else r["Home.team"]
        won = (r["Playing.for"] == r["Home.team"]) == (r["Home.score"] > r["Away.score"])
        rn = int(r.Round_num)
        out.append({
            "round": "OR" if (rn - 1 == 0 and season >= 2024) else str(
                rn - 1 if season >= 2024 else rn),
            "opp": ABBR.get(opp, opp.upper()), "won": bool(won),
            "exp": float(r.Exp_Votes),
            # Game-level figures are whole numbers; the catalogue's formats are
            # for per-game averages and would print "39.0 kicks".
            "stats": [(label[c],
                       "-" if pd.isna(r.get(c)) else f"{float(r[c]):,.0f}",
                       ranks.get((rn, c))) for c in order],
        })
    return out


# A game block is header + values + labels + the rank note, ~252px of content.
# The height follows the block count rather than being pinned to the compare
# card's 1500, which left a third of the canvas empty and meant X scaled the
# image down to fit dead space.
GAME_BH = 312
GAME_FOOT = 40        # bottom margin only; no footer text, by standing rule


def draw_games(player, place, games, d, season=2026):
    H2 = 322 + len(games) * GAME_BH + GAME_FOOT
    img = Image.new("RGB", (W * S, H2 * S), BG)
    k = ImageDraw.Draw(img)
    m, right = 56 * S, (W - 56) * S

    def text(xy, t, f, fill, anchor="la"):
        k.text(xy, t, font=f, fill=fill, anchor=anchor)

    draw_mark(img, m, 44 * S, 29)
    text((right, 44 * S), f"BROWNLOW COUNTDOWN   {ordinal(place).upper()}",
         font("display", 29), MUTED, anchor="ra")
    k.rectangle([m, 100 * S, right, 101 * S], fill=LINE)
    text((m, 132 * S), player.upper(), font("name", 80), INK)
    text((m, 236 * S), f"BIGGEST GAMES OF {season}", font("display", 32), MUTED)

    top, bh = 322 * S, GAME_BH * S
    for i, gm in enumerate(games):
        y = top + i * bh
        if i:
            k.rectangle([m, y - 26 * S, right, y - 25 * S], fill=LINE)
        head = f"ROUND {gm['round']}   v {gm['opp']}"
        text((m, y), head, font("display", 34), INK)
        text((right, y), "WON" if gm["won"] else "LOST", font("display", 30),
             GOLD if gm["won"] else MUTED, anchor="ra")
        cells = gm["stats"] + [(["EXPECTED", "VOTES"], f"{gm['exp']:.2f}", None)]
        cw = (right - m) // len(cells)
        for j, (lines, val, rk) in enumerate(cells):
            cx = m + cw * j + cw // 2
            last = j == len(cells) - 1
            text((cx, y + 62 * S), val, font("fig", 72),
                 EMERALD if last else INK, anchor="ma")
            for li, ln in enumerate(lines):
                text((cx, y + 158 * S + li * 32 * S), ln, font("display", 24),
                     MUTED, anchor="ma")
            # Only a genuinely rare figure earns the note. Everything else would
            # be a rank nobody is impressed by, printed in the accent colour.
            if rk == 1:
                text((cx, y + 228 * S), "LEAGUE BEST", font("display", 24),
                     EMERALD, anchor="ma")
            elif rk and rk <= 10:
                text((cx, y + 228 * S), f"{ordinal(rk).upper()} IN THE AFL",
                     font("display", 24), EMERALD, anchor="ma")

    # No footer text on a card, by standing rule. Every threshold and
    # window qualifier this used to carry now lives in the draft copy.

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", player.lower()).strip("_")
    path = os.path.join(OUT_DIR, f"countdown_{place:02d}_{slug}_games.png")
    img.save(path, "PNG", optimize=True)
    prev = os.path.join(OUT_DIR, f"countdown_{place:02d}_{slug}_games_timeline.png")
    img.resize((350, int(350 * H2 / W)), Image.LANCZOS).save(prev, "PNG")
    return path, prev


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
    PANEL_TOP, PANEL_BOT = 282 * S, 1444 * S
    k.rectangle([cx0, PANEL_TOP, cx0 + col_w, PANEL_BOT], fill=PANEL)
    k.rectangle([cx0, PANEL_TOP, cx0 + col_w, PANEL_TOP + 3 * S], fill=EMERALD)

    draw_mark(img, m, 44 * S, 29)
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
    rh = int((PANEL_BOT - top) / len(rows))
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

    # No footer text on a card, by standing rule. Every threshold and
    # window qualifier this used to carry now lives in the draft copy.

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", player.lower()).strip("_")
    path = os.path.join(OUT_DIR, f"countdown_{place:02d}_{slug}.png")
    img.save(path, "PNG", optimize=True)
    prev = os.path.join(OUT_DIR, f"countdown_{place:02d}_{slug}_timeline.png")
    img.resize((350, int(350 * H / W)), Image.LANCZOS).save(prev, "PNG")
    return path, prev


# --------------------------------------------------------------- split mode

# The with/without card. Rows are FIXED rather than picked from the data, and
# that is the whole design. pick_stats() exists to find a player's best angles,
# which is right for a season card and wrong here: choosing the rows after
# seeing which ones moved turns a breakdown into an argument, and a reader has
# no way to tell the two apart. These seven are declared before any split is
# computed and they do not change per subject.
#
# Time on ground is on this card, unlike everywhere else in this file, because
# a claim about workload that hides the minutes is not a claim about workload.
# It is also the row most likely to fall, which is the point of fixing the set.
SPLIT_ROWS = [
    (["CENTRE BOUNCE", "ATTENDANCE %"], "CentreBounceAttendancePercentage", "{:.0f}"),
    (["DISPOSALS"], "Disposals", "{:.1f}"),
    (["CLEARANCES"], "TotalClearances", "{:.1f}"),
    (["GROUND BALL GETS"], "GroundBallGets", "{:.1f}"),
    (["CONTESTED", "POSSESSIONS"], "ContestedPossessions", "{:.1f}"),
    (["TACKLES"], "Tackles", "{:.1f}"),
    (["TIME ON GROUND %"], "TimeOnGround", "{:.0f}"),
]

# A club-mate needs enough of a split for his average to be a rank rather than a
# cameo. 60% of that split's games, which at four games means three.
SPLIT_MIN_SHARE = 0.6


def display_round(rn, season):
    """AFLTables numbers Opening Round as Round 1 from 2024, one ahead of the
    AFL's own count. The games card already does this conversion inline; the
    footer here must match it or one card contradicts another. Conditional on
    season, never unconditional. See CLAUDE.md, "Round numbering".
    """
    rn = int(rn)
    if season < 2024:
        return str(rn)
    return "OR" if rn - 1 == 0 else str(rn - 1)


def gather_split(player, without, season=2026):
    """Split the player's season on whether a named club-mate played.

    Wheelo is the only source here. Its Round aligns with the raw AFLTables
    Round_num, and taking both sides of the split from ONE file is what makes
    the two columns comparable: a stat that exists in Wheelo and not in the
    archive would otherwise be present on one side of the card only.
    """
    w = pd.read_csv(WHEELO_2026 if season == 2026 else WHEELO_ALL, low_memory=False)
    w = w[w.Season == season]
    me = w[w.Player == player]
    if me.empty:
        raise SystemExit(f"{player} has no {season} Wheelo rows.")
    team = me.Team.iloc[-1]
    club = w[w.Team == team]
    if not (club.Player == without).any():
        raise SystemExit(f"{without} has no {season} rows for {team}.")

    out_rounds = set(club.loc[club.Player == without, "Round"])
    mine = set(me.Round)
    idx = {"with": sorted(mine & out_rounds), "without": sorted(mine - out_rounds)}
    if not idx["without"]:
        raise SystemExit(f"{player} played no {season} game without {without}.")

    d = {"team": team, "player": player, "without": without, "season": season,
         "without_surname": without.split()[-1].upper(), "rounds": idx}
    for side, rounds in idx.items():
        sub = club[club.Round.isin(rounds)]
        mrows = me[me.Round.isin(rounds)]
        val, rank, pool = {}, {}, None
        for _, col, _ in SPLIT_ROWS:
            val[col] = float(mrows[col].mean())
            g = sub.groupby("Player")[col].agg(["size", "mean"])
            g = g[g["size"] >= max(1, round(len(rounds) * SPLIT_MIN_SHARE))]
            rank[col] = int((g["mean"] > val[col]).sum()) + 1
            pool = len(g)
        d[side] = {"games": len(rounds), "val": val, "rank": rank, "pool": pool}
    return d


def draw_split(player, place, tagline, sp):
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = 56 * S, (W - 56) * S
    lab_w = 330 * S
    col_x0 = m + lab_w
    col_w = (right - col_x0) // 2
    centre = [col_x0 + col_w // 2, col_x0 + col_w + col_w // 2]
    sides = ["with", "without"]

    def text(xy, t, f, fill, anchor="la"):
        k.text(xy, t, font=f, fill=fill, anchor=anchor)

    PANEL_TOP, PANEL_BOT = 282 * S, 1444 * S
    cx0 = col_x0 + col_w
    k.rectangle([cx0, PANEL_TOP, cx0 + col_w, PANEL_BOT], fill=PANEL)
    k.rectangle([cx0, PANEL_TOP, cx0 + col_w, PANEL_TOP + 3 * S], fill=EMERALD)

    draw_mark(img, m, 44 * S, 29)
    text((right, 44 * S), f"BROWNLOW COUNTDOWN   {ordinal(place).upper()}",
         font("display", 29), MUTED, anchor="ra")
    k.rectangle([m, 100 * S, right, 101 * S], fill=LINE)
    text((m, 132 * S), player.upper(), font("name", 80), INK)
    if tagline:
        text((m, 234 * S), tagline, font("body", 33), MUTED)

    surname = sp["without_surname"]
    for i, side in enumerate(sides):
        cur = side == "without"
        head = f"WITH {surname}" if not cur else f"WITHOUT {surname}"
        text((centre[i], 302 * S), head, font("display", 38),
             EMERALD if cur else INK, anchor="ma")
        text((centre[i], 360 * S), ABBR.get(sp["team"], sp["team"].upper()),
             font("display", 25), MUTED, anchor="ma")
        text((centre[i], 394 * S), f"{sp[side]['games']} GAMES", font("display", 23),
             MUTED, anchor="ma")
    k.rectangle([m, 430 * S, right, 431 * S], fill=LINE)

    top = 452 * S
    rows = SPLIT_ROWS
    rh = int((PANEL_BOT - top) / len(rows))
    for ri, (lines, col, fmt) in enumerate(rows):
        y = top + ri * rh
        if ri:
            k.rectangle([m, y - 12 * S, right, y - 11 * S], fill=LINE)
        ly = y + (int(rh / S * 0.24) if len(lines) == 1 else int(rh / S * 0.11)) * S
        for li, ln in enumerate(lines):
            text((m, ly + li * 44 * S), ln, font("display", 34), INK)
        for i, side in enumerate(sides):
            cur = side == "without"
            v = sp[side]["val"][col]
            text((centre[i], y + int(rh / S * 0.10) * S), fmt.format(v),
                 font("fig", 70), EMERALD if cur else INK, anchor="ma")
            text((centre[i], y + int(rh / S * 0.56) * S),
                 ordinal(sp[side]["rank"][col]) + " AT CLUB", font("display", 30),
                 EMERALD if cur else RANK_INK, anchor="ma")

    # No footer text on a card, by standing rule. Every threshold and
    # window qualifier this used to carry now lives in the draft copy.

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", player.lower()).strip("_")
    wslug = re.sub(r"[^a-z0-9]+", "_", surname.lower()).strip("_")
    path = os.path.join(OUT_DIR, f"countdown_{place:02d}_{slug}_without_{wslug}.png")
    img.save(path, "PNG", optimize=True)
    prev = os.path.join(OUT_DIR,
                        f"countdown_{place:02d}_{slug}_without_{wslug}_timeline.png")
    img.resize((350, int(350 * H / W)), Image.LANCZOS).save(prev, "PNG")
    return path, prev


# --------------------------------------------------------------- form mode

# The before/after card. A season split at a round, which answers a different
# question from split mode: not "who was missing" but "when did he change".
#
# ROWS ARE FIXED, for the same reason SPLIT_ROWS are. Picking the rows after
# seeing which ones moved turns a breakdown into an argument and a reader cannot
# tell the two apart. Expected votes leads because this is a Brownlow card and
# it is the only row that answers the question directly; the four ball-winning
# rows underneath are there to say what the votes were made of.
#
# COACHES VOTES ARE PER GAME HERE, not a season total as on the season card.
# The two windows are different lengths (12 games against 8 for Rankine), so a
# total would read as a fall while the rate more than quadrupled.
# Fourth field is the population the rank is taken against: None for every
# qualifying player, "mid" for midfielders only. A goal tally means nothing
# against a league that includes key forwards, and everything against the
# players doing the same job: 47th of everyone, 2nd of midfielders.
FORM_ROWS = [
    (["EXPECTED", "VOTES / GAME"], "Exp_Votes", "{:.2f}", None),
    (["COACHES", "VOTES / GAME"], "Coaches_Votes", "{:.1f}", None),
    (["DISPOSALS"], "Disposals", "{:.1f}", None),
    (["CONTESTED", "POSSESSIONS"], "Contested.Possessions", "{:.1f}", None),
    (["CLEARANCES"], "Clearances", "{:.1f}", None),
    (["GOALS"], "Goals", "{:.1f}", "mid"),
    (["METRES", "GAINED"], "Metres_Gained", "{:.0f}", None),
]

# A league rank inside a short window needs a games floor or it is a list of
# players who had one good week. 60% of the window's rounds, the same share
# split mode uses at the club, and the card states both the share and the
# qualifying pool.
FORM_MIN_SHARE = 0.6

# "Midfielder" is not a column anywhere in this repo, so it is defined here and
# stated on the card: a player whose mean centre bounce attendance in THAT
# window is at least MID_CBA per cent, from Wheelo.
#
# 40 rather than 50, and the reason is the comparison rather than the definition.
# Rankine attended 45.3% of Adelaide's centre bounces before round 17 and 80.2%
# after. At a 50% line he is not a midfielder in the first window at all, so the
# left column would have no rank and the row would compare a number to nothing.
# 40 is the highest line he clears in both. His rank is 2nd at 40, 50 and 60, so
# the threshold moves the pool and not the answer, but the card must still say
# which line it drew.
MID_CBA = 40
MID_SUFFIX = " OF MIDS"


def _midfielders(lo, hi, season):
    """Player names whose mean centre bounce attendance across raw rounds
    lo..hi is at least MID_CBA per cent. Wheelo is the only source in the repo
    that carries centre bounce attendance at all, and its Round aligns with the
    raw AFLTables Round_num.
    """
    path = WHEELO_2026 if season == 2026 else WHEELO_ALL
    w = pd.read_csv(path, low_memory=False)
    w = w[(w.Season == season) & (w.Round >= lo) & (w.Round <= hi)]
    cba = w.groupby("Player")["CentreBounceAttendancePercentage"].mean()
    return set(cba[cba >= MID_CBA].index)


def gather_form(player, afl_round, season=2026):
    """Split a season at a round and rank each half against the league.

    `afl_round` is the AFL's own round number, because that is what the card
    prints and what anyone asking for this split has in mind. AFLTables numbers
    Opening Round as round 1 from 2024, so the raw cut is one higher. Getting
    this backwards silently moves the split by a week, which is exactly the kind
    of error a finished card cannot show you.

    Expected votes come from predictions/game_level_<season>.csv and are model
    output; every other row is a counted stat from the same file, with metres
    gained joined from data_advanced. One source for both halves, so a column
    present on one side and missing on the other cannot happen.
    """
    raw_split = afl_round + 1 if season >= 2024 else afl_round
    g = pd.read_csv(f"predictions/game_level_{season}.csv", low_memory=False)
    g = g.drop_duplicates(["Round_num", "ID"], keep="first")
    adv = pd.read_csv(SI_PATH, usecols=["Season", "Round_num", "ID"] + ADV_COLS)
    adv = adv[adv.Season == season].drop(columns="Season").drop_duplicates(
        ["Round_num", "ID"])
    g = g.merge(adv, on=["Round_num", "ID"], how="left")
    if player not in set(g.Player_Name):
        raise SystemExit(f"{player} has no {season} games.")

    d = {"player": player, "season": season, "afl_round": afl_round,
         "raw_split": raw_split}
    for side, w in (("before", g[g.Round_num < raw_split]),
                    ("after", g[g.Round_num >= raw_split])):
        mine = w[w.Player_Name == player]
        if mine.empty:
            raise SystemExit(f"{player} played no game {side} round {afl_round}.")
        nrounds = w.Round_num.nunique()
        floor = max(1, round(nrounds * FORM_MIN_SHARE))
        lo, hi = w.Round_num.min(), w.Round_num.max()
        mids = _midfielders(lo, hi, season)
        if player not in mids:
            raise SystemExit(
                f"{player} averaged under {MID_CBA}% centre bounce attendance "
                f"{side} round {afl_round}, so the goals row has no rank on one "
                f"side. Lower MID_CBA or drop the row.")
        val, rank, pool = {}, {}, {}
        for _, col, _, group in FORM_ROWS:
            val[col] = float(mine[col].mean())
            q = w.groupby("Player_Name")[col].agg(["size", "mean"])
            q = q[q["size"] >= floor]
            if group == "mid":
                q = q[q.index.isin(mids)]
            rank[col] = int((q["mean"] > val[col]).sum()) + 1
            pool[group] = len(q)
        d[side] = {"games": len(mine), "val": val, "rank": rank,
                   "pool": pool[None], "mid_pool": pool.get("mid"),
                   "rounds": nrounds, "floor": floor,
                   "won": int((mine.Outcome == "W").sum()),
                   "lost": int((mine.Outcome == "L").sum()),
                   "ev_total": float(mine.Exp_Votes.sum()),
                   "cv_total": float(mine.Coaches_Votes.sum())}
    return d


def draw_form(player, place, tagline, fm):
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = 56 * S, (W - 56) * S
    lab_w = 330 * S
    col_x0 = m + lab_w
    col_w = (right - col_x0) // 2
    centre = [col_x0 + col_w // 2, col_x0 + col_w + col_w // 2]
    sides = ["before", "after"]

    def text(xy, t, f, fill, anchor="la"):
        k.text(xy, t, font=f, fill=fill, anchor=anchor)

    PANEL_TOP, PANEL_BOT = 282 * S, 1444 * S
    cx0 = col_x0 + col_w
    k.rectangle([cx0, PANEL_TOP, cx0 + col_w, PANEL_BOT], fill=PANEL)
    k.rectangle([cx0, PANEL_TOP, cx0 + col_w, PANEL_TOP + 3 * S], fill=EMERALD)

    draw_mark(img, m, 44 * S, 29)
    text((right, 44 * S), f"BROWNLOW COUNTDOWN   {ordinal(place).upper()}",
         font("display", 29), MUTED, anchor="ra")
    k.rectangle([m, 100 * S, right, 101 * S], fill=LINE)
    text((m, 132 * S), player.upper(), font("name", 80), INK)
    if tagline:
        text((m, 234 * S), tagline, font("body", 33), MUTED)

    rd = fm["afl_round"]
    heads = [f"BEFORE ROUND {rd}", f"ROUND {rd} ONWARDS"]
    for i, side in enumerate(sides):
        cur = side == "after"
        text((centre[i], 302 * S), heads[i], font("display", 36),
             EMERALD if cur else INK, anchor="ma")
        text((centre[i], 360 * S), f"{fm[side]['games']} GAMES",
             font("display", 25), MUTED, anchor="ma")
        text((centre[i], 394 * S),
             f"{fm[side]['won']} WINS, {fm[side]['lost']} LOSSES",
             font("display", 23), MUTED, anchor="ma")
    k.rectangle([m, 430 * S, right, 431 * S], fill=LINE)

    top = 452 * S
    rh = int((PANEL_BOT - top) / len(FORM_ROWS))
    for ri, (lines, col, fmt, group) in enumerate(FORM_ROWS):
        y = top + ri * rh
        if ri:
            k.rectangle([m, y - 12 * S, right, y - 11 * S], fill=LINE)
        ly = y + (int(rh / S * 0.24) if len(lines) == 1 else int(rh / S * 0.11)) * S
        for li, ln in enumerate(lines):
            text((m, ly + li * 44 * S), ln, font("display", 34), INK)
        for i, side in enumerate(sides):
            cur = side == "after"
            text((centre[i], y + int(rh / S * 0.10) * S),
                 fmt.format(fm[side]["val"][col]), font("fig", 70),
                 EMERALD if cur else INK, anchor="ma")
            # A bare ordinal everywhere except the one row ranked against a
            # different population. That row says so, because "2nd" beside six
            # league ranks would read as 2nd in the league.
            note = ordinal(fm[side]["rank"][col])
            if group == "mid":
                note += MID_SUFFIX
            text((centre[i], y + int(rh / S * 0.56) * S), note,
                 font("display", 28), EMERALD if cur else RANK_INK, anchor="ma")

    # No footer text on a card, by standing rule. Every threshold and
    # window qualifier this used to carry now lives in the draft copy.

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", player.lower()).strip("_")
    path = os.path.join(OUT_DIR, f"countdown_{place:02d}_{slug}_form_r{rd}.png")
    img.save(path, "PNG", optimize=True)
    prev = path.replace(".png", "_timeline.png")
    img.resize((350, int(350 * H / W)), Image.LANCZOS).save(prev, "PNG")
    return path, prev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("player")
    ap.add_argument("place", type=int)
    ap.add_argument("--tagline", default="")
    ap.add_argument("--font", default="twcen", help=", ".join(FONT_SETS))
    ap.add_argument("--mode", choices=("compare", "games", "split", "form"),
                    default="compare",
                    help="compare = season v season; games = the biggest games; "
                         "split = with/without a named club-mate; "
                         "form = the season either side of a round")
    ap.add_argument("--split-round", dest="split_round", type=int, default=0,
                    help="form mode: the AFL round the second window starts at "
                         "(the AFL's own number, not the raw AFLTables one)")
    ap.add_argument("--without", default="",
                    help="split mode: the club-mate whose absence defines the split")
    ap.add_argument("--games", type=int, default=3,
                    help="games mode: how many to consider (weak ones are trimmed)")
    ap.add_argument("--game-stats", dest="game_stats", default="",
                    help="games mode: comma-separated catalogue columns to show "
                         "in every block instead of the automatic pick (e.g. "
                         "\"Clearances,Contested.Possessions,Metres_Gained\")")
    ap.add_argument("--seasons", type=int, default=2, choices=(2, 3),
                    help="2 = 2025 v 2026 (default), 3 = adds 2024")
    ap.add_argument("--stats", default="",
                    help="comma-separated catalogue columns to show instead of "
                         "the automatic pick, in row order (e.g. "
                         "\"Clearances,Metres_Gained,Inside.50s\")")
    a = ap.parse_args()
    set_fonts(a.font)
    seasons = [2024, 2025, 2026][-a.seasons:]
    if a.mode == "form":
        if not a.split_round:
            raise SystemExit("form mode needs --split-round <AFL round>")
        fm = gather_form(a.player, a.split_round)
        p, prev = draw_form(a.player, a.place, a.tagline, fm)
        print(f"OK  wrote {p}")
        print(f"    timeline preview: {prev}")
        print(f"    split at AFL round {a.split_round} = raw Round_num "
              f"{fm['raw_split']}")
        for side in ("before", "after"):
            r = fm[side]
            bits = [f"{c.split('.')[0][:9]} {r['val'][c]:.2f}"
                    f"({ordinal(r['rank'][c])}{'m' if grp else ''})"
                    for _, c, _, grp in FORM_ROWS]
            print(f"    {side:<7}{r['games']:>2}g {r['won']}-{r['lost']}  "
                  + "  ".join(bits))
            print(f"           expected votes total {r['ev_total']:.2f}, "
                  f"coaches votes total {r['cv_total']:.0f}, "
                  f"pool {r['pool']} at {r['floor']}+ of {r['rounds']} rounds")
        return 0
    if a.mode == "split":
        if not a.without:
            raise SystemExit("split mode needs --without \"<club-mate>\"")
        sp = gather_split(a.player, a.without)
        p, prev = draw_split(a.player, a.place, a.tagline, sp)
        print(f"OK  wrote {p}")
        print(f"    timeline preview: {prev}")
        for side in ("with", "without"):
            r = sp[side]
            bits = [f"{c[:14]} {r['val'][c]:.1f}({ordinal(r['rank'][c])})"
                    for _, c, _ in SPLIT_ROWS]
            print(f"    {side:<8}{r['games']:>2}g  " + "  ".join(bits))
        print(f"    without rounds: {sp['rounds']['without']}")
        return 0
    d = gather(a.player, seasons)
    picked = force_stats(a.stats) if a.stats else pick_stats(d, seasons)
    if a.mode == "games":
        force = [c.strip() for c in a.game_stats.split(",") if c.strip()]
        games = top_games(a.player, picked, n=a.games, force=force or None)
        p, prev = draw_games(a.player, a.place, games, d)
    else:
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
