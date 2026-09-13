"""Count-night tweet drafts: the moments, as the votes are read out.

    python scripts/count_tweets.py --dry-run --round 12     # refine the copy NOW
    python scripts/count_tweets.py --dry-run --round all    # every round, then the end
    python scripts/count_tweets.py --dry-run --round final  # the end-of-count posts alone
    python scripts/count_tweets.py --live                   # on the night

WHAT THIS IS
The count reads a round, this returns whatever about it is worth posting, and
nothing when nothing is. Templated, never generated: the same decision
draft_posts.py made and for the same reason, which is that a templated post
cannot invent an accuracy claim under time pressure.

Every format rule here comes from draft_formats_spec.md and is not re-litigated:
280 characters with the domain counted as 23, no em dashes, no padding or column
alignment because Twitter renders proportional and any alignment dies on paste,
rows self-describing with single spaces, "exp" rather than "projected votes",
and no accuracy percentage anywhere. Every post is standalone, so each carries
the link and the two hashtags project_brief.md gives a non-match post.

NO ROUND RECAP. THE POSTS ARE THE MOMENTS
There is deliberately no per-round leaderboard, best-on-ground or model-calls
post: the board is on the site all night and a recap of it every round is 75
posts nobody reads. What goes out instead is what changed, and only when it
does: a club or league record approached or taken, a career milestone crossed,
and the games where the player everyone had on top polled nothing. Most rounds
produce one post or none.

EVERY THRESHOLD HERE WAS MEASURED ON REAL VOTES, NOT CHOSEN
The snub post is the clearest case. Every looser version fires far too often to
post: since 2015 a player with 10 coaches votes has polled under 3 about 38
times a season, and 9-or-10 about 78. SNUB (the model's first pick, at least
SNUB_MIN_COACHES coaches votes, no Brownlow vote, and ahead of the three-vote
getter on BOTH disposals and coaches votes) fired 3, 10, 9 and 8 times across
2022 to 2025, about one every three rounds. The club-record bands were picked
the same way: 3 and 1 gives five posts across a count where a 5 gives twelve.

THE DRY RUN CANNOT SHOW THE SNUB POSTS, AND THAT IS NOT A FAULT IN THEM
--dry-run stands the AFL's predictor in for the count, and the predictor rarely
disagrees with the coaches, so the snub test almost never fires on it. Judge
that block's copy against a real season instead; every other block the dry run
shows in full.

PLAYERS ARE THE FEED'S IDS, JOINED TO OURS ON NAME AND CLUB
The award feed and game_level_2026.csv spell players differently: De Goey and de
Goey, Matthew and Matt Carroll, "Bailey J. Williams" and "Bailey Williams (West
Coast)". Matched on the raw name, those players could never be a model call and
always read as zero career votes, and nothing said so. The feed also carries two
Max Kings, whose votes a name key adds together. So votes are keyed by the feed's
own player id and printed under the feed's spelling, the one the broadcast reads
out, and each feed player is joined to game_level through
features.resolve_feed_names on name and club. Career votes then come off the
fitzRoy ID, never off a name. A polled player the join cannot place is printed
above the drafts rather than dropped.

A ROUND IS DRAFTED WHEN IT IS FINISHED, NOT WHEN IT STARTS
The count is read out game by game, and the feed may fill the same way. Drafting
a round as soon as its first vote appeared would post a round off one game of
nine. A round is finished when it holds 6 votes for every game played in it, or
once a later round has begun, since the count reads rounds in order. The second
test covers a feed that leaves out an ineligible player's votes, which would
stop a round ever reaching its full total.

END-OF-COUNT POSTS
Held until every round is finished, because each is a claim about the whole
season that one more round could overturn: the medal itself, three Brownlow
votes with no coaches votes, ten coaches votes with no Brownlow vote, and the
most coaches votes by a player the umpires never voted for. Coaches votes come
off game_level_2026, where all 207 games total exactly 30. That is what makes a
zero there a real zero rather than a failed join, and a game that stops
totalling 30 is left out and reported. The three crossover posts refuse while
any polled player is unjoined, because "no Brownlow votes" and "not matched"
would read the same. A list too long for 280 splits into numbered posts rather
than losing names: these go out once, as the record of the season.
"""

import argparse
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import count_sim                                          # noqa: E402
import night_pack as npk                                   # noqa: E402
import night_sections as ns                                # noqa: E402
from club_aliases import canonical_club                    # noqa: E402
from features import normalise_name, resolve_feed_names    # noqa: E402
from night_sections import MILESTONES, _modern_seasons     # noqa: E402

SITE_URL = "chachingbrownlow.com"
DOMAIN_COST = 23          # Twitter counts any link as 23 characters
# X Premium is on the account for the night, so a post is no longer capped at
# 280. Kept well under the Premium ceiling anyway: past roughly this length a
# post is collapsed behind "Show more" in the timeline, which in a thread costs
# more than splitting would. Blocks still trim themselves against it.
TWEET_MAX = 600
# --watch poll cadence. 60s against a count that reads a round every five or six
# minutes, matching the Live Tracker's own ttl. A pass costs one feed read and
# one pack load off a warm cache, so the loop is idle most of the interval.
WATCH_INTERVAL = 60
# One definition, so --watch and --last cannot end up reading different files.
DEFAULT_WATCH_LOG = os.path.join("drafts", "count_night_tweets.txt")
# How often --watch says it is still alive while nothing is changing, so a quiet
# terminal is distinguishable from a dead one without burying the drafts.
HEARTBEAT_EVERY = 600
# A --watch heartbeat line, so --last can strip them back out. They are the
# watcher reporting on itself and are noise in an answer to "what do I post".
_HEARTBEAT = re.compile(r"^\[\d{2}:\d{2}:\d{2}\] ")

# Set by watch() to its timestamped say(). Everything that is not a draft goes
# through _note, so under --watch it lands as a heartbeat line and --last strips
# it; under the single-shot modes it prints exactly as it always has.
#
# THE REASON IS A REHEARSAL, NOT TIDINESS. These lines are written between one
# round's last tweet and the next round's banner, so in the log they sit INSIDE
# the draft they follow. No parser separates them from tweet text by position,
# and what --last handed back was a post with
# "2026 Toyota AFL Premiership: COUNTING. partial: 216 of 1,242 votes" on the
# end of it. On a phone that is one careless copy away from being posted.
_WATCH_SAY = None


def _note(msg):
    """A diagnostic, never a draft."""
    if _WATCH_SAY is not None:
        _WATCH_SAY(msg.strip())
    else:
        print(msg)
BOARD_ROWS = 4            # names under the medallist on the final board
LEADER_ROWS = 5
LEADER_ROWS_MAX = 7       # a tie straddling the cut is shown whole up to this
RECORD_BANDS = (10, 5, 1)  # gaps to the league season record that speak
CLUB_BANDS = (3, 1)       # and to a club season record, measured: see the top
SNUB_MIN_COACHES = 8      # measured: see the module docstring
SNUB_GOALS_SHOWN = 2      # show goals only when one of the two kicked this many
FIRST_VOTE_MIN_GAMES = 65    # the 90th percentile of every first vote since 1985
FIRST_VOTE_RANK_MENTION = 25  # name the wait only this near the top of that list
VOTE_GAP_MIN = 75         # games between two votes before it is worth saying
VOTE_GAP_RANK_MENTION = 10   # name the position only this near the top
VOTE_GAP_FROM = 1984      # the per-game vote archive starts here
FIRST_VOTE_FROM = 1985    # careers that start inside the per-game archive
NUMBER_WORD = {2: "two", 3: "three"}
ACTIVE_FROM = 2020        # vote_milestones' own test for "the active one"
VOTES_PER_GAME = 6        # 3-2-1 from the umpires, every game
VALID_POINTS = (1, 2, 3)  # what a Brownlow vote can be worth. See vote_entries
COACHES_PER_GAME = 30     # 5-4-3-2-1 from each of two coaches, see CLAUDE.md
CLUB_CAREER_FROM = 1984   # the per-game archive's floor, see club_records
FINAL_HEAD = "Count complete."
HASHTAGS = "#AFL #Brownlow"   # project_brief.md's pair for a non-match post

# Where a post goes. The night runs as one thread carrying everything as it
# happens, because a thread is one item in a follower's timeline and volume
# inside it is close to free. Two things break out as their own post: the medal,
# and the all-time season record actually falling. A reply buried twenty deep
# gets a fraction of a standalone post's reach, and those two are the posts
# people share. Everything at the end of the count is standalone for the same
# reason. A thread reply carries no link and no hashtags; the thread's first and
# last posts carry them once.
THREAD, STANDALONE = "thread", "standalone"
WATCH_EVERY = 4           # rounds between leader-watch posts
BOLTER_MIN_VOTES = 2      # dashboard.py's Live Tracker rule, kept identical so
BOLTER_MODEL_MAX = 0.8    #   a bolter in a tweet is a bolter on the site
PERF_MIN_GAMES = 10       # games before a season over/underperformance counts
PERF_ROWS = 5
DIVERGENCE_MIN_VOTES = 8  # Brownlow votes before a rank gap means anything
FIRST_VOTE_STATS = 3      # stats shown beside a first career vote

# STAT_LABELS are plural because a stat line almost always carries more than
# one of a thing. "1 goals" is the exception that shows up the moment goals are
# guaranteed a place in the line, and it reads like a bug to anyone who sees it.
_SINGULAR = {"score involvements": "score involvement",
             "contested possessions": "contested possession"}


def _pick_stats(ranked, limit=None):
    """The stats to show beside a game, from the full percentile-ranked list.

    Three rules, and they are in tension, so the order they resolve in is the
    whole of this function.

      HARD CAP at FIRST_VOTE_STATS. A stat line is a clause in a sentence, not
        a box score. Appending a fourth for goals read as padding.
      GOALS ARE ALWAYS IN when he kicked one. Percentile judges a goal against
        the other twenty-one in the match, so in a game where three forwards
        kicked three, the man who kicked one ranks below marks and loses the
        only stat a reader wants said out loud.
      DISPOSALS LEAD when they are shown. The headline stat of the game reads
        first or the line reads like it is burying it.

    Goals displace the weakest OTHER stat rather than disposals, which is what
    keeps "28 disposals, 8 tackles, 1 goal" instead of dropping the 28 to make
    room. Everything after disposals stays in percentile order, so goals land
    where they were earned: first for a five-goal game, last for one.
    """
    limit = FIRST_VOTE_STATS if limit is None else limit
    goal = next(((lab, v) for lab, v in ranked if lab == "goals"), None)
    window = list(ranked[:limit])
    if goal and goal not in window:
        # Drop the weakest that is not disposals, then re-sort below.
        others = [x for x in window if x[0] != "disposals"]
        if others:
            window.remove(others[-1])
        else:
            window = window[:limit - 1]
        window.append(goal)
    # Percentile order is the order they came in; restore it, then lead with
    # disposals if they survived the cut.
    order = {lab: i for i, (lab, _) in enumerate(ranked)}
    window.sort(key=lambda x: order.get(x[0], 99))
    disp = next((x for x in window if x[0] == "disposals"), None)
    if disp:
        window = [disp] + [x for x in window if x[0] != "disposals"]
    return window[:limit]


def _stat_txt(lab, v):
    """One stat, agreeing in number."""
    if float(v) == 1:
        lab = _SINGULAR.get(lab, lab[:-1] if lab.endswith("s") else lab)
    return f"{v:g} {lab}"
WATCH_ROWS = 4            # players shown in the leader watch
WATCH_MIN_CHANCE = 0.01   # and the chance below which one is not worth a row
WATCH_MIN_ROWS = 3        # but never fewer than this many
CAREER_RANK_MAX = 100     # an all-time position worth printing
SNUB_STATS = 3            # and beside each half of a snub. Settled, do not trim
# The pool a first vote's stat line is chosen from, each shown as the label
# beside it. Picked by where the player ranked in his own game rather than by a
# fixed order, so a ruck's game reads as a ruck's game. Score involvements are
# the REAL stat from score_involvements.csv, never features.py's engineered
# column of the same name; CLAUDE.md explains why that must never reach a reader.
STAT_LABELS = [
    ("Disposals", "disposals"), ("Score_Involvements_Actual", "score involvements"),
    ("Clearances", "clearances"), ("Contested.Possessions", "contested possessions"),
    ("Tackles", "tackles"), ("Marks", "marks"), ("Goals", "goals"),
    ("Intercepts", "intercepts"),
]
DIVERGENCE_ROWS = 4
BOLTER_ROWS = 4

# chachingbrownlow.com is the front door, not the app, and its "Open Live
# Tracker" button is the reader's route to the count. The front door carries no
# all-time lists, the Live Tracker shows a top ten rather than every vote, and
# the app's Leaderboard shows the model's projections rather than the count. So
# the line names the one page the count is on, in as few characters as it takes.
LINK_LINE = f"Live Tracker at {SITE_URL}"

# The award feed's teamId, in game_level's club spelling. Measured against
# /teams for the 2026 compseason rather than fetched on the night: one fewer
# request to fail mid-count. An id missing here maps to None, and its players
# surface as unmatched rather than being guessed.
FEED_CLUBS = {
    1: "Adelaide", 2: "Brisbane Lions", 3: "Collingwood", 4: "Gold Coast",
    5: "Carlton", 6: "North Melbourne", 7: "Port Adelaide",
    8: "Western Bulldogs", 9: "Hawthorn", 10: "Geelong", 11: "St Kilda",
    12: "Essendon", 13: "Sydney", 14: "Fremantle",
    15: "Greater Western Sydney", 16: "Richmond", 17: "Melbourne",
    18: "West Coast",
}

# game_level's same-name suffix, as in "Bailey Williams (West Coast)". Club does
# that job inside the join, so the suffix comes off before it.
_SUFFIX_RE = re.compile(r"\s*\([^()]*\)$")

# The model's 3-2-1 reading of a game, by expectation rank.
_HARD_BY_RANK = {1: 3, 2: 2, 3: 1}


def _len(text):
    """Twitter's count: the domain costs 23 whatever its real length."""
    return len(text) - len(SITE_URL) + DOMAIN_COST if SITE_URL in text \
        else len(text)


def _fits(text):
    return _len(text) <= TWEET_MAX


def _close(lines, where):
    """A post finished the way its destination needs.

    A thread reply ends at its last row: the link and the hashtags belong on
    the thread's first and last posts, not on every reply. A standalone post is
    read on its own and carries both. Every block builds through here, so each
    trims against the space its own destination leaves.
    """
    tail = ["", LINK_LINE, HASHTAGS] if where == STANDALONE else []
    return "\n".join(lines + tail)


def _post(lines):
    """A finished standalone post."""
    return _close(lines, STANDALONE)


def thread_start():
    """The post the night hangs off. Hashtags, no link."""
    return "\n".join([
        f"The {npk.CUR_SEASON} Brownlow count.",
        "Every record, milestone and first vote as the votes are read, plus "
        "the games the coaches and the umpires saw differently.",
        "", HASHTAGS])


def thread_end():
    """The thread's last post, and the only one in it carrying the link."""
    return f"That's the {npk.CUR_SEASON} count. Every vote on the {LINK_LINE}"


def _round_label(rd):
    return "Opening Round" if int(rd) == 0 else f"Round {int(rd)}"


def _rounds_phrase(rds):
    """[18] Round 18, [4, 15] Rounds 4 and 15, [0, 15] Opening Round and Round 15."""
    rds = sorted({int(r) for r in rds})
    nums = [str(r) for r in rds if r]
    parts = ["Opening Round"] if 0 in rds else []
    if len(nums) == 1:
        parts.append(f"Round {nums[0]}")
    elif nums:
        parts.append("Rounds " + ", ".join(nums[:-1]) + " and " + nums[-1])
    return (" and ".join(parts) if len(parts) < 2 or len(nums) == 1
            else ", ".join(parts))


def _cut_with_ties(order, n, n_max):
    """The first n of a ranked list, never cutting through a tie.

    order is [(key, value), ...] best first. Returns (shown, tail). A tie
    straddling row n is kept whole while that stays within n_max rows, and is
    otherwise left out of shown and handed back as tail = (count, value), for
    one line in place of the names, because alphabetical order should not be
    what decides who is named and who is not.
    """
    shown, tail = order[:n], None
    if len(order) > n and order[n][1] == order[n - 1][1]:
        cut = order[n - 1][1]
        above = [kv for kv in order if kv[1] > cut]
        tied = [kv for kv in order if kv[1] == cut]
        if len(above) + len(tied) <= n_max:
            shown = above + tied
        else:
            shown, tail = above, (len(tied), cut)
    return shown, tail


# ---------------------------------------------------------------------------
# Vote sources
# ---------------------------------------------------------------------------

def vote_entries(players):
    """(round, pid, points, match id) for every real vote in a payload.

    A vote is worth 1, 2 or 3 and sits under a numeric round key. Nothing a
    healthy feed serves breaks either rule, which is the reason to enforce
    them: a single entry reading 99 points fired an all-time season record
    claim in testing, and a record post is the last place a feed glitch should
    be able to reach. Whatever this skips is counted and reported by
    build_context rather than passed on.
    """
    for p in players:
        for rkey, entries in (p.get("rounds") or {}).items():
            if not str(rkey).lstrip("-").isdigit():
                continue
            for e in entries or ():
                if e.get("points") in VALID_POINTS:
                    yield int(rkey), p["id"], int(e["points"]), e.get("providerId")


def rejected_entries(players):
    """How many vote-bearing entries vote_entries refused, and why."""
    bad = 0
    for p in players:
        for rkey, entries in (p.get("rounds") or {}).items():
            for e in entries or ():
                pts = e.get("points", 0)
                if pts and (pts not in VALID_POINTS
                            or not str(rkey).lstrip("-").isdigit()):
                    bad += 1
    return bad


def votes_from_feed(players):
    """{display_round: {pid: points}} from an award-API payload.

    Keyed by the feed's player id, never by name: the 2026 feed carries two Max
    Kings, and a name key adds one's votes to the other's.
    """
    out = {}
    for rd, pid, pts, _ in vote_entries(players):
        out.setdefault(rd, {})[pid] = pts
    return dict(sorted(out.items()))


def totals_through(by_round, upto):
    """Cumulative totals through and including `upto`, as the count stands."""
    tot = {}
    for rd, votes in by_round.items():
        if rd <= upto:
            for pid, pts in votes.items():
                tot[pid] = tot.get(pid, 0) + pts
    return tot


def games_per_round(d):
    """{display_round: games played}, off game_level_2026's fixtures."""
    g = d["game_2026"]
    key = g["Home.team"].astype(str) + "|" + g["Away.team"].astype(str)
    return key.groupby(g.Round_num - 1).nunique().astype(int).to_dict()


def matches_from_feed(players):
    """{display_round: {match id}}, the games whose votes have been read.

    Every vote-bearing entry carries the AFL's own match id: measured at 621 of
    621, the entries without one being the 7,253 that carry no points. The set
    per round matches game_level's fixture count for all 25 rounds of 2026,
    which is a free cross-check of our fixture list against the AFL's.
    """
    out = {}
    for rd, _, _, mid in vote_entries(players):
        if mid:
            out.setdefault(rd, set()).add(mid)
    return out


def finished_rounds(by_match, gpr):
    """Rounds whose reading is over. See the module docstring.

    Finished when every game in the round has been read, or once a later round
    has begun, since the count reads rounds in order. A round that passes
    neither is being read right now, and drafting it would post part of a round
    as the whole of it.

    COUNTING GAMES, NOT VOTES, IS WHAT MAKES THE LAST ROUND SAFE. Summing points
    and testing against 6 per game leaves a round short forever if the feed
    leaves any vote out, and "a later round has begun" cannot rescue the final
    round because there is no later round. The count would then never read as
    complete and the end-of-count posts would never be written. A game is read
    out 3-2-1 together, so its id appearing at all is the honest signal.
    """
    latest = max(by_match, default=-1)
    return {rd for rd, n in gpr.items()
            if rd in by_match and (len(by_match[rd]) == n or rd < latest)}


def _best_season(rows):
    """The top row of [(votes, holder, season, holder_id), ...], ties broken.

    Highest total, then the EARLIEST season, then the name. A tie is real (two
    players have held Fitzroy's 26 since 1931) and without the second and third
    keys the holder printed depends on the order pandas happened to sort in,
    which makes the same record read two ways on two runs.
    """
    return min(rows, key=lambda r: (-r[0], r[2], r[1]))


def league_season_record(d):
    """The highest COMPARABLE season total any player has had, 1924 on.

    BOTH ERAS, because the post says "all-time". _modern_seasons stops at 1984
    and reading the record off it alone is the same mistake the club records
    made: it happens to be right today only because Patrick Cripps' 45 clears
    the best comparable pre-1984 season (Des Fothergill's 32 in 1940), and it
    would silently understate the record the moment that stopped being true.

    COMPARABLE drops the 1924-1930 one-vote era and the 1976-77 seasons that
    ran two field umpires and twice the vote pool. That is what keeps Graham
    Teasdale's 59 in 1977 out of a record it is not comparable to.
    """
    mod = _modern_seasons(d)
    mod = mod[mod.Season.map(npk.COMPARABLE)]
    rows = [(int(r.votes), r["name"], int(r.Season), int(r.ID))
            for _, r in mod.sort_values("votes", ascending=False).head(5).iterrows()]
    pre = d["pre"]
    pre = pre[pre.Season.map(npk.COMPARABLE)]
    rows += [(int(r.Votes), r.Player, int(r.Season), None)
             for _, r in pre.sort_values("Votes", ascending=False).head(5).iterrows()]
    return _best_season(rows)


def club_records(d):
    """(season_rec, career_rec, career_base, complete_clubs).

    season_rec[club] = (votes, holder, season, holder_id), the best season any
    player has had for that club across every COMPARABLE season, 1924 on.
    holder_id is the fitzRoy ID where the record is modern and None where it
    predates the archive, which is what lets a caller tell "his own record"
    from "somebody else's" by identity rather than by name.

    THE PRE-1984 FILE DOES CARRY A CLUB, WHICH night_sections SAYS IT DOES NOT.
    7,508 of its 7,551 rows name exactly one club; the other 43 name two, space
    separated ("Richmond South Melbourne"), for a player who changed clubs that
    season, and are dropped because his total belongs to neither. Reading the
    record off 1984 onward alone gets two clubs wrong in 2026: North Melbourne's
    is Keith Greig's 27 in the 1970s, not Brent Harvey's 22, and Sydney's is
    Herbie Matthews' 32 in 1940, not Isaac Heeney's 28. COMPARABLE keeps the
    one-vote era and the two-umpire seasons out of both sides.

    career_rec[club] = (votes, holder, holder id) counts votes FOR THAT CLUB and
    starts at CLUB_CAREER_FROM, the per-game archive's floor, so for an older
    club it is a since-1984 figure and the post says so. complete_clubs is
    night_sections' own list of the clubs whose whole history is inside it.
    """
    hist = d["games"]
    cs = (hist.groupby(["Club", "Season", "ID"])
          .agg(name=("Player_Name", "first"), votes=("Votes", "sum"))
          .reset_index())
    cand = {}
    for _, r in cs.iterrows():
        cand.setdefault(r.Club, []).append(
            (int(r.votes), r["name"], int(r.Season), int(r.ID)))

    pre = d["pre"].assign(club=lambda x: x.Teams.map(canonical_club))
    pre = pre[pre.club.isin(set(hist.Club.unique()))
              & pre.Season.map(npk.COMPARABLE)]
    for _, r in pre.iterrows():
        cand.setdefault(r.club, []).append(
            (int(r.Votes), r.Player, int(r.Season), None))
    season_rec = {club: _best_season(rows) for club, rows in cand.items()}

    cc = (hist.groupby(["Club", "ID"])
          .agg(name=("Player_Name", "first"), votes=("Votes", "sum"))
          .reset_index())
    career_rec = {r.Club: (int(r.votes), r["name"], int(r.ID))
                  for _, r in cc.sort_values("votes", ascending=False)
                  .groupby("Club").head(1).iterrows()}
    career_base = {(r.Club, int(r.ID)): float(r.votes) for _, r in cc.iterrows()}
    return season_rec, career_rec, career_base, set(ns._complete_clubs())


def build_roster(players, polled, d):
    """Who each feed player is on our side.

    Returns (roster, game_to_pid, warnings). roster[pid] holds:
      name      the feed's spelling, which is what every post prints
      game      game_level's Player_Name, or None where the join failed
      base      career votes to 2025 for a polled player, or None where that
                cannot be known (and for every player who has not polled)
      polled    whether the player has a vote in the feed
      eligible  the feed's own flag. 26 players are ineligible in 2026 and
                their votes are still read out, so the medal is the highest
                ELIGIBLE total, not the highest.

    Every feed player is joined, not only those who polled, because the
    end-of-count posts name players the umpires never voted for and they should
    print under the same spelling as everyone else. Polled players go through a
    pass of their own with the resolver's report printed, since they are the
    ones whose failure to join changes a post, and only they raise warnings.
    """
    g = d["game_2026"]
    tgt = g[["Player_Name", "Playing.for"]].drop_duplicates().copy()
    tgt["_base"] = tgt.Player_Name.str.replace(_SUFFIX_RE, "", regex=True)
    by_club = {(b, c): n for b, c, n in
               zip(tgt._base, tgt["Playing.for"], tgt.Player_Name)}
    by_base = tgt.groupby("_base").Player_Name.unique()

    def resolve(rows, verbose, label):
        feed = pd.DataFrame(rows, columns=["pid", "name", "club", "eligible"])
        feed["shown"] = feed["name"]
        if feed.empty:
            return feed
        out, _ = resolve_feed_names(feed, tgt, "name", "club", None,
                                    target_name_col="_base", label=label,
                                    verbose=verbose)
        return out

    rows = [(p["id"], f"{p.get('firstName', '')} {p.get('surname', '')}".strip(),
             FEED_CLUBS.get(p.get("teamId")), bool(p.get("eligible", True)))
            for p in players]
    feed = pd.concat(
        # verbose off under --watch: the same summary every 60 seconds, written
        # into the draft stream. A name that cannot be placed is reported
        # separately and still reaches the log.
        [resolve([r for r in rows if r[0] in polled],
                 _WATCH_SAY is None, "award feed"),
         resolve([r for r in rows if r[0] not in polled], False, "unpolled")],
        ignore_index=True)

    # An unknown teamId arrives here as NaN, not None, so test with isna.
    feed["no_club"] = feed.club.isna()
    feed["polled"] = feed.pid.isin(polled)
    # Name alone ONLY when the club is unknown. A known club without this name
    # is a different player: Sydney's Max King is not St Kilda's, and a
    # name-only fallback handed him the St Kilda one's career.
    feed["game"] = [
        (by_base[n][0] if len(by_base.get(n, [])) == 1 else None) if nc
        else by_club.get((n, c))
        for n, c, nc in zip(feed.name, feed.club, feed.no_club)]
    visible = feed[feed.polled | feed.game.notna()]
    n_shown = visible.shown.value_counts()

    ids = pd.to_numeric(g.ID, errors="coerce").groupby(g.Player_Name).max()
    car = d["career"]
    modern = car[car.ID > 0]           # pre-1984 careers carry negative ids
    by_id = dict(zip(modern.ID.astype(int), modern.votes.astype(float)))
    active = modern[modern["last"] >= ACTIVE_FROM]
    active_norm = active.name.map(normalise_name)

    roster, warnings = {}, []
    junk = rejected_entries(players)
    if junk:
        warnings.append(f"{junk} vote entries in the feed are not 1, 2 or 3 "
                        f"points under a numeric round, and were ignored")
    stray = sorted(set(FEED_CLUBS.values()) - set(tgt["Playing.for"]))
    if stray:
        warnings.append(f"FEED_CLUBS names {stray}, which game_level does not "
                        f"use, so those clubs' players join on name alone")
    for r in feed.itertuples(index=False):
        game = None if pd.isna(r.game) else r.game
        shown = (f"{r.shown} ({r.club})"
                 if n_shown.get(r.shown, 0) > 1 and not r.no_club else r.shown)
        base, cid = None, None
        if r.polled and game is None:
            if r.no_club:
                who = f"{shown} (club unknown)"
            elif shown.endswith(f"({r.club})"):
                who = shown
            else:
                who = f"{shown} ({r.club})"
            warnings.append(f"{who} is not in game_level_2026, so the record "
                            f"and milestone posts cannot see them")
        elif r.polled and pd.notna(ids.get(game)):
            cid = int(ids[game])
            base = by_id.get(cid, 0.0)              # no row: first votes ever
        elif r.polled:
            # fitzRoy returns no ID for a dozen 2026 players, Jack Ross and
            # Charlie Cameron among them. Fall back to the name only where one
            # active modern career owns it, vote_milestones' own test, which is
            # what keeps a pre-1984 namesake's votes off. The id it finds is
            # kept, because the career games behind a first vote need it too.
            hit = active[active_norm == normalise_name(r.name)]
            if len(hit) == 1:
                cid, base = int(hit.ID.iloc[0]), float(hit.votes.iloc[0])
            elif len(hit) == 0:
                base = 0.0
            else:
                warnings.append(f"{shown} has no ID and {len(hit)} active "
                                f"careers share the name, so milestones skip "
                                f"them")
        roster[r.pid] = {"name": shown, "game": game, "base": base, "cid": cid,
                         "polled": bool(r.polled), "eligible": bool(r.eligible)}

    # One feed player per game_level name. A polled player outranks unpolled
    # namesakes, since he is certainly the one who played; two polled players
    # on one name cannot be separated, and the game posts skip it.
    owners = {}
    for pid, info in roster.items():
        if info["game"]:
            owners.setdefault(info["game"], []).append(pid)
    game_to_pid = {}
    for game, pids in owners.items():
        live = [p for p in pids if roster[p]["polled"]] or pids
        if len(live) == 1:
            game_to_pid[game] = live[0]
        elif roster[live[0]]["polled"]:
            warnings.append(f"{len(live)} polled feed players joined onto "
                            f"{game}, so the game posts skip that name")
    return roster, game_to_pid, warnings


def _disp(ctx, game):
    """A game_level name as the posts print it: the feed's spelling if joined."""
    pid = ctx["game_to_pid"].get(game)
    return ctx["roster"][pid]["name"] if pid is not None else game


def _record_band(gap, bands):
    """How near a total sits to a record. Lower is nearer.

    -2 past it, -1 level, then one step per band from the tightest out, and
    None while still outside the widest. A post fires when a round moves a
    player into a nearer band, never on the band he is already in, which is
    what stops "has broken the record" posting again every round after it.
    """
    if gap < 0:
        return -2
    if gap == 0:
        return -1
    for i, b in enumerate(sorted(bands)):
        if gap <= b:
            return i
    return None


def _poss(name):
    """Possessive: Geelong's, but Western Bulldogs' and Nathan Jones'.

    Two of the eighteen clubs end in s, and so do plenty of surnames, so this
    is not a rare case: the club season record post read "Western Bulldogs's".
    """
    return f"{name}'" if name.endswith("s") else f"{name}'s"


def _ordinal(n):
    """117 -> 117th. The teens are all th, including 111th and 113th."""
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


_GAMES_CACHE = {}


def _round_order(r):
    """A sortable position for a round label, finals after the home and away.

    Finals carry letters, and a player's game number at the moment of a vote
    has to count the ones he has already played. Their order inside a season is
    fixed: qualifying and elimination, then semi, then preliminary, then grand.
    """
    t = str(r).strip().upper()
    if t.isdigit():
        return int(t)
    return {"QF": 90, "EF": 90, "SF": 91, "PF": 92, "GF": 93}.get(t, 89)


def all_games_played():
    """{fitzRoy ID: sorted (season, round order)} for every game, finals included.

    The vote archive is home and away only, which is right for votes and wrong
    for a career game number: a reader counts finals. Both stats archives carry
    them, so the count comes from there. 1965 onward, which covers every career
    that could reach a 2026 vote several times over.
    """
    if "games" in _GAMES_CACHE:
        return _GAMES_CACHE["games"]
    frames = []
    for path in ("data_history/fitzroy_stats_1965_2006.csv.gz",
                 "fitzroy_stats_all.csv"):
        if os.path.exists(path):
            f = pd.read_csv(path, usecols=["Season", "Round", "ID"],
                            low_memory=False)
            frames.append(f)
    a = pd.concat(frames, ignore_index=True)
    a = a[pd.to_numeric(a.ID, errors="coerce").notna()]
    a["ID"] = a.ID.astype(int)
    a["_ord"] = a.Round.map(_round_order)
    a = a.drop_duplicates(["ID", "Season", "_ord"])
    out = {i: sorted(zip(g.Season, g._ord)) for i, g in a.groupby("ID")}
    _GAMES_CACHE["games"] = out
    return out


def career_game_number(cid, season, round_ord, played_2026=None):
    """Which game of his career this one was, finals included, at that moment.

    Counts everything up to and including the game in question and nothing
    after it, which is what makes the number stable: a final played later in
    the same September cannot change what his 100th game was.
    """
    games = all_games_played().get(int(cid), [])
    n = sum(1 for s, o in games if (s, o) < (season, round_ord))
    if played_2026 is not None and season == npk.CUR_SEASON:
        n += sum(1 for r in played_2026 if r < round_ord)
    return n + 1


def wait_ladder():
    """Games played before a first Brownlow vote, every career from 1985.

    On the SAME basis as the number the post prints, finals included. Computed
    off the vote archive for when the first vote landed and the stats archives
    for how many games preceded it, because no single file carries both.
    """
    if "waits" in _GAMES_CACHE:
        return _GAMES_CACHE["waits"]
    d = npk.load()
    v = d["games"]
    first = (v[v.Votes > 0].sort_values(["Season", "Round_num"])
             .groupby("ID").first()[["Season", "Round_num", "Player_Name"]])
    games = all_games_played()
    rows = []
    for cid, r in first.iterrows():
        played = games.get(int(cid))
        if not played or played[0][0] < FIRST_VOTE_FROM:
            continue                # career opens before the archive can see it
        rows.append((r.Player_Name, int(r.Season),
                     career_game_number(cid, int(r.Season), int(r.Round_num))))
    rows.sort(key=lambda x: -x[2])
    _GAMES_CACHE["waits"] = rows
    return rows


def first_vote_history(d):
    """(waits, record): how long every player waited for his first vote.

    waits is one number per player, games played before he first polled, and
    record is (name, games, season) at the top of it. Careers starting before
    FIRST_VOTE_FROM are left out: the per-game archive opens in 1984, so a
    player already playing by then has games it cannot see and his wait would
    read short.

    GAMES ARE HOME AND AWAY GAMES. That is what the archive holds (23 a club in
    2025) and it is the right denominator anyway, since no Brownlow vote has
    ever been awarded in a final. A reader counting a player's games on
    afl.com.au will see a bigger number, so the post says which it is.
    """
    h = d["games"].sort_values(["ID", "Season", "Round_num"])
    opened = h.groupby("ID").Season.min()
    h = h[h.ID.isin(opened[opened >= FIRST_VOTE_FROM].index)].copy()
    h["_gn"] = h.groupby("ID").cumcount() + 1
    fv = h[h.Votes > 0].groupby("ID").first()
    waits = fv["_gn"].sort_values(ascending=False)
    top = fv.loc[waits.index[0]]
    return waits.to_numpy(), (top.Player_Name, int(top["_gn"]), int(top.Season))


# ---------------------------------------------------------------------------
# The blocks. Each takes (rs, ctx) and returns a list of posts, often empty.
# ---------------------------------------------------------------------------

def block_league_record(rs, ctx):
    """The all-time season record coming into range, as a line for the round.

    Speaks only on the round that moves the best total into a nearer band:
    within 10, within 5, within 1. The record actually being equalled or broken
    is not this block; it is the post of the night after the medal and breaks
    out of the thread on its own.
    """
    rec, holder, yr, _ = ctx["league_season_rec"]
    if not rs["totals"]:
        return []
    best = max(rs["totals"].values())
    prev_best = max(rs["prev"].values()) if rs["prev"] else 0
    now_b = _record_band(rec - best, RECORD_BANDS)
    prev_b = _record_band(rec - prev_best, RECORD_BANDS)
    gap = rec - best
    if now_b is None or gap <= 0 or (prev_b is not None and now_b >= prev_b):
        return []
    who = " and ".join(sorted(ctx["roster"][p]["name"]
                              for p, v in rs["totals"].items() if v == best))
    return [f"{who} on {best:.0f}, {gap:.0f} from the all-time season record "
            f"of {rec:.0f}, {holder} in {yr}."]


def block_record_taken(rs, ctx, where):
    """The all-time season record equalled or broken. Its own post, always."""
    rec, holder, yr, _ = ctx["league_season_rec"]
    if not rs["totals"]:
        return []
    best = max(rs["totals"].values())
    prev_best = max(rs["prev"].values()) if rs["prev"] else 0
    if rec - best > 0:                      # not taken yet
        return []
    now_b = _record_band(rec - best, RECORD_BANDS)
    prev_b = _record_band(rec - prev_best, RECORD_BANDS)
    if now_b is None or (prev_b is not None and now_b >= prev_b):
        return []                           # already said, on an earlier round
    who = " and ".join(sorted(ctx["roster"][p]["name"]
                              for p, v in rs["totals"].items() if v == best))
    many = " and " in who
    if rec == best:
        line = (f"{who} {'have' if many else 'has'} equalled the all-time "
                f"season record.")
        held = f"{best:.0f} votes. The record is {rec:.0f}, {holder} in {yr}."
    else:
        line = (f"{who} {'have' if many else 'has'} broken the all-time "
                f"season record.")
        held = (f"{best:.0f} votes. The previous record was {rec:.0f}, "
                f"{holder} in {yr}.")
    text = _close([f"{_round_label(rs['rd'])} counted.", "", line, held], where)
    return [text] if _fits(text) else []


def block_leader_watch(rs, ctx, where):
    """Where the race stands every WATCH_EVERY rounds, with the chance of winning.

    THE ONE PLACE THIS SYSTEM LOOKS FORWARD, AND IT IS BACKTESTED BEFORE IT DOES.
    project_brief.md forbids forward-looking vote claims. Count night is the
    case the rule was not written for: every game is played and every vote
    already exists, so a figure for an unread round describes a result rather
    than predicting a match.

    The chance of winning comes from count_sim, which holds the votes read as
    fixed and samples the rounds still to come from the model's own per-game
    probabilities, so a player's number answers for every rival's draw as well
    as his own. Its dispersion was chosen by replaying 18 completed seasons at
    89 checkpoints: it tells the leader 64.9% in spots he goes on to win 66.3%
    of. An undispersed version says 71% for the same spots, which is the
    overconfidence this had to be calibrated away from.

    Two chances can add to more than 100%. A tied count shares the medal, both
    men win one, and the excess is exactly the probability of that tie.
    """
    rd = rs["rd"]
    if rd == 0 or rd % WATCH_EVERY or not rs["totals"]:
        return []
    chance, projected = ctx["chances"](rd)
    if not chance:
        return []
    best = max(rs["totals"].values())
    leaders = sorted((ctx["roster"][p]["name"]
                      for p, v in rs["totals"].items() if v == best))
    left = sum(1 for r in ctx["all_rounds"] if r > rd)
    lines = [f"Leader watch, after {_round_label(rd).lower()}.", "",
             f"{' and '.join(leaders)} "
             f"{'lead' if len(leaders) > 1 else 'leads'} on {best}."]

    ranked = [(g, c) for g, c in
              sorted(chance.items(), key=lambda kv: -kv[1])[:WATCH_ROWS]
              if c >= WATCH_MIN_CHANCE]
    # Always a few rows even once the race is over: "Daicos 100%" on its own
    # says he has won it, and the names under him are what say by how far. Top
    # up on VOTES COUNTED rather than on chance, because by then every other
    # player is on zero and sorting zeroes returns whoever sorts first, which
    # put two alphabetical names on nothing beside the leader.
    if len(ranked) < WATCH_MIN_ROWS:
        have = {g for g, _ in ranked}
        for pid, _ in sorted(rs["totals"].items(), key=lambda kv: -kv[1]):
            game = ctx["roster"][pid]["game"]
            if game and game not in have:
                ranked.append((game, chance.get(game, 0.0)))
                have.add(game)
            if len(ranked) >= WATCH_MIN_ROWS:
                break
    # Chance decides WHO appears, votes decide the order they appear in. The
    # post is a state of the count, so it reads down from whoever is actually
    # leading it; ranking by chance put the leader third in his own watch.
    # Each row carries its own labels, so no header line is needed to read one.
    def _votes(entry):
        pid = ctx["game_to_pid"].get(entry[0])
        return rs["totals"].get(pid, 0) if pid is not None else 0

    lines.append("")
    for game, c in sorted(ranked, key=lambda e: (-_votes(e), -e[1])):
        now = _votes((game, c))
        lines.append(f"{_disp(ctx, game)} {now} "
                     f"vote{'' if now == 1 else 's'}, exp final tally "
                     f"{projected.get(game, 0):.0f}, {c:.0%} chance of winning")

    # The 3-2-1 read belongs to whoever actually leads the count, not to
    # whoever the simulation likes best: the two are different players early,
    # and it is the leader's remaining games a reader is asking about.
    for pid in sorted((p for p, v in rs["totals"].items() if v == best),
                      key=lambda p: ctx["roster"][p]["name"]):
        game = ctx["roster"][pid]["game"]
        hard = [str(int(ctx["hard_votes"].get((r + 1, game), 0)))
                for r in sorted(ctx["all_rounds"]) if r > rd][:WATCH_EVERY]
        if hard:
            lines += ["", f"{ctx['roster'][pid]['name']} on the model's 3-2-1 "
                          f"read of his next {len(hard)}: {', '.join(hard)}."]
    text = _close(lines, where)
    return [text] if _fits(text) else []


def block_club_season_record(rs, ctx):
    """A player against his own club's best season, at 3, 1, level and past."""
    out = []
    for pid, tot in sorted(rs["totals"].items(), key=lambda kv: -kv[1]):
        club = ctx["club_of"].get(pid)
        rec = ctx["club_season_rec"].get(club)
        if rec is None:
            continue
        prev = rs["prev"].get(pid, 0)
        now_b = _record_band(rec[0] - tot, CLUB_BANDS)
        prev_b = _record_band(rec[0] - prev, CLUB_BANDS)
        if now_b is None or (prev_b is not None and now_b >= prev_b):
            continue
        name = ctx["roster"][pid]["name"]
        v, holder, yr, hid = rec
        # Identity, not spelling: two club career records are held by a name
        # another fitzRoy ID also carries, and a name test would call one
        # player's record his namesake's own.
        own = hid is not None and hid == ctx["player_id"].get(pid)
        whose = (f"his own {v} from {yr}" if own
                 else f"{_poss(holder)} {v} from {yr}")
        gap = v - tot
        if gap > 0:
            out.append(f"{name} on {tot}, {gap} from {_poss(club)} season "
                       f"record, {whose}.")
        elif gap == 0:
            out.append(f"{name} equals {_poss(club)} season record on {tot}, "
                       f"level with {whose}.")
        else:
            out.append(f"{name} passes {_poss(club)} season record with {tot}, "
                       f"past {whose}.")
    return out


def block_club_career_record(rs, ctx):
    """A player passing somebody else's club career vote record.

    Only somebody else's: most club records already belong to the player
    holding them, and "passes his own record" is not news. Votes count for THAT
    CLUB and start at CLUB_CAREER_FROM, so for a club older than the archive
    the line says since when.
    """
    out = []
    for pid, tot in rs["totals"].items():
        club = ctx["club_of"].get(pid)
        gid = ctx["player_id"].get(pid)
        rec = ctx["club_career_rec"].get(club)
        if rec is None or gid is None:
            continue
        v, holder, hid = rec
        if hid == gid:          # his own record. Identity, never the spelling
            continue
        base = ctx["club_career_base"].get((club, gid), 0.0)
        before, now = base + rs["prev"].get(pid, 0), base + tot
        if not (before <= v < now):
            continue
        since = ("" if club in ctx["complete_clubs"]
                 else f" since {CLUB_CAREER_FROM}")
        out.append(f"{ctx['roster'][pid]['name']} passes {holder} as "
                   f"{_poss(club)} leading vote-getter{since}, "
                   f"{now:.0f} to {v}.")
    return out


def block_milestones(rs, ctx):
    """Career milestones crossed BY THIS ROUND, not milestones already passed.

    The window is (base + previous) to (base + now), so a mark fires on the one
    round that crossed it and never again. Testing against the cumulative total
    alone keeps the condition true for the rest of the count, which posts "Max
    Gawn passes 150" in round 12 and again in every round after it.

    Where the mark leaves him is worth a clause, and which ladder to quote is
    decided by what is true rather than by what is bigger: the club figure is
    only used for a player whose whole career is at that club, because his club
    votes and his career votes are then the same number. For anyone who has
    moved, a club position beside a career milestone is two different
    quantities in one sentence.
    """
    roster = ctx["roster"]
    out = []
    crossed = []
    for pid, season_votes in rs["totals"].items():
        base = roster[pid]["base"]
        if base is None:
            continue                   # reported above the drafts
        before = base + rs["prev"].get(pid, 0)
        now = base + season_votes
        for mk in MILESTONES:
            if before < mk <= now:
                crossed.append((pid, mk, now))
    crossed.sort(key=lambda x: -x[1])
    # Ranked including tonight's votes, so a position quoted here cannot
    # contradict block_club_career, which has always read live totals.
    live_by_gid = {}
    for _p, _v in rs["totals"].items():
        _g = ctx["player_id"].get(_p)
        if _g:
            live_by_gid[int(_g)] = live_by_gid.get(int(_g), 0.0) + float(_v)
    career_rank_live, club_rank_live = ctx["rankings"](live_by_gid)
    for pid, mk, now in crossed:
        name = roster[pid]["name"]
        # "passes 100 ... now on 100" is a contradiction a reader will catch.
        line = (f"{name} reaches {mk:.0f} career votes" if now == mk
                else f"{name} passes {mk:.0f} career votes, now on {now:.0f}")
        rank = career_rank_live.get(ctx["player_id"].get(pid))
        club = club_rank_live.get(ctx["player_id"].get(pid))
        if club and club[2]:
            # "1st most" is not English, and before the ladders were ranked
            # live nobody ever reached the top of one mid-count, so the case
            # never came up. Now it is the case the night is built to catch.
            line += (f", the most at {club[1]}" if club[0] == 1
                     else f", {_ordinal(club[0])} most at {club[1]}")
        elif rank and rank <= CAREER_RANK_MAX:
            # A position only says something while it is a short number.
            # "489th most all time" is a true fact and a wasted clause, and it
            # is what a player who has changed clubs falls back to, since a
            # club position cannot be quoted beside a career total for him.
            line += (", the most all time" if rank == 1
                     else f", {_ordinal(rank)} most all time")
        out.append(line + ".")
    return out


def block_first_vote(rs, ctx):
    """A player's first career vote, with the game number and how he played.

    The game number is what it was AT THE MOMENT OF THE VOTE, finals included:
    everything he had played up to and including that game, and nothing after
    it. A final played later in the same September cannot retrospectively
    change what his hundredth game was, which is what makes the figure stable
    and checkable.

    The wait ladder it is compared against is built on the same basis. Reading
    the number one way and the record the other would put two figures on
    different definitions in one sentence, and the first reader to check would
    find it.
    """
    out = []
    for pid, pts in sorted(rs["votes"].items(), key=lambda kv: -kv[1]):
        r = ctx["roster"][pid]
        cid = ctx["player_id"].get(pid)
        if (r["base"] != 0 or rs["prev"].get(pid, 0) or not r["game"]
                or cid is None):
            continue
        rn = rs["rd"] + 1
        gnum = career_game_number(cid, npk.CUR_SEASON, rn,
                                  ctx["rounds_2026"].get(r["game"], ()))
        if gnum < FIRST_VOTE_MIN_GAMES:
            continue
        n = int(pts)
        what = ("his first Brownlow vote" if n == 1 else
                f"his first Brownlow votes, {NUMBER_WORD[n]} of them,")
        stats = _pick_stats(ctx["stat_line"].get((rn, r["game"]), []))
        tail = (": " + ", ".join(_stat_txt(lab, v) for lab, v in stats)
                if stats else "")
        line = f"{r['name']} polls {what} in career game {gnum}{tail}."
        waits = wait_ladder()
        longer = sum(1 for _, _, w in waits if w > gnum)
        if longer == 0:
            top = waits[0]
            line += (f" The longest wait since {FIRST_VOTE_FROM}, past "
                     f"{top[0]}'s {top[2]} in {top[1]}.")
        elif longer < FIRST_VOTE_RANK_MENTION:
            # HIS POSITION, NOT THE COUNT ABOVE HIM. "Only 18 waited longer"
            # and "the 18th most games" are different claims and the second is
            # off by one: 18 ahead of him makes him 19th. Easy to carry the
            # wrong number straight across when rewording, and it would be
            # wrong in public with the right number sitting next to it.
            #
            # Ties are real at this end of the ladder and are named rather than
            # rounded away. Tom Sparrow's 124 is also Robert Copeland's 124 in
            # 2007, so Sparrow is equal 19th, not 19th outright.
            rank = longer + 1
            tied = sum(1 for _, _, w in waits if w == gnum)
            line += (f" That is {'equal ' if tied else 'the '}"
                     f"{_ordinal(rank)} most games played before a first vote "
                     f"since {FIRST_VOTE_FROM}.")
        out.append(line)
    return out


def snub_games(rd, votes, ctx):
    """(snubbed row, three-vote row) for each game where the obvious 3 missed.

    The test, and every number in it measured on real votes rather than picked:
    the model's first pick in the game, at least SNUB_MIN_COACHES coaches
    votes, NO Brownlow vote, and ahead of the player who took the three on both
    disposals and coaches votes. That last clause is what makes the post argue
    itself, and it is why a looser version cannot be used: 10 coaches votes and
    under 3 happens about 38 times a season.
    """
    g = ctx["d"]["game_2026"]
    g = g[g.Round_num - 1 == int(rd)]
    out = []
    for _, grp in g.groupby(["Home.team", "Away.team"]):
        # Both halves of this post are coaches-vote claims, so the same guard
        # the end-of-count posts use applies here: in a game whose coaches
        # votes do not total 30 the file is damaged and a 0 may be a missing
        # row rather than a real zero. CLAUDE.md records how that happens.
        if grp.Coaches_Votes.sum() != COACHES_PER_GAME:
            continue
        top = grp.sort_values("Exp_Votes", ascending=False).iloc[0]
        pid = ctx["game_to_pid"].get(top.Player_Name)
        if pid is None or votes.get(pid, 0) != 0:
            continue
        if top.Coaches_Votes < SNUB_MIN_COACHES:
            continue
        won = [r for _, r in grp.iterrows()
               if votes.get(ctx["game_to_pid"].get(r.Player_Name), 0) == 3]
        if len(won) != 1:
            continue
        w = won[0]
        if top.Disposals > w.Disposals and top.Coaches_Votes > w.Coaches_Votes:
            out.append((top, w))
    return out


def block_snub(rs, ctx, where):
    """The games where the player both the model and the coaches had first
    polled nothing, with the two stat lines side by side."""
    out = []
    for top, w in snub_games(rs["rd"], rs["votes"], ctx):
        goals = max(top.Goals, w.Goals) >= SNUB_GOALS_SHOWN

        def line(r, votes_txt):
            bits = [f"{int(r.Disposals)} disposals"]
            if goals:
                bits.append("1 goal" if int(r.Goals) == 1
                            else f"{int(r.Goals)} goals")
            bits.append("1 coaches vote" if int(r.Coaches_Votes) == 1
                        else f"{int(r.Coaches_Votes)} coaches votes")
            return f"{_disp(ctx, r.Player_Name)}: " + ", ".join(bits) + \
                   f". {votes_txt}"

        # "First snub of the night" is derived rather than remembered: the
        # live path drafts each round in its own process, so a flag would reset.
        first = not any(snub_games(r, ctx["by_round"].get(r, {}), ctx)
                        for r in sorted(ctx["by_round"]) if r < rs["rd"])
        head = ("First snub of the night. " if first and not out else "")
        text = _close([f"{head}{_round_label(rs['rd'])}. "
                       f"{top['Home.team']} v {top['Away.team']}.", "",
                       line(top, "No Brownlow votes."),
                       line(w, "3 Brownlow votes.")], where)
        if _fits(text):
            out.append(text)
    return out


# Single-line items, bundled into the round's own reply in this order.
def _last_archived_vote():
    """{fitzRoy ID: (season, round order)} of the last vote in the archive.

    The archive ends at 2025, so this is "before tonight" by construction and
    needs no filtering against the current season.
    """
    if "last_vote" in _GAMES_CACHE:
        return _GAMES_CACHE["last_vote"]
    d = npk.load()
    v = d["games"]
    vv = v[v.Votes > 0][["ID", "Season", "Round_num"]].dropna(subset=["ID"]).copy()
    vv["ID"] = vv.ID.astype(int)
    vv["_ord"] = vv.Round_num.map(_round_order)
    vv = vv.sort_values(["Season", "_ord"]).groupby("ID").last()
    out = {int(i): (int(r.Season), int(r._ord)) for i, r in vv.iterrows()}
    _GAMES_CACHE["last_vote"] = out
    return out


def vote_gap_ladder():
    """(name, from_season, to_season, games) for every gap between two
    consecutive Brownlow votes since 1984, longest first.

    The gap is games PLAYED between the two votes, finals included, on exactly
    the basis career_game_number uses. bisect over the same sorted per-career
    game list is the same arithmetic as that function's count, and the +1 each
    end would add cancels in a subtraction.

    Measured before it was used, like every other threshold in this file. Over
    the 20,189 vote-to-vote intervals since 1984:

        0-49 games   19,900     498 a season, so worth nothing
        50-99           269     6.7 a season
        100-149          19     0.5 a season
        150+              1     Heath Grundy, 2010 to 2017, 162 games

    VOTE_GAP_MIN is 75, which fires about twice a season. At 60 it is four a
    season and stops being a rarity; at 100 whole seasons pass with nothing.
    """
    if "vote_gaps" in _GAMES_CACHE:
        return _GAMES_CACHE["vote_gaps"]
    import bisect
    d = npk.load()
    v = d["games"]
    vv = v[v.Votes > 0][["ID", "Season", "Round_num", "Player_Name"]].dropna(
        subset=["ID"]).copy()
    vv["ID"] = vv.ID.astype(int)
    vv["_ord"] = vv.Round_num.map(_round_order)
    vv = vv.sort_values(["ID", "Season", "_ord"])
    games = all_games_played()
    rows = []
    for cid, grp in vv.groupby("ID"):
        seq = games.get(int(cid))
        if not seq:
            continue
        pts = list(zip(grp.Season, grp._ord, grp.Player_Name))
        for (s0, o0, _), (s1, o1, nm) in zip(pts, pts[1:]):
            rows.append((nm, int(s0), int(s1),
                         bisect.bisect_left(seq, (s1, o1))
                         - bisect.bisect_left(seq, (s0, o0))))
    rows.sort(key=lambda r: -r[3])
    _GAMES_CACHE["vote_gaps"] = rows
    return rows


def block_vote_gap(rs, ctx):
    """A player polling again after a long time without.

    THE OTHER SIDE OF A FIRST VOTE. block_first_vote catches a career's first;
    this catches the ones who polled early, disappeared from the umpires'
    cards for years, and came back. Ryan Lester last polled in 2017 and polls
    again 137 games later, which is the fourth longest gap since 1984.

    The previous vote is taken from TONIGHT first and the archive second. A
    player who polled in round 2 and again in round 20 has a gap of eighteen
    rounds, not of the years since 2022, and reading the archive alone would
    announce the same stale gap every time he polled all night.

    Both ends are career game numbers on one basis, so the difference is games
    he actually played and not rounds the competition played without him.
    """
    out = []
    ladder = vote_gap_ladder()
    for pid, pts in sorted(rs["votes"].items(),
                           key=lambda kv: ctx["roster"][kv[0]]["name"]):
        r = ctx["roster"][pid]
        cid, game = r.get("cid"), r.get("game")
        if not cid or not game:
            continue
        rd = rs["rd"]
        played = ctx["rounds_2026"].get(game, ())
        here = career_game_number(cid, npk.CUR_SEASON, rd + 1, played)

        # Tonight's earlier votes win over the archive.
        prev_rd = max((r0 for r0, votes in ctx["by_round"].items()
                       if r0 < rd and votes.get(pid)), default=None)
        if prev_rd is not None:
            prev_n = career_game_number(cid, npk.CUR_SEASON, prev_rd + 1, played)
            from_season = npk.CUR_SEASON
        else:
            hist = _last_archived_vote().get(int(cid))
            if not hist:
                continue                 # no earlier vote: block_first_vote's
            s0, o0 = hist
            prev_n = career_game_number(cid, s0, o0)
            from_season = s0
        gap = here - prev_n
        if gap < VOTE_GAP_MIN:
            continue
        n = int(pts)
        line = (f"{r['name']} polls his first Brownlow "
                f"vote{'' if n == 1 else 's'} since {from_season}, "
                f"{gap} games ago.")
        longer = sum(1 for _, _, _, w in ladder if w > gap)
        if longer == 0:
            top = ladder[0]
            line += (f" The longest any player has gone between votes since "
                     f"{VOTE_GAP_FROM}, past {top[0]}'s {top[3]}.")
        elif longer < VOTE_GAP_RANK_MENTION:
            line += (f" That is the {_ordinal(longer + 1)} longest gap between "
                     f"votes since {VOTE_GAP_FROM}.")
        out.append(line)
    return out


LINE_BLOCKS = [
    ("league record", block_league_record),
    ("club season record", block_club_season_record),
    ("club career record", block_club_career_record),
    ("milestones", block_milestones),
    ("first career vote", block_first_vote),
    ("long gap between votes", block_vote_gap),
]

# Multi-line units, each its own post. The middle word is where it goes, and
# moving one between the thread and its own post is that word and nothing else.
POST_BLOCKS = [
    ("the obvious 3 missed", THREAD, block_snub),
    ("leader watch", THREAD, block_leader_watch),
    ("record taken", STANDALONE, block_record_taken),
]


def _thread_posts(head, lines):
    """A round's lines as one post, or as few as the cap allows.

    Splitting is the fallback and not the shape: inside a thread the round
    reads as one reply, and only a round busy enough to overrun becomes two
    consecutive ones.
    """
    out, cur = [], []
    for ln in lines:
        trial = cur + [ln]
        if cur and not _fits(_close([head, ""] + trial, THREAD)):
            out.append(_close([head, ""] + cur, THREAD))
            cur = [ln]
        else:
            cur = trial
    if cur:
        out.append(_close([head, ""] + cur, THREAD))
    return out


def tweets_for_round(ctx, rd):
    """Every draft for one round, as (kind, where, text). Often none.

    The round's single-line items are bundled into one thread reply, which is
    what makes the thread read as a running account rather than as a stack of
    near-identical posts each repeating the round number. The two multi-line
    units, the snub comparison and the leader watch, keep their own replies,
    and the record falling keeps its own post outside the thread.
    """
    by_round = ctx["by_round"]
    rs = {"rd": rd, "votes": by_round.get(rd, {}),
          "totals": totals_through(by_round, rd),
          "prev": totals_through(by_round, rd - 1)}
    out = ([("start of the thread", THREAD, thread_start())]
           if rd == ctx["first_round"] else [])
    lines = []
    for kind, fn in LINE_BLOCKS:
        try:
            lines += fn(rs, ctx)
        except Exception as exc:
            lines.append(f"[{kind} failed: {type(exc).__name__}: {exc}]")
    posts = _thread_posts(f"{_round_label(rd)} counted.", lines) if lines else []
    for i, text in enumerate(posts, 1):
        out.append((f"the round" if len(posts) == 1 else f"the round {i}",
                    THREAD, text))
    for kind, where, fn in POST_BLOCKS:
        try:
            texts = fn(rs, ctx, where)
        except Exception as exc:                      # one bad block, not a set
            out.append((kind, where,
                        f"[block failed: {type(exc).__name__}: {exc}]"))
            continue
        for i, text in enumerate(texts, 1):
            out.append((kind if len(texts) == 1 else f"{kind} {i}",
                        where, text))
    return out


def season_frame(ctx):
    """One row per 2026 player-game, Brownlow votes off the feed beside coaches'.

    Built from game_level's side, so a player the umpires never voted for is a
    row on 0 rather than an absence: the join night_sections.reverse_frame
    makes, for the same reason. Returns (frame, n_games_dropped), the second
    counting games whose coaches votes do not total 30, where a zero could be
    a failed join rather than a real zero.
    """
    m = ctx["d"]["game_2026"][["Round_num", "Player_Name", "Home.team",
                               "Away.team", "Coaches_Votes",
                               "Exp_Votes"]].copy()
    bv = {}
    for rd, votes in ctx["by_round"].items():
        for pid, pts in votes.items():
            game = ctx["roster"][pid]["game"]
            if game:
                bv[(rd + 1, game)] = pts       # AFL round to AFLTables numbering
    m["BV"] = [bv.get(k, 0) for k in zip(m.Round_num, m.Player_Name)]
    key = (m.Round_num.astype(str) + "|" + m["Home.team"].astype(str) + "|"
           + m["Away.team"].astype(str))
    ok = m.Coaches_Votes.groupby(key).transform("sum") == COACHES_PER_GAME
    return m[ok], int(key[~ok].nunique())


def _posts(head, rows):
    """head and rows as one post, or as numbered posts when 280 cannot hold them.

    End-of-count lists go out once, as the record of the season, so rows split
    across posts rather than being dropped, and every part carries the header.
    """
    def body(mark, rs):
        return _post([f"{head}{mark}:", ""] + rs)

    if _fits(body("", rows)):
        return [body("", rows)]
    parts, cur = [], []
    for r in rows:
        if cur and not _fits(body(" (9/9)", cur + [r])):
            parts.append(cur)
            cur = []
        cur.append(r)
    parts.append(cur)
    # The greedy fill leaves a stub last part, seven rows and then two. Spread
    # the rows evenly over the same number of parts where that still fits.
    size = -(-len(rows) // len(parts))
    even = [rows[i:i + size] for i in range(0, len(rows), size)]
    if len(even) == len(parts) and all(_fits(body(" (9/9)", p)) for p in even):
        parts = even
    return [body(f" ({i}/{len(parts)})", p) for i, p in enumerate(parts, 1)]


def _game_rows(ctx, hit):
    """'Name, Round N' per player, rounds grouped, in the order they were read."""
    groups = sorted(hit.groupby("Player_Name"),
                    key=lambda kv: (kv[1].Round_num.min(), _disp(ctx, kv[0])))
    return [f"{_disp(ctx, game)}, {_rounds_phrase(grp.Round_num - 1)}"
            for game, grp in groups]


def final_medal(ctx, m):
    """The medal itself.

    THE WINNER IS THE HIGHEST ELIGIBLE TOTAL, NOT THE HIGHEST. The feed marks
    26 players ineligible in 2026 and their votes are read out and counted like
    anyone else's, so taking the top of the board would hand the medal to a
    suspended player. An ineligible player above the winner is his own line,
    because it is the obvious question.
    """
    totals = totals_through(ctx["by_round"], max(ctx["by_round"], default=0))
    if not totals:
        return []
    roster = ctx["roster"]
    elig = {p: v for p, v in totals.items() if roster[p]["eligible"]}
    if not elig:
        return []
    best = max(elig.values())
    winners = sorted(roster[p]["name"] for p, v in elig.items() if v == best)
    if len(winners) == 1:
        head = (f"{winners[0]} wins the {npk.CUR_SEASON} Brownlow Medal with "
                f"{best} votes.")
    else:
        head = (f"{' and '.join(winners)} share the {npk.CUR_SEASON} Brownlow "
                f"Medal on {best} votes.")
    won = {p for p, v in elig.items() if v == best}
    order = sorted(((p, v) for p, v in totals.items() if p not in won),
                   key=lambda kv: (-kv[1], roster[kv[0]]["name"]))
    shown, tail = _cut_with_ties(order, BOARD_ROWS, BOARD_ROWS + 2)
    rows = [f"{roster[p]['name']} {v}"
            + ("" if roster[p]["eligible"] else " (ineligible)")
            for p, v in shown]
    if tail:
        rows.append(f"{tail[0]} players on {tail[1]}")
    # Only for an ineligible player the board does not already show: the rows
    # carry "(ineligible)" themselves, and saying it twice reads as a stumble.
    shown_pids = {p for p, _ in shown}
    above = [f"{roster[p]['name']} polled {v} and was ineligible."
             for p, v in sorted(totals.items(), key=lambda kv: -kv[1])
             if not roster[p]["eligible"] and v > best and p not in shown_pids]
    text = _post([FINAL_HEAD, "", head, ""] + rows + above)
    while not _fits(text) and rows:
        rows = rows[:-1]
        text = _post([FINAL_HEAD, "", head, ""] + rows + above)
    return [text]


def final_three_no_coaches(ctx, m):
    """Best on ground to the umpires, and not one coaches vote."""
    hit = m[(m.BV == 3) & (m.Coaches_Votes == 0)]
    if hit.empty:
        return []
    return _posts("Three Brownlow votes, no coaches votes",
                  _game_rows(ctx, hit))


def final_ten_coaches_no_votes(ctx, m):
    """Best on ground to both coaches, and nothing from the umpires."""
    hit = m[(m.Coaches_Votes == 10) & (m.BV == 0)]
    if hit.empty:
        return []
    return _posts("Ten coaches votes, no Brownlow votes",
                  _game_rows(ctx, hit))


def final_most_coaches_no_votes(ctx, m):
    """The season's most coaches votes by a player the umpires never voted for.

    A season total, which is why it waits for the end: one late three-vote game
    takes a player off this list entirely.
    """
    s = m.groupby("Player_Name").agg(cv=("Coaches_Votes", "sum"),
                                     bv=("BV", "sum"))
    s = s[(s.bv == 0) & (s.cv > 0)]
    if s.empty:
        return []
    order = sorted(((game, int(cv)) for game, cv in s.cv.items()),
                   key=lambda kv: (-kv[1], _disp(ctx, kv[0])))
    shown, tail = _cut_with_ties(order, LEADER_ROWS, LEADER_ROWS_MAX)
    rows = [f"{_disp(ctx, game)} {v}" for game, v in shown]
    if tail:
        rows.append(f"{tail[0]} players on {tail[1]}")
    return _posts("Most coaches votes without a Brownlow vote",
                  rows)


def _season_table(ctx, m):
    """One row per player: Brownlow votes, coaches votes, model exp, games.

    Off season_frame, so it carries only games whose coaches votes total 30 and
    the model's exp is summed over exactly the games the votes are summed over.
    """
    s = m.groupby("Player_Name").agg(bv=("BV", "sum"),
                                     cv=("Coaches_Votes", "sum"),
                                     exp=("Exp_Votes", "sum"),
                                     games=("BV", "size"))
    s["delta"] = s.bv - s.exp
    return s


def final_divergence(ctx, m):
    """Where the umpires and the coaches disagreed most, by rank.

    NOT "most Brownlow votes with no coaches votes", the exact mirror of the
    post above it, because that mirror is thin: the best anyone managed in 2026
    was two votes, and three players tied on one. Almost nobody polls Brownlow
    votes without the coaches also rating them, which is a fine fact and a poor
    post.

    Rank answers the same question and survives the two awards being on
    different scales. The coaches put 30 votes into a game against the umpires'
    6, so a raw difference is five times larger on one side and a scaled one
    still rewards whoever polled most. Rank is neither.
    """
    s = _season_table(ctx, m)
    s = s[s.bv > 0].copy()
    s["bv_rank"] = s.bv.rank(ascending=False, method="min").astype(int)
    s["cv_rank"] = s.cv.rank(ascending=False, method="min").astype(int)
    s["spread"] = s.cv_rank - s.bv_rank
    sel = s[s.bv >= DIVERGENCE_MIN_VOTES].sort_values(
        "spread", ascending=False).head(DIVERGENCE_ROWS)
    if sel.empty:
        return []
    rows = [f"{_disp(ctx, n)}: umpires {_ordinal(int(r.bv_rank))}, "
            f"coaches {_ordinal(int(r.cv_rank))}"
            for n, r in sel.iterrows()]
    return _posts("The umpires rated them far above the coaches", rows)


def final_bolters(ctx, m):
    """The votes nobody had coming.

    BOLTER_MIN_VOTES and BOLTER_MODEL_MAX are dashboard.py's Live Tracker
    constants, copied rather than re-chosen, so a bolter in a tweet is a bolter
    on the site. Ranked by how far under the model had him, which is the point.
    """
    exp = {(r.Round_num, r.Player_Name): float(r.Exp_Votes)
           for r in m.itertuples()}
    hit = []
    for rd, votes in ctx["by_round"].items():
        for pid, v in votes.items():
            game = ctx["roster"][pid]["game"]
            e = exp.get((rd + 1, game)) if game else None
            if v >= BOLTER_MIN_VOTES and e is not None and e < BOLTER_MODEL_MAX:
                hit.append((ctx["roster"][pid]["name"], rd, v, e))
    if not hit:
        return []
    hit.sort(key=lambda x: (-x[2], x[3]))
    rows = [f"{n} {v}, {_round_label(rd)}, model {e:.2f} exp"
            for n, rd, v, e in hit[:BOLTER_ROWS]]
    return _posts("The votes nobody had coming", rows)


def _perf_posts(ctx, m, over):
    s = _season_table(ctx, m)
    s = s[s.games >= PERF_MIN_GAMES]
    sel = s.sort_values("delta", ascending=not over).head(PERF_ROWS)
    if sel.empty:
        return []
    head = ("Polled more than the model expected" if over else
            "Polled fewer than the model expected")
    rows = [f"{_disp(ctx, n)} {int(r.bv)}, model {r.exp:.1f} exp"
            for n, r in sel.iterrows()]
    return _posts(head, rows)


def final_overperformers(ctx, m):
    return _perf_posts(ctx, m, True)


def final_underperformers(ctx, m):
    return _perf_posts(ctx, m, False)


# The medal first: it is the post of the night, and everything after it reads
# as a footnote to it.
FINAL_BLOCKS = [
    ("the medal", final_medal),
    ("three votes, no coaches votes", final_three_no_coaches),
    ("ten coaches votes, no votes", final_ten_coaches_no_votes),
    ("most coaches votes, no votes", final_most_coaches_no_votes),
    ("umpires above coaches", final_divergence),
    ("bolters", final_bolters),
    ("overperformers", final_overperformers),
    ("underperformers", final_underperformers),
]


def final_tweets(ctx):
    """The end-of-count posts, and notes to print above them.

    The medal goes out whatever happens below it; the three crossover posts
    refuse while a polled player is unjoined, since "no Brownlow votes" and
    "not matched" would read the same.
    """
    m, dropped = season_frame(ctx)
    notes = ([f"{dropped} game(s) whose coaches votes do not total "
              f"{COACHES_PER_GAME} are left out of the end-of-count posts"]
             if dropped else [])
    unjoined = sorted(r["name"] for r in ctx["roster"].values()
                      if r["polled"] and not r["game"])
    # EVERY CROSSOVER POST IS A CLAIM ABOUT VOTES THAT WERE NOT AWARDED, so it
    # is only true once every vote has been. Against an empty feed the three of
    # them fired sixteen posts naming most of the competition as having polled
    # nothing, which is exactly what a feed that has not started serving the
    # count looks like. A short pool is not necessarily an error either: a feed
    # that leaves an ineligible player's votes out is short and correct. Either
    # way the season-wide claims wait.
    got, pool = ctx["votes_in"], ctx["vote_pool"]
    if got != pool:
        notes.append(f"crossover posts held: the feed holds {got:,} of the "
                     f"{pool:,} votes a full season carries, so a player with "
                     f"none cannot be told from a player whose have not been "
                     f"read yet")
    out = [("end of the thread", THREAD, thread_end())]
    for kind, fn in FINAL_BLOCKS:
        if fn is not final_medal and (unjoined or got != pool):
            continue
        try:
            texts = fn(ctx, m)
        except Exception as exc:                      # one bad block, not a set
            out.append((kind, STANDALONE,
                        f"[block failed: {type(exc).__name__}: {exc}]"))
            continue
        for i, text in enumerate(texts, 1):
            out.append((kind if len(texts) == 1
                        else f"{kind}, part {i} of {len(texts)}",
                        STANDALONE, text))
    if unjoined:
        notes.append(f"crossover posts refused: {', '.join(unjoined)} polled "
                     f"but did not join game_level, so 'no Brownlow votes' "
                     f"cannot be told from 'not matched'")
    return out, notes


def emit(label, drafts, dry):
    """Print one round's drafts, thread replies first and in posting order.

    A round with nothing to say says so in a line.
    """
    banner = "  *** DRY RUN, predictor data, DO NOT POST ***" if dry else ""
    if not drafts:
        print(f"\n{label}: nothing to post.")
        return
    print(f"\n{'=' * 72}\n{label.upper()}{banner}\n{'=' * 72}")
    for where, title in ((THREAD, "THREAD, reply in this order"),
                         (STANDALONE, "ITS OWN POST")):
        group = [(k, t) for k, w, t in drafts if w == where]
        if group:
            print(f"\n>> {title}")
        for kind, text in group:
            n = _len(text)
            flag = "" if n <= TWEET_MAX else f"  !! {n} CHARS, OVER LIMIT"
            print(f"\n--- {kind} [{n} chars]{flag} ---")
            print(text)


def _seen_path():
    """Where the live path records what it has already drafted.

    In the repo's gitignored drafts/ rather than in TEMP. TEMP is cleared by
    Windows housekeeping and emptied by a reboot, and losing this file mid-count
    makes every round already posted look new, so the next poll redrafts the
    whole night and buries the round that actually just landed. drafts/ is where
    this project already keeps night output, it is gitignored, and it is
    somewhere the file can be opened and edited while the count runs.

    Named by season, so last year's file can never suppress this year's drafts.
    Only --live writes it, so no dry run can poison it.
    """
    os.makedirs("drafts", exist_ok=True)
    return os.path.join("drafts", f"count_night_drafted_{npk.CUR_SEASON}.txt")


def _load_seen():
    """What has already been drafted live: round numbers, and "final".

    So a loop does not redraft what it has.
    """
    p = _seen_path()
    if not os.path.exists(p):
        return set()
    with open(p, encoding="utf-8") as fh:
        return {x for x in fh.read().split() if x.strip()}


def _save_seen(seen):
    with open(_seen_path(), "w", encoding="utf-8") as fh:
        fh.write(" ".join(sorted(seen, key=lambda t: (not t.isdigit(),
                                                      int(t) if t.isdigit()
                                                      else 0))))


def stale_cache():
    """Whether the night pack is serving a cache older than its own sources.

    npk.load() returns its pickle whenever one exists and checks nothing about
    it, so a cache built before the last predictions run answers every record
    question here from old data and says nothing about it. That is the one
    failure on this path that produces confident wrong numbers rather than an
    error, which is why it is checked rather than trusted.
    """
    import all_time_tables as att
    cache = npk.CACHE
    if not os.path.exists(cache):
        return None
    src = [npk.PRE_FILE, npk.COACHES_ALL, npk.COACHES_CUR, att.ARCHIVE,
           att.MODERN, "predictions/season_2026.csv",
           "predictions/season_projection_2026.csv",
           "predictions/game_level_2026.csv"]
    t = os.path.getmtime(cache)
    newer = [s for s in src if os.path.exists(s) and os.path.getmtime(s) > t]
    return (f"the night pack cache is OLDER than {', '.join(newer)}, so every "
            f"record here may be computed from stale data. Run "
            f"`python scripts/night_pack.py --refresh` before posting"
            if newer else None)


SI_PATH = "data_advanced/score_involvements.csv"


def _game_detail(g):
    """(stat_line, hard_votes) per (round, player) for the 2026 season.

    stat_line ranks each player's own game by where he finished among the
    twenty-two on each stat, and keeps the strongest few. Ordering by rank
    rather than by a fixed list is what lets a ruck's game read as a ruck's and
    a forward's as a forward's, instead of opening with disposals every time.

    The score involvements here are the REAL ones out of score_involvements.csv.
    features.py carries an engineered column of the same name that is a
    different quantity entirely, and CLAUDE.md's rule is that it must never
    reach a reader.

    hard_votes is the model's 3-2-1 reading of each game, the same rule the
    site's rounded board uses: the top expectation takes the three.
    """
    g = g.copy()
    if os.path.exists(SI_PATH):
        si = pd.read_csv(SI_PATH)
        si = si[si.Season == npk.CUR_SEASON].drop(columns=["Season"])
        si = si.drop_duplicates(["Round_num", "ID"])   # see CLAUDE.md
        g = g.merge(si, on=["Round_num", "ID"], how="left")
    gk = (g.Round_num.astype(str) + "|" + g["Home.team"].astype(str)
          + "|" + g["Away.team"].astype(str))
    cols = [(c, lab) for c, lab in STAT_LABELS if c in g.columns]
    # Read as plain arrays rather than through itertuples, which renames any
    # column that is not a valid identifier and silently hides the ones here.
    rounds = g.Round_num.to_numpy()
    names = g.Player_Name.to_numpy()
    vals = {lab: g[c].to_numpy() for c, lab in cols}
    pcts = {lab: g.groupby(gk)[c].rank(pct=True).to_numpy() for c, lab in cols}
    stat_line = {}
    for i in range(len(g)):
        picks = []
        for _, lab in cols:
            v, pct = vals[lab][i], pcts[lab][i]
            if pd.notna(v) and pd.notna(pct) and v > 0:
                picks.append((float(pct), lab, float(v)))
        picks.sort(reverse=True)
        stat_line[(rounds[i], names[i])] = [(lab, v) for _, lab, v in picks]
    rk = g.groupby(gk).Exp_Votes.rank(ascending=False, method="first").to_numpy()
    hard = {(rounds[i], names[i]): _HARD_BY_RANK.get(int(rk[i]), 0)
            for i in range(len(g))}
    return stat_line, hard


def _rankings(d, career_base, live=None):
    """(career_rank, club_rank) by fitzRoy ID, AS AT THIS POINT IN THE COUNT.

    club_rank is (position, club, whole career at that club). The last flag is
    what decides whether a club position may be quoted beside a CAREER
    milestone: for a one-club player the two numbers are the same votes, and
    for anyone who has moved they are not.

    `live` maps fitzRoy ID to votes polled SO FAR TONIGHT and is added to both
    ladders before they are sorted. Without it these were computed once, off
    the pre-season base, and then quoted beside milestones reached during the
    count — so every position was stale by exactly the votes being read out,
    and it drifted further every round.

    Caught in rehearsal, and it contradicted another block in the same thread
    two rounds apart. Toby Greene started 2026 on 96 with Josh Kelly on 97.
    Round 7: "Toby Greene passes Josh Kelly as Greater Western Sydney's leading
    vote-getter, 99 to 97", which reads live totals and was right. Round 9:
    "Toby Greene reaches 100 career votes, 2nd most at Greater Western Sydney",
    off this function, still ranking him behind a player he had passed two
    rounds earlier. Both posts in one thread, both about the same player.
    """
    live = live or {}
    car = d["career"]
    car = car[car.ID > 0].copy()
    car["_live"] = (car.votes.astype(float)
                    + car.ID.astype(int).map(lambda i: live.get(int(i), 0.0)))
    car = car.sort_values("_live", ascending=False)
    career_rank = {int(i): n for n, i in enumerate(car.ID, 1)}
    total = dict(zip(car.ID.astype(int), car["_live"].astype(float)))
    by_club = {}
    for (club, cid), v in career_base.items():
        by_club.setdefault(club, []).append((v + live.get(int(cid), 0.0), cid))
    club_rank = {}
    for club, rows in by_club.items():
        for pos, (v, cid) in enumerate(sorted(rows, reverse=True), 1):
            club_rank[int(cid)] = (pos, club,
                                   abs(total.get(int(cid), 0.0) - v) < 1e-6)
    return career_rank, club_rank


def build_context(players, d):
    """Everything the blocks read, assembled once. (ctx, warnings)."""
    by_round = votes_from_feed(players)
    by_match = matches_from_feed(players)
    polled = {pid for votes in by_round.values() for pid in votes}
    roster, game_to_pid, warnings = build_roster(players, polled, d)
    g = d["game_2026"]
    club_by_name = g.groupby("Player_Name")["Playing.for"].last()
    season_rec, career_rec, career_base, complete = club_records(d)
    waits, record = first_vote_history(d)
    hist = d["games"]
    hid = pd.to_numeric(hist.ID, errors="coerce")
    gpr = games_per_round(d)
    stat_line, hard = _game_detail(g)
    career_rank, club_rank = _rankings(d, career_base)

    # The chance of winning, memoised per round: one simulation is a second and
    # a half and the watch asks for the same round more than once.
    _chance = {}

    def chances(rd):
        if rd not in _chance:
            cur = {}
            for r, votes in by_round.items():
                if r <= rd:
                    for pid, v in votes.items():
                        gm = roster[pid]["game"]
                        if gm:
                            cur[gm] = cur.get(gm, 0) + v
            rem = g[g.Round_num - 1 > rd]
            _chance[rd] = (({}, {}) if rem.empty or not cur
                           else count_sim.chances_from_frame(rem, cur, seed=rd))
        return _chance[rd]
    ctx = {"d": d, "by_round": by_round, "by_match": by_match,
           "roster": roster, "game_to_pid": game_to_pid,
           # What the feed holds against what a finished count carries. The
           # end-of-count posts read both; see final_tweets.
           "votes_in": sum(sum(v.values()) for v in by_round.values()),
           "vote_pool": VOTES_PER_GAME * sum(gpr.values()),
           "league_season_rec": league_season_record(d),
           "club_of": {pid: club_by_name.get(r["game"])
                       for pid, r in roster.items() if r["game"]},
           "player_id": {pid: r["cid"] for pid, r in roster.items()},
           # Career games behind a first vote, and the 2026 rounds each player
           # has played, so the block counts games without touching the frames.
           "career_games": hist[hid.notna()].groupby(
               hid[hid.notna()].astype(int)).size(),
           "rounds_2026": {n: sorted(s) for n, s in
                           g.groupby("Player_Name").Round_num},
           # (display round, exp) per player, for the leader watch's figure
           # over the rounds still to be read.
           "exp_rows": {n: list(zip(grp.Round_num - 1, grp.Exp_Votes))
                        for n, grp in g.groupby("Player_Name")},
           "all_rounds": sorted(gpr),
           "first_round": min(gpr),
           "first_vote_waits": waits, "first_vote_record": record,
           "club_season_rec": season_rec, "club_career_rec": career_rec,
           "club_career_base": career_base, "complete_clubs": complete,
           "stat_line": stat_line, "hard_votes": hard, "chances": chances,
           "career_rank": career_rank, "club_rank": club_rank,
           # Ranked as at a point in the count. block_milestones quotes a
           # position beside a milestone reached tonight, so it must rank on
           # tonight's totals; the two frozen dicts above are the pre-count
           # standing and are kept only for anything that wants that.
           "rankings": lambda live: _rankings(d, career_base, live)}
    return ctx, warnings


def _read_feed():
    """One read of the AFL feed. Returns (season_id, season_name, players)."""
    import count_night as cn
    sid, sname = cn.season_id()
    return sid, sname, cn.fetch(sid)


def run_once(args, feed=None):
    """One drafting pass. Returns (status, message).

    NEVER exits the process, so --watch can keep polling through the two things
    that are ordinary on the night rather than fatal: a feed that cannot be
    reached, and a count that has not started yet. main() turns those back into
    the SystemExit the single-shot modes have always raised, so --dry-run and
    --live behave exactly as before.

    Statuses: FEED_ERROR, REFUSED, NOTHING_NEW, DRAFTED, COMPLETE.
    """
    import count_night as cn
    if feed is None:
        # A poll that cannot reach the AFL is an ordinary event on the night,
        # not a crash: the next tick of the loop tries again. Say so in one line
        # rather than printing a traceback over the drafts.
        try:
            feed = _read_feed()
        except Exception as exc:
            return "FEED_ERROR", (f"could not read the AFL feed "
                                  f"({type(exc).__name__}: {exc}). Nothing "
                                  f"drafted; try the next poll.")
    sid, sname, players = feed

    if args.live:
        state, why = cn.classify(cn.digest(players), cn.load_snapshot())
        if state not in ("COUNTING", "COUNTED"):
            return "REFUSED", f"refusing: {state}. {why}"
        _note(f"{sname}: {state}. {why}")

    d = npk.load()
    ctx, warnings = build_context(players, d)
    for w in [stale_cache()] + warnings:
        if w:
            _note(f"  !! {w}")
    by_round = ctx["by_round"]
    gpr = games_per_round(d)
    done = finished_rounds(ctx["by_match"], gpr)
    complete = set(gpr) <= done

    if args.round == "final":
        rounds, want_final = [], True
    elif args.round == "all":
        rounds, want_final = sorted(by_round), complete
    else:
        rounds, want_final = [int(args.round)], False

    # A round still being read is reported and left for the next poll. Silent
    # under --watch: the same "3 of 9 games in" line every 60 seconds buries the
    # round that actually landed, and the status line already carries progress.
    for rd in rounds:
        if rd not in done and not getattr(args, "watch", False):
            got = len(ctx["by_match"].get(rd, ()))
            print(f"  {_round_label(rd)} is still being read: {got} of "
                  f"{gpr.get(rd, 0)} games in. Not drafted yet.")
    rounds = [r for r in rounds if r in done]

    # Only NEW rounds on the live path. Without this a loop polling every minute
    # redrafts the whole count on every tick, and the genuinely new round is
    # buried in twenty-four repeats of the ones already posted. An explicit
    # --round final always drafts; the automatic one fires once.
    seen = set()
    if args.live and not args.replay:
        seen = _load_seen()
        rounds = [r for r in rounds if str(r) not in seen]
        if args.round == "all" and "final" in seen:
            want_final = False
        if not rounds and not want_final:
            return "NOTHING_NEW", (f"no new rounds since the last run "
                                   f"({len(seen)} already drafted). "
                                   f"Nothing to post.")

    for rd in rounds:
        emit(_round_label(rd), tweets_for_round(ctx, rd), args.dry_run)

    if want_final:
        if not complete:
            _note(f"  !! drafting the end-of-count posts on request, but "
                  f"only {len(done)} of {len(gpr)} rounds are finished")
        drafts, notes = final_tweets(ctx)
        for n in notes:
            _note(f"  !! {n}")
        emit("End of count", drafts, args.dry_run)

    if args.live and not args.replay:
        final_done = {"final"} if want_final and complete else set()
        _save_seen(seen | {str(r) for r in rounds} | final_done)

    if complete and want_final:
        return "COMPLETE", None
    return "DRAFTED", None


class _Tee:
    """stdout to the terminal AND to a file, so checking in after a round shows
    what scrolled past. Line-buffered: the file is readable from another window
    while the night is still running, which is the whole point of it."""

    def __init__(self, stream, path):
        self.stream = stream
        self.fh = open(path, "a", encoding="utf-8", buffering=1)

    def write(self, s):
        self.stream.write(s)
        self.fh.write(s)
        return len(s)

    def flush(self):
        self.stream.flush()
        self.fh.flush()

    def close(self):
        try:
            self.fh.close()
        except Exception:
            pass


def read_last(log, n=1):
    """Print the last n drafted sections from a --watch log. Returns an int code.

    FOR CHECKING IN FROM A PHONE. --watch writes the whole night to one file,
    which by the end is several hundred lines, and the answer to "what just
    landed" is the last section of it. Reading the file is all this does: no
    feed request, no pack load, no model, so it answers instantly and costs
    nothing whether it is read over Remote Control or in a terminal.

    Cheapness is the point rather than a bonus. Checking in after each of 25
    rounds by having an assistant read the entire growing log is 25 reads of a
    file that ends up 450 lines long; this hands back only the rounds asked for.

    Sections are delimited by emit()'s 72-character banner, written as
    banner / TITLE / banner, so a heartbeat line between sections cannot be
    mistaken for one.
    """
    if not os.path.exists(log):
        print(f"no log yet at {log}. Has --watch been started?")
        return 1
    with open(log, encoding="utf-8") as fh:
        lines = fh.read().split("\n")

    bar = "=" * 72
    starts = [i for i in range(len(lines) - 2)
              if lines[i] == bar and lines[i + 2] == bar]
    if not starts:
        print(f"{log} has no drafted rounds yet. "
              f"{sum(1 for ln in lines if ln.strip())} lines so far, "
              f"most recently:")
        for ln in [x for x in lines if x.strip()][-3:]:
            print(f"  {ln}")
        return 0

    n = max(1, int(n))
    picked = starts[-n:]
    for j, s in enumerate(picked):
        end = starts[starts.index(s) + 1] if starts.index(s) + 1 < len(starts) \
            else len(lines)
        body = "\n".join(lines[s:end]).rstrip()
        # Heartbeats are the watcher talking to itself; they are noise in an
        # answer to "what do I post".
        body = "\n".join(ln for ln in body.split("\n")
                         if not _HEARTBEAT.match(ln))
        print(body.rstrip())
        if j < len(picked) - 1:
            print()
    if len(starts) > n:
        print(f"\n({len(starts)} sections drafted so far; showing the last "
              f"{n}. Pass --last {len(starts)} for all of them.)")
    return 0


def watch(args):
    """Poll the count until it finishes, drafting each round as it lands.

    THIS IS THE WHOLE NIGHT IN ONE COMMAND. It replaces running --live by hand
    once per round, which is 25 invocations over about two hours while also
    watching the broadcast.

    IT NEVER POSTS AND NEVER CALLS A MODEL. Every post here is templated, so
    there is nothing for a language model to decide per round and no token is
    spent by this loop; it is an ordinary Python process reading a public feed.
    Drafting is all it does. What goes out is still your call, from the
    scrollback or from the log.

    Quiet on purpose. A status line prints only when the status CHANGES, plus a
    heartbeat every HEARTBEAT_EVERY seconds so a silent terminal is
    distinguishable from a dead one. Everything else on screen is a draft. A
    poll that fails is counted and retried rather than fatal: the feed dropping
    one request is the expected case, not the end of the night.

    Stops when the count is complete and the end-of-count posts have been
    drafted. Ctrl+C stops it cleanly at any time, and because the rounds it has
    already drafted are recorded in drafts/, restarting picks up where it left
    off instead of replaying the night.
    """
    import time as _t
    os.makedirs("drafts", exist_ok=True)
    log = args.log or DEFAULT_WATCH_LOG
    os.makedirs(os.path.dirname(log) or ".", exist_ok=True)
    tee = _Tee(sys.stdout, log)
    real_stdout, sys.stdout = sys.stdout, tee

    def say(msg):
        print(f"[{_t.strftime('%H:%M:%S')}] {msg}", flush=True)

    global _WATCH_SAY
    _WATCH_SAY = say
    say(f"watching the count every {args.interval}s. Drafts also appended to "
        f"{log}")
    say("nothing is posted and no model is called. Ctrl+C to stop.")
    last, fails, last_beat = None, 0, _t.time()
    try:
        while True:
            status, msg = run_once(args)
            if status == "FEED_ERROR":
                fails += 1
                # Only the first failure of a run speaks. A flapping feed would
                # otherwise fill the screen with the same line.
                if status != last:
                    say(f"{msg} (failure {fails})")
            elif status in ("REFUSED", "NOTHING_NEW"):
                if status != last or _t.time() - last_beat > HEARTBEAT_EVERY:
                    say(msg)
                    last_beat = _t.time()
            elif status == "COMPLETE":
                say("the count is complete and the end-of-count posts are "
                    "drafted above. Stopping.")
                return 0
            last = status
            _t.sleep(args.interval)
    except KeyboardInterrupt:
        say("stopped. Rounds already drafted are recorded, so restarting "
            "resumes rather than replaying.")
        return 0
    finally:
        _WATCH_SAY = None
        sys.stdout = real_stdout
        tee.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="use the AFL predictor as stand-in votes")
    ap.add_argument("--live", action="store_true",
                    help="use the real count, refusing unless it is running")
    ap.add_argument("--watch", action="store_true",
                    help="live: poll all night, drafting each round as it "
                         "lands. Never posts, never calls a model")
    ap.add_argument("--interval", type=int, default=WATCH_INTERVAL,
                    help=f"watch: seconds between polls (default "
                         f"{WATCH_INTERVAL})")
    ap.add_argument("--log", default=None,
                    help=f"watch/--last: the night's log "
                         f"(default {DEFAULT_WATCH_LOG})")
    ap.add_argument("--round", default="all",
                    help="a round number, 'all', or 'final' for the "
                         "end-of-count posts alone")
    ap.add_argument("--replay", action="store_true",
                    help="live: redraft rounds already emitted")
    ap.add_argument("--last", nargs="?", const=1, type=int, default=None,
                    metavar="N",
                    help="print the last N drafted sections from the watch "
                         "log and exit (default 1). Reads the file only")
    args = ap.parse_args(argv)

    # --last answers from the log alone, so it takes neither --dry-run nor
    # --live and is checked before the mode test below. It is what a check-in
    # from a phone runs.
    if args.last is not None:
        return read_last(args.log or DEFAULT_WATCH_LOG, args.last)
    if args.watch:
        # --watch is a live-only mode by definition: it exists to sit through a
        # count. Implying --live rather than demanding both keeps the command
        # short on the one night it is typed under pressure.
        args.live = True
        if args.round != "all":
            raise SystemExit("--watch drafts every round as it lands; "
                             "do not pass --round with it")
    if args.dry_run == args.live:
        raise SystemExit("pass exactly one of --dry-run or --live")
    if args.watch:
        return watch(args)

    status, msg = run_once(args)
    # The single-shot modes exit the way they always have: a feed that cannot be
    # read and a count that has not started are both failures to a caller that
    # asked for one pass, and both are ordinary to the watcher.
    if status in ("FEED_ERROR", "REFUSED"):
        raise SystemExit(msg)
    if msg:
        print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
