"""season_rollover.py — move the whole pipeline from one season to the next.

    python season_rollover.py 2027            # check everything, change nothing
    python season_rollover.py 2027 --apply    # do it

--apply does, in order, and stops at the first failure:
  1. Backfills the finished season's actual votes, from
     data_<old>/brownlow_votes_<old>.csv, into predictions/game_level_<old>.csv
     (Brownlow.Votes) and predictions/season_<old>.csv (Actual_Votes). Until
     then the finished season reads 0 votes everywhere, because those files were
     written as live predictions, and the moment LIVE_SEASON moves past it the
     dashboard reads it as history: every player would show as never polling.
  2. Retrains stack.py on every counted season, so the vote model has seen the
     finished season and applies to the new one.
  3. Sets LIVE_SEASON in season.py.

Nothing here posts, pushes or commits. The files it writes are all tracked, so
`git diff` shows exactly what it did and `git checkout` undoes it.

What it cannot do, and prints as a checklist: the values in season.SEASONS for
the new season that only exist once the season does (the fixture's round and
game counts, the count-night date, ESPN's tracker article).
"""

import argparse
import os
import re
import sys

import pandas as pd

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)
import season as season_cfg  # noqa: E402

KEY = ["Round_num", "Home.team", "Away.team", "Player_Name", "Playing.for"]


def _p(*parts):
    return os.path.join(REPO, *parts)


def check_votes(old):
    """The finished season's count: present, complete, and joinable."""
    vf = _p(f"data_{old}", f"brownlow_votes_{old}.csv")
    if not os.path.exists(vf):
        return None, [f"no {os.path.relpath(vf, REPO)}: run "
                      f"python scripts/fetch_brownlow_votes.py {old} after the count"]
    v = pd.read_csv(vf)
    problems = []
    per_game = v.groupby(["Round_num", "Home.team", "Away.team"])["Brownlow.Votes"].sum()
    games = season_cfg.cfg(old)["games"]
    if (per_game != 6).any():
        problems.append(f"{int((per_game != 6).sum())} game(s) in the count do not total 6")
    if games and len(per_game) != games:
        problems.append(f"the count holds {len(per_game)} games, season.py says {games}")
    return v, problems


def backfill(old, v, apply):
    gl_path = _p("predictions", f"game_level_{old}.csv")
    se_path = _p("predictions", f"season_{old}.csv")
    gl = pd.read_csv(gl_path, low_memory=False)
    m = gl.merge(v[KEY + ["Brownlow.Votes"]].rename(columns={"Brownlow.Votes": "_v"}),
                 on=KEY, how="left", validate="many_to_one")
    if len(m) != len(gl):
        raise SystemExit("the vote join changed the row count; refusing")
    # Every vote-getter must land on a row, or votes vanish from history.
    landed = m["_v"].notna().groupby([m.Round_num, m["Home.team"], m["Away.team"]]).sum()
    got = int(m["_v"].fillna(0).sum())
    want = int(v["Brownlow.Votes"].sum())
    # The file can hold a player twice in one game (CLAUDE.md, 78 rows of 2025),
    # and a left join then counts his votes twice. Measured on the unique rows.
    uniq = m.drop_duplicates(KEY)
    if int(uniq["_v"].fillna(0).sum()) != want:
        raise SystemExit(f"only {int(uniq['_v'].fillna(0).sum())} of {want} votes found a row "
                         f"in {os.path.relpath(gl_path, REPO)}; refusing")
    before = float(pd.to_numeric(gl["Brownlow.Votes"], errors="coerce").fillna(0).sum())
    print(f"  game_level_{old}.csv: Brownlow.Votes {before:.0f} -> {int(uniq['_v'].fillna(0).sum())} "
          f"across {len(landed)} games")
    se = pd.read_csv(se_path)
    tot = uniq.groupby("Player_Name")["_v"].sum()
    if apply:
        gl["Brownlow.Votes"] = m["_v"].fillna(0).values
        gl.to_csv(gl_path, index=False)
        se["Actual_Votes"] = se.Player_Name.map(tot).fillna(0)
        se.to_csv(se_path, index=False)
    print(f"  season_{old}.csv: Actual_Votes set for {int((se.Player_Name.map(tot).fillna(0) > 0).sum())} players")


def set_live(new):
    p = _p("season.py")
    s = open(p, encoding="utf-8").read()
    s2, n = re.subn(r'LIVE_SEASON = int\(os\.environ\.get\("BROWNLOW_SEASON", "\d{4}"\)\)',
                    f'LIVE_SEASON = int(os.environ.get("BROWNLOW_SEASON", "{new}"))', s)
    if n != 1:
        raise SystemExit("could not find the LIVE_SEASON line in season.py")
    open(p, "w", encoding="utf-8").write(s2)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("new", type=int)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    new, old = a.new, a.new - 1
    print(f"Rollover {old} -> {new} ({'APPLY' if a.apply else 'check only'})")
    if new not in season_cfg.SEASONS:
        raise SystemExit(f"season.py has no SEASONS[{new}]; add it first")

    v, problems = check_votes(old)
    for pr in problems:
        print(f"  ! {pr}")
    if problems:
        raise SystemExit("fix the above first")

    print(f"1. backfill {old}'s count")
    backfill(old, v, a.apply)

    import stack
    obj = stack.load()
    through = obj["trained_through"] if obj else None
    print(f"2. stack.pkl trained through {through}")
    if a.apply and (through is None or through < old):
        stack.train(weight_latest=1.0)

    print(f"3. LIVE_SEASON {season_cfg.LIVE_SEASON} -> {new}")
    if a.apply:
        set_live(new)

    missing = [k for k, val in season_cfg.cfg(new).items() if val is None]
    print(f"\nStill to fill in season.SEASONS[{new}] when known: {', '.join(missing) or 'nothing'}")
    print("  raw_rounds / games   from the fixture; the projection and count_night.py use them")
    print("  count_night          landing_summary.py will not write site/landing.json without it")
    print("  espn_slug            scraper_espn.py skips until it is set")
    if a.apply:
        print("\nDone. Review with git diff, then commit and push.")
    else:
        print("\nNothing changed. Re-run with --apply.")


if __name__ == "__main__":
    main()
