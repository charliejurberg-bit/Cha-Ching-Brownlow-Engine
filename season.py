"""season.py — the one place the live season is set.

    LIVE_SEASON = 2026        change this line to roll the whole pipeline over

Every script in the weekly chain (update.py and everything it runs) and the
dashboard's live-season logic read the season from here, so a new season is one
edit plus the values in SEASONS below that only become known during it. Before
this file existed "2026" was written into about a dozen scripts separately.

`BROWNLOW_SEASON=2027 python predict_2026.py` overrides it for one run, which is
how a rollover is rehearsed without touching the site.

ROLLOVER, in order (python season_rollover.py <new season> checks each one):
  1. The old season's count is saved: data_<old>/brownlow_votes_<old>.csv
     (scripts/fetch_brownlow_votes.py, which refuses a partial count).
  2. python season_rollover.py <new> --apply backfills those votes into
     predictions/game_level_<old>.csv and season_<old>.csv, which the dashboard
     reads as history. Until then the old season's file still reads 0 votes.
  3. python stack.py train, so the vote model has seen the old season.
  4. Set LIVE_SEASON below and fill SEASONS[<new>].

Values set to None are unknown until the season is under way. Code that needs
one refuses or falls back and says which, rather than borrowing last season's.
"""

import os

_REPO = os.path.dirname(os.path.abspath(__file__))

LIVE_SEASON = int(os.environ.get("BROWNLOW_SEASON", "2027"))

SEASONS = {
    2026: {
        # AFLTables' raw H&A Round_num count: Opening Round is raw round 1, so
        # 24 official rounds plus Opening Round is 25. predict_2026.py used 23
        # here, the games-per-club figure, against a raw round number, which
        # understated the rounds remaining by two all season.
        "raw_rounds": 25,
        "games": 207,                       # 18 clubs x 23 / 2
        "count_night": "2026-09-21",
        "espn_slug": "afl-2026-brownlow-medal-predictor-tracker-leaderboard-odds-every-vote",
        # fitzRoy's coaches feed stopped at raw round 23 and rounds 24-25 were
        # hand-transcribed, so a refetch would delete them. See CLAUDE.md.
        "coaches_fetch": False,
    },
    2027: {
        "raw_rounds": None,                 # from the 2027 fixture
        "games": None,
        "count_night": None,                # announced mid-season
        "espn_slug": None,                  # ESPN publishes a new article each year
        "coaches_fetch": True,              # fetch_coaches_season.R, guarded
    },
}


def cfg(season=None):
    season = LIVE_SEASON if season is None else season
    if season not in SEASONS:
        raise SystemExit(f"season.py has no entry for {season}; add one to SEASONS")
    return SEASONS[season]


def counted(season):
    """True once `season`'s Brownlow count is saved (scripts/fetch_brownlow_votes.py
    refuses a partial one, so the file existing means the count is complete)."""
    return os.path.exists(os.path.join(_REPO, data_path("brownlow_votes_{s}.csv", season)))


def current_season():
    """The season the public site leads with: LIVE_SEASON once it has
    predictions, otherwise the latest season that does.

    Between a rollover and the new season's first predicted round, LIVE_SEASON
    has nothing to show, and every default page would otherwise open on an
    empty season. The weekly chain keeps reading LIVE_SEASON; only the site's
    defaults read this."""
    for s in range(LIVE_SEASON, LIVE_SEASON - 5, -1):
        if os.path.exists(os.path.join(_REPO, pred_path("game_level_{s}.csv", s))):
            return s
    return LIVE_SEASON


def data_dir(season=None):
    return f"data_{LIVE_SEASON if season is None else season}"


def data_path(name, season=None):
    """data_<season>/<name>, with {s} in `name` replaced by the season. Forward
    slashes, as every path in this repo was written, so a path that ends up in a
    printed message or a cache key reads exactly as it did before."""
    season = LIVE_SEASON if season is None else season
    return f"{data_dir(season)}/{name.format(s=season)}"


def pred_path(name, season=None):
    """predictions/<name>, with {s} replaced by the season."""
    season = LIVE_SEASON if season is None else season
    return f"predictions/{name.format(s=season)}"
