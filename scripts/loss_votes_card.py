"""Career Brownlow votes polled in LOSING sides, one player marked.

    python scripts/loss_votes_card.py "Patrick Cripps" 6
    python scripts/loss_votes_card.py "Patrick Cripps" 6 --rows 6 --preview

Writes a PNG to drafts/ (gitignored). Portrait 1200x1500 at S=2, downsampled
once to Twitter's 2048 long edge, same as the other countdown cards. Fonts,
colours and the CHA CHING mark are imported from countdown_card rather than
restated. No footer text, by standing rule: the window and the legend sit in
the header and the two rates sit in the figure band, both at a size that
survives a timeline.

WHY THIS CARD EXISTS
Umpires vote for winners. 37,071 of the 44,478 votes awarded between 1984 and
2025 went to a player whose side won and only 7,029, 15.8%, to one whose side
lost, so a vote in a beaten team is the scarce kind. Cripps has 82 of them,
more than any player in the window, from a Carlton side that finished outside
the eight in ten of his twelve completed seasons. That is a standing claim, it
is a Brownlow claim rather than a stat-shape one, and no other card in the set
makes it: career_votes_card ranks the total, which rewards the era and the
team, and this one ranks the part of the total the team did not help with.

THE BAR IS THE CAREER TOTAL AND THE EMERALD IS THE LOSS PORTION
Ranked on the emerald, drawn against the whole. Ablett's bar is the longest on
the card and his emerald is not, which is the finding stated as a picture: this
is not a longevity ladder, and a plain ladder of the loss figure alone would
leave a reader to wonder whether the leader had simply played the most games.
The share under each name is the same fact as a number.

THE SHARE IS NOT THE RANKED QUANTITY, AND MUST NOT BE READ AS ONE
Cripps' 40.0% is second in the window, not first: Paul Kelly polled 43 of his
103 votes in losses, 41.7%. The count is the record and the share is context,
which is why the count sets the order and the figure column. Any copy that
turns 40% into "the highest proportion ever" is wrong.

THE 1984 FLOOR IS THE ARCHIVE'S, AND IT TRUNCATES EARLIER CAREERS
Per-game votes exist from 1984 (data_history/fitzroy_stats_1965_2006.csv.gz
carries Brownlow.Votes as all-null before it), so a player who debuted earlier
is counted only from 1984 on and his figure here is a floor. Paul Roos, 12th on
this ladder, is such a case. Nobody in the drawn rows is, checked on each run:
main() warns for any row whose first counted season is 1984.

NOTHING IS PROJECTED ONTO THE BARS, DELIBERATELY, AND THIS DIFFERS FROM
career_votes_card.py
That card draws a 2026 ghost because its ladder is live: Neale needs 22 votes
to pass Dempsey and the gap moves while he chases it. This one is settled.
Cripps leads a retired player by 7 and the nearest active man, Dangerfield, is
36 behind with a 1.8-vote expectation, so a projection cannot change a place on
the card. Drawn anyway it was worse than useless: the loss portion of his 2026
expectation is 3.6 votes, about 2% of the bar, which at the 0.29 scale Twitter
serves is a hairline sitting inside the slate remainder, and its label read as
if it belonged to the career total beside it.

main() still computes and prints the projection, because the copy needs it. The
figure is the model's expectation summed over the games Carlton actually lost,
3.6 of his 22.2: they won twelve this year and he polls in wins like everyone
else. The card is a career record, not a 2026 claim, and the header says so.
"""

import argparse
import os
import re
import sys

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from countdown_card import (  # noqa: E402
    BG, INK, MUTED, RANK_INK, EMERALD, LINE,
    W, H, S, draw_mark, font, ordinal, set_fonts, FONT_SETS,
)
from club_votes_card import BAR  # noqa: E402

OUT_DIR = "drafts"
STATS_HIST = "data_history/fitzroy_stats_1965_2006.csv.gz"
STATS_ALL = "fitzroy_stats_all.csv"
STATS_CUR = "data_2026/afltables_2026.csv"
GAME_2026 = "predictions/game_level_2026.csv"
VOTES_FROM = 1984          # the first season with per-game votes in the archive
PROJ_SEASON = 2026


def _ha(d):
    """Home-and-away rows. Finals carry a string round and coerce to NaN.

    No votes are awarded in a final, so a finals row would enter the denominator
    as a game nobody could have polled in, and in both archives it arrives with
    a blank vote cell that a `!= 0` test would read as a vote.
    """
    d = d.copy()
    d["Round_num"] = pd.to_numeric(d["Round"], errors="coerce")
    return d[d["Round_num"].notna()]


def modern():
    """1984 onward, both archives, with a W/L/D result on every row."""
    h = pd.read_csv(STATS_HIST, low_memory=False)
    a = pd.read_csv(STATS_ALL, low_memory=False)
    cols = [c for c in a.columns if c in h.columns]
    d = pd.concat([_ha(h[cols]), _ha(a[cols])], ignore_index=True)
    d = d[d["Season"] >= VOTES_FROM]
    home = d["Playing.for"] == d["Home.team"]
    away = d["Playing.for"] == d["Away.team"]
    if not (home | away).all():
        raise SystemExit("a row's club is neither the home nor the away team")
    diff = np.where(home, d["Home.score"] - d["Away.score"],
                    d["Away.score"] - d["Home.score"])
    d["res"] = np.where(diff > 0, "W", np.where(diff < 0, "L", "D"))
    return d


def projected_2026():
    """fitzRoy ID -> (expected votes in losses, expected votes, games).

    Keyed on ID rather than name because the archives and the prediction file
    spell some players differently, and because 92 rows of game_level_2026 carry
    no ID at all. Those are dropped rather than name-matched; no player this card
    can draw is among them, and a player who resolves to nothing simply gets no
    ghost rather than a wrong one.
    """
    g = pd.read_csv(GAME_2026, low_memory=False,
                    usecols=["ID", "Round_num", "Is_Loss", "Exp_Votes"])
    g = g[g["ID"].notna()]
    if g.duplicated(["ID", "Round_num"]).any():
        # predictions/game_level_*.csv is known to emit exactly-duplicated rows.
        # Here a duplicate does not multiply a join, it simply doubles a
        # player's expectation for that round, which is worse for being quiet.
        g = g.drop_duplicates(["ID", "Round_num"])
    agg = g.groupby("ID").agg(exp=("Exp_Votes", "sum"),
                              games=("Round_num", "size"))
    agg["loss"] = g[g["Is_Loss"] == 1].groupby("ID")["Exp_Votes"].sum()
    agg["loss"] = agg["loss"].fillna(0.0)
    return {int(i): (float(r["loss"]), float(r["exp"]), int(r["games"]))
            for i, r in agg.iterrows()}


def build(player, n_rows=6):
    d = modern()
    tot_votes = float(d["Brownlow.Votes"].sum())
    n_games = len(d.drop_duplicates(["Season", "Round_num",
                                     "Home.team", "Away.team"]))
    if tot_votes != 6 * n_games:
        raise SystemExit(f"{tot_votes:.0f} votes across {n_games} games is not "
                         "6 per game; the frame is wrong before anything is drawn")
    league_loss = float(d.loc[d["res"] == "L", "Brownlow.Votes"].sum())

    v = (d.groupby(["ID", "Player", "res"])["Brownlow.Votes"].sum()
         .unstack(fill_value=0.0))
    for c in ("W", "L", "D"):
        if c not in v.columns:
            v[c] = 0.0
    v["tot"] = v[["W", "L", "D"]].sum(axis=1)
    v = v.join(d.groupby(["ID", "Player"]).agg(first=("Season", "min"),
                                               last=("Season", "max"),
                                               games=("Round_num", "size")))
    v = v.reset_index()
    v["rank"] = v["L"].rank(method="min", ascending=False).astype(int)

    me = v[v["Player"] == player]
    if me.empty:
        raise SystemExit(f"{player!r} has no votes in the archive since {VOTES_FROM}")
    if len(me) > 1:
        raise SystemExit(f"{player!r} resolves to {len(me)} careers; the archive "
                         "keys players on ID, so this card needs a unique name")
    me = me.iloc[0]

    cur = pd.read_csv(STATS_CUR, low_memory=False, usecols=["ID", "Round"])
    cur = cur[pd.to_numeric(cur["Round"], errors="coerce").notna()]
    active = set(pd.to_numeric(cur["ID"], errors="coerce").dropna().astype(int))
    proj = projected_2026()

    shown = v.sort_values(["L", "tot"], ascending=False).head(n_rows)
    if player not in set(shown["Player"]):
        shown = pd.concat([shown.head(n_rows - 1), me.to_frame().T])
    rows = []
    for _, r in shown.iterrows():
        pid = int(r["ID"])
        lo, ex, gm = proj.get(pid, (0.0, 0.0, 0))
        if pid not in active:
            lo = ex = 0.0
            gm = 0
        rows.append(dict(rank=int(r["rank"]), name=str(r["Player"]),
                         loss=float(r["L"]), tot=float(r["tot"]),
                         games=int(r["games"]),
                         span=(int(r["first"]),
                               PROJ_SEASON if pid in active else int(r["last"])),
                         exp_loss=lo, exp=ex, games26=gm,
                         me=str(r["Player"]) == player,
                         truncated=int(r["first"]) == VOTES_FROM))

    mine = next(r for r in rows if r["me"])
    new_loss = mine["loss"] + mine["exp_loss"]
    return dict(rows=rows, me=mine, n=len(v),
                league_loss=league_loss, league_tot=tot_votes,
                league_games=n_games, new_loss=new_loss,
                new_rank=int((v["L"] > new_loss).sum()) + 1)


def draw(player, place, b, preview=False):
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

    head = "VOTES IN DEFEAT"
    text((m, 128 * S), head, fit(head, "name", 80, right - m), INK)
    text((m, 232 * S), f"EVERY PLAYER, {VOTES_FROM} TO {PROJ_SEASON - 1}",
         font("display", 30), MUTED)
    legend = "BAR: CAREER VOTES    EMERALD: THE PART POLLED IN LOSSES"
    text((m, 274 * S), legend, fit(legend, "display", 30, right - m), RANK_INK)
    k.rectangle([m, 328 * S, right, 329 * S], fill=LINE)

    # -- the ladder ------------------------------------------------
    rows = b["rows"]
    top, bot = 372 * S, 1244 * S
    rh = (bot - top) // len(rows)
    bx0 = m + 62 * S                      # bars start clear of the rank numeral
    bx1 = right - 140 * S                 # and stop clear of the figure
    span = bx1 - bx0
    scale = max(r["tot"] for r in rows)
    bh = 26 * S

    def end(val):
        return bx0 + int(span * val / scale)

    for ri, r in enumerate(rows):
        y = top + ri * rh
        if ri:
            k.rectangle([m, y - 20 * S, right, y - 19 * S], fill=LINE)
        ink = EMERALD if r["me"] else INK
        text((m, y + 2 * S), str(r["rank"]), font("display", 38),
             EMERALD if r["me"] else RANK_INK)
        text((bx0, y - 2 * S), r["name"].upper(),
             fit(r["name"].upper(), "name", 44, span), ink)
        sub = (f"{r['span'][0]}-{r['span'][1]}      "
               f"{r['loss']:.0f} OF {r['tot']:.0f} CAREER VOTES      "
               f"{100 * r['loss'] / r['tot']:.0f}%")
        text((bx0, y + 50 * S), sub, fit(sub, "display", 25, span), MUTED)

        by = y + 88 * S
        # The whole career, then the loss portion over it, drawn in that order
        # so the emerald reads as a part of the total rather than beside it.
        k.rectangle([bx0, by, end(r["tot"]), by + bh], fill=BAR)
        k.rectangle([bx0, by, end(r["loss"]), by + bh], fill=EMERALD)
        text((right, by - 22 * S), f"{r['loss']:.0f}", font("fig", 50), ink,
             anchor="ra")

    # -- the two rates ---------------------------------------------
    k.rectangle([m, 1284 * S, right, 1285 * S], fill=LINE)
    me, half = b["me"], m + (right - m) // 2
    pairs = [
        (m, f"{100 * me['loss'] / me['tot']:.0f}%", EMERALD,
         "HIS VOTES IN DEFEAT", f"{me['loss']:.0f} OF {me['tot']:.0f}"),
        (half, f"{100 * b['league_loss'] / b['league_tot']:.0f}%", INK,
         "THE LEAGUE", f"{b['league_loss']:,.0f} OF {b['league_tot']:,.0f}"),
    ]
    for x, big, col, lab, sub in pairs:
        text((x, 1312 * S), big, font("fig", 88), col)
        text((x, 1410 * S), lab, font("display", 27), INK)
        text((x, 1446 * S), sub, font("display", 25), MUTED)

    os.makedirs(OUT_DIR, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", player.lower()).strip("_")
    path = os.path.join(OUT_DIR, f"lossvotes_{place:02d}_{slug}.png")
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
    ap.add_argument("--rows", type=int, default=6, help="ladder rows (default 6)")
    ap.add_argument("--font", default="twcen", help=", ".join(FONT_SETS))
    ap.add_argument("--preview", action="store_true",
                    help="also write the 350px version Twitter shows on a phone")
    a = ap.parse_args()
    set_fonts(a.font)
    b = build(a.player, a.rows)
    path, prev = draw(a.player, a.place, b, a.preview)
    me = b["me"]
    print(f"OK  wrote {path}")
    if prev:
        print(f"    timeline preview: {prev}")
    print(f"    league {VOTES_FROM}-{PROJ_SEASON - 1}: {b['league_tot']:,.0f} votes "
          f"over {b['league_games']:,} games, {b['league_loss']:,.0f} in losses "
          f"({100 * b['league_loss'] / b['league_tot']:.1f}%)")
    print(f"    {a.player}: {me['loss']:.0f} of {me['tot']:.0f} in losses "
          f"({100 * me['loss'] / me['tot']:.1f}%) from {me['games']} games, "
          f"{ordinal(me['rank'])} of {b['n']:,} players")
    print(f"    + {me['exp_loss']:.1f} projected from {PROJ_SEASON} losses, of "
          f"{me['exp']:.1f} from {me['games26']} games = {b['new_loss']:.1f}, "
          f"{ordinal(b['new_rank'])}")
    for r in b["rows"]:
        tail = (f"  + {r['exp_loss']:.1f} = {r['loss'] + r['exp_loss']:.1f}"
                if r["exp_loss"] else "")
        print(f"    {r['rank']:>2}. {r['name']:<22}{r['loss']:>6.0f} of "
              f"{r['tot']:>4.0f}  {100 * r['loss'] / r['tot']:>5.1f}%  "
              f"{r['games']:>3} games{tail}"
              + ("   <- him" if r["me"] else ""))
    trunc = [r["name"] for r in b["rows"] if r["truncated"]]
    if trunc:
        print(f"    WARNING drawn row truncated at the {VOTES_FROM} floor, its "
              "figure is a floor and not a career total: " + ", ".join(trunc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
