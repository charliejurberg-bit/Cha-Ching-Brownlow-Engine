"""How often a player is judged best on ground, as a share of his career.

    python scripts/bog_share_card.py "Marcus Bontempelli" 3
    python scripts/bog_share_card.py "Marcus Bontempelli" 3 --rows 8 --preview

Writes a PNG to drafts/ (gitignored). Portrait 1200x1500 at S=2, downsampled
once to Twitter's 2048 long edge, same as the other countdown cards. Fonts,
colours and the CHA CHING mark are imported from countdown_card rather than
restated. No footer text, by standing rule: the window and the games floor sit
in the header, where they are set at a size that survives a timeline.

WHY THIS CARD EXISTS
A career vote total rewards longevity and a season total rewards one year.
Neither answers the question a reader actually has about a player like
Bontempelli, which is how often he was the best player on the ground. Three
votes is the umpires saying exactly that, once per game, and the share of a
career spent collecting them is the closest thing the vote record holds to a
peak-rate measure. career_votes_card.py ranks the total and loss_votes_card.py
ranks the hard part of the total; this ranks the top of it.

THE SHARE IS THE RANKED QUANTITY AND THE BAR DRAWS IT
Unlike loss_votes_card, where the count is the record and the share is context,
here the share IS the record, so it sets the order, the bar and the figure. The
count still has to be visible, because a share with an invisible denominator is
the trap threshold_votes_card names: 20% reads the same whether it came from 3
of 15 or 52 of 245. Every row therefore carries "N OF M GAMES" under the name,
and the games floor is in the header rather than left to be assumed.

THE GAMES FLOOR IS DOING REAL WORK AND IS NOT COSMETIC
At no floor the ladder is a list of short careers: a player with 14 games and
four big ones outranks everyone. 150 is the same floor career_votes_card's own
rate table uses, and the leader is the same player at 150 and at 200. It
changes at 250, where Bontempelli has not yet played enough, so the floor is
printed on the card and any copy has to state it.

THE 1984 FLOOR IS THE ARCHIVE'S, NOT A CHOSEN WINDOW
Per-game votes exist from 1984; data_history/fitzroy_stats_1965_2006.csv.gz
carries Brownlow.Votes as all-null before it, so no three-vote game before then
can be counted. A player who debuted earlier is counted only from 1984 on and
his share is computed over the part of his career the archive can see, which
makes it a mix rather than a floor and is worse than a truncated total. Any
such player in the drawn rows is reported on stdout on every run so the copy
can say so; on the current archive there are none.

THE CURRENT SEASON IS NOT IN IT
No 2026 votes are awarded until count night, so the ladder stops at 2025 and
the card says so. A projection has no place on a card about what has already
been judged.
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
    W, H, S, draw_mark, font, ordinal, set_fonts, FONT_SETS,
)

OUT_DIR = "drafts"
STATS_HIST = "data_history/fitzroy_stats_1965_2006.csv.gz"
STATS_ALL = "fitzroy_stats_all.csv"
VOTES_FROM = 1984          # Brownlow.Votes is all-null before this
LAST_SETTLED = 2025        # 2026 votes are not public until count night
BAR = "#1c2a36"


def _load(path):
    d = pd.read_csv(path, low_memory=False)
    d = d[pd.to_numeric(d["Round"], errors="coerce").notna()]
    return pd.DataFrame({
        "Season": pd.to_numeric(d["Season"], errors="coerce"),
        # THE KEY IS THE fitzRoy ID, NEVER THE NAME. Grouping by name merges
        # Gary Ablett senior (ID 567, 226 games and 22 best-on-grounds in the
        # window) into Gary Ablett junior (1105, 332 and 55), reading one
        # 558-game career on 77, and does the same to the two Josh Kennedys
        # (4169 West Coast, 11672 Sydney) at 544 games. Both land at the top of
        # a career ladder rather than the bottom, so a name key does not fail
        # quietly: the first version of this card told the reader Ablett led the
        # raw count on 77 when the real leader is Dangerfield on 56. Stored as a
        # string because one archive types the column int and the other float.
        "ID": d["ID"].astype("float64").astype("Int64").astype(str),
        "P": (d["First.name"].astype(str).str.strip() + " "
              + d["Surname"].astype(str).str.strip()),
        "club": d["Playing.for"].replace({"Kangaroos": "North Melbourne",
                                          "Footscray": "Western Bulldogs"}),
        "bv": pd.to_numeric(d["Brownlow.Votes"], errors="coerce")})


def build(player, min_games, rows):
    """The share ladder, plus the subject's row and his raw-count standing."""
    d = pd.concat([_load(STATS_HIST), _load(STATS_ALL)], ignore_index=True)
    d = d[(d.Season >= VOTES_FROM) & (d.Season <= LAST_SETTLED) & d.bv.notna()]
    if d.empty:
        raise SystemExit("no votes in the archive window")

    g = d.groupby("ID").agg(games=("bv", "size"), votes=("bv", "sum"),
                            bogs=("bv", lambda s: int((s == 3).sum())),
                            y0=("Season", "min"), y1=("Season", "max"),
                            P=("P", "last"), club=("club", "last")).reset_index()
    g["share"] = g.bogs / g.games
    q = g[g.games >= min_games].sort_values(
        ["share", "bogs"], ascending=False).reset_index(drop=True)
    if player not in set(q.P):
        mine = g[g.P == player]
        played = int(mine.games.max()) if len(mine) else 0
        raise SystemExit(f"{player} does not reach {min_games} games "
                         f"in {VOTES_FROM}-{LAST_SETTLED} (has {played})")
    # A name that resolves to two IDs cannot be marked unambiguously.
    if (q.P == player).sum() > 1:
        raise SystemExit(f"{player} matches more than one fitzRoy ID: "
                         + ", ".join(q[q.P == player].ID))
    q["rank"] = q.share.rank(ascending=False, method="min").astype(int)

    # A career that starts before 1984 is measured over only part of itself.
    # Reported rather than silently drawn, because the share is then a mix of a
    # counted period and an uncountable one, not a floor.
    trunc = [r.P for _, r in q.head(rows).iterrows() if r.y0 == VOTES_FROM]

    me = q[q.P == player].iloc[0]
    return {"rows": q.head(rows).to_dict("records"), "me": me.to_dict(),
            "n_qual": len(q), "truncated": trunc,
            "count_rank": int((g.bogs > me.bogs).sum()) + 1,
            "count_top": g.sort_values("bogs", ascending=False)
                          .head(4).to_dict("records")}


def draw(player, place, b, min_games, preview=False):
    img = Image.new("RGB", (W * S, H * S), BG)
    k = ImageDraw.Draw(img)
    m, right = 56 * S, (W - 56) * S

    def text(xy, t, f, fill, anchor="la"):
        k.text(xy, t, font=f, fill=fill, anchor=anchor)

    def fit(t, role, size, width):
        while size > 18 and k.textlength(t, font=font(role, size)) > width:
            size -= 2
        return font(role, size)

    # -- masthead --------------------------------------------------
    draw_mark(img, m, 44 * S, 29)
    text((right, 44 * S), f"BROWNLOW COUNTDOWN   {ordinal(place).upper()}",
         font("display", 29), MUTED, anchor="ra")
    k.rectangle([m, 100 * S, right, 101 * S], fill=LINE)

    text((m, 128 * S), "BEST ON GROUND",
         fit("BEST ON GROUND", "name", 80, right - m), INK)
    text((m, 218 * S), "MOST OFTEN",
         fit("MOST OFTEN", "name", 80, right - m), INK)
    sub = (f"SHARE OF CAREER GAMES POLLING 3 VOTES   "
           f"{VOTES_FROM} TO {LAST_SETTLED}")
    text((m, 316 * S), sub, fit(sub, "display", 29, right - m), RANK_INK)
    sub2 = f"{min_games} GAMES OR MORE   {b['n_qual']:,} PLAYERS QUALIFY"
    text((m, 356 * S), sub2, fit(sub2, "display", 29, right - m), MUTED)
    k.rectangle([m, 404 * S, right, 405 * S], fill=LINE)

    # -- the ladder ------------------------------------------------
    # ROW GEOMETRY IS LOAD BEARING AND WAS WRONG ONCE. A row is three stacked
    # elements (name, detail, bar) and the eye groups by proximity, so the gap
    # BETWEEN rows has to beat the gaps inside one. At eight rows the pitch is
    # 101 units against about 96 of content, which put every bar nearer the
    # next player's name than its own and read as if Bontempelli's 21% were
    # Neale's. Six rows gives 134 and the ladder still carries everyone above
    # 17%. The percentage is also set level with its own name rather than with
    # its bar, so the figure is anchored to the right player whatever the pitch.
    rows = b["rows"]
    top, bot = 444 * S, 1252 * S
    rh = (bot - top) // max(len(rows), 1)
    bx0 = m + 62 * S                      # bars start clear of the rank numeral
    bx1 = right - 150 * S                 # and stop clear of the figure
    span = bx1 - bx0
    scale = max(r["share"] for r in rows)
    bh = 18 * S

    for ri, r in enumerate(rows):
        y = top + ri * rh
        if ri:
            k.rectangle([m, y - 22 * S, right, y - 21 * S], fill=LINE)
        me = r["P"] == player
        ink = EMERALD if me else INK
        text((m, y + 2 * S), str(r["rank"]), font("display", 38),
             EMERALD if me else RANK_INK)
        text((bx0, y - 4 * S), r["P"].upper(),
             fit(r["P"].upper(), "name", 44, span), ink)
        # One decimal, not none. Rounded to whole percents rows 3, 4 and 5 all
        # read 18% while being ranked 3, 4, 5, which looks like a sorting fault
        # rather than a close finish. The figure is set large enough that the
        # decimal survives the timeline.
        text((right, y - 12 * S), f"{100 * r['share']:.1f}%",
             font("fig", 46), ink, anchor="ra")
        line = (f"{int(r['y0'])}-{int(r['y1'])}      "
                f"{r['bogs']} OF {r['games']} GAMES")
        text((bx0, y + 46 * S), line, fit(line, "display", 25, span), MUTED)
        by = y + 82 * S
        k.rectangle([bx0, by, bx1, by + bh], fill=BAR)
        k.rectangle([bx0, by, bx0 + int(span * r["share"] / scale), by + bh],
                    fill=EMERALD if me else RANK_INK)

    # -- the two figures -------------------------------------------
    k.rectangle([m, 1292 * S, right, 1293 * S], fill=LINE)
    me, half = b["me"], m + (right - m) // 2
    lead = b["count_top"][0]
    pairs = [
        (m, f"{me['bogs']}", EMERALD, "HIS BEST-ON-GROUND GAMES",
         f"FROM {me['games']} SINCE {int(me['y0'])}"),
        (half, ordinal(b["count_rank"]).upper(), INK, "ON THE RAW COUNT",
         f"{lead['P'].upper()} LEADS ON {lead['bogs']}"),
    ]
    for x, big, col, lab, s2 in pairs:
        text((x, 1320 * S), big, font("fig", 88), col)
        text((x, 1418 * S), lab, font("display", 27), INK)
        text((x, 1454 * S), s2, fit(s2, "display", 25, half - m - 20 * S), MUTED)

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", player.lower()).strip("_")
    path = os.path.join(OUT_DIR, f"countdown_{place:02d}_{slug}_bog_share.png")
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
    ap.add_argument("--rows", type=int, default=6,
                    help="ladder rows (default 6; see the row-geometry note "
                         "in draw before raising it)")
    ap.add_argument("--min-games", dest="min_games", type=int, default=150,
                    help="career games floor (default 150)")
    ap.add_argument("--font", default="twcen", help=", ".join(FONT_SETS))
    ap.add_argument("--preview", action="store_true",
                    help="also write the 350px version Twitter shows on a phone")
    a = ap.parse_args()
    set_fonts(a.font)
    b = build(a.player, a.min_games, a.rows)
    path, prev = draw(a.player, a.place, b, a.min_games, a.preview)
    me = b["me"]
    print(f"OK  wrote {path}")
    if prev:
        print(f"    timeline preview: {prev}")
    print(f"    {VOTES_FROM}-{LAST_SETTLED}, {b['n_qual']:,} players with "
          f"{a.min_games}+ games")
    print(f"    {a.player}: {me['bogs']} of {me['games']} games "
          f"({100 * me['share']:.1f}%), rank {ordinal(me['rank'])} on share, "
          f"{ordinal(b['count_rank'])} on the raw count")
    for r in b["rows"]:
        mark = "  <<" if r["P"] == a.player else ""
        print(f"      {r['rank']:2d} {r['P']:22} {int(r['y0'])}-{int(r['y1'])}  "
              f"{r['bogs']:3d}/{r['games']:3d}  {100 * r['share']:5.1f}%  "
              f"{r['votes']:.0f} votes{mark}")
    print("    raw-count leaders: " + ", ".join(
        f"{r['P']} {r['bogs']}" for r in b["count_top"]))
    if b["truncated"]:
        print("    WARNING careers reaching back past the 1984 archive floor, "
              "their share is measured over part of a career only: "
              + ", ".join(b["truncated"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
