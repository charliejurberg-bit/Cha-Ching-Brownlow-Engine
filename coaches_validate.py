"""Completeness validation for the AFL Coaches Association vote feed.

The coaches features carry ~45% of the full model's gain across six features
(mean gain 72.8 against the 20 Wheelo features' 3.3), and their failure mode is
silent: a missing player merges to zero, and zero is the modal value, so nothing
downstream trips. A player who polled 10 and a player who polled nothing are
indistinguishable once the merge has dropped a row.

This is the coaches equivalent of the per-game completeness test that
update_wheelo_2026.py got. Same discipline, same three-status vocabulary, an
end-of-run summary, and a hard refusal to let "absent" read as "zero".

WHAT THE AWARD ALLOCATES, measured rather than assumed. Both coaches in a game
award 5-4-3-2-1, so every game carries exactly 2 * (5+4+3+2+1) = 30 votes, and
between 5 players (both coaches naming an identical five) and 10 (no overlap)
receive them. Verified against all 189 games of 2026: every single game totals
exactly 30, with 5 to 9 players polling. The feed stores each player's two-coach
sum, hence values of 1 through 10 on a single row.

Usage:
    python coaches_validate.py            # retrospective, whole season
"""

import sys

import pandas as pd

import features as feat

SEASON = 2026
COACHES_CSV = "data_2026/coaches_votes_2026.csv"
AFLTABLES_CSV = "data_2026/afltables_2026.csv"

# 2 coaches x (5+4+3+2+1). Confirmed on 189/189 games of 2026.
VOTES_PER_COACH = 15
COACHES_PER_GAME = 2
EXPECTED_VOTES_PER_GAME = VOTES_PER_COACH * COACHES_PER_GAME

# Both coaches name five players, so the union is 5 (identical fives) to 10
# (disjoint fives). 2026 ran 5 to 9.
MIN_VOTED_PLAYERS = 5
MAX_VOTED_PLAYERS = COACHES_PER_GAME * 5

# A round short of this share of its expected total has the partial-scrape
# signature: some games present, others silently absent. Anything at or above
# it but not exact is reported as a shortfall too, just less loudly.
PARTIAL_ROUND_THRESHOLD = 0.95

# ── Round statuses ───────────────────────────────────────────
# Same vocabulary as update_wheelo_2026.py, for the same reason: one "no data"
# line covering every failure is what let a real gap hide for a week.
STATUS_OK = "OK"
STATUS_NOT_PUBLISHED = "NOT_PUBLISHED"      # round absent from the feed
STATUS_EMPTY = "EMPTY"                      # round present, no votes in it
STATUS_INCOMPLETE = "INCOMPLETE"            # round present, votes missing
STATUS_FOREIGN = "FOREIGN_FIXTURES"         # round carries another round's games


def _load():
    aflt = pd.read_csv(AFLTABLES_CSV, low_memory=False)
    aflt['Round_num'] = pd.to_numeric(aflt['Round'], errors='coerce')
    aflt = aflt.dropna(subset=['Round_num'])
    aflt['Round_num'] = aflt['Round_num'].astype(int)
    aflt['Player_Name'] = (aflt['First.name'].str.strip() + ' '
                           + aflt['Surname'].str.strip())

    cv = pd.read_csv(COACHES_CSV)
    cv['Round_num'] = pd.to_numeric(cv['Round'], errors='coerce')
    cv = cv.dropna(subset=['Round_num'])
    cv['Round_num'] = cv['Round_num'].astype(int)
    cv['Coaches.Votes'] = pd.to_numeric(cv['Coaches.Votes'],
                                        errors='coerce').fillna(0)
    cv['Player_Name'] = cv['Player.Name'].str.extract(r'^(.+?)\s*\(')[0].str.strip()
    cv['Playing.for'] = (cv['Player.Name'].str.extract(r'\(([^)]+)\)')[0]
                         .map(feat.TEAM_ABBREV))
    for col in ('Home.Team', 'Away.Team'):
        cv[col] = cv[col].replace(feat.COACHES_TEAM_FIXES)
    return aflt, cv


def _fixtures(df, home, away):
    """Round's fixtures as unordered {frozenset({home, away})}."""
    pairs = df[[home, away]].drop_duplicates().values
    return {frozenset(p) for p in pairs}


def validate(aflt, cv, verbose=True):
    """Validate the coaches feed against the AFLTables fixture list.

    Returns (rounds_report, findings). rounds_report maps round -> status;
    findings is a list of (round, severity, message).
    """
    findings = []
    report = {}

    # Player names have to be reconciled before any per-player test, or the
    # feed's O'Sullivan against AFLTables' OSullivan reads as a player who
    # polled in a game he did not play.
    cv_named = cv.dropna(subset=['Playing.for']).copy()
    cv_named, unresolved = feat.resolve_feed_names(
        cv_named, aflt, feed_name_col='Player_Name',
        feed_team_col='Playing.for', feed_round_col='Round_num',
        label='coaches', verbose=False)
    if len(unresolved):
        findings.append((None, 'WARN',
                         f"{len(unresolved)} vote row(s) name a player who "
                         f"could not be matched to AFLTables"))

    aflt_rounds = sorted(aflt['Round_num'].unique())

    for rnd in aflt_rounds:
        a_r = aflt[aflt['Round_num'] == rnd]
        c_r = cv_named[cv_named['Round_num'] == rnd]
        a_fix = _fixtures(a_r, 'Home.team', 'Away.team')
        expected_total = len(a_fix) * EXPECTED_VOTES_PER_GAME

        # ── Round present at all? ──
        if c_r.empty:
            report[rnd] = STATUS_NOT_PUBLISHED
            findings.append((rnd, 'INFO',
                             f"absent from the feed; {len(a_fix)} game(s) "
                             f"played, {expected_total} votes expected"))
            continue
        if c_r['Coaches.Votes'].sum() == 0:
            report[rnd] = STATUS_EMPTY
            findings.append((rnd, 'ERROR', "present but carries zero votes"))
            continue

        # ── Foreign fixtures: a republished copy of another round ──
        c_fix = _fixtures(c_r, 'Home.Team', 'Away.Team')
        foreign = c_fix - a_fix
        if foreign:
            report[rnd] = STATUS_FOREIGN
            sample = ', '.join(' v '.join(sorted(f)) for f in list(foreign)[:3])
            findings.append((rnd, 'ERROR',
                             f"carries {len(foreign)} fixture(s) AFLTables did "
                             f"not play that round ({sample}) - this is the "
                             f"feed republishing another round under this "
                             f"number, NOT a published round"))
            continue

        status = STATUS_OK

        # ── Round total against the fixture list ──
        total = c_r['Coaches.Votes'].sum()
        if total != expected_total:
            share = total / expected_total if expected_total else 0
            sev = 'ERROR' if share < PARTIAL_ROUND_THRESHOLD else 'WARN'
            status = STATUS_INCOMPLETE
            findings.append((rnd, sev,
                             f"round total {int(total)} against {expected_total} "
                             f"expected ({share:.1%}) - "
                             f"{'partial scrape signature' if sev == 'ERROR' else 'shortfall'}"))

        # ── Missing games ──
        missing = a_fix - c_fix
        if missing:
            status = STATUS_INCOMPLETE
            sample = ', '.join(' v '.join(sorted(f)) for f in list(missing)[:3])
            findings.append((rnd, 'ERROR',
                             f"{len(missing)} game(s) played but carrying no "
                             f"votes ({sample})"))

        # ── Per game: exact total, and players polling within bounds ──
        for (h, aw), g in c_r.groupby(['Home.Team', 'Away.Team']):
            gt = g['Coaches.Votes'].sum()
            if gt != EXPECTED_VOTES_PER_GAME:
                status = STATUS_INCOMPLETE
                findings.append((rnd, 'ERROR',
                                 f"{h} v {aw}: {int(gt)} votes, expected "
                                 f"{EXPECTED_VOTES_PER_GAME}"))
            n = g['Player_Name'].nunique()
            if not (MIN_VOTED_PLAYERS <= n <= MAX_VOTED_PLAYERS):
                status = STATUS_INCOMPLETE
                findings.append((rnd, 'ERROR',
                                 f"{h} v {aw}: {n} player(s) polled, expected "
                                 f"{MIN_VOTED_PLAYERS}-{MAX_VOTED_PLAYERS}"))

        # ── No votes for a player who did not play that game ──
        played = set(zip(a_r['Player_Name'], a_r['Playing.for']))
        ghosts = [(p, t) for p, t in
                  zip(c_r['Player_Name'], c_r['Playing.for'])
                  if (p, t) not in played]
        if ghosts:
            status = STATUS_INCOMPLETE
            sample = ', '.join(f"{p} ({t})" for p, t in ghosts[:3])
            findings.append((rnd, 'ERROR',
                             f"{len(ghosts)} vote row(s) for a player AFLTables "
                             f"does not list in that round ({sample})"))

        report[rnd] = status

    if verbose:
        _print_report(report, findings, aflt_rounds)
    return report, findings


def _print_report(report, findings, aflt_rounds):
    by_round = {}
    for rnd, sev, msg in findings:
        by_round.setdefault(rnd, []).append((sev, msg))

    for rnd in aflt_rounds:
        status = report.get(rnd, STATUS_NOT_PUBLISHED)
        marker = '  OK  ' if status == STATUS_OK else f'  {status}'
        print(f"  R{rnd:<3} {marker}")
        for sev, msg in by_round.get(rnd, []):
            print(f"         {sev}: {msg}")
    for sev, msg in by_round.get(None, []):
        print(f"  (feed-wide) {sev}: {msg}")

    tally = {}
    for s in report.values():
        tally[s] = tally.get(s, 0) + 1
    print()
    print("Coaches feed summary: " + ", ".join(
        f"{n} {s.lower().replace('_', ' ')}"
        for s, n in sorted(tally.items(), key=lambda kv: -kv[1])))
    errors = sum(1 for _, sev, _ in findings if sev == 'ERROR')
    published = tally.get(STATUS_OK, 0)
    print(f"  {published}/{len(aflt_rounds)} round(s) complete and verified, "
          f"{errors} error-level finding(s)")


def main():
    aflt, cv = _load()
    print(f"Validating coaches votes for {SEASON} against the AFLTables "
          f"fixture list\n")
    report, findings = validate(aflt, cv)
    bad = [r for r, s in report.items()
           if s in (STATUS_EMPTY, STATUS_INCOMPLETE)]
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
