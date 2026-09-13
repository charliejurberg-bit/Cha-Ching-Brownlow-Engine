"""The season board if the model awarded 3-2-1 in every game.

    python scripts/leaderboard_card.py
    python scripts/leaderboard_card.py --rows 10 --preview

Writes a PNG to drafts/ (gitignored). Same 1200x1500 portrait, palette, fonts
and CHA CHING mark as the countdown cards, imported rather than restated.

THE 3-2-1 RULE IS THE DASHBOARD'S, REPLICATED HERE RATHER THAN REIMAGINED
dashboard.load_game_rounded ranks each game's players by Exp_Votes, breaking
exact ties on Poll_Prob then P_3 then name, and hands 3/2/1 to the top three.
This file does the same thing on the same source so the card and the site
cannot disagree. If that function's tiebreak changes, change it here too. It is
duplicated rather than imported because dashboard.py is a Streamlit app and
importing it executes the whole page.

THE CARD SAYS THIS IS A MODEL AND THAT IS NOT NEGOTIABLE
No 2026 Brownlow vote is public until count night. A board of player names
against vote totals is the single most mistakable artifact this repo produces,
because it is shaped exactly like the real thing the AFL publishes in September.
The guard is carried in TWO places, neither of them removable: the title itself
reads "THE MODEL'S BOARD", and the masthead reads "2026 MODEL PROJECTION". An
explanatory subtitle under the title was dropped on request, which is fine
precisely because the title is doing that work. If a future edit rewords the
title away from the word "model", the subtitle has to come back.

THE RECORD LINE ON ROW 1 IS NARROWER THAN IT LOOKS, AND DELIBERATELY SO
It names Cripps rather than saying "would break the record", because the raw
all-time list does not support the broader claim. Graham Teasdale polled 59 in
1977 and Graham Moss 48 in 1976, and 48 would equal Moss rather than pass him.
Those two seasons awarded DOUBLE votes: 1,512 across the season against 756 in
1975 and 792 in 1978, measured from data_history/brownlow_seasons_1924_1983.csv,
whose Vote_system column calls all of 1931-1983 "3-2-1" and so does not record
the doubling. Against a single 3-2-1 allocation per game, every season except
1976 and 1977, Cripps' 45 in 2024 is the record and 48 passes it by three.
Naming him is both the honest claim and the one that pre-empts the reply.

TIES SHARE A RANK AND BOTH ROWS SHOW IT
Rank is minimum-on-ties, so two players level on 24 both read 7 and the next
player down reads 9. Ranking them 7 and 8 by a decimal the card does not show
would invent a separation the stated figures do not support. The 2026 board has
two such pairs in the top ten, which is why this is handled rather than assumed
away.

WHOLE VOTES ONLY, NO DECIMAL COLUMN
The decimal board (Exp_Votes) is a different quantity and putting both on one
card invites a reader to subtract them. The site carries both behind a toggle,
which is the right place for that comparison. Here the tiebreak uses Exp_Votes
and never shows it.
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from countdown_card import (  # noqa: E402
    BG, EMERALD, INK, MUTED, RANK_INK, GOLD, LINE,
    W, H, S, draw_mark, font, set_fonts, FONT_SETS,
)

OUT_DIR = "drafts"
GAME_LEVEL = "predictions/game_level_{}.csv"
CUR_SEASON = 2026
BAR = "#1c2a36"
HARD_VOTE_BY_RANK = {1: 3, 2: 2, 3: 1}
VOTES_PER_GAME = 6              # 3 + 2 + 1

# The season record under a single 3-2-1 allocation. See the module docstring
# for why this is not the raw all-time maximum, and why the card names him.
RECORD_VOTES = 45
RECORD_HOLDER = "CRIPPS"
RECORD_SEASON = 2024

# Fixed seed and a sim count ten times predict_2026.py's, because this reads out
# a single tail probability rather than a percentile and a card must render the
# same number twice. At 10,000 the figure moves by a few tenths between seeds.
SIMS = 100_000
SEED = 42

# style -> (title 1, title 2, headline figure, band end labels, leader notes).
#
# "range" is the chosen one and carries NO prose at all: every row is the same
# height, the band ends print their own numbers, and the record and probability
# lines are gone. Nothing on it needs reading, which is the point at the size a
# timeline renders an image. The record claim and the two percentages live in
# the post copy instead, where they can be qualified properly.
#
# "bars" is the plain board. "spread" is "range" with the leader's notes kept.
# "expected" reframes on what the model expects and relegates the 3-2-1 total
# to the tick, which is the honest ordering and the least excitable of the four.
STYLES = {
    "bars":     ("THE MODEL'S BOARD", "3-2-1 IN EVERY GAME", "hard", False, True),
    "range":    ("THE MODEL'S BOARD", "3-2-1, AND THE RANGE", "hard", True, False),
    "spread":   ("THE MODEL'S BOARD", "3-2-1 AGAINST THE ODDS", "hard", True, True),
    "expected": ("WHAT THE MODEL", "ACTUALLY EXPECTS", "exp", False, True),
}


def _game_key(g):
    """One value per match, matching dashboard._game_key."""
    if "Game_ID" in g.columns:
        return g["Game_ID"].astype(str)
    return (g["Round_num"].astype(str) + "|" + g["Home.team"].astype(str)
            + "|" + g["Away.team"].astype(str))


def _sim_totals(g, player, sims=SIMS, seed=SEED):
    """`sims` simulated season totals for one player. See record_chance."""
    pg = g[g["Player_Name"] == player]
    P = pg[["P_1", "P_2", "P_3"]].to_numpy(dtype=float)
    p0 = np.clip(1.0 - P.sum(axis=1), 0, None)
    pr = np.column_stack([p0, P]).clip(0)
    pr /= pr.sum(axis=1, keepdims=True)
    cdf = pr.cumsum(axis=1)
    u = np.random.default_rng(seed).random((len(pr), sims))
    return (cdf[:, :, None] < u[:, None, :]).sum(axis=1).sum(axis=0)


def record_chance(g, player, threshold, sims=SIMS, seed=SEED):
    """P(the player's ACTUAL season votes exceed `threshold`), as a fraction.

    The same Monte Carlo predict_2026.py runs for the floor and ceiling bands,
    asked a different question. Each game is sampled with ITS OWN p1/p2/p3, so
    a player's season is the sum of draws from as many different categorical
    distributions as he played games. Do not average his probabilities first:
    that is mean-preserving and looks fine, but it inflates the variance and
    would push this number up. predict_2026.py carries the full account.

    THIS IS A DIFFERENT QUANTITY FROM THE 3-2-1 TOTAL ON THE CARD. The board
    hands 3/2/1 to whoever the model ranks top three in each game, which is a
    deterministic reading of the same probabilities. This asks how often a
    simulated season of real voting clears the record. The leader reads 48 on
    the board and clears 45 in well under one season in ten, and the two are
    consistent: the board is what happens if every call lands his way.
    """
    return float((_sim_totals(g, player, sims, seed) > threshold).mean())


def build(season=CUR_SEASON, rows=10):
    path = GAME_LEVEL.format(season)
    if not os.path.exists(path):
        raise SystemExit(f"no game-level file at {path}")
    g = pd.read_csv(path)
    if "Exp_Votes" not in g.columns:
        raise SystemExit(f"{path} carries no Exp_Votes column")

    # An exactly-duplicated row would take two of a game's three vote slots and
    # push a real player out, so it is refused rather than silently deduped:
    # whatever wrote the file needs fixing, not papering over here.
    dupes = int(g.duplicated().sum())
    if dupes:
        raise SystemExit(f"{path} holds {dupes} exactly-duplicated rows, which "
                         f"would corrupt the 3-2-1 award. Fix the writer.")

    g = g.copy()
    g["_gkey"] = _game_key(g)
    srt = (["_gkey", "Exp_Votes"]
           + [c for c in ("Poll_Prob", "P_3") if c in g.columns]
           + ["Player_Name"])
    asc = [True, False] + [False] * (len(srt) - 3) + [True]
    g = g.sort_values(srt, ascending=asc)
    g["hard"] = (g.groupby("_gkey").cumcount() + 1).map(
        HARD_VOTE_BY_RANK).fillna(0).astype(int)

    n_games = int(g["_gkey"].nunique())
    awarded = int(g["hard"].sum())
    if awarded != n_games * VOTES_PER_GAME:
        raise SystemExit(f"awarded {awarded} votes across {n_games} games, "
                         f"expected {n_games * VOTES_PER_GAME}")

    b = (g.groupby(["Player_Name", "Playing.for"])
           .agg(hard=("hard", "sum"), exp=("Exp_Votes", "sum"),
                games=("Exp_Votes", "size"))
           .reset_index()
           .sort_values(["hard", "exp"], ascending=False))
    b["rank"] = b["hard"].rank(ascending=False, method="min").astype(int)
    top = b.head(rows).to_dict("records")

    # Floor and ceiling are the 10th and 90th percentiles of the same simulated
    # seasons, matching predict_2026.py. Computed here rather than read from
    # season_projection_2026.csv because that file's Season_Total_Projected is
    # zero once the home-and-away rounds are done (no rounds left to project),
    # so its row order is meaningless at this point in the season even though
    # its Floor_Projection and Ceiling_Projection columns are still right.
    for r in top:
        t = _sim_totals(g, r["Player_Name"])
        r["floor"] = float(np.percentile(t, 10))
        r["p90"] = float(np.percentile(t, 90))
        r["mid"] = float(np.percentile(t, 50))
        # THE CEILING IS max(p90, the 3-2-1 total), matching the dashboard.
        # The card and the site describe one season, so a reader must never see
        # a total on one that breaks the stated maximum on the other: Daicos
        # reads 34-45 on the simulated band and 48 on this board.
        #
        # It is max() and NEVER a swap. Across the full board the 3-2-1 total
        # sits BELOW p90 for most players with ten or more games, so swapping
        # would quietly lower almost everyone's ceiling. Only the leader lifts
        # here: 45 to 48. Every other row in the top five is unchanged.
        r["ceiling"] = max(r["p90"], float(r["hard"]))
    chance = reach = None
    if top and top[0]["hard"] > RECORD_VOTES:
        t = _sim_totals(g, top[0]["Player_Name"])
        # Two different questions, and the card asks both. `chance` is beating
        # the record, strictly greater than it. `reach` is his real total
        # getting to the board figure itself, which is >= rather than == : the
        # chance of landing on exactly 48 is half of it and is not a thing
        # anyone means by "what are the odds he gets 48".
        chance = float((t > RECORD_VOTES).mean())
        reach = float((t >= top[0]["hard"]).mean())
    return {"rows": top, "season": season, "n_games": n_games,
            "awarded": awarded, "n_players": int((b.hard > 0).sum()),
            "chance": chance, "reach": reach}


def draw(b, preview=False, style="bars"):
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = 56 * S, (W - 56) * S
    if style not in STYLES:
        raise SystemExit(f"--style must be one of {', '.join(STYLES)}")
    # The spread style shares one axis across every row, so its bar geometry is
    # set by the axis rather than by each player's own figure.
    axis_max = (int(np.ceil(max(max(r["hard"] for r in b["rows"]),
                                max(r["ceiling"] for r in b["rows"])) / 10) * 10)
                if b["rows"] else 10)

    def text(xy, t, f, fill, anchor="la"):
        k.text(xy, t, font=f, fill=fill, anchor=anchor)

    def fit(t, role, size, width):
        while size > 16 and k.textlength(t, font=font(role, size)) > width:
            size -= 2
        return font(role, size)

    draw_mark(img, m, 44 * S, 29)
    # One of the two model guards. See the module docstring before changing it.
    text((right, 44 * S), f"{b['season']} MODEL PROJECTION", font("display", 29),
         MUTED, anchor="ra")
    k.rectangle([m, 100 * S, right, 101 * S], fill=LINE)

    t1, t2, headline, show_labels, show_notes = STYLES[style]
    text((m, 128 * S), t1, fit(t1, "name", 72, right - m), INK)
    text((m, 214 * S), t2, fit(t2, "name", 72, right - m), INK)
    key = None
    if style != "bars":
        # "Floor and ceiling", the site's own words, rather than "10th to 90th
        # percentile". Once the ceiling is lifted to max(p90, 3-2-1) the band is
        # no longer a pure percentile range, and the old wording would be a
        # false precision on exactly the row a reader looks at first.
        key = (f"BAR IS THE FLOOR AND CEILING FROM {SIMS:,} SIMULATED "
               f"SEASONS   TICK IS THE 3-2-1 TOTAL")
        text((m, 296 * S), key, fit(key, "display", 24, right - m), MUTED)
    k.rectangle([m, 336 * S if key else 312 * S,
                 right, 337 * S if key else 313 * S], fill=LINE)

    rows = b["rows"]
    # Row 1 carries the record line, so it is given the height for it rather
    # than the annotation being squeezed against the next row's hairline.
    # Only the notes need the leader to have a taller slot. Without them every
    # row is identical, which is what "range" wants.
    lead_extra = 84 * S if show_notes else 0
    top, bot = (380 * S if key else 356 * S), 1440 * S
    n = max(len(rows), 1)
    rh = (bot - top - lead_extra) // n
    bx0, bx1 = m + 62 * S, right - 132 * S
    span = bx1 - bx0
    scale = max(r["hard"] for r in rows)

    # Type and bar scale with the row height, and each row's content is centred
    # in its slot. Without this a --rows 5 card keeps the ten-row metrics, and
    # every row reads as a small block stranded at the top of a tall empty slot.
    # Capped at 1.5: past that the longest name collides with the figure column.
    sc = min(max(rh / (104 * S), 1.0), 1.5)
    nsz, fsz, csz, rsz = int(42 * sc), int(48 * sc), int(23 * sc), int(34 * sc)
    bh, gap = int(14 * sc) * S, int(54 * sc) * S
    lead = rows[0] if rows else None
    pct, rch = b.get("chance"), b.get("reach")
    # The chance is of the REAL total clearing the record, not of the board
    # figure landing. See record_chance for why those are different questions.
    # The expected-style note names the record on the second line, because its
    # first line does not, and "getting there" with no target named is nothing.
    if headline == "exp" and lead:
        note = (f"3-2-1 BOARD READS {lead['hard']:.0f}, "
                f"HIS CEILING IS {lead['ceiling']:.0f}")
        note2 = (f"{pct * 100:.0f}% CHANCE HE BEATS {RECORD_HOLDER}' "
                 f"RECORD {RECORD_VOTES}" if pct is not None else None)
    else:
        note = (f"WOULD PASS {RECORD_HOLDER}' RECORD "
                f"{RECORD_VOTES} FROM {RECORD_SEASON}")
        note2 = (f"{pct * 100:.0f}% CHANCE HE BEATS {RECORD_VOTES}     "
                 f"{rch * 100:.0f}% CHANCE HE REACHES {lead['hard']:.0f}"
                 if pct is not None and rch is not None else None)
    # The spread style prints the band's two numbers under every bar, so every
    # row reserves that height and the record note sits below it. Without this
    # the leader's floor label lands underneath the gold note on row 1.
    lab_h = int(30 * sc) * S if show_labels else 0
    nof = fit(note, "display", int(24 * sc), span)
    nof2 = fit(note2, "display", int(22 * sc), span) if note2 else None
    note_h = int(30 * sc) * S + (int(32 * sc) * S if note2 else 0)

    for ri, r in enumerate(rows):
        me = ri == 0
        slot_top = top + ri * rh + (0 if me else lead_extra)
        slot_h = rh + (lead_extra if me else 0)
        show_note = me and show_notes and r["hard"] > RECORD_VOTES
        block = gap + bh + lab_h + (note_h if show_note else 0)
        y = slot_top + (slot_h - block) // 2
        if ri:
            k.rectangle([m, slot_top - 1 * S, right, slot_top], fill=LINE)
        # The site's palette, not a per-row highlight: emerald is the accent on
        # every bar and the leader is inked like everyone else. The one gold
        # thing on the card is the leader's figure, which is what the eye is
        # meant to land on.
        text((m, y + int(6 * sc) * S), str(r["rank"]), font("display", rsz),
             RANK_INK)
        name = r["Player_Name"].upper()
        # The name is fitted against what the figure actually measures, not a
        # fixed reserve. A fixed one held at ten rows and failed at five, where
        # the type is half again as large.
        fig_txt = (f"{r['exp']:.1f}" if headline == "exp"
                   else f"{r['hard']:.0f}")
        ff = font("fig", fsz)
        edge = right - k.textlength(fig_txt, font=ff) - 30 * S
        nf = fit(name, "name", nsz, edge - bx0 - 16 * S)
        text((bx0, y), name, nf, INK)
        text((right, y - int(8 * sc) * S), fig_txt, ff,
             GOLD if me else INK, anchor="ra")
        by = y + gap
        acc = EMERALD

        if style == "bars":
            k.rectangle([bx0, by, bx1, by + bh], fill=BAR)
            k.rectangle([bx0, by, bx0 + int(span * r["hard"] / scale), by + bh],
                        fill=acc)
        else:
            # Floor to ceiling as the filled band, on an axis shared by every
            # row so the bands can be compared down the card. The 3-2-1 figure
            # is a tick, deliberately OUTSIDE the band it usually sits above:
            # the whole point of these two styles is that the board total is a
            # ceiling reading, not a middle one.
            def px(v):
                return bx0 + int(span * min(v, axis_max) / axis_max)
            k.rectangle([bx0, by, bx1, by + bh], fill=BAR)
            k.rectangle([px(r["floor"]), by, px(r["ceiling"]), by + bh],
                        fill=acc)
            tick = px(r["hard"])
            k.rectangle([tick - 2 * S, by - int(7 * sc) * S,
                         tick + 2 * S, by + bh + int(7 * sc) * S], fill=INK)
            if show_labels:
                lf = font("display", int(20 * sc))
                text((px(r["floor"]), by + bh + int(12 * sc) * S),
                     f"{r['floor']:.0f}", lf, MUTED)
                text((px(r["ceiling"]), by + bh + int(12 * sc) * S),
                     f"{r['ceiling']:.0f}", lf, MUTED, anchor="ra")
        if show_note:
            ny = by + bh + lab_h + int(14 * sc) * S
            text((bx0, ny), note, nof, GOLD)
            if nof2:
                text((bx0, ny + int(32 * sc) * S), note2, nof2, MUTED)

    k.rectangle([m, 1466 * S, right, 1467 * S], fill=LINE)

    os.makedirs(OUT_DIR, exist_ok=True)
    suffix = "" if style == "bars" else f"_{style}"
    path = os.path.join(OUT_DIR, f"leaderboard_{b['season']}_rounded{suffix}.png")
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
    ap.add_argument("--season", type=int, default=CUR_SEASON)
    ap.add_argument("--rows", type=int, default=10)
    ap.add_argument("--font", default="twcen", help=", ".join(FONT_SETS))
    ap.add_argument("--style", default="bars", choices=sorted(STYLES),
                    help="bars | range | spread | expected")
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()
    set_fonts(a.font)
    b = build(a.season, a.rows)
    path, prev = draw(b, a.preview, a.style)
    print(f"OK  wrote {path}")
    if prev:
        print(f"    timeline preview: {prev}")
    if b.get("chance") is not None:
        print(f"    P(leader's real total beats {RECORD_VOTES}) = "
              f"{b['chance'] * 100:.1f}% over {SIMS:,} sims")
    print(f"    {b['awarded']} votes over {b['n_games']} games, "
          f"{b['n_players']} players polled")
    for r in b["rows"]:
        print(f"      {r['rank']:2d} {r['Player_Name']:22} "
              f"{r['Playing.for']:18} {r['hard']:3.0f}   "
              f"({r['exp']:.2f} expected, band {r['floor']:.0f}-{r['ceiling']:.0f}"
              f"{' LIFTED from ' + format(r['p90'], '.0f') if r['ceiling'] > r['p90'] else ''}, "
              f"{r['games']} games)")
    ties = [r["rank"] for r in b["rows"]]
    for t in sorted(set(x for x in ties if ties.count(x) > 1)):
        who = [r["Player_Name"] for r in b["rows"] if r["rank"] == t]
        print(f"    tied at {t}: {' and '.join(who)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
