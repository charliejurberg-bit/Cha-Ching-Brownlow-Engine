"""Count-night tweet drafts, one set per round as the votes are read out.

    python scripts/count_tweets.py --dry-run --round 12   # refine the copy NOW
    python scripts/count_tweets.py --dry-run --round all  # every round, to eyeball
    python scripts/count_tweets.py --live                 # on the night

WHAT THIS IS
A round gets counted, this returns the posts for it. Templated, never generated:
the same decision draft_posts.py made and for the same reason, which is that a
templated post cannot invent an accuracy claim under time pressure.

Every format rule here comes from draft_formats_spec.md and is not re-litigated:
280 characters with the domain counted as 23, no em dashes, no padding or column
alignment because Twitter renders proportional and any alignment dies on paste,
rows self-describing with single spaces, the link inside each block because each
block is pasted as its own post, "exp" rather than "projected votes", and no
accuracy percentage anywhere.

THE ACCURACY RULE BITES HARDEST HERE AND IS WORTH RESTATING
A count-night model-check post wants to say "we got 6 of 9". That is an accuracy
figure wearing a fraction's clothes, and project_brief.md's rule is absolute
without Charlie supplying the number. So the model block NAMES THE CALLS instead:
the specific players the model had first for votes in a game who then polled
three. A reader can count them, which is the honest version, and the post never
asserts a rate.

DRY RUN IS THE POINT, NOT A CONVENIENCE
The plumbing either works or it does not, and that is testable tonight. The copy
can only be judged by reading it, and on the night there is no time to iterate.
--dry-run treats the AFL predictor's per-round allocation as if it were the
count, so every post can be read in full, now, and the templates changed while
changing them is cheap. It prints a DRY RUN banner on every block so a dry-run
post can never be mistaken for a real one and pasted.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import night_pack as npk                                   # noqa: E402
from night_sections import MILESTONES, _modern_seasons     # noqa: E402

SITE_URL = "chachingbrownlow.com"
DOMAIN_COST = 23          # Twitter counts any link as 23 characters
TWEET_MAX = 280
LEADER_ROWS = 5
MOVER_ROWS = 5


def _len(text):
    """Twitter's count: the domain costs 23 whatever its real length."""
    return len(text) - len(SITE_URL) + DOMAIN_COST if SITE_URL in text \
        else len(text)


def _fits(text):
    return _len(text) <= TWEET_MAX


def _round_label(rd):
    return "Opening Round" if int(rd) == 0 else f"Round {int(rd)}"


# ---------------------------------------------------------------------------
# Vote sources
# ---------------------------------------------------------------------------

def votes_from_feed(players):
    """{display_round: {player: points}} from an award-API payload."""
    out = {}
    for p in players:
        name = f"{p.get('firstName', '')} {p.get('surname', '')}".strip()
        for rkey, entries in (p.get("rounds") or {}).items():
            for e in entries:
                pts = e.get("points", 0)
                if pts:
                    out.setdefault(int(rkey), {})[name] = int(pts)
    return dict(sorted(out.items()))


def totals_through(by_round, upto):
    """Cumulative totals through and including `upto`, as the count stands."""
    tot = {}
    for rd, votes in by_round.items():
        if rd <= upto:
            for name, pts in votes.items():
                tot[name] = tot.get(name, 0) + pts
    return tot


# ---------------------------------------------------------------------------
# The blocks
# ---------------------------------------------------------------------------

def block_leaderboard(rd, totals, prev_totals):
    """The staple. Where the count stands, and the move each name just made."""
    order = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    lines = [f"{_round_label(rd)} counted.", ""]
    for name, v in order[:LEADER_ROWS]:
        gain = v - prev_totals.get(name, 0)
        lines.append(f"{name} {v}" + (f" (+{gain})" if gain else ""))
    lines += ["", f"Full board at {SITE_URL}"]
    return "\n".join(lines)


def block_movers(rd, votes):
    """Who gained most in the round just counted. Ties broken by name."""
    order = sorted(votes.items(), key=lambda kv: (-kv[1], kv[0]))
    top = [(n, v) for n, v in order if v == 3]
    lines = [f"{_round_label(rd)}. Best on ground:", ""]
    for name, _ in top[:MOVER_ROWS + 4]:
        lines.append(name)
    body = "\n".join(lines + ["", f"Every vote at {SITE_URL}"])
    # Nine three-vote games in a full round is often over the limit. Drop rows
    # from the bottom until it fits rather than truncating mid-name, and say so,
    # because a silently short list reads as a complete one.
    while not _fits(body) and len(top) > 1:
        top = top[:-1]
        lines = [f"{_round_label(rd)}. Best on ground, first {len(top)}:", ""]
        lines += [n for n, _ in top]
        body = "\n".join(lines + ["", f"Every vote at {SITE_URL}"])
    return body


def block_model_calls(rd, votes, d):
    """Players the model had first for votes in a game who then polled three.

    NAMES THE CALLS, NEVER A HIT RATE. "6 of 9" is an accuracy figure and
    project_brief.md forbids one without Charlie supplying it. A reader can
    count the names, which is the same information without the assertion.
    """
    g = d["game_2026"].copy()
    g["rd"] = g.Round_num - 1          # AFLTables to AFL numbering, 2024 on
    g = g[g.rd == int(rd)]
    if g.empty:
        return None
    g["_k"] = (g["Home.team"].astype(str) + " v " + g["Away.team"].astype(str))
    firsts = (g.sort_values("Exp_Votes", ascending=False)
              .groupby("_k", as_index=False).head(1))
    hit = []
    for _, r in firsts.iterrows():
        nm = str(r.Player_Name)
        if votes.get(nm, 0) == 3:
            hit.append((nm, r._k, float(r.Exp_Votes)))
    if not hit:
        return None
    lines = [f"{_round_label(rd)}. Called first for votes, polled three:", ""]
    for nm, fixture, exp in hit:
        lines.append(f"{nm} {exp:.2f} exp")
    body = "\n".join(lines + ["", f"Every game at {SITE_URL}"])
    while not _fits(body) and len(hit) > 1:
        hit = hit[:-1]
        lines = [f"{_round_label(rd)}. Called first for votes, polled three:",
                 ""]
        lines += [f"{nm} {exp:.2f} exp" for nm, _, exp in hit]
        body = "\n".join(lines + ["", f"Every game at {SITE_URL}"])
    return body


def block_milestones(rd, totals, prev_totals, d):
    """Career milestones crossed BY THIS ROUND, not milestones already passed.

    The window is (base + previous) to (base + now), so a mark fires on the one
    round that crossed it and never again. Testing against the cumulative total
    alone keeps the condition true for the rest of the count, which posts "Max
    Gawn passes 150" in round 12 and again in every round after it.

    career votes come from the seam-joined ladder, so a career predating 1984
    carries that ladder's caveats. Nobody polling in 2026 does.
    """
    car = d["career"]
    by_name = dict(zip(car.name, car.votes))
    crossed = []
    for name, season_votes in totals.items():
        base = float(by_name.get(name, 0.0))
        before = base + prev_totals.get(name, 0)
        now = base + season_votes
        for mk in MILESTONES:
            if before < mk <= now:
                crossed.append((name, mk, now))
    if not crossed:
        return None
    crossed.sort(key=lambda x: -x[1])

    def _row(n, m, v):
        # "passes 100 ... now on 100" is a contradiction a reader will catch.
        return (f"{n} reaches {m:.0f} career votes" if v == m
                else f"{n} passes {m:.0f} career votes, now on {v:.0f}")

    head = f"{_round_label(rd)} counted. Career milestones:"
    sel = crossed[:4]
    body = "\n".join([head, ""] + [_row(*c) for c in sel]
                     + ["", f"All-time lists at {SITE_URL}"])
    while not _fits(body) and len(sel) > 1:
        sel = sel[:-1]
        body = "\n".join([head, ""] + [_row(*c) for c in sel]
                         + ["", f"All-time lists at {SITE_URL}"])
    return body


def block_season_record(rd, totals, d):
    """The leader against the all-time season record, once it is in range.

    Silent until the leader is within 10, because a record watch posted in
    Round 4 is noise and the same post in Round 21 is the story.
    """
    mod = _modern_seasons(d)
    comp = mod[mod.Season.map(npk.COMPARABLE)].sort_values(
        "votes", ascending=False).iloc[0]
    rec, holder, yr = float(comp.votes), comp["name"], int(comp.Season)
    if not totals:
        return None
    name, v = max(totals.items(), key=lambda kv: kv[1])
    gap = rec - v
    if gap > 10:
        return None
    if gap > 0:
        line = f"{name} is {gap:.0f} from the all-time season record."
    elif gap == 0:
        line = f"{name} has equalled the all-time season record."
    else:
        line = f"{name} has broken the all-time season record."
    body = "\n".join([f"{_round_label(rd)} counted.", "", line,
                      f"{v:.0f} votes. The record is {rec:.0f}, "
                      f"{holder} in {yr}.", "",
                      f"All-time lists at {SITE_URL}"])
    return body if _fits(body) else None


BLOCKS = [
    ("leaderboard", lambda rd, v, t, p, d: block_leaderboard(rd, t, p)),
    ("best on ground", lambda rd, v, t, p, d: block_movers(rd, v)),
    ("model calls", lambda rd, v, t, p, d: block_model_calls(rd, v, d)),
    ("milestones", lambda rd, v, t, p, d: block_milestones(rd, t, p, d)),
    ("season record", lambda rd, v, t, p, d: block_season_record(rd, t, d)),
]


def tweets_for_round(d, rd, by_round):
    """Every draft for one round. Blocks that have nothing to say return None."""
    votes = by_round.get(rd, {})
    totals = totals_through(by_round, rd)
    prev = totals_through(by_round, rd - 1)
    out = []
    for kind, fn in BLOCKS:
        try:
            text = fn(rd, votes, totals, prev, d)
        except Exception as exc:                      # one bad block, not a set
            out.append((kind, f"[block failed: {type(exc).__name__}: {exc}]"))
            continue
        if text:
            out.append((kind, text))
    return out


def emit(rd, drafts, dry):
    banner = "  *** DRY RUN, predictor data, DO NOT POST ***" if dry else ""
    print(f"\n{'=' * 72}\n{_round_label(rd).upper()}{banner}\n{'=' * 72}")
    if not drafts:
        print("  (nothing to post for this round)")
    for kind, text in drafts:
        n = _len(text)
        flag = "" if n <= TWEET_MAX else f"  !! {n} CHARS, OVER LIMIT"
        print(f"\n--- {kind} [{n} chars]{flag} ---")
        print(text)


def _seen_path():
    return os.path.join(os.environ.get("TEMP", "/tmp"),
                        "count_tweets_emitted.txt")


def _load_seen():
    """Rounds already emitted live, so a loop does not redraft what it has.

    Deliberately in the scratchpad rather than the repo: it is per-run bookkeeping
    with no value after the night, and a stale copy committed from a dry run
    would suppress real drafts.
    """
    p = _seen_path()
    if not os.path.exists(p):
        return set()
    with open(p, encoding="utf-8") as fh:
        return {int(x) for x in fh.read().split() if x.strip().isdigit()}


def _save_seen(seen):
    with open(_seen_path(), "w", encoding="utf-8") as fh:
        fh.write(" ".join(str(x) for x in sorted(seen)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true",
                    help="use the AFL predictor as stand-in votes")
    ap.add_argument("--live", action="store_true",
                    help="use the real count, refusing unless it is running")
    ap.add_argument("--round", default="all",
                    help="a round number, or 'all'")
    ap.add_argument("--replay", action="store_true",
                    help="live: redraft rounds already emitted")
    args = ap.parse_args(argv)
    if args.dry_run == args.live:
        raise SystemExit("pass exactly one of --dry-run or --live")

    import count_night as cn
    sid, sname = cn.season_id()
    players = cn.fetch(sid)

    if args.live:
        state, why = cn.classify(cn.digest(players), cn.load_snapshot())
        if state not in ("COUNTING", "COUNTED"):
            raise SystemExit(f"refusing: {state}. {why}")
        print(f"{sname}: {state}. {why}")

    by_round = votes_from_feed(players)
    d = npk.load()
    rounds = (sorted(by_round) if args.round == "all" else [int(args.round)])

    # Only NEW rounds on the live path. Without this a loop polling every minute
    # redrafts the whole count on every tick, and the genuinely new round is
    # buried in twenty-four repeats of the ones already posted.
    seen = set()
    if args.live and not args.replay:
        seen = _load_seen()
        fresh = [r for r in rounds if r not in seen]
        if not fresh:
            print(f"no new rounds since the last run "
                  f"({len(seen)} already drafted). Nothing to post.")
            return 0
        rounds = fresh

    for rd in rounds:
        emit(rd, tweets_for_round(d, rd, by_round), args.dry_run)

    if args.live and not args.replay:
        _save_seen(seen | set(rounds))
    return 0


if __name__ == "__main__":
    sys.exit(main())
