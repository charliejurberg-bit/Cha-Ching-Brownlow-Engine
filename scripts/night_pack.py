"""Brownlow night research pack. Every vote record this repo can source, precomputed.

    python scripts/night_pack.py              # build everything into drafts/brownlow_night/
    python scripts/night_pack.py career club  # build only the named sections
    python scripts/night_pack.py --list       # what sections exist

WHAT THIS IS FOR
On count night the questions arrive faster than a query can be written. This
builds the answers ahead of time as ranked markdown tables under
drafts/brownlow_night/, one file per topic plus an INDEX.md, so the answer to
"who holds the club record" is a grep rather than a load of a 69 MB CSV.

RECON OUTPUT, NOT POST-READY. Every table here is research material. A claim
drawn from one still needs the copy rules in project_brief.md applied to it.

THE FOUR SOURCES, AND WHERE EACH ONE STOPS
  per-game votes      1984-2025   all_time_tables.load_frame(), ID-keyed
  season totals       1924-1983   data_history/brownlow_seasons_1924_1983.csv
  coaches votes       2004-2026   coaches_votes_all.csv + data_2026/
  2026 projections    2026        predictions/season_2026.csv and friends

The 1984 boundary is fitzRoy's own coverage, not a fetch range: Brownlow.Votes
is all-null on all 100,560 rows of 1965-1983. See CLAUDE.md, "Brownlow votes
before 1984". So every per-game, per-club, per-round and per-opponent record
here is capped at 1984 and says so in its own header. Only career and season
TOTALS reach 1924, because a season total carries no game attribution.

THE ERA TRAP THAT SITS ON TOP OF EVERY ALL-TIME SEASON RECORD
Season vote totals are not comparable across the whole 1924-2025 span, and the
Vote_system column in the pre-1984 file does not tell you so:

  1924-1930  ONE vote per game to one player. A 1924 season of 7 is 7 games won.
  1931-1975  3-2-1, one umpire. 6 votes per game.
  1976-1977  3-2-1 from EACH OF TWO field umpires. 12 votes per game.
  1978-      3-2-1, back to 6 votes per game.

The 1976-77 doubling is measured here rather than recalled: those two seasons
award exactly 1,512 votes each against 792 in every neighbouring season, a
clean 2x. The file labels both "3-2-1" like any other season, so a naive
all-time season ladder returns Graham Teasdale's 59 (1977) and Graham Moss'
48 (1976) at the top and neither is comparable to a modern total. ERA_OF() and
the `system` column on every season table exist to stop that claim shipping.

Season LENGTH is the second half of the same problem and is handled the same
way: a 17-round 2020 and a 22-round 1983 are different denominators, so the
season tables carry games and votes-per-game beside the total.

WHY THE CAREER LADDER IS IMPORTED AND NOT REBUILT
vote_milestones.career_table() already solves the 1984 seam: pre-1984 totals
carry a name and no fitzRoy ID, so they attach only where exactly ONE modern
career owns the name and reaches the boundary. That is what keeps Gary Ablett
senior's votes off junior's total. A second implementation of that join is a
second chance to get it wrong.
"""

import importlib.util
import os
import pickle
import sys
import textwrap

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import all_time_tables as att            # noqa: E402

OUT_DIR = os.path.join("drafts", "brownlow_night")
CACHE = os.path.join(os.environ.get("TEMP", "/tmp"), "night_pack_cache.pkl")

PRE_FILE = "data_history/brownlow_seasons_1924_1983.csv"
COACHES_ALL = "coaches_votes_all.csv"
COACHES_CUR = "data_2026/coaches_votes_2026.csv"
CUR_SEASON = 2026
OPENING_ROUND_FROM = 2024      # AFLTables numbers Opening Round as Round 1

# Seasons whose vote pool is double every other season's: two field umpires
# each awarding 3-2-1. Measured, not recalled - see the module docstring.
TWO_UMPIRE = (1976, 1977)
SINGLE_VOTE_TO = 1930


def ERA_OF(season):
    """The scoring system in force, as a short label safe to put in a table."""
    s = int(season)
    if s <= SINGLE_VOTE_TO:
        return "1-vote"
    if s in TWO_UMPIRE:
        return "3-2-1 x2"
    return "3-2-1"


def COMPARABLE(season):
    """True where a season total sits on the same scale as a modern one."""
    return int(season) > SINGLE_VOTE_TO and int(season) not in TWO_UMPIRE


def display_round(round_num, season):
    """AFLTables Round_num to the AFL's own round number. Opening Round is 0."""
    try:
        rn, sn = int(round_num), int(season)
    except (TypeError, ValueError):
        return round_num
    return rn - 1 if sn >= OPENING_ROUND_FROM else rn


def _vote_milestones():
    """scripts/vote_milestones.py, imported by path so the name cannot collide."""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "vote_milestones.py")
    spec = importlib.util.spec_from_file_location("_vm", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def load(refresh=False):
    """Every source this pack reads, loaded once and cached to the scratchpad.

    The cache is a convenience for iterating on the builders, not a data store:
    it lives outside the repo, and refresh=True rebuilds it. Nothing downstream
    may assume it exists.
    """
    if not refresh and os.path.exists(CACHE):
        with open(CACHE, "rb") as fh:
            return pickle.load(fh)

    d = {}
    df, prov = att.load_frame()
    df["Round_disp"] = [display_round(r, s)
                        for r, s in zip(df.Round_num, df.Season)]
    d["games"], d["prov"] = df, prov

    pre = pd.read_csv(PRE_FILE)
    pre["system"] = pre.Season.map(ERA_OF)
    d["pre"] = pre

    vm = _vote_milestones()
    car, amb = vm.career_table(vm.modern())
    d["career"], d["career_ambiguous"] = car, amb

    d["season_2026"] = pd.read_csv("predictions/season_2026.csv")
    d["proj_2026"] = pd.read_csv("predictions/season_projection_2026.csv")
    gl = pd.read_csv("predictions/game_level_2026.csv", low_memory=False)
    # game_level carries exactly-duplicated rows (89 in 2026); see CLAUDE.md.
    d["game_2026"] = gl.drop_duplicates(["Round_num", "ID"], keep="first")

    with open(CACHE, "wb") as fh:
        pickle.dump(d, fh)
    return d


def fixtures(d):
    """One row per 1984-2025 fixture with both scores, cached on the load dict.

    Read separately rather than by widening load_frame's usecols, because a
    score is a property of the FIXTURE and not of the player-row: 320,857
    player-rows carry 7,413 scorelines between them. Reading at fixture grain
    and merging costs one dedupe; widening load_frame costs a second full pass
    over a 69 MB file for every consumer that does not need scores.
    """
    if "_fixtures" in d:
        return d["_fixtures"]
    cols = ["Season", "Round", "Home.team", "Away.team",
            "Home.score", "Away.score"]
    frames = []
    for path, lo in (("data_history/fitzroy_stats_1965_2006.csv.gz", 1984),
                     ("fitzroy_stats_all.csv", 2007)):
        f = pd.read_csv(path, low_memory=False, usecols=lambda c: c in cols)
        f["Season"] = pd.to_numeric(f["Season"], errors="coerce")
        f["Round_num"] = pd.to_numeric(f["Round"], errors="coerce")
        f = f[f.Season.notna() & f.Round_num.notna() & (f.Season >= lo)]
        frames.append(f.drop(columns=["Round"]))
    fx = pd.concat(frames, ignore_index=True).drop_duplicates(
        ["Season", "Round_num", "Home.team", "Away.team"])
    fx["Season"] = fx.Season.astype(int)
    fx["Round_num"] = fx.Round_num.astype(int)
    d["_fixtures"] = fx
    return fx


def with_result(d):
    """The games frame plus res (W/L/D) and Margin on every player-row.

    Refuses on a missing score rather than filling one. A NaN margin compares
    false against both > 0 and < 0, so an unguarded fill would silently file
    every unmatched row as a draw and quietly shrink the loss ladder.
    """
    if "_with_result" in d:
        return d["_with_result"]
    m = d["games"].merge(fixtures(d),
                         on=["Season", "Round_num", "Home.team", "Away.team"],
                         how="left", validate="many_to_one")
    if m["Home.score"].isna().any():
        n = int(m["Home.score"].isna().sum())
        raise SystemExit(f"{n:,} player-rows found no fixture score")
    home = m["Playing.for"] == m["Home.team"]
    diff = (m["Home.score"] - m["Away.score"]).where(
        home, m["Away.score"] - m["Home.score"])
    m["Margin"] = diff
    m["res"] = pd.Series("D", index=m.index).where(
        diff == 0, pd.Series("W", index=m.index).where(diff > 0, "L"))
    d["_with_result"] = m
    return m


# Columns that are identifiers rather than quantities. A thousands separator on
# a year turns 1977 into "1,977", which reads as a number nobody recognises.
YEARLIKE = {"Season", "in_season", "first", "last", "from", "to", "year",
            "Round", "Round_num", "Round_disp", "rank", "milestone"}


def table(df, cols=None, floatfmt=2):
    """A DataFrame to a markdown table. Numbers formatted, never truncated.

    A float column whose values are all whole is printed without decimals. Vote
    counts arrive as floats because the pre-1984 and modern halves concatenate
    through a float column, and "59.00 votes" is a figure no reader would use.
    A column with a genuine fraction anywhere keeps its decimals throughout, so
    a rate never loses precision to a tidy neighbour.
    """
    if cols:
        df = df[cols]
    out = df.copy()
    for c in out.columns:
        if c in YEARLIKE:
            out[c] = out[c].map(
                lambda v: "" if pd.isna(v) else f"{v:.0f}"
                if isinstance(v, float) else str(v))
        elif pd.api.types.is_float_dtype(out[c]):
            whole = out[c].dropna().mod(1).eq(0).all()
            fmt = 0 if whole else floatfmt
            out[c] = out[c].map(
                lambda v: "" if pd.isna(v) else f"{v:,.{fmt}f}")
        elif pd.api.types.is_integer_dtype(out[c]):
            out[c] = out[c].map(lambda v: f"{v:,}")
    head = "| " + " | ".join(str(c) for c in out.columns) + " |"
    rule = "|" + "|".join("---" for _ in out.columns) + "|"
    body = ["| " + " | ".join(str(v) for v in row) + " |"
            for row in out.itertuples(index=False)]
    return "\n".join([head, rule] + body)


def wrap(text):
    """Prose to 78 columns, paragraph by paragraph."""
    return "\n\n".join(textwrap.fill(" ".join(p.split()), 78)
                       for p in text.strip().split("\n\n"))


def write(name, title, blocks):
    """One topic file. `blocks` is a list of (heading, prose, markdown) triples."""
    os.makedirs(OUT_DIR, exist_ok=True)
    lines = [f"# {title}", ""]
    for heading, prose, md in blocks:
        if heading:
            lines += [f"## {heading}", ""]
        if prose:
            lines += [wrap(prose), ""]
        if md:
            lines += [md, ""]
    path = os.path.join(OUT_DIR, f"{name}.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines).rstrip() + "\n")
    print(f"  wrote {path}")
    return path


def main(argv):
    import night_sections as sec

    order = [("career", sec.build_career), ("seasons", sec.build_seasons),
             ("clubs", sec.build_clubs), ("rounds", sec.build_rounds),
             ("coaches", sec.build_coaches), ("age", sec.build_age),
             ("projections", sec.build_2026), ("players", sec.build_players)]
    names = [n for n, _ in order]

    args = [a for a in argv if not a.startswith("-")]
    refresh = "--refresh" in argv
    if "--list" in argv:
        print("sections: " + ", ".join(names) + ", index")
        return 0
    want = args or names
    unknown = [a for a in want if a not in names]
    if unknown:
        print(f"unknown section(s): {unknown}. Known: {names}")
        return 2

    print("loading sources...")
    d = load(refresh=refresh)
    for name, fn in order:
        if name in want:
            print(f"{name}:")
            fn(d)
    # The index reads the files on disk, so it is rebuilt whenever any section
    # is, and never claims a section that was not written this run.
    print("index:")
    sec.build_index(d)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
