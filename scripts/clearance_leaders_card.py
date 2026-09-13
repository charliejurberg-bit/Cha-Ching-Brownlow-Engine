"""What the AFL's clearance leader polls, and where he finishes.

    python scripts/clearance_leaders_card.py
    python scripts/clearance_leaders_card.py --place 11 --preview

Writes a PNG to drafts/ (gitignored). Same 1200x1500 portrait, palette, fonts
and CHA CHING mark as countdown_card.py, imported rather than restated.

Every figure is computed from the archives on each run and none is typed in.

THE CARD SHOWS 2015 ON, AND NOTHING ON IT SAYS SO EXCEPT THE HEADER
An earlier version put 1998-2014 beside 2015-2025 in two panels, and a later one
kept the earlier era as a footnote. Both are gone: one era at full width with no
small print is what stays legible at the size Twitter renders an image in a
timeline, and that is what the card is for.

The cost is real and lands on the copy instead. 2015 is a window, not the whole
record, and it flatters the subject: across 1998-2014 the leader averaged 13.9
votes and a median finish of 15th, against 28.6 and 3rd here. The card's header
carries the years, but a reader who does not read a header will take the figures
for all time. **Any post using this card must say "since 2015" in its own
words.** main() prints the omitted era on every run so the operator sees what the
card is not showing, and drafts/countdown_11_jai_newcombe_tweet.md holds the full
28-season table.

MEAN VOTES BUT MEDIAN FINISH, AND THE MIXTURE IS DELIBERATE
Votes are a count and average honestly. A finishing position does not: across
the full 1998-2025 record six seasons put the leader outside 30th and one put
him 95th, dragging the mean finish to 19th where the median is 7th. A mean rank
would describe none of the seasons. Do not "fix" the inconsistency by averaging
both.

CLEARANCES START IN 1998 AND THAT IS THE SOURCE'S BOUNDARY, NOT A CHOICE
The column is null for every season before 1998 in
data_history/fitzroy_stats_1965_2006.csv.gz and populated from 1998 on. Nothing
earlier can be built, by this script or any other in the repo.

FINISH IS A VOTES RANK AND CANNOT SEE SUSPENSION
Position is the player's rank by season vote total, minimum rank on ties. A
player ineligible to win still appears at his vote position, because the archive
carries votes and carries nothing about eligibility.

THE CURRENT SEASON IS A CLEARANCE COUNT AND NOTHING ELSE
Its votes are not awarded until count night, so 2026 sits below a hairline with
its vote and finish cells struck out rather than blank. A blank cell reads as
missing data; a stated "not awarded yet" reads as what it is.
"""

import argparse
import os
import sys

import pandas as pd
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from countdown_card import (  # noqa: E402
    BG, INK, MUTED, RANK_INK, EMERALD, LINE,
    W, H, S, draw_mark, font, ordinal, set_fonts, FONT_SETS,
)

OUT_DIR = "drafts"
STATS_HIST = "data_history/fitzroy_stats_1965_2006.csv.gz"
STATS_ALL = "fitzroy_stats_all.csv"
STATS_CUR = "data_2026/afltables_2026.csv"
CUR_SEASON = 2026
FIRST_SEASON = 1998      # first season carrying clearances, checked not assumed
SPLIT = 2015             # the shown window starts here; see the docstring
BAR_TRACK = "#131e28"    # the unfilled remainder of a vote bar
BAR_SLATE = "#31404e"    # a leader who missed the top three
TOP3 = 3
COLS = ["Season", "ID", "P", "Playing.for", "Clearances", "Brownlow.Votes"]


def _name(d):
    return (d["First.name"].astype(str).str.strip() + " "
            + d["Surname"].astype(str).str.strip())


def _ha_only(d):
    """Home-and-away rows. Finals carry a string round and coerce to NaN."""
    return d[pd.to_numeric(d["Round"], errors="coerce").notna()]


def _load(path):
    d = pd.read_csv(path, low_memory=False)
    d = _ha_only(d)
    return d.assign(P=_name(d))[COLS]


def gather():
    """One row per season: the clearance leader, his votes and his finish."""
    hist = _load(STATS_HIST)
    d = pd.concat([hist[hist.Season >= FIRST_SEASON], _load(STATS_ALL)],
                  ignore_index=True)
    if d["Clearances"].isna().all():
        raise SystemExit("no clearance data found in the archives")

    # Keyed on fitzRoy ID, not on the name string: two players sharing a name in
    # one season would otherwise be summed into one impossible leader.
    g = (d.groupby(["Season", "ID", "P"])
           .agg(team=("Playing.for", lambda s: s.mode().iat[0]),
                games=("Clearances", "size"),
                cl=("Clearances", "sum"),
                bv=("Brownlow.Votes", "sum"))
           .reset_index())

    rows = []
    for sn, s in g.groupby("Season"):
        s = s.copy()
        # Minimum rank on ties, so two players level on votes both read the
        # same position and the next player down is not promoted over them.
        s["fin"] = s.bv.rank(ascending=False, method="min").astype(int)
        tied = s[s.cl == s.cl.max()]
        lead = tied.iloc[0]
        rows.append(dict(season=int(sn), player=lead.P, team=lead.team,
                         games=int(lead.games), cl=int(lead.cl),
                         votes=int(lead.bv), finish=int(lead.fin),
                         shared=len(tied), winner=int(s.bv.max())))
    r = pd.DataFrame(rows).sort_values("season").reset_index(drop=True)

    # The current season is a clearance count only. Its votes do not exist yet,
    # so it can never join the table above and gets its own row below the rule.
    c = _load(STATS_CUR)
    cg = c.groupby(["ID", "P"]).agg(cl=("Clearances", "sum")).reset_index()
    top = cg.cl.max()
    return r, dict(season=CUR_SEASON, cl=int(top),
                   players=sorted(cg[cg.cl == top].P.tolist()))


def era(r, lo, hi):
    s = r[(r.season >= lo) & (r.season <= hi)]
    return dict(lo=lo, hi=hi, n=len(s), rows=s,
                votes=s.votes.mean(), finish=s.finish.median(),
                won=int((s.finish == 1).sum()),
                top3=int((s.finish <= TOP3).sum()))


def draw(r, cur, place, preview=False):
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = 56 * S, (W - 56) * S
    span = right - m

    def text(xy, t, f, fill, anchor="la"):
        k.text(xy, t, font=f, fill=fill, anchor=anchor)

    def rule(y, x0=None, x1=None, fill=LINE):
        k.rectangle([x0 if x0 is not None else m, y * S,
                     x1 if x1 is not None else right, y * S + S], fill=fill)

    shown = era(r, SPLIT, int(r.season.max()))

    # -- masthead --------------------------------------------------
    draw_mark(img, m, 44 * S, 29)
    if place:
        text((right, 44 * S), f"BROWNLOW COUNTDOWN   {ordinal(place).upper()}",
             font("display", 29), MUTED, anchor="ra")
    rule(100)

    text((m, 128 * S), "THE AFL'S CLEARANCE LEADER", font("name", 62), INK)
    # The only statement of the window anywhere on the card. See the docstring.
    text((m, 212 * S), f"{shown['lo']} TO {shown['hi']}   "
         f"{shown['n']} SEASONS", font("display", 32), RANK_INK)
    rule(268)

    # -- the three figures the card exists for ----------------------
    for x, val, lab in ((m, f"{shown['votes']:.1f}", "AVG VOTES"),
                        (m + int(span * 0.37), ordinal(int(shown["finish"])).upper(),
                         "MEDIAN FINISH"),
                        (m + int(span * 0.73), str(shown["won"]),
                         f"MEDALS FROM {shown['n']}")):
        text((x, 306 * S), val, font("fig", 118), EMERALD)
        text((x, 444 * S), lab, font("display", 30), MUTED)
    rule(496)

    # -- the seasons ------------------------------------------------
    # Column anchors, all relative to span so the layout survives a margin
    # change. CL, VOTES and FINISH are right-aligned; the bar sits between CL
    # and VOTES so the eye reads magnitude before it reads the number.
    c_name = m + 110 * S
    c_cl = m + int(span * 0.52)
    bar_x, bar_w = m + int(span * 0.56), int(span * 0.19)
    c_votes = m + int(span * 0.85)
    vmax = float(shown["rows"].votes.max())

    for lab, x, anchor in (("SEASON", m, "la"), ("LEADER", c_name, "la"),
                           ("CL", c_cl, "ra"), ("VOTES", c_votes, "ra"),
                           ("FINISH", right, "ra")):
        text((x, 522 * S), lab, font("display", 26), MUTED, anchor=anchor)

    # With the footnotes gone the rows take the height back rather than leaving
    # the bottom third of the card empty.
    top, rh = 574 * S, 68 * S
    for i, (_, row) in enumerate(shown["rows"].iterrows()):
        y = top + i * rh
        hit = row.finish <= TOP3
        text((m, y), str(row.season), font("display", 34), RANK_INK)
        text((c_name, y), row.player.upper(), font("display", 34),
             INK if hit else MUTED)
        text((c_cl, y), str(row.cl), font("fig", 34), MUTED, anchor="ra")
        # Bar length is votes on a zero-based linear scale, so two bars can be
        # compared by eye without reading either number.
        k.rectangle([bar_x, y + 14 * S, bar_x + bar_w, y + 32 * S],
                    fill=BAR_TRACK)
        k.rectangle([bar_x, y + 14 * S,
                     bar_x + int(bar_w * row.votes / vmax), y + 32 * S],
                    fill=EMERALD if hit else BAR_SLATE)
        text((c_votes, y), str(row.votes), font("fig", 36),
             INK if hit else MUTED, anchor="ra")
        text((right, y), ordinal(row.finish), font("fig", 36),
             EMERALD if hit else MUTED, anchor="ra")

    # -- the current season, counted but not polled ------------------
    y = top + shown["n"] * rh + 16 * S
    rule(y // S)
    y += 26 * S
    text((m, y), str(cur["season"]), font("display", 34), EMERALD)
    names = ", ".join(p.split(" ", 1)[1].upper() for p in cur["players"])
    text((c_name, y), names, font("display", 34), EMERALD)
    text((c_cl, y), str(cur["cl"]), font("fig", 34), EMERALD, anchor="ra")
    text((right, y), "NOT AWARDED YET", font("display", 30), MUTED, anchor="ra")

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "clearance_leaders_brownlow.png")
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
    ap.add_argument("--place", type=int, default=11,
                    help="countdown place for the masthead, 0 to omit it")
    ap.add_argument("--font", default="twcen", help=", ".join(FONT_SETS))
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args()
    set_fonts(a.font)
    r, cur = gather()
    path, prev = draw(r, cur, a.place, a.preview)
    print(f"OK  wrote {path}")
    if prev:
        print(f"    timeline preview: {prev}")
    # Both eras are printed even though only one is drawn, so the operator can
    # see what the card leaves off before posting it.
    for lo, hi, tag in ((SPLIT, int(r.season.max()), "on the card"),
                        (FIRST_SEASON, SPLIT - 1, "NOT on the card")):
        e = era(r, lo, hi)
        print(f"    {lo}-{hi}  n={e['n']:2d}  avg votes {e['votes']:5.2f}  "
              f"median finish {ordinal(int(e['finish'])):>4}  won {e['won']}  "
              f"top3 {e['top3']}   ({tag})")
    print(f"    all {len(r)} seasons: avg votes {r.votes.mean():.2f}, "
          f"median finish {ordinal(int(r.finish.median()))}, "
          f"{int((r.finish == 1).sum())} medals")
    print(f"    seasons with a shared clearance lead: {int((r.shared > 1).sum())}")
    print(f"    {cur['season']}: {', '.join(cur['players'])} on {cur['cl']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
