"""Team-level head-to-head fixture preview. CLI and facts-file writer.

    python team_h2h.py --teams "Richmond" "St Kilda"
    python team_h2h.py --teams "Richmond" "St Kilda" --date 2026-08-15
    python team_h2h.py --teams "Richmond" "St Kilda" --scope ha --without "Tim Taranto"

The first team named is the subject. Every record is oriented to it, never to
the home side.

Output is a **markdown facts file** to drafts/, which is gitignored. No tweet
copy and no draft: draft_gate.py has no team-mode coverage, so nothing here is
post-ready and nothing here claims to be. Copy is written separately once the
gate covers team mode.

Three things the writer is built to prevent, each from the spec:

  - **A cut read as a finding.** A 106-meeting series always contains a
    striking pattern somewhere in the cut space. Every conditional section
    prints the number of cuts tested, so a pattern reads as one-in-N rather
    than as a discovery.
  - **A truncated archive read as club history.** The floor is 1965 and it is a
    hard truncation of the data, not the start of the fixture. Richmond and St
    Kilda met from 1908. The caveat is stated prominently once and repeated on
    every ranking.
  - **An empty arm read as a contrast.** If a with/without arm has no matches
    there is no comparator, so the numbers print and the framing is withheld
    with the reason given.
"""

import argparse
import os
import sys

import pandas as pd

from team_h2h_crossopp import LIVE_STREAK_TRIGGER, cross_opponent_streaks
from team_h2h_records import H2HError, h2h_records
from team_h2h_streaks import FLOOR_CAVEAT, FLOOR_SEASON, h2h_streaks
from team_h2h_without import h2h_without
from team_match_table import load_match_table

OUT_DIR = 'drafts'

# Section 6 sections 3 to 8 are the conditional cuts. The count of cells across
# them is what makes a striking cell readable as one of N rather than as a
# finding, so it is computed from the frames rather than declared.
CUT_SECTIONS = ('by_venue', 'by_timeslot', 'by_day', 'by_venue_timeslot',
                'same_calendar_date', 'by_quarter')


def _slug(text):
    return ''.join(c.lower() if c.isalnum() else '' for c in text)


def _table(df, cols=None, drop=('source_file',)):
    """A markdown table, or a stated absence. Never a silent blank."""
    if df is None or df.empty:
        return '_No rows. An empty section is a failed lookup, not a zero._\n'
    d = df[cols] if cols else df.drop(columns=[c for c in drop if c in df.columns])
    head = '| ' + ' | '.join(str(c) for c in d.columns) + ' |'
    rule = '|' + '---|' * len(d.columns)
    body = '\n'.join(
        '| ' + ' | '.join('' if pd.isna(v) else str(v) for v in row) + ' |'
        for row in d.itertuples(index=False)
    )
    return f'{head}\n{rule}\n{body}\n'


def _sources(df):
    if df is None or df.empty or 'source_file' not in df.columns:
        return ''
    seen = sorted({s for s in df.source_file.dropna() for s in str(s).split('; ')})
    return '\nSource: ' + ', '.join(f'`{s}`' for s in seen) + '\n' if seen else ''


def _et_note(df):
    """Name any section whose population includes an extra-time match."""
    if df is None or df.empty or 'includes_extra_time' not in df.columns:
        return ''
    hit = df[df.includes_extra_time]
    if hit.empty:
        return ''
    n = int(hit.extra_time_n.sum()) if 'extra_time_n' in hit.columns else len(hit)
    return (f'\n**Extra time in this population.** {n} match(es) here went to '
            f'extra time. The match result uses the extra-time score and the '
            f'quarter results are regulation, so a quarter record and a match '
            f'record are not the same quantity on those matches.\n')


def build_facts(subject, opponent, scope='all', fixture_date=None,
                without=(), matches=None):
    """Return the facts file as markdown text, and the run's own metadata."""
    table = load_match_table() if matches is None else matches

    # --without is resolved BEFORE anything is written. An ambiguous name stops
    # the run rather than skipping the cut and continuing, because a preview
    # that quietly omits the section it was asked for is worse than no preview.
    resolved = []
    for player in without:
        cut = h2h_without(subject, opponent, player, matches=table)
        if cut['status'] in ('ambiguous', 'not_found'):
            return None, cut
        resolved.append((player, cut))

    rec = h2h_records(subject, opponent, scope=scope,
                      fixture_date=fixture_date, matches=table)
    stk = h2h_streaks(subject, opponent, scope=scope, matches=table)
    m = rec['meetings']
    ov = rec['series_overview'].iloc[0]

    cuts_tested = sum(len(rec[s]) for s in CUT_SECTIONS if s in rec)

    L = []
    a = L.append
    a(f'# {subject} v {opponent}, head to head facts\n')
    a(f'Subject team: **{subject}**. Every record below is oriented to '
      f'{subject}, never to the home side.\n')
    a(f'- Scope: `{scope}`')
    a(f'- Meetings in scope: **{int(ov.denominator)}**')
    a(f'- Fixture date supplied: {fixture_date or "none, section 7 not computed"}')
    a(f'- Conditional cells tested across sections 3 to 8: **{cuts_tested}**')
    a(f'- Generated by `team_h2h.py`. Facts only: no tweet copy, no draft, '
      f'and `draft_gate.py` has no team-mode coverage.\n')
    # FLOOR_CAVEAT already opens with "Archive floor 1965.", so it is quoted
    # rather than prefixed.
    a(f'> {FLOOR_CAVEAT}\n')
    a('> **Reading the cuts.** A series this long will contain a striking '
      'pattern somewhere in {quarters x result x venue x timeslot x day}. '
      f'{cuts_tested} cells were tested to produce the sections below, so any '
      'single striking cell is one of ' + str(cuts_tested) + ', not a finding. '
      'Every cell prints its own denominator.\n')
    a('---\n')

    a('## 1. Series overview\n')
    a(_table(rec['series_overview']))
    a(_sources(rec['series_overview']))
    a(_et_note(rec['series_overview']))

    a('\n## 2. Scope split, home and away against finals\n')
    a(_table(rec['scope_split']))
    a(_sources(rec['scope_split']))

    for n, key, title in ((3, 'by_venue', 'Venue'),
                          (4, 'by_timeslot', 'Timeslot'),
                          (5, 'by_day', 'Day of week'),
                          (6, 'by_venue_timeslot', 'Venue x timeslot')):
        a(f'\n## {n}. {title}\n')
        if key == 'by_timeslot':
            a('_Bins are Day before 1600, Twilight 1600 to 1829, Night 1830 '
              'and later, on the venue-local HHMM start time. Each row carries '
              'its own season range because the bins are not comparable across '
              'eras: every 1965-era match started at 1420 and lands in Day._\n')
        if key == 'by_venue_timeslot':
            a('_Cells with no matches are suppressed. A suppressed cell never '
              'existed rather than having been filtered out._\n')
        a(_table(rec[key]))
        a(_sources(rec[key]))
        a(_et_note(rec[key]))

    a('\n## 7. Same calendar date\n')
    if fixture_date is None:
        a('_Not computed. This section needs the scheduled fixture date, and '
          'inventing a reference date would fabricate the whole section. Pass '
          '`--date`._\n')
    else:
        a(f'_Meetings sharing day and month with {fixture_date}, any year. '
          f'Reported as a fact rather than a signal: an expected count of 0 to '
          f'3 across a century is noise unless read with its denominator._\n')
    a(_table(rec['same_calendar_date']))

    a('\n## 8. Quarter by quarter\n')
    a('_Regulation quarters, differenced from the cumulative scores. Extra '
      'time is not a quarter and is never folded into one._\n')
    a(_table(rec['by_quarter']))
    a(_sources(rec['by_quarter']))
    a(_et_note(rec['by_quarter']))

    a('\n## 9. Streaks\n')
    a(f'_Streaks compute on **all {len(stk["population"])} meetings** whatever '
      f'the scope. A final between two home and away results breaks '
      f'continuity, and excluding it manufactures a streak that never '
      f'happened. Finals exclusion is right for rates and wrong for counts._\n')
    a(f'_A loss breaks a run, a draw does not. Win streaks and non-loss '
      f'streaks are separate definitions and are never mixed. Archive floor '
      f'{FLOOR_SEASON}: say "since {FLOOR_SEASON}", never "ever"._\n')
    for label, key in (('Win streaks', 'win_streaks'),
                       ('Non-loss streaks', 'non_loss_streaks')):
        f = stk[key]
        a(f'\n### {label}\n')
        a(_table(f, cols=['basis', 'kind', 'length', 'composition', 'phrase',
                          'start_season', 'end_season', 'start_date',
                          'end_date', 'finals_in_window', 'suppressed',
                          'reason']))
        a(_et_note(f))
        if scope == 'ha':
            a('\n**Finals inside these streak windows.** Scope is `ha`, but '
              'streaks still count finals. Each one inside a window is named '
              'here so the inclusion is visible rather than assumed.\n')
            rows = []
            for _, r in f.iterrows():
                for d in (r.get('finals_detail') or []):
                    rows.append({'basis': r.basis, 'kind': r.kind, **d})
            a(_table(pd.DataFrame(rows)) if rows else
              '_No final falls inside any window on this definition._\n')

    a('\n## 10. Cross-opponent enumeration\n')
    live = stk['win_streaks']
    live_match = int(live[(live.basis == 'match') & (live.kind == 'live')].length.iloc[0])
    if live_match < LIVE_STREAK_TRIGGER:
        a(f'_Not run. The trigger is a live win streak of '
          f'{LIVE_STREAK_TRIGGER} or more on the match basis, and the live '
          f'streak is {live_match}. The trigger is a cost control and is '
          f'tunable._\n')
    else:
        cross = cross_opponent_streaks(subject, 'win', 'match', matches=table)
        cm = cross['meta'].iloc[0]
        a(f'_Live win streak of {live_match} reached the trigger of '
          f'{LIVE_STREAK_TRIGGER}. The full ranked table follows: every '
          f'opponent, no top-N and no minimum-meetings floor, because a '
          f'collection floor removes exactly the rows that would contest the '
          f'claim._\n')
        a(f'- Definition: **win streak**, basis **match**, one definition '
          f'throughout')
        a(f'- Denominator: **{int(cm.denominator)} opponents** enumerated')
        a(f'- Rank 1: **{cm.rank1_opponents}** on {int(cm.rank1_length)}')
        if cm.tied_at_rank1:
            a(f'- **Tied at rank 1.** Gap to rank 2 is 0 and this is NOT a '
              f'superlative. No tie is broken by recency, meetings or anything '
              f'else.')
        else:
            a(f'- Gap to rank 2: **{cm.gap_to_rank_2}**')
        a(f'- Archive floor {FLOOR_SEASON}: this ranks meetings since '
          f'{FLOOR_SEASON}, not in club history.\n')
        a(_table(cross['table'], cols=['rank', 'opponent', 'length',
                                       'composition', 'start_season',
                                       'end_season', 'meetings',
                                       'finals_in_window', 'note']))

    a('\n## 11. With and without\n')
    if not resolved:
        a('_Not run. Opt-in via `--without`, repeatable._\n')
    for player, cut in resolved:
        meta = cut['meta'].iloc[0]
        arms = cut['arms']
        a(f'\n### {meta.player}\n')
        a(f'- Identifier: `{meta.url}`')
        a(f'- fitzRoy ID: {meta.ID or "null, not yet minted"} '
          f'(traceability only; `url` is the key)')
        a(f'- Clubs on record: {meta.clubs_on_record}')
        a(f'- Tenure at {meta.tenure_club}: **{meta.tenure_first} to '
          f'{meta.tenure_last}**, {int(meta.tenure_games_for_club)} games of '
          f'{int(meta.career_games)} career')
        a(f'- Reconciles: {int(meta.with_n)} with plus {int(meta.without_n)} '
          f'without plus {int(meta.outside_n)} outside the window equals '
          f'{int(meta.series_meetings)} meetings\n')
        a(_table(arms, cols=['arm', 'wins', 'losses', 'draws', 'denominator',
                             'first_meeting', 'last_meeting', 'finals']))
        with_n = int(arms.loc[arms.arm == 'with', 'denominator'].iloc[0])
        without_n = int(arms.loc[arms.arm == 'without', 'denominator'].iloc[0])
        if with_n == 0 or without_n == 0:
            empty = 'with' if with_n == 0 else 'without'
            a(f'\n**No contrast available.** The `{empty}` arm has a '
              f'denominator of 0, so there is nothing to compare against and '
              f'this is a bare record rather than a with/without finding. The '
              f'numbers are printed above; the framing is withheld. Do not '
              f'write this as "{subject} are X with {meta.player}" as though a '
              f'comparator existed.\n')
        a(f'\n_{meta.availability_note}_\n')
        a(f'\n_No quarter-by-quarter breakdown on this cut._\n')

    a('\n---\n')
    a(f'_Facts only. No forward-looking claim appears above: this tool is '
      f'retrospective and touches no model output. Archive floor '
      f'{FLOOR_SEASON}._\n')

    run = {'subject': subject, 'opponent': opponent, 'scope': scope,
           'fixture_date': fixture_date, 'meetings': int(ov.denominator),
           'cuts_tested': cuts_tested, 'live_match_streak': live_match,
           'without': [p for p, _ in resolved]}
    return '\n'.join(L), run


def main(argv=None):
    p = argparse.ArgumentParser(
        description='Team-level head-to-head fixture preview, facts file only.')
    p.add_argument('--teams', nargs=2, required=True, metavar=('SUBJECT', 'OPPONENT'),
                   help='subject team first; every record is oriented to it')
    p.add_argument('--scope', default='all', choices=('all', 'ha', 'finals'))
    p.add_argument('--date', default=None,
                   help='scheduled fixture date, YYYY-MM-DD. Feeds section 7 '
                        'only; without it that section reports as not computed')
    p.add_argument('--without', action='append', default=[], metavar='PLAYER',
                   help='player name or afltables url, repeatable, opt-in')
    p.add_argument('--out-dir', default=OUT_DIR)
    args = p.parse_args(argv)

    subject, opponent = args.teams
    try:
        text, run = build_facts(subject, opponent, scope=args.scope,
                                fixture_date=args.date, without=args.without)
    except H2HError as exc:
        print(f'FAILED: {exc}', file=sys.stderr)
        return 1

    if text is None:
        # An ambiguous or unresolvable --without stops the run. The candidates
        # are printed so the caller can pass a url, and nothing is written.
        print(f'STOPPED: {run["message"]}', file=sys.stderr)
        cand = run.get('candidates')
        if cand is not None and not cand.empty:
            print(cand.to_string(index=False), file=sys.stderr)
        print('Nothing was written.', file=sys.stderr)
        return 2

    os.makedirs(args.out_dir, exist_ok=True)
    path = os.path.join(args.out_dir,
                        f'h2h_{_slug(subject)}_{_slug(opponent)}.md')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(text)
    print(f'wrote {path}')
    print(f'  {run["meetings"]} meetings, scope {run["scope"]}, '
          f'{run["cuts_tested"]} cells tested, live match streak '
          f'{run["live_match_streak"]}')
    if run['without']:
        print(f'  with/without: {", ".join(run["without"])}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
