"""Section builders for the Brownlow night research pack. See night_pack.py.

Each build_* function writes one markdown file under drafts/brownlow_night/.
They share night_pack.load()'s single read of the four sources, so a figure in
one file and the same figure in another cannot drift apart.

WHY THE SECTIONS ARE SPLIT THIS WAY, AND WHERE EACH ONE STOPS
The split follows the data's own boundaries rather than the shape of a post:

  career, seasons   reach 1924, because a season TOTAL needs no game attribution
  clubs, rounds     stop at 1984, because both need to know WHICH game a vote
                    came from and the pre-1984 file does not record it
  coaches           2004-2026, the AFLCA archive's own span
  projections       2026 only

A claim that crosses a boundary is the one that goes wrong, so every table
carries its own window in its header rather than inheriting one from the file.

THE SUPERLATIVE RULE IS WHY THESE TABLES ARE LONG
project_brief.md requires any "only / no other / most / best" claim to print the
ranked table it came from. A top-3 table cannot support a superlative because it
cannot show what is fourth, so the ladders here run deep enough to be checked.
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import brownlow_medallists as bm                                   # noqa: E402
from club_aliases import canonical_club                            # noqa: E402
from night_pack import (COMPARABLE, CUR_SEASON, ERA_OF, TWO_UMPIRE,  # noqa: E402
                        display_round, table, with_result, write)

MILESTONES = (50, 100, 150, 200, 250, 300)

# First VFL/AFL season, so a club table can say for itself whether its "record"
# is the club's record or only its since-1984 record. Not derivable from the
# archive: every club's first row there is 1984 or its entry year, whichever is
# later, so a club founded in 1897 and one founded in 1984 look identical.
# Brisbane Lions carries the Bears' 1987 entry, because canonical_club folds
# Brisbane Bears into it. Fitzroy stays separate and stays truncated.
CLUB_FIRST_SEASON = {
    "Adelaide": 1991, "Brisbane Lions": 1987, "Carlton": 1897,
    "Collingwood": 1897, "Essendon": 1897, "Fitzroy": 1897,
    "Fremantle": 1995, "Geelong": 1897, "Gold Coast": 2011,
    "Greater Western Sydney": 2012, "Hawthorn": 1925, "Melbourne": 1897,
    "North Melbourne": 1925, "Port Adelaide": 1997, "Richmond": 1908,
    "St Kilda": 1897, "Sydney": 1897, "West Coast": 1987,
    "Western Bulldogs": 1925,
}
VOTE_FLOOR = 1984
KNOWN_CLUBS = set(CLUB_FIRST_SEASON)


def _club_complete(club):
    """Whether the 1984 vote floor truncates this club's record or not."""
    return "yes" if CLUB_FIRST_SEASON.get(club, 1897) >= VOTE_FLOOR else ""


def _complete_clubs():
    return sorted(c for c in CLUB_FIRST_SEASON
                  if CLUB_FIRST_SEASON[c] >= VOTE_FLOOR)


def _rank(df):
    """A 1-based rank column on a frame already sorted.

    Idempotent: a frame that carries a rank from an earlier slice has it
    replaced rather than refused, because several tables here are re-ranked
    after a filter and the old column would be a stale position.
    """
    df = df.reset_index(drop=True)
    if "rank" in df.columns:
        df = df.drop(columns=["rank"])
    df.insert(0, "rank", range(1, len(df) + 1))
    return df


def _live(d):
    """fitzRoy IDs named in the 2026 prediction file."""
    return set(pd.to_numeric(d["game_2026"]["ID"], errors="coerce")
               .dropna().astype(int))


# ---------------------------------------------------------------------------
# Career
# ---------------------------------------------------------------------------

def build_career(d, top=120):
    car = d["career"].copy()
    car = _rank(car.sort_values("votes", ascending=False))
    live = _live(d)
    car["active"] = car.ID.map(lambda i: "yes" if int(i) in live else "")
    car["span"] = [("to 1983" if f == 0 else f"{int(f)}-{int(l)}")
                   for f, l in zip(car["first"], car["last"])]
    amb = ", ".join(d["career_ambiguous"]) or "none"

    blocks = [(
        "All-time career Brownlow votes, 1924-2025",
        f"""Every player who has polled, ranked on career total. Per-game votes
        exist only from 1984 and season totals before it, so a career that
        straddles 1984 is the sum of two differently sourced halves and the
        split is shown in the pre_votes and modern_votes columns.

        A pre-1984 total attaches to a modern career only where exactly ONE
        career carries that name and reaches back to the boundary, which is what
        keeps Gary Ablett senior's votes off junior's total. Names that resolve
        to more than one career are reported rather than guessed at: {amb}.

        Two things will bite a claim drawn from this table. A career overlapping
        1976 or 1977 carries votes from a season with twice the normal pool, so
        it is inflated against a modern one. And a career that began before 1924
        is truncated, not merely early.

        active = named in the 2026 prediction file, so the total is still
        moving. See projections_2026.md for where each of them lands.""",
        table(car.head(top), ["rank", "name", "votes", "span", "pre_votes",
                              "modern_votes", "active"], floatfmt=0))]

    g = d["games"]
    per = g.groupby("ID").agg(name=("Player_Name", "first"),
                              votes=("Votes", "sum"),
                              games=("Votes", "size"),
                              first=("Season", "min"),
                              last=("Season", "max")).reset_index()
    per = per[per["first"] >= 1985]
    per["per_game"] = per.votes / per.games
    for floor in (100, 200):
        r = _rank(per[per.games >= floor]
                  .sort_values("per_game", ascending=False).head(30))
        r["span"] = r["first"].astype(str) + "-" + r["last"].astype(str)
        r["active"] = r.ID.map(lambda i: "yes" if int(i) in live else "")
        blocks.append((
            f"Career votes per game, minimum {floor} home-and-away games",
            """A different ladder from the total, and the one a short career can
            win. Home-and-away games only: no votes are awarded in a final, so a
            finals appearance in the denominator is a game nobody could have
            polled in.

            Restricted to players whose first season is 1985 or later. A career
            that began before 1984 has its votes truncated at the boundary while
            every one of its games is still counted, which does not shorten the
            ladder so much as put a wrong number on it.""",
            table(r, ["rank", "name", "votes", "games", "per_game", "span",
                      "active"], floatfmt=3)))

    three = (g[g.Votes == 3].groupby("ID")
             .agg(name=("Player_Name", "first"), threes=("Votes", "size"))
             .join(g.groupby("ID").Votes.sum().rename("votes"))
             .reset_index().sort_values("threes", ascending=False))
    three = _rank(three.head(40))
    three["active"] = three.ID.map(lambda i: "yes" if int(i) in live else "")
    blocks.append((
        "Most three-vote (best-on-ground) games, career, 1984-2025",
        """Exactly one three-vote row exists per game, so this counts outright
        best-on-ground verdicts rather than votes.

        It cannot be extended backwards even though the pre-1984 file carries a
        Votes_3 column. In 1924-1930 that column holds SINGLE votes, not
        three-vote games, and from 1931 it is a season count with no game
        attached, so concatenating it would silently mix two quantities.""",
        table(three, ["rank", "name", "threes", "votes", "active"],
              floatfmt=0)))

    wr = with_result(d)
    L = (wr.groupby("ID").agg(name=("Player_Name", "first"),
                              votes=("Votes", "sum"))
         .join(wr[wr.res == "L"].groupby("ID").Votes.sum().rename("in_losses"))
         .fillna({"in_losses": 0.0}))
    L = _rank(L[L.votes > 0].sort_values("in_losses", ascending=False)
              .head(30).reset_index())
    L["share_pct"] = L.in_losses / L.votes * 100
    L["active"] = L.ID.map(lambda i: "yes" if int(i) in live else "")
    tv, tl = float(wr.Votes.sum()), float(wr[wr.res == "L"].Votes.sum())
    blocks.append((
        "Most career votes polled in a losing side, 1984-2025",
        f"""Umpires vote for winners. Of the {tv:,.0f} votes awarded between
        1984 and 2025, {tl:,.0f} ({tl / tv * 100:.1f}%) went to a player whose
        side lost, so a vote in a beaten team is the scarce kind.

        The ranked quantity is the COUNT. The share column is context and is a
        different ladder with a different leader, so copy that turns a share
        into "the highest proportion ever" is making a claim this table does not
        support.""",
        table(L, ["rank", "name", "in_losses", "votes", "share_pct", "active"],
              floatfmt=1)))

    won = {i for ids in bm.MEDALLIST_IDS.values() for i in ids}
    unwon = car[(car.ID > 0) & (~car.ID.isin(won))].copy()
    # pre_votes == 0 means the player polled nothing before 1984, and a
    # medallist by definition polled, so he cannot be a pre-1984 medallist that
    # the dictionary does not know about. Without this filter the table is
    # topped by Gary Dempsey, who won in 1975.
    clean = _rank(unwon[unwon.pre_votes == 0].head(30))
    clean["active"] = clean.ID.map(lambda i: "yes" if int(i) in live else "")
    blocks.append((
        "Most career votes without ever winning the medal",
        """Medallists come from brownlow_medallists.py, which is canonical and
        covers 1984-2025. It cannot be derived from vote totals, because three
        seasons had a leading poller who did not win: Chris Grant in 1997 and
        Corey McKernan in 1996 were ineligible through suspension, and Jobe
        Watson was stripped in 2016.

        THE DICTIONARY STOPS AT 1984 AND THIS TABLE IS FILTERED SO THAT DOES NOT
        MATTER. Only players with no pre-1984 votes are listed. A medallist
        polled by definition, so a player who polled nothing before 1984 cannot
        be a pre-1984 winner the dictionary has never heard of. Without that
        filter the table opens with Gary Dempsey, who won in 1975.

        The one hole left is a pre-1984 winner whose name is ambiguous across
        two careers, since the seam leaves those at zero: {amb} is the only such
        name in the archive.""".replace("{amb}", amb),
        table(clean, ["rank", "name", "votes", "span", "active"], floatfmt=0)))

    carried = _rank(unwon[unwon.pre_votes > 0].head(20))
    blocks.append((
        "Excluded from the table above: careers reaching back past 1984",
        """These players have pre-1984 votes, so the medallist dictionary cannot
        clear them and they are held out of the ladder rather than ranked on it.
        Some genuinely never won (Leigh Matthews is the famous case) and some
        did (Gary Dempsey, 1975). Check a published honour roll before using any
        row here.""",
        table(carried, ["rank", "name", "votes", "span", "pre_votes",
                        "modern_votes"], floatfmt=0)))

    write("career", "Career vote records", blocks)


# ---------------------------------------------------------------------------
# Seasons
# ---------------------------------------------------------------------------

def _modern_seasons(d):
    """One row per player-season, 1984-2025: votes, H&A games, club, threes."""
    g = d["games"]
    s = (g.groupby(["ID", "Season"])
         .agg(name=("Player_Name", "first"), club=("Club", "first"),
              votes=("Votes", "sum"), games=("Votes", "size"))
         .reset_index())
    thr = (g[g.Votes == 3].groupby(["ID", "Season"]).size().rename("threes"))
    pol = (g[g.Votes > 0].groupby(["ID", "Season"]).size().rename("polled"))
    s = s.join(thr, on=["ID", "Season"]).join(pol, on=["ID", "Season"])
    s[["threes", "polled"]] = s[["threes", "polled"]].fillna(0).astype(int)
    s["per_game"] = s.votes / s.games
    s["system"] = s.Season.map(ERA_OF)
    return s


def build_seasons(d, top=60):
    mod = _modern_seasons(d)
    pre = d["pre"]
    old = pd.DataFrame({"name": pre.Player, "Season": pre.Season,
                        "club": pre.Teams, "votes": pre.Votes.astype(float),
                        "games": pre.Games.astype(float),
                        "threes": pre.Votes_3, "polled": pre.Games_polled,
                        "system": pre.system, "ID": -1})
    old["per_game"] = old.votes / old.games
    allsn = pd.concat([old, mod], ignore_index=True)

    blocks = []
    a = _rank(allsn.sort_values("votes", ascending=False).head(top))
    blocks.append((
        "Highest single-season vote totals, 1924-2025, ALL ERAS MIXED",
        """Read the system column before quoting any row of this table. It is
        the raw ladder and the top of it is not a like-for-like list.

        1976 and 1977 awarded 3-2-1 from EACH of two field umpires, so those two
        seasons put 1,512 votes into the pool against 792 in every neighbouring
        season, an exact doubling measured from the file rather than recalled.
        Graham Teasdale's 59 in 1977 and Graham Moss' 48 in 1976 sit at or near
        the top here and neither is comparable to a modern total.

        1924-1930 is the opposite distortion: one vote per game to one player,
        so a season of 7 means seven best-on-grounds.

        The next table is the one to quote from.""",
        table(a, ["rank", "name", "Season", "club", "votes", "games",
                  "per_game", "system"], floatfmt=2)))

    comp = allsn[allsn.Season.map(COMPARABLE)]
    c = _rank(comp.sort_values("votes", ascending=False).head(top))
    blocks.append((
        "Highest single-season totals on the modern scale (3-2-1, one umpire)",
        f"""1931-2025 with {TWO_UMPIRE[0]} and {TWO_UMPIRE[1]} removed, which is
        every season scored the way a 2026 season will be scored. This is the
        ladder a 2026 total belongs on.

        The games column still matters and is not a caveat to be waved through:
        seasons here run from 17 rounds (2020) to 23 (2023 onward), so a total
        and a rate can disagree about who had the bigger year. Both are
        printed.""",
        table(c, ["rank", "name", "Season", "club", "votes", "games",
                  "per_game", "system"], floatfmt=2)))

    r = _rank(mod[mod.games >= 10].sort_values("per_game", ascending=False)
              .head(40))
    blocks.append((
        "Highest votes per home-and-away game in a season, 1984-2025",
        """Minimum 10 home-and-away games. Restricted to 1984 onward because the
        pre-1984 Games column counts every match played rather than only the
        vote-eligible ones, so a rate built on it would divide votes that finals
        could not contribute to by a denominator that includes them.

        The maximum possible is 3.000. Nobody is close, and the shape of the top
        of this ladder is the useful fact: a season above 1.5 is rare.""",
        table(r, ["rank", "name", "Season", "club", "votes", "games",
                  "per_game", "threes", "polled"], floatfmt=3)))

    t = _rank(mod.sort_values(["threes", "votes"], ascending=False).head(40))
    blocks.append((
        "Most three-vote games in a season, 1984-2025",
        """Best-on-ground verdicts, not votes. A player can lead a season's
        votes without leading its threes and the two ladders do come apart, so
        this is a separate claim rather than a restatement of the last one.""",
        table(t, ["rank", "name", "Season", "club", "threes", "votes", "games",
                  "polled"], floatfmt=0)))

    p = _rank(mod.sort_values(["polled", "votes"], ascending=False).head(40))
    blocks.append((
        "Most games polled in a season, 1984-2025",
        """Games in which the player got at least one vote, which is the
        consistency ladder rather than the peak one. Shown beside games played,
        because polling in 18 of 22 and 18 of 19 are not the same season.""",
        table(p, ["rank", "name", "Season", "club", "polled", "games", "votes",
                  "threes"], floatfmt=0)))

    # ---- medal context -----------------------------------------------------
    win_rows = []
    for sn, ids in sorted(bm.MEDALLIST_IDS.items()):
        sub = mod[mod.Season == sn]
        wt = sub[sub.ID.isin(ids)]
        if wt.empty:
            continue
        winner_votes = float(wt.votes.max())
        others = sub[~sub.ID.isin(ids)].votes
        runner = float(others.max()) if len(others) else 0.0
        win_rows.append({
            "Season": sn,
            "medallist": " & ".join(sorted(wt.name)),
            "votes": winner_votes,
            "games": int(wt.games.max()),
            "runner_up": runner,
            "margin": winner_votes - runner,
            "top_poller": sub.loc[sub.votes.idxmax(), "name"],
            "top_votes": float(sub.votes.max())})
    W = pd.DataFrame(win_rows)
    blocks.append((
        "Every medal since 1984: winning total, margin, and who led the count",
        """The medallist list is canonical (brownlow_medallists.py), never
        derived from the totals. Three seasons prove why it cannot be: 1996 and
        1997 had an ineligible leading poller, and 2012's winner was stripped in
        2016 and the medal reallocated. In those seasons top_poller and
        medallist differ and the margin column goes negative, which is correct
        rather than a bug.

        A joint medal lists both names and takes the higher total, so the margin
        is measured against the highest non-medallist.""",
        table(W.sort_values("Season", ascending=False),
              ["Season", "medallist", "votes", "games", "runner_up", "margin",
               "top_poller", "top_votes"], floatfmt=0)))

    blocks.append((
        "Tightest and widest counts since 1984",
        """Same table, ranked on margin. A negative margin is one of the three
        ineligible or stripped seasons above.""",
        table(_rank(W.sort_values("margin").head(15)),
              ["rank", "Season", "medallist", "votes", "runner_up", "margin"],
              floatfmt=0) + "\n\nWidest:\n\n" +
        table(_rank(W.sort_values("margin", ascending=False).head(15)),
              ["rank", "Season", "medallist", "votes", "runner_up", "margin"],
              floatfmt=0)))

    won_pairs = {(sn, i) for sn, ids in bm.MEDALLIST_IDS.items() for i in ids}
    won_mask = pd.Series([(s, i) in won_pairs
                          for s, i in zip(mod.Season, mod.ID)], index=mod.index)
    nw = mod[~won_mask]
    nw = _rank(nw.sort_values("votes", ascending=False).head(30))
    blocks.append((
        "Highest season totals that did NOT win the medal, 1984-2025",
        """Includes the ineligible seasons, which is the point of the table:
        Chris Grant's 1997 and Corey McKernan's 1996 belong here and are the
        reason a medallist can never be inferred from a vote total.""",
        table(nw, ["rank", "name", "Season", "club", "votes", "games",
                   "per_game"], floatfmt=2)))

    # ---- consecutive-game polling streaks ---------------------------------
    g = d["games"].sort_values(["ID", "Season", "Round_num"])
    g = g.assign(hit=(g.Votes > 0).astype(int))
    brk = (g.hit == 0).groupby(g.ID).cumsum()
    # first/last, never min/max. The frame is sorted by ID, Season, Round_num,
    # so first and last are the run's true endpoints. min and max would take the
    # smallest season and the smallest ROUND independently, which for a run
    # crossing a summer reports the season it started and a round from the
    # season it finished: an 11-game run read "2016 R1 to 2017 R23".
    runs = (g[g.hit == 1].groupby(["ID", brk[g.hit == 1]])
            .agg(name=("Player_Name", "first"), n=("hit", "size"),
                 votes=("Votes", "sum"),
                 s0=("Season", "first"), r0=("Round_num", "first"),
                 s1=("Season", "last"), r1=("Round_num", "last"))
            .reset_index(drop=False).sort_values("n", ascending=False))
    runs = _rank(runs.head(30))
    runs["from"] = (runs.s0.astype(str) + " R" + runs.r0.astype(str))
    runs["to"] = (runs.s1.astype(str) + " R" + runs.r1.astype(str))
    runs["crosses_seasons"] = (runs.s1 != runs.s0).map({True: "yes",
                                                        False: ""})
    blocks.append((
        "Longest runs of consecutive home-and-away games polling a vote",
        """1984-2025. The run is over the player's own consecutive VOTE-ELIGIBLE
        appearances, so a final, a bye, a suspension or an injury break does not
        end it and does not extend it either. Rounds are raw AFLTables numbers,
        which run one ahead of the AFL's from 2024 on.

        A run spanning two seasons is kept as one run. That is a judgment call
        rather than an obvious rule, and the from/to columns are there so a
        cross-season run can be spotted and dropped if the claim needs the
        stricter reading.""",
        table(runs, ["rank", "name", "n", "votes", "from", "to",
                     "crosses_seasons"], floatfmt=0)))

    write("seasons", "Season vote records", blocks)


# ---------------------------------------------------------------------------
# Clubs
# ---------------------------------------------------------------------------

def build_clubs(d, per_club=12):
    g = d["games"]
    mod = _modern_seasons(d)
    live = _live(d)

    car = (g.groupby(["Club", "ID"])
           .agg(name=("Player_Name", "first"), votes=("Votes", "sum"),
                games=("Votes", "size"), first=("Season", "min"),
                last=("Season", "max")).reset_index())
    car["per_game"] = car.votes / car.games

    car["complete"] = car.Club.map(_club_complete)
    done = ", ".join(_complete_clubs())
    blocks = [(
        "Club career vote record holders, 1984-2025",
        f"""Votes polled FOR THAT CLUB, not career votes. They are the same
        number for a one-club player and different for everybody else, and the
        claim being made is a club record, so the club is the filter.

        THE complete COLUMN DECIDES WHETHER THE WORD "RECORD" IS HONEST HERE.
        Per-game votes start in 1984, so for a club that predates the archive
        this is a since-1984 figure and not the club record a club historian
        would recognise. The season-total file that reaches 1924 carries no club
        attribution and cannot extend it, so the gap cannot be closed from
        anything in this repo.

        Complete: {done}. Every other club is truncated.

        Fitzroy stays Fitzroy and is not folded into Brisbane; Brisbane Bears
        canonicalises to Brisbane Lions, so the Lions row runs from 1987.""",
        table(_rank(car.sort_values("votes", ascending=False)
                    .groupby("Club", as_index=False).head(1)
                    .sort_values("votes", ascending=False)),
              ["rank", "Club", "name", "votes", "games", "per_game",
               "first", "last", "complete"], floatfmt=2))]

    best_season = (mod.sort_values("votes", ascending=False)
                   .groupby("club", as_index=False).head(1)
                   .sort_values("votes", ascending=False))
    best_season["complete"] = best_season.club.map(_club_complete)
    blocks.append((
        "Club single-season vote record holders, 1984-2025",
        """The biggest season any player has had for each club. Same 1984 floor
        and the same complete column as the table above.

        A player who changed clubs mid-season has his votes attributed to the
        club he earned them at, because the grouping is on club as well as
        player.""",
        table(_rank(best_season), ["rank", "club", "name", "Season", "votes",
                                   "games", "per_game", "threes", "complete"],
              floatfmt=2)))

    agg = (g.groupby(["Season", "Club"])
           .agg(votes=("Votes", "sum"),
                pollers=("ID", lambda s: s[g.loc[s.index, "Votes"] > 0].nunique()))
           .reset_index())
    fx = g.drop_duplicates(["Season", "Round_num", "Home.team", "Away.team"])
    gm = pd.concat([
        fx.groupby(["Season", "Home.team"]).size().rename("n"),
        fx.groupby(["Season", "Away.team"]).size().rename("n")]).groupby(
        level=[0, 1]).sum().rename("club_games")
    agg = agg.join(gm, on=["Season", "Club"])
    agg["per_game"] = agg.votes / agg.club_games
    blocks.append((
        "Biggest club-seasons: total votes polled by one club in one season",
        """Every vote polled by every player of that club. The club_games column
        is the number of home-and-away games the club played that season, so the
        per_game figure is votes per club game and its theoretical maximum is 6
        (a club whose players took all three vote places in every one of its own
        games).

        club_games is derived from the fixture list rather than assumed, so the
        17-round 2020 and the 23-game seasons from 2023 sit on their own
        denominators.""",
        table(_rank(agg.sort_values("votes", ascending=False).head(40)),
              ["rank", "Season", "Club", "votes", "pollers", "club_games",
               "per_game"], floatfmt=2)))

    blocks.append((
        "Lowest club-seasons, same window",
        """The other end of the same table. Useful for a "worst ever" line, and
        the club_games column is what stops 2020 dominating it for the wrong
        reason.""",
        table(_rank(agg.sort_values("per_game").head(25)),
              ["rank", "Season", "Club", "votes", "pollers", "club_games",
               "per_game"], floatfmt=2)))

    for club in sorted(g.Club.dropna().unique()):
        cc = _rank(car[car.Club == club].sort_values("votes", ascending=False)
                   .head(per_club))
        cc["active"] = cc.ID.map(lambda i: "yes" if int(i) in live else "")
        ss = _rank(mod[mod.club == club].sort_values("votes", ascending=False)
                   .head(8))
        entered = CLUB_FIRST_SEASON.get(club, 1897)
        note = ("complete: the club entered the competition in "
                f"{entered}, after the 1984 vote floor"
                if entered >= VOTE_FLOOR else
                f"TRUNCATED: the club has played since {entered} and the vote "
                f"archive starts in 1984, so both ladders below are since-1984 "
                f"figures rather than club records")
        blocks.append((
            club,
            f"""Career votes for {club} first, biggest single seasons for
            {club} second. 1984-2025, and {note}.""",
            "**Career votes for the club**\n\n" +
            table(cc, ["rank", "name", "votes", "games", "per_game", "first",
                       "last", "active"], floatfmt=2) +
            "\n\n**Biggest seasons for the club**\n\n" +
            table(ss, ["rank", "name", "Season", "votes", "games", "per_game",
                       "threes"], floatfmt=2)))

    write("clubs", "Club vote records", blocks)


# ---------------------------------------------------------------------------
# Rounds
# ---------------------------------------------------------------------------

def build_rounds(d, per_round=10):
    g = d["games"].copy()
    live = _live(d)

    seasons_with = g.groupby("Round_disp").Season.nunique().rename("seasons")
    # slot_games, not games: `car` below already carries a per-player games
    # column and the two mean different things.
    games_in = (g.drop_duplicates(["Season", "Round_num", "Home.team",
                                   "Away.team"])
                .groupby("Round_disp").size().rename("slot_games"))

    car = (g.groupby(["Round_disp", "ID"])
           .agg(name=("Player_Name", "first"), votes=("Votes", "sum"),
                games=("Votes", "size"), threes=("Votes", lambda s: (s == 3).sum()))
           .reset_index())

    lead = (car.sort_values(["votes", "threes"], ascending=False)
            .groupby("Round_disp", as_index=False).head(1)
            .sort_values("Round_disp"))
    lead = lead.join(seasons_with, on="Round_disp").join(games_in, on="Round_disp")
    blocks = [(
        "The round-by-round record holder, 1984-2025",
        """One row per round number: the player with the most career votes in
        that round slot. This is the table behind a "most votes ever in Round
        12" line.

        ROUND NUMBERING. The Round column is the AFL's own number, which is
        AFLTables' raw Round_num minus one from 2024 on, because AFLTables
        counts Opening Round as its Round 1. Opening Round therefore appears
        here as **Round 0** and exists only in 2024, 2025 and 2026.

        THE SLOTS ARE NOT EQUAL AND THE SEASONS COLUMN IS NOT DECORATION. Round
        0 has been played three times and Round 23 only in seasons long enough
        to reach it, so a low total at the ends of the table is a shorter
        history rather than a weaker record. A round-slot record is a
        coincidence of scheduling as much as an achievement: a player misses the
        slot entirely in a season his club has the bye, and split rounds move
        fixtures between slots.

        games = home-and-away games ever played in that slot. seasons = how many
        seasons contain it.""",
        table(lead, ["Round_disp", "name", "votes", "games", "threes",
                     "slot_games", "seasons"], floatfmt=0).replace(
            "| Round_disp |", "| Round |"))]

    thr_lead = (car.sort_values(["threes", "votes"], ascending=False)
                .groupby("Round_disp", as_index=False).head(1)
                .sort_values("Round_disp"))
    blocks.append((
        "Most three-vote games in each round slot, 1984-2025",
        """The same shape ranked on best-on-ground verdicts instead of votes.
        It has a different leader in most slots, so it is a separate claim.""",
        table(thr_lead, ["Round_disp", "name", "threes", "votes", "games"],
              floatfmt=0).replace("| Round_disp |", "| Round |")))

    for rd in sorted(car.Round_disp.unique()):
        sub = _rank(car[car.Round_disp == rd]
                    .sort_values(["votes", "threes"], ascending=False)
                    .head(per_round))
        sub["active"] = sub.ID.map(lambda i: "yes" if int(i) in live else "")
        ns = int(seasons_with.get(rd, 0))
        ng = int(games_in.get(rd, 0))
        label = "Opening Round (AFL Round 0)" if rd == 0 else f"Round {rd}"
        blocks.append((
            label,
            f"""Career votes in this slot, 1984-2025. Played in {ns} seasons,
            {ng:,} home-and-away games.""",
            table(sub, ["rank", "name", "votes", "games", "threes", "active"],
                  floatfmt=0)))

    write("rounds", "Round-by-round vote records", blocks)


# ---------------------------------------------------------------------------
# Coaches votes crossed with Brownlow votes
# ---------------------------------------------------------------------------

def coaches_frame(d):
    """AFLCA rows 2004-2026, cleaned, with the Brownlow vote for the same game.

    The cleaning is scripts/coaches_season_card.py's, imported rather than
    reimplemented, because it is the only repair in the repo that reaches 2020's
    phantom rounds: five rounds of repeated fixtures that each sum to 30, carry
    integer values and duplicate no player-round key, so neither the 30-check
    nor coaches_guard's key dedupe can see them. Left in, Christian Petracca
    reads 128 votes for 2020 against a true 78.

    Brownlow votes are attached by season, round, resolved name and club. 2026
    attaches to nothing by design: those votes are not awarded until count
    night, and a 0 there would be indistinguishable from a real duck.
    """
    if "_cv" in d:
        return d["_cv"]
    import importlib.util
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "coaches_season_card.py")
    spec = importlib.util.spec_from_file_location("_csc", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    raw = pd.concat([pd.read_csv(m.COACHES_ALL), pd.read_csv(m.COACHES_CUR)],
                    ignore_index=True)
    played = m._played()
    cv, n_dup, n_bad = m._clean(raw)
    cv, leaked = m._drop_leaked_finals(cv, played)
    cv, n_unres = m._resolve(cv, played)

    g = d["games"]
    j = cv.merge(g[["Season", "Round_num", "Player_Name", "Club", "ID",
                    "Votes", "Home.team", "Away.team"]],
                 left_on=["Season", "Round", "A", "club"],
                 right_on=["Season", "Round_num", "Player_Name", "Club"],
                 how="left")
    j = j.rename(columns={"Coaches.Votes": "cv", "Votes": "bv", "A": "player"})

    have = (played.drop_duplicates(["Season", "rd", "hm", "aw"])
            .groupby("Season").size().rename("archive_games"))
    got = (cv.groupby("Season")
           .apply(lambda x: x.groupby(["Round", "Home.Team", "Away.Team"])
                  .ngroups, include_groups=False).rename("cv_games"))
    cover = pd.concat([have, got], axis=1)
    cover["pct"] = cover.cv_games / cover.archive_games * 100
    cover["complete"] = (cover.cv_games >= cover.archive_games).map(
        {True: "yes", False: ""})

    d["_cv"] = (j, cover, {"dup_games": n_dup, "bad_30": n_bad,
                           "leaked_finals": leaked, "unresolved": n_unres})
    return d["_cv"]


def reverse_frame(d):
    """Every Brownlow row in a coaches-covered game, with cv filled to 0.

    THE COACHES FILE HOLDS ONLY PLAYERS WHO POLLED, WHICH INVERTS THE WHOLE JOIN.
    "Most coaches votes for no Brownlow vote" can be read off the coaches rows
    directly, because the player is in the file by definition. Its mirror, three
    Brownlow votes for NO coaches votes, cannot: that player has no coaches row
    at all, so he is invisible to a join that starts from the coaches side. He
    has to be found from the Brownlow side instead, with a missing coaches row
    read as a real zero.

    That reading is only safe inside a game the coaches file actually covers. In
    a game it does not cover, every player looks like a zero and the whole
    fixture would arrive as 44 false findings. So the frame is restricted to
    fixtures with at least one matched coaches row, identified in the ARCHIVE's
    own club names rather than the feed's.
    """
    if "_rev" in d:
        return d["_rev"]
    j, cover, _ = coaches_frame(d)
    m = j[j.ID.notna() & j["Home.team"].notna()]
    covered = set(zip(m.Season, m.Round_num, m["Home.team"], m["Away.team"]))

    g = d["games"]
    key = list(zip(g.Season, g.Round_num, g["Home.team"], g["Away.team"]))
    sub = g[[k in covered for k in key]].copy()

    cvmap = m.set_index(["Season", "Round_num", "ID"]).cv
    idx = pd.MultiIndex.from_arrays([sub.Season, sub.Round_num, sub.ID])
    sub["cv"] = cvmap.reindex(idx).fillna(0.0).values
    d["_rev"] = (sub, len(covered))
    return d["_rev"]


def build_coaches(d):
    j, cover, prov = coaches_frame(d)
    matched = j[j.Season < CUR_SEASON]
    miss = int(matched.bv.isna().sum())
    ok = matched[matched.bv.notna()].copy()

    blocks = [(
        "What this section can and cannot carry",
        f"""The AFL Coaches Association archive runs 2004-2026 here. Both
        coaches rank five players 5-4-3-2-1, so a game awards exactly 30 votes
        and one player's ceiling is 10.

        THE ARCHIVE IS NOT COMPLETE AND THE RECENT SEASONS ARE THE SHORT ONES.
        The coverage table below is the first thing to read: 2023, 2024 and 2025
        each hold around 91-95% of their games. Every GAME-level record in this
        section is safe regardless, because a game either is in the file with
        both figures or is absent entirely. Every SEASON-level total for an
        incomplete season is a FLOOR, and a "most coaches votes in a season"
        claim drawn from one is not safe.

        Cleaning applied, all from scripts/coaches_season_card.py:
        {prov['dup_games']} repeated vote blocks dropped (2020's phantom rounds),
        {prov['bad_30']} games dropped for not summing to 30,
        {len(prov['leaked_finals'])} finals dropped that were filed under a
        home-and-away round label, {prov['unresolved']} rows whose player could
        not be resolved to the stats archive.

        {miss} pre-2026 rows found no Brownlow row to join to. They are one
        fixture: 2025 Brisbane v Geelong, which the coaches feed files under
        Round 4 and the archive holds in Opening Round. Reported rather than
        forced onto a round.

        2026 carries coaches votes and no Brownlow votes, because those are not
        awarded until count night.""",
        table(cover.reset_index(), ["Season", "archive_games", "cv_games",
                                    "pct", "complete"], floatfmt=1))]

    z = ok[ok.bv == 0].sort_values("cv", ascending=False)
    blocks.append((
        "Biggest coaches vote in a game that polled NO Brownlow vote",
        f"""The disagreement table. {len(z):,} player-games since 2004 drew
        coaches votes and no umpire vote.

        A perfect 10 means both coaches independently rated him the best player
        on the ground. The rows at 10 with a Brownlow duck are the strongest
        version of the claim and are listed in full in the next table.""",
        table(_rank(z.head(50)), ["rank", "player", "club", "Season", "Round",
                                  "cv", "bv", "Home.Team", "Away.Team"],
              floatfmt=0)))

    ten = ok[ok.cv == 10]
    ten0 = ten[ten.bv == 0].sort_values(["Season", "Round"])
    blocks.append((
        "Every 10-vote coaches game that polled zero Brownlow votes",
        f"""{len(ten):,} player-games since 2004 drew the maximum 10 from the
        coaches. Of those, {len(ten0):,} ({len(ten0) / max(len(ten), 1) * 100:.1f}%)
        polled no Brownlow vote at all.

        The full list is printed because the claim is a superlative about a
        countable set and a top-10 slice could not support it. Distribution of
        what a 10-vote game actually polls:

        {' | '.join(f"{int(k)} votes: {v}" for k, v in ten.bv.value_counts().sort_index().items())}""",
        table(_rank(ten0), ["rank", "player", "club", "Season", "Round",
                            "Home.Team", "Away.Team"], floatfmt=0)))

    who_ten = (ten0.groupby(["player", "club"]).size().rename("tens_no_vote")
               .reset_index()
               .merge(ten.groupby(["player", "club"]).size().rename("tens")
                      .reset_index(), on=["player", "club"])
               .sort_values(["tens_no_vote", "tens"], ascending=False))
    blocks.append((
        "Who collects the most 10-vote coaches games that poll nothing",
        """The same set as the table above, grouped by player, because a list of
        284 games answers "how often" and not "who". tens is his total 10-vote
        games and tens_no_vote is how many of them the umpires passed over.

        A player near the top of this is not necessarily unlucky: a high tens
        count is itself a career achievement, and a player with two 10-vote
        games can never appear above one with fifteen. Read it beside the tens
        column, not alone.""",
        table(_rank(who_ten.head(30)),
              ["rank", "player", "club", "tens_no_vote", "tens"], floatfmt=0)))

    per_player = (ok.groupby(["player", "club"])
                  .agg(cv=("cv", "sum"), bv=("bv", "sum"),
                       games=("cv", "size"),
                       zero_bv_cv=("cv", lambda s: s[ok.loc[s.index, "bv"] == 0]
                                   .sum()))
                  .reset_index())
    # float("nan"), not pd.NA: pd.NA turns the column to object dtype, which the
    # markdown formatter skips, and the ratio prints at full float precision.
    per_player["cv_per_bv"] = (per_player.cv
                               / per_player.bv.replace(0, float("nan")))
    hi = per_player[per_player.games >= 60].sort_values(
        "cv_per_bv", ascending=False)
    blocks.append((
        "Career: most coaches votes per Brownlow vote, 2004-2025",
        """Minimum 60 coaches-vote games in the file. The ratio is how many
        coaches votes the player drew for each Brownlow vote he got, so a high
        number is a career the coaches rated more than the umpires did.

        Both figures cover only games IN THE COACHES FILE, so a career spanning
        2023-2025 is measured on the incomplete seasons and both halves of the
        ratio are floors. The ratio itself is more robust than either total,
        because the missing games remove coaches votes and Brownlow votes
        together.""",
        table(_rank(hi.head(30)), ["rank", "player", "club", "cv", "bv",
                                   "cv_per_bv", "zero_bv_cv", "games"],
              floatfmt=2)))

    lo = per_player[per_player.games >= 60].sort_values("cv_per_bv")
    blocks.append((
        "The inverse: fewest coaches votes per Brownlow vote",
        """Same table, other end. A low ratio is a career the umpires rated
        above the coaches' read of it.""",
        table(_rank(lo.head(30)), ["rank", "player", "club", "cv", "bv",
                                   "cv_per_bv", "zero_bv_cv", "games"],
              floatfmt=2)))

    # ---- the mirror: Brownlow votes the coaches did not see ---------------
    rev, n_cov = reverse_frame(d)
    threes = rev[rev.Votes == 3]
    t0 = threes[threes.cv == 0].sort_values(["Season", "Round_num"])
    dist = threes.cv.value_counts().sort_index()
    blocks.append((
        "Best on ground to the umpires, NOTHING from the coaches",
        f"""The mirror of the two tables above, and it needs a different join to
        find at all. The coaches file lists only players who polled, so a player
        with no coaches votes has no row in it and is invisible to any lookup
        that starts from the coaches side. These are found from the Brownlow
        side, inside the {n_cov:,} fixtures the coaches file actually covers, so
        that an absent row can be read as a real zero rather than as a missing
        game.

        {len(threes):,} three-vote games sit inside a covered fixture.
        {len(t0):,} of them ({len(t0) / max(len(threes), 1) * 100:.1f}%) drew no
        coaches votes at all: the umpires' best on ground did not make either
        coach's top five.

        What a three-vote Brownlow game draws from the coaches:

        {' | '.join(f"{int(k)} cv: {v:,}" for k, v in dist.items())}""",
        table(_rank(t0), ["rank", "Player_Name", "Club", "Season",
                          "Round_num", "Home.team", "Away.team"],
              floatfmt=0)))

    low = threes[threes.cv <= 2].groupby(["ID"]).agg(
        name=("Player_Name", "first"), club=("Club", "first"),
        n=("Votes", "size")).reset_index()
    zero_by = threes[threes.cv == 0].groupby("ID").size().rename("with_zero")
    low = low.join(zero_by, on="ID").fillna({"with_zero": 0})
    low = low.sort_values(["with_zero", "n"], ascending=False)
    blocks.append((
        "Who collects the most three-vote games the coaches ignored",
        """Grouped by player. n counts his three-vote games drawing two coaches
        votes or fewer; with_zero counts the subset that drew none.

        Same caution as its mirror: a player cannot appear here without first
        having a lot of three-vote games, so this is partly a ladder of
        best-on-ground counts. Read it against career.md's three-vote table.""",
        table(_rank(low.head(30)), ["rank", "name", "club", "with_zero", "n"],
              floatfmt=0)))

    per_g = rev.groupby(["ID"]).agg(
        name=("Player_Name", "first"), club=("Club", "first"),
        bv=("Votes", "sum"), cv=("cv", "sum"), games=("Votes", "size"))
    per_g = per_g[(per_g.games >= 60) & (per_g.bv >= 20)].copy()
    per_g["cv_per_bv"] = per_g.cv / per_g.bv
    blocks.append((
        "Career: fewest coaches votes per Brownlow vote, both sides counted",
        f"""The ratio again, but computed off the reverse frame so a game with
        no coaches votes counts as a zero rather than as an absence. Minimum 60
        games inside covered fixtures and 20 career Brownlow votes in them.

        This is the honest version of the "umpires rate him, coaches do not"
        claim, and it is a different table from the one above, which could only
        see games where he polled with the coaches.""",
        table(_rank(per_g.reset_index().sort_values("cv_per_bv").head(30)),
              ["rank", "name", "club", "bv", "cv", "cv_per_bv", "games"],
              floatfmt=2)))

    # ---- season level ------------------------------------------------------
    sea = (ok.groupby(["Season", "player", "club"])
           .agg(cv=("cv", "sum"), bv=("bv", "sum"), games=("cv", "size"))
           .reset_index())
    full = set(cover[cover.complete == "yes"].index)
    sea["complete_season"] = sea.Season.map(
        lambda s: "yes" if s in full else "")
    sea["cv_rank"] = sea.groupby("Season").cv.rank(ascending=False,
                                                   method="min")
    sea["bv_rank"] = sea.groupby("Season").bv.rank(ascending=False,
                                                   method="min")
    sea["rank_gap"] = sea.bv_rank - sea.cv_rank

    big = sea[sea.cv >= 40].sort_values(["bv", "cv"],
                                        ascending=[True, False])
    blocks.append((
        "Most coaches votes for the fewest Brownlow votes, in one season",
        """Players with 40 or more coaches votes in a season, ranked on how few
        Brownlow votes came with them. The coaches watched every game of that
        season and the umpires watched the same games.

        The complete_season column is load-bearing. A row from 2023, 2024 or
        2025 sits on an incomplete coaches archive, so its cv figure is a floor
        and the gap it shows is the smallest the gap could be, not the size of
        it. The games column is coaches-vote appearances in the file, not games
        played.""",
        table(_rank(big.head(40)), ["rank", "player", "club", "Season", "cv",
                                    "bv", "games", "cv_rank", "bv_rank",
                                    "complete_season"], floatfmt=0)))

    top_cv = sea.sort_values("cv", ascending=False)
    blocks.append((
        "Biggest coaches-vote seasons, and what they polled",
        """The straight coaches ladder with the Brownlow return beside it.
        Ranked on a figure that is a floor in the incomplete seasons, so a
        superlative off the top row needs the complete_season column checked
        first.""",
        table(_rank(top_cv.head(40)), ["rank", "player", "club", "Season", "cv",
                                       "bv", "games", "cv_rank", "bv_rank",
                                       "complete_season"], floatfmt=0)))

    snub = sea[(sea.cv_rank <= 3) & (sea.games >= 10)].sort_values(
        "rank_gap", ascending=False)
    blocks.append((
        "Top-three coaches seasons that the umpires ranked furthest down",
        """Players who finished top three at their club-independent coaches
        count for a season and finished far lower on that season's Brownlow
        ladder. rank_gap is Brownlow rank minus coaches rank, so a large
        positive number is a player the coaches rated and the umpires did
        not.""",
        table(_rank(snub.head(30)), ["rank", "player", "club", "Season",
                                     "cv", "cv_rank", "bv", "bv_rank",
                                     "rank_gap", "complete_season"],
              floatfmt=0)))

    inv = sea[(sea.bv_rank <= 3) & (sea.games >= 10)].sort_values("rank_gap")
    blocks.append((
        "The inverse: top-three Brownlow seasons the coaches ranked lower",
        """Same table read the other way. A large negative rank_gap is a player
        the umpires rated well above the coaches' read of the same season.""",
        table(_rank(inv.head(30)), ["rank", "player", "club", "Season", "cv",
                                    "cv_rank", "bv", "bv_rank", "rank_gap",
                                    "complete_season"], floatfmt=0)))

    cur = j[j.Season == CUR_SEASON]
    cs = (cur.groupby(["player", "club"])
          .agg(cv=("cv", "sum"), games=("cv", "size"), tens=("cv", lambda s: (s == 10).sum()))
          .reset_index().sort_values("cv", ascending=False))
    se = d["season_2026"][["Player_Name", "Exp_Total_Votes"]]
    cs = cs.merge(se, left_on="player", right_on="Player_Name", how="left")
    cs["exp_rank"] = cs.Exp_Total_Votes.rank(ascending=False, method="min")
    blocks.append((
        f"{CUR_SEASON} coaches votes, complete, against the model's projection",
        f"""The {CUR_SEASON} coaches file holds all 207 home-and-away games, so
        unlike 2023-2025 this season's coaches totals are complete rather than a
        floor. That makes it the one independent read on the {CUR_SEASON} count
        that exists before the night.

        Exp_Total_Votes is the model's expectation and is retrospective, never a
        forward claim about a game still to be played.""",
        table(_rank(cs.head(50)), ["rank", "player", "club", "cv", "tens",
                                   "games", "Exp_Total_Votes", "exp_rank"],
              floatfmt=1)))

    write("coaches", "Coaches votes crossed with Brownlow votes", blocks)


# ---------------------------------------------------------------------------
# 2026 projections against every record above
# ---------------------------------------------------------------------------

def _scenarios(d):
    """Per-player 2026 floor / expected / rounded 3-2-1 / ceiling, keyed on ID.

    The rounded column applies predict_2026's own 3-2-1 allocation: within each
    fixture the three highest expected-vote players take 3, 2 and 1. It answers
    "what does he collect if every game the model gives him lands", which is a
    different question from the p90 ceiling and is not a substitute for it.
    """
    g = d["game_2026"].copy()
    g["_k"] = (g.Round_num.astype(str) + "|" + g["Home.team"].astype(str)
               + "|" + g["Away.team"].astype(str))
    g = g.sort_values(["_k", "Exp_Votes", "Poll_Prob", "P_3", "Player_Name"],
                      ascending=[True, False, False, False, True])
    g["Hard"] = (g.groupby("_k").cumcount() + 1).map(
        {1: 3, 2: 2, 3: 1}).fillna(0)
    s = (g.groupby("ID").agg(name=("Player_Name", "first"),
                             raw_club=("Team", "first"),
                             games=("Round_num", "size"),
                             exp=("Exp_Votes", "sum"),
                             rounded=("Hard", "sum")).reset_index())
    s["ID"] = s.ID.astype(int)
    # The prediction file spells two clubs differently from the archive
    # ("Footscray", "GWS"). Unmapped, they match no club record and every
    # Bulldogs and Giants player drops out of the club tables silently, which is
    # the same failure that cost scraper_advanced 529 rows. Refuse instead.
    s["club"] = s.raw_club.map(canonical_club)
    bad = sorted(s.loc[~s.club.isin(KNOWN_CLUBS), "raw_club"].unique())
    if bad:
        raise SystemExit(f"2026 club label(s) not in the vote archive: {bad}")
    s = s.drop(columns=["raw_club"])
    pr = d["proj_2026"][["Player", "Floor_Projection", "Ceiling_Projection"]]
    s = s.merge(pr, left_on="name", right_on="Player", how="left")
    s["floor"] = s.Floor_Projection.fillna(0.0)
    # The displayed ceiling is max(p90, the 3-2-1 total); see CLAUDE.md. The CSV
    # carries raw p90, so the lift is applied here rather than read.
    s["ceiling"] = s[["Ceiling_Projection", "rounded"]].max(axis=1)
    return s.drop(columns=["Player", "Floor_Projection", "Ceiling_Projection"])


def build_2026(d, top=40):
    s = _scenarios(d).sort_values("exp", ascending=False)
    car = d["career"].set_index("ID")

    blocks = [(
        f"The model's {CUR_SEASON} board",
        f"""Four figures per player, and they answer four different questions.

        floor is the 10th percentile of a 10,000-run Monte Carlo over his
        completed games, expected is the sum of his per-game expected votes,
        rounded is what he collects if the top three of every game the model
        ranks him in all land as ranked, and ceiling is the 90th percentile
        lifted to at least the rounded total.

        Every figure is retrospective. It describes games already played, and no
        copy drawn from it may say a player is projected to poll anything in a
        game still to come.""",
        table(_rank(s.head(top)), ["rank", "name", "club", "games", "floor",
                                   "exp", "rounded", "ceiling"], floatfmt=1))]

    # ---- career milestones -------------------------------------------------
    rows = []
    for _, r in s.head(120).iterrows():
        if r.ID not in car.index:
            continue
        base = float(car.loc[r.ID, "votes"])
        for mk in MILESTONES:
            if base >= mk:
                continue
            need = mk - base
            if need <= r.ceiling:
                rows.append({"name": r["name"], "club": r.club,
                             "career_to_2025": base, "milestone": mk,
                             "needs": need, "expected": r.exp,
                             "rounded": r.rounded, "ceiling": r.ceiling,
                             "on_expected": "yes" if need <= r.exp else "",
                             "on_rounded": "yes" if need <= r.rounded else ""})
            break
    M = pd.DataFrame(rows).sort_values("needs")
    blocks.append((
        "Career vote milestones in reach on count night",
        """The next round number each player has not yet passed, and whether the
        season reaches it. Only the next one is listed: a player 3 votes short
        of 100 is not also chasing 150.

        career_to_2025 comes from the seam-joined all-time ladder, so it carries
        that ladder's caveats. on_expected means the expected total alone gets
        him there; on_rounded means the 3-2-1 allocation does.""",
        table(_rank(M), ["rank", "name", "club", "career_to_2025", "milestone",
                         "needs", "expected", "rounded", "ceiling",
                         "on_expected", "on_rounded"], floatfmt=1)))

    # ---- all-time ladder movement -----------------------------------------
    ladder = d["career"].sort_values("votes", ascending=False).reset_index(
        drop=True)
    ladder["pos"] = range(1, len(ladder) + 1)
    tot = ladder.votes.values
    mv = []
    for _, r in s.head(60).iterrows():
        if r.ID not in car.index:
            continue
        base = float(car.loc[r.ID, "votes"])
        now = int((tot > base).sum()) + 1
        after = {}
        for lbl, add in (("expected", r.exp), ("rounded", r.rounded),
                         ("ceiling", r.ceiling)):
            v = base + add
            # A rival active in 2026 is also moving; this holds rivals still, so
            # the projected position is a ceiling on the position, not a
            # forecast of it. Stated in the prose rather than modelled away.
            after[lbl] = int((tot > v).sum()) + 1
        mv.append({"name": r["name"], "club": r.club, "career_to_2025": base,
                   "pos_now": now, "pos_expected": after["expected"],
                   "pos_rounded": after["rounded"],
                   "pos_ceiling": after["ceiling"],
                   "places": now - after["expected"]})
    MV = pd.DataFrame(mv).sort_values("pos_expected")
    blocks.append((
        "Where the all-time career ladder moves",
        """Position on the 1924-2025 career ladder now, and after each 2026
        scenario is added.

        THE RIVALS ARE HELD STILL AND THAT MATTERS. Every other active player is
        also adding votes on the same night, so a projected position is the best
        case rather than the expected one. Dangerfield and Pendlebury are inside
        the top five and both played 2026. Read a row as "no worse than" rather
        than "will be".""",
        table(_rank(MV.head(40)), ["rank", "name", "club", "career_to_2025",
                                   "pos_now", "pos_expected", "pos_rounded",
                                   "pos_ceiling", "places"], floatfmt=1)))

    # ---- club records in reach --------------------------------------------
    g = d["games"]
    club_career = (g.groupby(["Club", "ID"]).Votes.sum()
                   .reset_index().sort_values("Votes", ascending=False))
    cc_best = club_career.groupby("Club", as_index=False).head(1).set_index(
        "Club")
    name_by_id = g.groupby("ID").Player_Name.first()
    mod = _modern_seasons(d)
    cs_best = (mod.sort_values("votes", ascending=False)
               .groupby("club", as_index=False).head(1).set_index("club"))

    club_for = g.groupby(["ID", "Club"]).Votes.sum()
    rows = []
    for _, r in s.head(120).iterrows():
        cl = r.club
        if cl not in cs_best.index:
            continue
        rec = float(cs_best.loc[cl, "votes"])
        holder = cs_best.loc[cl, "name"]
        rows.append({"name": r["name"], "club": cl, "club_season_record": rec,
                     "held_by": holder,
                     "in_season": int(cs_best.loc[cl, "Season"]),
                     "expected": r.exp, "rounded": r.rounded,
                     "ceiling": r.ceiling,
                     "gap_on_expected": rec - r.exp,
                     "gap_on_ceiling": rec - r.ceiling,
                     "complete": _club_complete(cl)})
    CS = pd.DataFrame(rows)
    # Within five of the record on the ceiling. A gap of exactly 0 is a TIE and
    # is why this is a gap column rather than a beats/does-not-beat flag: a
    # boolean would file "equals the record" under "does not", which is the
    # wrong side of the line for a count-night line.
    CS = CS[CS.gap_on_ceiling <= 5]
    blocks.append((
        "Club single-season records in reach",
        """The club record is the biggest season any player has had for that
        club SINCE 1984, which for a club older than the archive is not the
        club's actual record. The complete column says which is which; see
        clubs.md for the club-by-club ladders.

        Listed where the ceiling comes within five votes of the record. A gap
        column is NEGATIVE when the scenario clears the record and ZERO when it
        equals it.""",
        table(_rank(CS.sort_values("gap_on_expected")),
              ["rank", "name", "club", "expected", "rounded", "ceiling",
               "club_season_record", "held_by", "in_season", "gap_on_expected",
               "gap_on_ceiling", "complete"], floatfmt=1)))

    rows = []
    for _, r in s.head(150).iterrows():
        cl, pid = r.club, int(r.ID)
        if cl not in cc_best.index:
            continue
        rec = float(cc_best.loc[cl, "Votes"])
        holder = name_by_id.get(int(cc_best.loc[cl, "ID"]), "?")
        base = float(club_for.get((pid, cl), 0.0))
        his = int(cc_best.loc[cl, "ID"]) == pid
        rows.append({"name": r["name"], "club": cl, "for_club_to_2025": base,
                     "club_career_record": rec, "held_by": holder,
                     "already_his": "yes" if his else "",
                     "needs": rec - base + 1, "expected": r.exp,
                     "ceiling": r.ceiling,
                     "beats_on_expected": "yes" if base + r.exp > rec else "",
                     "beats_on_ceiling": "yes" if base + r.ceiling > rec else ""})
    CC = pd.DataFrame(rows)
    CC = CC[CC.needs <= CC.ceiling * 2].sort_values(["already_his", "needs"])
    blocks.append((
        "Club CAREER vote records in reach",
        """Votes for that club only, so a player who changed clubs starts again.
        Same 1984 truncation as elsewhere: for a club older than the archive the
        "record" is a since-1984 figure.

        THE already_his COLUMN SEPARATES TWO DIFFERENT STORIES. A blank row is a
        player taking the record off somebody. A "yes" row is the current holder
        extending his own, which needs 1 vote by definition and is not a record
        change at all: it is a line about how far clear he finishes. Sorted so
        the genuine changes come first.

        Listed where the gap is inside twice the player's ceiling, which keeps
        the near misses visible rather than only the certainties.""",
        table(_rank(CC.head(40)), ["rank", "name", "club", "for_club_to_2025",
                                   "club_career_record", "held_by",
                                   "already_his", "needs", "expected",
                                   "ceiling", "beats_on_expected",
                                   "beats_on_ceiling"], floatfmt=1)))

    # ---- season records in reach ------------------------------------------
    comp_best = mod[mod.Season.map(COMPARABLE)].sort_values(
        "votes", ascending=False).head(1).iloc[0]
    hi = float(comp_best.votes)
    S = s.head(20).copy()
    S["beats_alltime_on_expected"] = (S.exp > hi).map({True: "yes", False: ""})
    S["beats_alltime_on_ceiling"] = (S.ceiling > hi).map({True: "yes",
                                                          False: ""})
    blocks.append((
        "The all-time season record, and who is near it",
        f"""The highest single-season total on the modern scale is
        {hi:,.0f}, by {comp_best['name']} ({comp_best.club}) in
        {int(comp_best.Season)} from {int(comp_best.games)} games. See
        seasons.md for the full ladder and for why 1976 and 1977 are excluded
        from it.""",
        table(_rank(S), ["rank", "name", "club", "games", "floor", "exp",
                         "rounded", "ceiling", "beats_alltime_on_expected",
                         "beats_alltime_on_ceiling"], floatfmt=1)))

    # ---- round records in reach -------------------------------------------
    gm = d["games"]
    rc = (gm.groupby(["Round_disp", "ID"]).Votes.sum().reset_index())
    rc_best = rc.sort_values("Votes", ascending=False).groupby(
        "Round_disp", as_index=False).head(1)
    rc_best["holder"] = rc_best.ID.map(name_by_id)
    g26 = d["game_2026"].copy()
    g26["Round_disp"] = [display_round(r, CUR_SEASON) for r in g26.Round_num]
    cur_round = (g26.groupby(["Round_disp", "ID"])
                 .agg(name=("Player_Name", "first"), exp=("Exp_Votes", "sum"))
                 .reset_index())
    base_round = rc.rename(columns={"Votes": "career_in_round"})
    cur_round["ID"] = pd.to_numeric(cur_round.ID, errors="coerce")
    cur_round = cur_round[cur_round.ID.notna()]
    cur_round["ID"] = cur_round.ID.astype(int)
    cr = cur_round.merge(base_round, on=["Round_disp", "ID"], how="left")
    cr["career_in_round"] = cr.career_in_round.fillna(0.0)
    cr = cr.merge(rc_best[["Round_disp", "Votes", "holder"]].rename(
        columns={"Votes": "round_record"}), on="Round_disp", how="left")
    cr["after_expected"] = cr.career_in_round + cr.exp
    cr = cr[cr.after_expected >= cr.round_record - 3].sort_values(
        ["Round_disp", "after_expected"], ascending=[True, False])
    blocks.append((
        "Round-slot records within three votes",
        """A player's career votes in one round slot plus what the model expects
        him to add there this season, listed where the total comes within three
        of the slot record.

        Round-slot records are the softest claim in this pack. The slot a
        fixture lands in is scheduling, a bye removes a player from a slot
        entirely, and the 2024 renumbering means the AFL's Round 12 and
        AFLTables' are different rounds. Treat a hit here as a line to check
        rather than a record to announce.""",
        table(_rank(cr), ["rank", "Round_disp", "name", "career_in_round",
                          "exp", "after_expected", "round_record", "holder"],
              floatfmt=1).replace("| Round_disp |", "| Round |")))

    write("projections_2026", f"{CUR_SEASON} projections against the records",
          blocks)


# ---------------------------------------------------------------------------
# One briefing block per player on the board
# ---------------------------------------------------------------------------

def build_players(d, top=40):
    """A single block per projected top-40 player: every figure in one place.

    This is the file the night actually runs on. The other sections are ranked
    ladders, which answer "who holds it"; a name arrives instead, and the
    question is "what is the story on him". Assembling that from five ladders
    under time pressure is where a wrong figure gets read out, so it is
    assembled here once instead.
    """
    s = _scenarios(d).sort_values("exp", ascending=False)
    s = _rank(s.head(top))
    g = d["games"]
    mod = _modern_seasons(d)
    ladder = d["career"].sort_values("votes", ascending=False).reset_index(
        drop=True)
    tot = ladder.votes.values
    car = d["career"].set_index("ID")
    wr = with_result(d)

    club_career = g.groupby(["ID", "Club"]).Votes.sum()
    club_rank = (g.groupby(["Club", "ID"]).Votes.sum().reset_index()
                 .sort_values("Votes", ascending=False))
    club_rank["pos"] = club_rank.groupby("Club").cumcount() + 1
    club_rank = club_rank.set_index(["Club", "ID"])
    name_by_id = g.groupby("ID").Player_Name.first()
    cs_best = (mod.sort_values("votes", ascending=False)
               .groupby("club", as_index=False).head(1).set_index("club"))

    j, cover, _ = coaches_frame(d)
    # Keyed on the resolved NAME, not on ID: the 2026 coaches rows join to no
    # Brownlow row (those votes are not awarded yet), so they carry no ID.
    cur_cv_by_name = (j[j.Season == CUR_SEASON].groupby("player")
                      .agg(cv=("cv", "sum"),
                           tens=("cv", lambda x: (x == 10).sum())))
    cv_order = cur_cv_by_name.cv.rank(ascending=False, method="min")

    blocks = [(
        "How to read these",
        f"""One block per player on the model's projected top {top}, ordered by
        expected votes. Every figure is computed in this run from the same
        frames as the ladders in the other files, so a number here and the same
        number there cannot disagree.

        career_to_2025 and the all-time positions carry the 1984 seam's caveats
        (career.md). Club figures are since 1984 and for that club only
        (clubs.md). The 2026 coaches total is complete, all 207 games
        (coaches.md). Projections are retrospective and describe games already
        played.""", None)]

    for _, r in s.iterrows():
        pid = int(r.ID)
        rows = []

        rows.append(("2026 model", "games played", f"{int(r.games)}"))
        rows.append(("2026 model", "projected rank", f"{int(r['rank'])}"))
        for lbl in ("floor", "exp", "rounded", "ceiling"):
            rows.append(("2026 model", lbl, f"{float(r[lbl]):.1f}"))

        if r["name"] in cur_cv_by_name.index:
            c = cur_cv_by_name.loc[r["name"]]
            rows.append(("2026 coaches", "coaches votes",
                         f"{float(c.cv):.0f}"))
            rows.append(("2026 coaches", "rank",
                         f"{int(cv_order[r['name']])}"))
            rows.append(("2026 coaches", "10-vote games", f"{int(c.tens)}"))

        if pid in car.index:
            base = float(car.loc[pid, "votes"])
            pos = int((tot > base).sum()) + 1
            rows.append(("career", "votes to 2025", f"{base:.0f}"))
            rows.append(("career", "all-time position", f"{pos}"))
            for lbl in ("exp", "rounded", "ceiling"):
                v = base + float(r[lbl])
                rows.append(("career", f"position on {lbl}",
                             f"{int((tot > v).sum()) + 1} ({v:.0f} votes)"))
            nxt = next((m for m in MILESTONES if m > base), None)
            if nxt:
                rows.append(("career", "next milestone",
                             f"{nxt} ({nxt - base:.0f} away)"))
        else:
            rows.append(("career", "votes to 2025",
                         "0 - no vote before 2026"))

        own = g[g.ID == pid]
        if len(own):
            rows.append(("career", "H&A games 1984-2025",
                         f"{len(own)}"))
            rows.append(("career", "votes per game",
                         f"{own.Votes.sum() / len(own):.3f}"))
            rows.append(("career", "three-vote games",
                         f"{int((own.Votes == 3).sum())}"))
            rows.append(("career", "games polled",
                         f"{int((own.Votes > 0).sum())}"))
            lv = float(wr[(wr.ID == pid) & (wr.res == "L")].Votes.sum())
            rows.append(("career", "votes in losses", f"{lv:.0f}"))
            bs = mod[mod.ID == pid].sort_values("votes", ascending=False)
            if len(bs):
                b = bs.iloc[0]
                rows.append(("career", "best season",
                             f"{int(b.votes)} in {int(b.Season)} "
                             f"({b.club}, {int(b.games)} games)"))

        cl = r.club
        cfor = float(club_career.get((pid, cl), 0.0))
        rows.append((f"at {cl}", "votes for the club", f"{cfor:.0f}"))
        if (cl, pid) in club_rank.index:
            rows.append((f"at {cl}", "position at the club",
                         f"{int(club_rank.loc[(cl, pid), 'pos'])}"))
        if cl in cs_best.index:
            rows.append((f"at {cl}", "club season record",
                         f"{int(cs_best.loc[cl, 'votes'])} by "
                         f"{cs_best.loc[cl, 'name']} "
                         f"({int(cs_best.loc[cl, 'Season'])})"))
        top_club = club_rank.reset_index()
        top_club = top_club[top_club.Club == cl].iloc[0]
        rows.append((f"at {cl}", "club career record",
                     f"{int(top_club.Votes)} by "
                     f"{name_by_id.get(int(top_club.ID), '?')}"))
        rows.append((f"at {cl}", "1984 floor truncates the club",
                     "no" if _club_complete(cl) else "yes"))

        T = pd.DataFrame(rows, columns=["scope", "figure", "value"])
        blocks.append((f"{int(r['rank'])}. {r['name']} ({cl})", None,
                       table(T)))

    write("players", f"Player briefings, {CUR_SEASON} projected top {top}",
          blocks)


# ---------------------------------------------------------------------------
# Age
# ---------------------------------------------------------------------------

def _aged(d):
    """The 1984-2025 frame with Age attached, as a decimal year at match time.

    DOB is unusable here: it is null on 100% of the 1984-2006 archive and 82% of
    the modern file. Age is populated on every row of both, already computed by
    fitzRoy as years at the date of that match, so it is the column to use and
    the reason an age section is possible at all.
    """
    if "_aged" in d:
        return d["_aged"]
    cols = ["Season", "Round", "ID", "Age"]
    frames = []
    for path, lo in (("data_history/fitzroy_stats_1965_2006.csv.gz", 1984),
                     ("fitzroy_stats_all.csv", 2007)):
        f = pd.read_csv(path, low_memory=False, usecols=lambda c: c in cols)
        f["Season"] = pd.to_numeric(f["Season"], errors="coerce")
        f["Round_num"] = pd.to_numeric(f["Round"], errors="coerce")
        f = f[f.Season.notna() & f.Round_num.notna() & (f.Season >= lo)
              & f.ID.notna()]
        frames.append(f[["Season", "Round_num", "ID", "Age"]])
    a = pd.concat(frames, ignore_index=True)
    a["ID"] = a.ID.astype(int)
    a["Season"] = a.Season.astype(int)
    a["Round_num"] = a.Round_num.astype(int)
    a = a.drop_duplicates(["Season", "Round_num", "ID"])
    # A MISSING DOB ARRIVES AS Age == 0, NOT AS NaN, AND THAT IS THE WHOLE TRAP.
    # 888 rows across 1984-2022 carry it. notna() passes every one of them, so
    # an unguarded "youngest ever" list is a list of fictional newborns with the
    # real record nowhere on it. Coerced to NaN here, once, so no table
    # downstream has to remember. Anything under MIN_PLAUSIBLE_AGE goes the same
    # way: no VFL/AFL player has been that young, so it is corrupt rather than
    # remarkable.
    MIN_PLAUSIBLE_AGE = 15.0
    bad = int((a.Age < MIN_PLAUSIBLE_AGE).sum())
    a.loc[a.Age < MIN_PLAUSIBLE_AGE, "Age"] = pd.NA
    a["Age"] = pd.to_numeric(a["Age"], errors="coerce")
    m = d["games"].merge(a, on=["Season", "Round_num", "ID"], how="left")
    d["_aged"] = m
    d["_age_dropped"] = bad
    return m


def _yrs(v):
    """A decimal age to years and days, which is how an age record is quoted."""
    if pd.isna(v):
        return ""
    y = int(v)
    return f"{y}y {int(round((v - y) * 365.25))}d"


def build_age(d):
    g = _aged(d)
    miss = float(g.Age.isna().mean() * 100)
    dropped = d.get("_age_dropped", 0)
    blocks = [(
        "Where the age figures come from",
        f"""Age is fitzRoy's own column, decimal years at the date of the match,
        usable on {100 - miss:.1f}% of rows. DOB is not used and could not be:
        it is null on every row of the 1984-2006 archive and on most of the
        modern file.

        {dropped:,} rows carry Age as 0 rather than as missing, spread thinly
        across 1984-2022. They are a DOB the archive does not hold, and they are
        coerced to missing here. Left alone they pass a notna() test and sit at
        the top of every youngest-ever list as 0-year-olds, with the real record
        pushed off the table entirely.

        1984-2025 only, because every table here needs to know which game a vote
        came from. A player who debuted before 1984 has his early votes missing,
        so a "youngest to reach N career votes" row for such a career would be
        computed off a truncated total and is excluded rather than shown.""",
        None)]

    three = g[(g.Votes == 3) & g.Age.notna()].sort_values("Age")
    t = _rank(three.head(25).copy())
    t["age"] = t.Age.map(_yrs)
    blocks.append((
        "Youngest players to poll three votes in a game",
        """Best-on-ground from the umpires, at the age he was on the day.""",
        table(t, ["rank", "Player_Name", "age", "Club", "Season", "Round_num",
                  "Home.team", "Away.team"], floatfmt=0)))

    o = _rank(three.sort_values("Age", ascending=False).head(25).copy())
    o["age"] = o.Age.map(_yrs)
    blocks.append((
        "Oldest players to poll three votes in a game",
        None,
        table(o, ["rank", "Player_Name", "age", "Club", "Season", "Round_num",
                  "Home.team", "Away.team"], floatfmt=0)))

    sea = (g.groupby(["ID", "Season"])
           .agg(name=("Player_Name", "first"), club=("Club", "first"),
                votes=("Votes", "sum"), games=("Votes", "size"),
                age_end=("Age", "max")).reset_index())
    for thresh in (20, 25, 30):
        sub = sea[(sea.votes >= thresh) & sea.age_end.notna()]
        y = _rank(sub.sort_values("age_end").head(20).copy())
        y["age_at_season_end"] = y.age_end.map(_yrs)
        blocks.append((
            f"Youngest to poll {thresh} or more votes in a season",
            f"""Age is his age at his last home-and-away game of that season,
            which is the closest this data comes to "age at the count".
            {len(sub)} player-seasons since 1984 have reached {thresh}.""",
            table(y, ["rank", "name", "club", "Season", "votes", "games",
                      "age_at_season_end"], floatfmt=0)))

    teen = sea[sea.age_end < 20]
    tn = _rank(teen.sort_values("votes", ascending=False).head(25).copy())
    tn["age_at_season_end"] = tn.age_end.map(_yrs)
    blocks.append((
        "Most votes in a season by a player still a teenager at season's end",
        """Under 20 at his last home-and-away game of the season.""",
        table(tn, ["rank", "name", "club", "Season", "votes", "games",
                   "age_at_season_end"], floatfmt=0)))

    # ---- youngest to career milestones ------------------------------------
    firsts = g.groupby("ID").Season.min()
    safe = set(firsts[firsts >= 1985].index)
    gs = g[g.ID.isin(safe) & g.Age.notna()].sort_values(
        ["ID", "Season", "Round_num"]).copy()
    gs["cum"] = gs.groupby("ID").Votes.cumsum()
    rows = []
    for mk in (50, 100, 150, 200):
        hit = gs[gs.cum >= mk].groupby("ID").head(1)
        for _, r in hit.nsmallest(8, "Age").iterrows():
            rows.append({"milestone": mk, "name": r.Player_Name,
                         "club": r.Club, "age": _yrs(r.Age),
                         "Season": int(r.Season), "Round": int(r.Round_num)})
    A = pd.DataFrame(rows)
    blocks.append((
        "Youngest to reach each career vote milestone",
        """The game at which his running career total first reached the mark,
        and how old he was that day.

        Restricted to careers beginning in 1985 or later. A career that started
        before the 1984 archive is missing its early votes, so its milestone
        game would be dated too late and its age recorded too high, which puts a
        wrong name on a youngest-ever list rather than merely omitting one.""",
        table(A, ["milestone", "name", "club", "age", "Season", "Round"],
              floatfmt=0)))

    # ---- where 2026 would land --------------------------------------------
    s = _scenarios(d)
    g26 = d["game_2026"]
    age26 = (g26[g26.ID.notna()].assign(ID=lambda x: x.ID.astype(int))
             .groupby("ID").Age.max())
    s = s.join(age26, on="ID")
    cand = s[s.Age.notna() & (s.exp >= 12)].copy()
    out = []
    for _, r in cand.iterrows():
        for lbl in ("exp", "rounded", "ceiling"):
            v = float(r[lbl])
            for thresh in (20, 25, 30):
                if v < thresh:
                    continue
                younger = sea[(sea.votes >= thresh)
                              & (sea.age_end < r.Age)]
                out.append({"name": r["name"], "club": r.club,
                            "age_2026": _yrs(r.Age), "scenario": lbl,
                            "votes": v, "threshold": thresh,
                            "younger_ever": len(younger),
                            "would_rank": len(younger) + 1})
    O = pd.DataFrame(out)
    if len(O):
        O = O.sort_values(["would_rank", "threshold"])
    blocks.append((
        f"Where a {CUR_SEASON} season would sit on the youngest-ever lists",
        f"""For every player the model expects to reach 12 votes, how many
        players younger than him have ever reached 20, 25 and 30 in a season.
        would_rank of 1 means no player that young has ever done it since 1984.

        Age is his age at his last {CUR_SEASON} home-and-away game. Read a row
        as conditional on the scenario in the scenario column actually landing,
        not as a projection that it will.""",
        table(_rank(O.head(40)), ["rank", "name", "club", "age_2026",
                                  "scenario", "votes", "threshold",
                                  "younger_ever", "would_rank"], floatfmt=1)
        if len(O) else "No candidate reaches a threshold in any scenario."))

    write("age", "Age and vote records", blocks)


# ---------------------------------------------------------------------------
# Index, generated from the files that actually exist
# ---------------------------------------------------------------------------

FILE_NOTES = {
    "players": "One block per projected top-40 player. START HERE when a NAME "
               "arrives.",
    "projections_2026": "The 2026 board and every record it threatens. START "
                        "HERE when a RECORD question arrives.",
    "career": "All-time career ladders: total, rate, three-vote games, votes "
              "in losses, most without a medal.",
    "seasons": "Single-season ladders, the era trap, every medal since 1984 "
               "with its margin, and polling streaks.",
    "clubs": "Per-club career and season ladders, club-season aggregates, and "
             "which clubs the 1984 floor truncates.",
    "rounds": "Career votes by round slot. The 'most votes ever in Round 12' "
              "table.",
    "coaches": "AFLCA votes crossed with Brownlow votes, 2004-2026. The "
               "10-vote-no-poll set and the coaches-versus-umpires gaps.",
    "age": "Youngest and oldest to poll, youngest to each career milestone, "
           "and where a 2026 season would sit on those lists.",
}

QUESTION_MAP = [
    ("What is the story on <player>?", "players.md"),
    ("Who leads the model for 2026?", "projections_2026.md"),
    ("What is the all-time career vote record?", "career.md"),
    ("Who has the most career votes without a medal?", "career.md"),
    ("Best votes-per-game career?", "career.md"),
    ("Most three-vote games ever?", "career.md"),
    ("Most votes in losing sides?", "career.md"),
    ("Biggest season ever?", "seasons.md (read the era warning first)"),
    ("Highest total that did not win?", "seasons.md"),
    ("Tightest count ever?", "seasons.md"),
    ("Longest run of games polling?", "seasons.md"),
    ("Who holds <club>'s record?", "clubs.md"),
    ("Biggest club season by total votes?", "clubs.md"),
    ("Most votes ever in Round N?", "rounds.md"),
    ("Youngest ever to poll 3 votes / 20 in a season?", "age.md"),
    ("Youngest to 100 career votes?", "age.md"),
    ("Most coaches votes for fewest Brownlow votes?", "coaches.md"),
    ("Ten coaches votes and no Brownlow vote?", "coaches.md"),
    ("Three Brownlow votes and no coaches votes?", "coaches.md"),
    ("Who do the coaches rate that the umpires do not?", "coaches.md"),
    ("What records could fall tonight?", "projections_2026.md"),
    ("What milestones are in reach?", "projections_2026.md"),
    ("Where does <player> land on the all-time list?",
     "players.md, then projections_2026.md"),
]


def build_index(d):
    import glob
    import re
    out = os.path.join("drafts", "brownlow_night")
    blocks = [(
        "Question to file",
        """Straight lookup. Every figure in every file below was computed in one
        run from one load of the sources, so two files cannot disagree.""",
        table(pd.DataFrame(QUESTION_MAP, columns=["question", "file"])))]

    rows = []
    for p in sorted(glob.glob(os.path.join(out, "*.md"))):
        name = os.path.splitext(os.path.basename(p))[0]
        if name == "INDEX":
            continue
        txt = open(p, encoding="utf-8").read()
        heads = re.findall(r"^## (.+)$", txt, flags=re.M)
        rows.append({"file": f"{name}.md", "sections": len(heads),
                     "lines": txt.count("\n") + 1,
                     "what it is": FILE_NOTES.get(name, "")})
    blocks.append((
        "The files",
        None,
        table(pd.DataFrame(rows))))

    for p in sorted(glob.glob(os.path.join(out, "*.md"))):
        name = os.path.splitext(os.path.basename(p))[0]
        if name in ("INDEX", "players"):
            continue
        txt = open(p, encoding="utf-8").read()
        heads = re.findall(r"^## (.+)$", txt, flags=re.M)
        blocks.append((f"{name}.md sections", None,
                       "\n".join(f"- {h}" for h in heads)))

    ppath = os.path.join(out, "players.md")
    if os.path.exists(ppath):
        heads = re.findall(r"^## (.+)$", open(ppath, encoding="utf-8").read(),
                           flags=re.M)
        blocks.append((
            "players.md blocks",
            "Grep this file for a surname to jump straight to his block.",
            "\n".join(f"- {h}" for h in heads if h[0].isdigit())))

    blocks.append((
        "Standing cautions, in the order they bite",
        """1. SEASON TOTALS ACROSS ERAS. 1976 and 1977 doubled the vote pool
        (two umpires each awarding 3-2-1) and 1924-1930 awarded a single vote
        per game. A naive all-time season ladder is topped by two seasons that
        do not belong on it. seasons.md prints the comparable ladder second and
        that is the one to quote.

        2. THE 1984 FLOOR. Per-game votes start in 1984, so every club, round
        and opponent record here is a since-1984 record. Only career and season
        totals reach 1924. Clubs older than the archive are marked truncated.

        3. THE COACHES ARCHIVE IS SHORT IN 2023, 2024 AND 2025 (91-95% of
        games). Game-level coaches claims are safe; season totals from those
        years are floors.

        4. RIVALS MOVE TOO. A projected all-time position holds every other
        active player still, so it is a best case rather than a forecast.

        5. NO MAE FIGURE, NO ACCURACY PERCENTAGE. Unresolved in the repo; see
        project_brief.md. Nothing in this pack supplies one.

        6. EXP_VOTES IS RETROSPECTIVE. It describes games already played. No
        copy may say a player is projected to poll in a game still to come.

        7. ROUND-SLOT RECORDS ARE THE SOFTEST CLAIM HERE. Scheduling, byes and
        the 2024 renumbering all move a fixture between slots.""",
        None))

    write("INDEX", "Brownlow night research pack", blocks)
