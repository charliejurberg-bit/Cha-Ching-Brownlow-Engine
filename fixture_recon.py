"""Per-fixture player-level recon, scripted. The end state fixture_recon_spec.md asked for.

    python fixture_recon.py --teams "Geelong" "Richmond" --venue "Kardinia Park"

The first team named is the home club and the fixture is written home club
first. Output is a markdown recon file to drafts/, which is gitignored. It is
review material, not copy: no tweet is drafted here and nothing here is
post-ready.

Team-level records are NOT duplicated here. `team_h2h.py` owns those and writes
its own facts file. This covers the player-level blocks 1 to 8 only.

The spec's four open scoping questions are settled here, and the calls are
recorded so they can be argued with rather than rediscovered:

  - **Block 7 scope is career, not fixture.** A record earned at another club is
    still true, so the meeting count is the player's own across every club he
    played for, and the club split is printed beside it. A fixture-scoped count
    hides half of Tim Taranto's record against St Kilda.
  - **Block 6 groups on fitzRoy ID, never on name.** Two players have shared a
    name in this archive. The clubs the record was earned at are printed as a
    label rather than used as a grouping key.
  - **Club aliases are canonicalised through club_aliases.canonical_club().**
    `coaches_votes_all.csv` alone spells Geelong as "Geelong Cats", so block 4
    silently returns nothing without this.
  - **The current season is excluded from every career rate.** 2026 votes are
    not public until count night, so including the season would drag every
    career rate down for a reason that has nothing to do with the player.

Finals are excluded everywhere and the exclusion reconciles: rows in, finals
removed, rows out, reported per block. The archive labels finals with a string
round (QF, EF, SF, PF, GF); the 1990-2006 file holds home-and-away rounds only.
`coaches_votes_all.csv` numbers finals continuously, so it is filtered against
each season's own home-and-away ceiling instead.

The three-number rule from the spec preamble is enforced in the output: every
player-level record prints meetings PLAYED, polls, and zero-vote games as three
separate figures. A poll count is never printed in language implying a meeting
count. The one exemption is block 4, where the source holds rows only for
players who polled, so the denominator is unavailable and is reported as such.
"""

import argparse
import json
import os
import re
import sys

import pandas as pd

from club_aliases import canonical_club

OUT_DIR = 'drafts'


# `coaches_votes_all.csv` is the only file that spells clubs with their
# nickname attached, and `club_aliases.canonical_club()` does not know those
# forms: it returns "Geelong Cats" unchanged, which then matches nothing and
# empties block 4 without an error. Six clubs are affected. Kept local and
# explicit rather than widened in club_aliases, because three copies of the
# club-alias map already exist and a fourth shared one is worse than a narrow
# reader-specific fix. "Brisbane Lions" and "Western Bulldogs" are already
# canonical and must not be stripped, which is why this is a dict and not a
# suffix rule.
COACHES_CLUB = {
    'Adelaide Crows': 'Adelaide',
    'GWS Giants': 'Greater Western Sydney',
    'Geelong Cats': 'Geelong',
    'Gold Coast Suns': 'Gold Coast',
    'Sydney Swans': 'Sydney',
    'West Coast Eagles': 'West Coast',
}


def coaches_club(name):
    """Canonical club for a coaches-file spelling."""
    return canonical_club(COACHES_CLUB.get(str(name).strip(), name))



ARCHIVE = 'fitzroy_stats_all.csv'          # 2007-2025, full stat rows
HISTORY = 'data_history/brownlow_votes_1990_2006.csv'
COACHES = 'coaches_votes_all.csv'
CURRENT = 'predictions/game_level_2026.csv'

CURRENT_SEASON = 2026
FINALS_LABELS = ('QF', 'EF', 'SF', 'PF', 'GF')

# Five meetings is the floor a rate is quoted against anywhere in this repo's
# drafts. Below it the figure is printed with its meeting count beside it and
# never as a settled rate.
RATE_FLOOR = 5
VENUE_POLL_FLOOR = 6
TOP_N_2026 = 8

# draft_gate.py needs two rows before it will call a table a ranking.
MIN_TABLE_ROWS = 2


def _slug(s):
    return re.sub(r'[^a-z0-9]', '', str(s).lower())


def _label(name, pid):
    """Name with its fitzRoy ID. Two Gary Abletts sit in one fixture table."""
    return "{} (ID {})".format(name, int(pid))


def _is_final(round_value):
    return str(round_value).strip().upper() in FINALS_LABELS


def load_votes():
    """The 1990-2025 vote frame, finals removed, with the exclusion reconciled."""
    hist = pd.read_csv(HISTORY, low_memory=False)
    hist = hist.rename(columns={'Player': 'Name'})
    hist['Name'] = hist['Name'].astype(str)

    arch = pd.read_csv(ARCHIVE, low_memory=False)
    arch['Name'] = (arch['First.name'].astype(str) + ' '
                    + arch['Surname'].astype(str))

    cols = ['Season', 'Round', 'Venue', 'ID', 'Name', 'Playing.for',
            'Home.team', 'Away.team', 'Brownlow.Votes']
    frames, audit = [], []
    for label, df in (('history 1990-2006', hist), ('archive 2007-2025', arch)):
        rows_in = len(df)
        keep = ~df['Round'].map(_is_final)
        out = df.loc[keep, cols].copy()
        audit.append({'source': label, 'rows_in': rows_in,
                      'finals_excluded': int((~keep).sum()),
                      'rows_out': len(out)})
        frames.append(out)

    votes = pd.concat(frames, ignore_index=True)
    votes.attrs['finals_by_source'] = audit
    for c in ('Playing.for', 'Home.team', 'Away.team'):
        votes[c] = votes[c].map(canonical_club)
    votes['Brownlow.Votes'] = pd.to_numeric(votes['Brownlow.Votes'],
                                            errors='coerce')
    return votes, pd.DataFrame(audit)


def load_votes_with_finals():
    """The same 1990-2025 frame with finals still in, flagged.

    CHECK 5 wants each meeting-based rate to reconcile in its own unit, so a
    per-player, per-opponent finals count has to be available. The global audit
    counts player-game rows across the whole archive and cannot answer it.
    """
    hist = pd.read_csv(HISTORY, low_memory=False).rename(columns={'Player': 'Name'})
    arch = pd.read_csv(ARCHIVE, low_memory=False)
    arch['Name'] = (arch['First.name'].astype(str) + ' '
                    + arch['Surname'].astype(str))
    cols = ['Season', 'Round', 'Venue', 'ID', 'Name', 'Playing.for',
            'Home.team', 'Away.team', 'Brownlow.Votes']
    both = pd.concat([hist[cols], arch[cols]], ignore_index=True)
    for c in ('Playing.for', 'Home.team', 'Away.team'):
        both[c] = both[c].map(canonical_club)
    both['is_final'] = both['Round'].map(_is_final)
    both['Brownlow.Votes'] = pd.to_numeric(both['Brownlow.Votes'], errors='coerce')
    return both


def load_current():
    cur = pd.read_csv(CURRENT, low_memory=False)
    cur['Round_num'] = pd.to_numeric(cur['Round'], errors='coerce')
    cur = cur[cur['Round_num'].notna()].copy()
    for c in ('Playing.for', 'Home.team', 'Away.team'):
        if c in cur.columns:
            cur[c] = cur[c].map(canonical_club)
    return cur


def fixture_rows(votes, home, away):
    """Every player-game in meetings between the two clubs."""
    pair = {home, away}
    mask = (votes['Home.team'].isin(pair)) & (votes['Away.team'].isin(pair)) \
        & (votes['Home.team'] != votes['Away.team'])
    return votes[mask].copy()


def three_numbers(frame):
    """Meetings played, polls, zero-vote games, votes. The spec's rule."""
    played = len(frame)
    scored = frame['Brownlow.Votes'].notna()
    polls = int((frame['Brownlow.Votes'] > 0).sum())
    return {
        'meetings': played,
        'vote_eligible': int(scored.sum()),
        'polls': polls,
        'zeros': int(scored.sum()) - polls,
        'votes': float(frame['Brownlow.Votes'].sum(skipna=True)),
    }


# ─────────────────────────────────────────────────────────────
# Blocks
# ─────────────────────────────────────────────────────────────

def block1_active_streaks(cur, clubs, min_run=3, top_rank=3):
    """Runs of consecutive games ranked top `top_rank` by Exp_Votes in 2026.

    Consecutive APPEARANCES, not consecutive rounds. A round the player missed
    neither breaks the run nor extends it, so every row prints the rounds the
    run spans and how many of them he did not play, and whether the run is
    still open at his most recent appearance. Without those columns a run
    across a five-round absence reads the same as an unbroken one.
    """
    cur = cur.copy()
    cur['rank'] = cur.groupby(
        ['Round_num', 'Home.team', 'Away.team'])['Exp_Votes'].rank(
            ascending=False, method='min')
    sub = cur[cur['Playing.for'].isin(clubs)]
    rows = []
    for pid, g in sub.sort_values('Round_num').groupby('ID'):
        g = g.reset_index(drop=True)
        flags = (g['rank'] <= top_rank).tolist()
        best, best_end, run = 0, None, 0
        for k, f in enumerate(flags):
            run = run + 1 if f else 0
            if run > best:
                best, best_end = run, k
        if best < min_run:
            continue
        span = g.iloc[best_end - best + 1: best_end + 1]
        first_r, last_r = int(span['Round_num'].min()), int(span['Round_num'].max())
        rows.append({
            'ID': pid,
            'who': _label(g['Player_Name'].iloc[-1], pid),
            'club': g['Playing.for'].iloc[-1],
            'run': best,
            'rounds': "R{} to R{}".format(first_r, last_r),
            'missed': (last_r - first_r + 1) - best,
            'active': bool(best_end == len(g) - 1),
            'detail': "; ".join(
                "R{} v {} {:.2f} (rank {})".format(
                    int(r['Round_num']),
                    r['Away.team'] if r['Home.team'] == r['Playing.for']
                    else r['Home.team'],
                    r['Exp_Votes'], int(r['rank']))
                for _, r in span.iterrows()),
        })
    cols = ['ID', 'who', 'club', 'run', 'rounds', 'missed', 'active', 'detail']
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows).sort_values(['run', 'active'], ascending=False)


def block2_fixture_votes(fx, min_polls=2):
    """Actual Brownlow votes in this fixture, keyed on ID AND club."""
    rows = []
    for (pid, club), g in fx.groupby(['ID', 'Playing.for']):
        t = three_numbers(g)
        if t['polls'] < min_polls:
            continue
        detail = g[g['Brownlow.Votes'] > 0].sort_values(['Season', 'Round'])
        seasons = sorted(detail['Season'].astype(int).tolist())
        gaps = [b - a for a, b in zip(seasons, seasons[1:])]
        rows.append({
            'ID': pid, 'who': _label(g['Name'].iloc[0], pid), 'club': club, **t,
            'contiguous': all(gp <= 1 for gp in gaps) if gaps else True,
            'detail': "; ".join(
                "{} R{} {}v".format(int(r['Season']), r['Round'],
                                    int(r['Brownlow.Votes']))
                for _, r in detail.iterrows()),
        })
    out = pd.DataFrame(rows)
    if not len(out):
        return out
    return out.sort_values(['votes', 'polls'], ascending=False)


def block3_2026_meeting(cur, home, away):
    pair = {home, away}
    m = cur[(cur['Home.team'].isin(pair)) & (cur['Away.team'].isin(pair))
            & (cur['Home.team'] != cur['Away.team'])]
    if not len(m):
        return None, m
    return int(m['Round_num'].iloc[0]), m.nlargest(5, 'Exp_Votes')


def block4_coaches(home, away, votes):
    """Coaches votes in this fixture. Denominator unavailable, and says so."""
    cv = pd.read_csv(COACHES, low_memory=False)
    cv['Home.Team'] = cv['Home.Team'].map(coaches_club)
    cv['Away.Team'] = cv['Away.Team'].map(coaches_club)
    pair = {home, away}
    fx = cv[(cv['Home.Team'].isin(pair)) & (cv['Away.Team'].isin(pair))
            & (cv['Home.Team'] != cv['Away.Team'])].copy()
    rows_in = len(fx)

    # Finals are numbered continuously here, so each row is compared against
    # its own season's home-and-away ceiling taken from the vote archive.
    ceiling = votes.groupby('Season')['Round'].apply(
        lambda s: pd.to_numeric(s, errors='coerce').max())
    fx['rnum'] = pd.to_numeric(fx['Round'], errors='coerce')
    fx['ceiling'] = fx['Season'].map(ceiling)
    keep = fx['rnum'].notna() & (fx['rnum'] <= fx['ceiling'])
    kept = fx[keep].copy()

    # The 2020 duplication is per fixture, not season-wide: identical per-player
    # values repeated across consecutive rounds. Detected here, not assumed.
    dup = False
    y2020 = kept[kept['Season'] == 2020]
    if len(y2020):
        per = y2020.groupby(['Player.Name', 'Coaches.Votes'])['Round'].nunique()
        dup = bool((per > 1).any())

    scope = kept[kept['Season'] != 2020] if dup else kept
    agg = scope.groupby('Player.Name')['Coaches.Votes'].agg(
        polls='size', votes='sum').reset_index()
    return {
        'rows_in': rows_in,
        'finals_excluded': int((~keep).sum()),
        'rows_out': len(kept),
        'meetings': int(kept.groupby(['Season', 'Round']).ngroups) if len(kept) else 0,
        'dup_2020': dup,
        'table': agg.sort_values('votes', ascending=False).head(10),
        'season_min': int(kept['Season'].min()) if len(kept) else None,
        'season_max': int(kept['Season'].max()) if len(kept) else None,
    }


def block5_season_totals(cur, club, n=TOP_N_2026):
    sub = cur[cur['Playing.for'] == club]
    agg = sub.groupby(['ID', 'Player_Name']).agg(
        games=('Exp_Votes', 'size'), exp=('Exp_Votes', 'sum')).reset_index()
    return agg.nlargest(n, 'exp')


def block6_venue(votes, venue_strings, shortlist_ids):
    """Ground record, all opponents. Club-level list, then the per-player split."""
    at = votes[votes['Venue'].isin(venue_strings)].copy()
    per = []
    for pid, g in at.groupby('ID'):
        t = three_numbers(g)
        if t['polls'] >= VENUE_POLL_FLOOR or pid in shortlist_ids:
            per.append({'ID': pid, 'who': _label(g['Name'].iloc[0], pid),
                        'clubs': ", ".join(sorted(set(g['Playing.for']))), **t})
    out = pd.DataFrame(per)
    if not len(out):
        return at, out
    return at, out.sort_values('votes', ascending=False)


def block7_droughts(votes, opponent, ids):
    """Career record against this opponent for a set of players."""
    rows = []
    for pid in ids:
        g = votes[votes['ID'] == pid]
        opp = g[((g['Home.team'] == opponent) | (g['Away.team'] == opponent))
                & (g['Playing.for'] != opponent)]
        if not len(opp):
            rows.append({'ID': pid, 'who': None, 'meetings': 0,
                         'vote_eligible': 0, 'polls': 0, 'zeros': 0,
                         'votes': 0.0, 'clubs': '', 'last_poll': None})
            continue
        t = three_numbers(opp)
        scored = opp[opp['Brownlow.Votes'] > 0].sort_values(['Season', 'Round'])
        rows.append({
            'ID': pid, 'who': _label(opp['Name'].iloc[0], pid), **t,
            'clubs': ", ".join(sorted(set(opp['Playing.for']))),
            'last_poll': "{} {}v".format(
                int(scored['Season'].iloc[-1]),
                int(scored['Brownlow.Votes'].iloc[-1])) if len(scored) else None,
        })
    return pd.DataFrame(rows)


def block8_deep_dive(votes, pid, opponent, venue_strings):
    """The player's own baseline, and where this opponent and ground sit in it."""
    g = votes[votes['ID'] == pid]
    if not len(g):
        return None
    career = three_numbers(g)
    career['vpg'] = (career['votes'] / career['vote_eligible']
                     if career['vote_eligible'] else 0.0)

    by_opp = []
    for opp in sorted(set(g['Home.team']) | set(g['Away.team'])):
        sub = g[((g['Home.team'] == opp) | (g['Away.team'] == opp))
                & (g['Playing.for'] != opp)]
        if not len(sub):
            continue
        t = three_numbers(sub)
        by_opp.append({'opponent': opp, **t,
                       'vpg': t['votes'] / t['vote_eligible']
                       if t['vote_eligible'] else 0.0})
    opp_tbl = pd.DataFrame(by_opp)
    if len(opp_tbl):
        opp_tbl = opp_tbl[opp_tbl['meetings'] >= RATE_FLOOR].sort_values(
            'vpg', ascending=False)

    by_venue = []
    for v, sub in g.groupby('Venue'):
        t = three_numbers(sub)
        by_venue.append({'venue': v, **t,
                         'vpg': t['votes'] / t['vote_eligible']
                         if t['vote_eligible'] else 0.0})
    ven_tbl = pd.DataFrame(by_venue)
    if len(ven_tbl):
        ven_tbl = ven_tbl[ven_tbl['meetings'] >= RATE_FLOOR].sort_values(
            'vpg', ascending=False)

    at_opp = g[((g['Home.team'] == opponent) | (g['Away.team'] == opponent))
               & (g['Playing.for'] != opponent)]
    at_ven = g[g['Venue'].isin(venue_strings)]
    comp = {
        'opponent_split': at_opp[at_opp['Brownlow.Votes'] > 0][
            'Brownlow.Votes'].value_counts().sort_index().to_dict(),
        'venue_split': at_ven[at_ven['Brownlow.Votes'] > 0][
            'Brownlow.Votes'].value_counts().sort_index().to_dict(),
        'clubs': sorted(set(g['Playing.for'])),
    }
    return {'career': career, 'by_opponent': opp_tbl, 'by_venue': ven_tbl,
            'composition': comp, 'name': _label(g['Name'].iloc[0], pid)}



# ─────────────────────────────────────────────────────────────
# Facts file for draft_gate.py
# ─────────────────────────────────────────────────────────────

# The direction matters. These entries are computed from the source frames, not
# scraped back out of a draft, so the gate is checking copy against data rather
# than against itself. Copy is written to match this file; this file is never
# written to match copy.

def build_facts_json(home, away, venue_strings, venue_label, round_num,
                     raw_round):
    votes, audit = load_votes()
    raw = load_votes_with_finals()
    cur = load_current()
    clubs = [home, away]
    fx = fixture_rows(votes, home, away)
    top = {c: block5_season_totals(cur, c) for c in clubs}
    shortlist = sorted(set(top[home]['ID']) | set(top[away]['ID']))

    rates, totals, ranked = [], [], []

    def subj(name, tail):
        return "{} {}".format(name, tail)

    # Fixture-wide totals.
    meetings = int(fx.groupby(['Season', 'Round']).ngroups)
    fixture_name = "{} v {} meetings".format(home, away)
    totals.append({'subject': fixture_name, 'value': meetings,
                   'source_file': ARCHIVE})
    totals.append({'subject': "{} v {} total Brownlow votes".format(home, away),
                   'value': float(fx['Brownlow.Votes'].sum(skipna=True)),
                   'source_file': ARCHIVE})

    for pid in shortlist:
        g = votes[votes['ID'] == pid]
        row2026 = cur[cur['ID'] == pid]
        name = (row2026['Player_Name'].iloc[0] if len(row2026)
                else (g['Name'].iloc[0] if len(g) else str(pid)))
        club = row2026['Playing.for'].iloc[0] if len(row2026) else None
        opp = away if club == home else home

        # 2026 side. A count, never a rate: these are model expectations and a
        # per-game average of them is not a vote rate.
        if len(row2026):
            totals.append({'subject': subj(name, "2026 games"),
                           'value': int(len(row2026)), 'source_file': CURRENT})
            totals.append({'subject': subj(name, "2026 expected votes"),
                           'value': round(float(row2026['Exp_Votes'].sum()), 2),
                           'source_file': CURRENT})

        if not len(g):
            continue

        c = three_numbers(g)
        for label, value in (("career vote-eligible games", c['vote_eligible']),
                             ("career polls", c['polls']),
                             ("career zero-vote games", c['zeros']),
                             ("career Brownlow votes", c['votes'])):
            totals.append({'subject': subj(name, label), 'value': value,
                           'source_file': ARCHIVE})
        if c['vote_eligible']:
            rates.append({
                'subject': subj(name, "career Brownlow votes per game"),
                'value': round(c['votes'] / c['vote_eligible'], 2),
                'denominator': c['vote_eligible'],
                'denominator_type': 'vote_eligible_games',
                'source_file': ARCHIVE})

        # Against this opponent.
        o = g[((g['Home.team'] == opp) | (g['Away.team'] == opp))
              & (g['Playing.for'] != opp)]
        if len(o):
            t = three_numbers(o)
            for label, value in (
                    ("meetings with {}".format(opp), t['meetings']),
                    ("polls against {}".format(opp), t['polls']),
                    ("zero-vote meetings with {}".format(opp), t['zeros']),
                    ("Brownlow votes against {}".format(opp), t['votes'])):
                totals.append({'subject': subj(name, label), 'value': value,
                               'source_file': ARCHIVE})
            if t['vote_eligible']:
                raw_opp = raw[(raw['ID'] == pid)
                              & ((raw['Home.team'] == opp)
                                 | (raw['Away.team'] == opp))
                              & (raw['Playing.for'] != opp)]
                dropped = int(raw_opp['is_final'].sum())
                rates.append({
                    'subject': subj(name, "votes per game against {}".format(opp)),
                    'value': round(t['votes'] / t['vote_eligible'], 2),
                    'denominator': t['vote_eligible'],
                    'denominator_type': 'matches_between_clubs',
                    'rows_in': int(len(raw_opp)),
                    'finals_excluded': dropped,
                    'rows_out': int(len(raw_opp)) - dropped,
                    'source_file': ARCHIVE})

        # At the ground.
        vroom = g[g['Venue'].isin(venue_strings)]
        if len(vroom):
            t = three_numbers(vroom)
            for label, value in (
                    ("games at {}".format(venue_label), t['meetings']),
                    ("polls at {}".format(venue_label), t['polls']),
                    ("Brownlow votes at {}".format(venue_label), t['votes'])):
                totals.append({'subject': subj(name, label), 'value': value,
                               'source_file': ARCHIVE})
            if t['vote_eligible']:
                rates.append({
                    'subject': subj(name, "votes per game at {}".format(venue_label)),
                    'value': round(t['votes'] / t['vote_eligible'], 2),
                    'denominator': t['vote_eligible'],
                    'denominator_type': 'vote_eligible_games',
                    'source_file': ARCHIVE})

        # The opponent table the rates are read against.
        d = block8_deep_dive(votes, pid, opp, venue_strings)
        if d is not None and len(d['by_opponent']) >= MIN_TABLE_ROWS:
            ranked.append({
                'subject': subj(name, "opponents faced {} or more times".format(
                    RATE_FLOOR)),
                'window': "home and away, 1990 to {}, {} excluded".format(
                    CURRENT_SEASON - 1, CURRENT_SEASON),
                'rows': [{'opponent': r['opponent'],
                          'meetings': int(r['meetings']),
                          'polls': int(r['polls']),
                          'zeros': int(r['zeros']),
                          'votes': float(r['votes']),
                          'votes_per_game': round(float(r['vpg']), 2)}
                         for _, r in d['by_opponent'].iterrows()]})
        if d is not None and len(d['by_venue']) >= MIN_TABLE_ROWS:
            ranked.append({
                'subject': subj(name, "grounds played {} or more times".format(
                    RATE_FLOOR)),
                'window': "home and away, 1990 to {}, {} excluded".format(
                    CURRENT_SEASON - 1, CURRENT_SEASON),
                'rows': [{'venue': r['venue'],
                          'meetings': int(r['meetings']),
                          'polls': int(r['polls']),
                          'votes': float(r['votes']),
                          'votes_per_game': round(float(r['vpg']), 2)}
                         for _, r in d['by_venue'].iterrows()]})

    # Block 1 belongs in the facts too. Its round numbers are figures the copy
    # prints, and a round number outside the 1990-2026 year exemption has no
    # other entry that could carry it.
    b1 = block1_active_streaks(cur, clubs)
    if len(b1) >= MIN_TABLE_ROWS:
        ranked.append({
            'subject': "{} v {} top-three exp runs".format(home, away),
            'window': "2026 home and away to raw Round {}".format(raw_round - 1),
            'rows': [{'player': r['who'], 'club': r['club'], 'run': int(r['run']),
                      'rounds': r['rounds'], 'missed': int(r['missed']),
                      'still_open': bool(r['active'])}
                     for _, r in b1.iterrows()]})
    elif len(b1) == 1:
        r = b1.iloc[0]
        totals.append({'subject': "{} top-three exp run".format(r['who']),
                       'value': "{} games, {}, {} missed".format(
                           int(r['run']), r['rounds'], int(r['missed'])),
                       'source_file': CURRENT})

    # The fixture's own all-time vote list.
    b2 = block2_fixture_votes(fx, min_polls=1)
    if len(b2) >= MIN_TABLE_ROWS:
        ranked.append({
            'subject': "{} v {} vote leaders".format(home, away),
            'window': "home and away, 1990 to {}".format(CURRENT_SEASON - 1),
            'rows': [{'player': r['who'], 'club': r['club'],
                      'meetings': int(r['meetings']), 'polls': int(r['polls']),
                      'votes': float(r['votes'])}
                     for _, r in b2.head(10).iterrows()]})

    # Each club's 2026 order, so a "leads the club" line has a table behind it.
    for c in clubs:
        ranked.append({
            'subject': "{} 2026 expected-vote order".format(c),
            'window': "2026 home and away to raw Round {}".format(raw_round - 1),
            'rows': [{'player': r['Player_Name'], 'games': int(r['games']),
                      'expected_votes': round(float(r['exp']), 2)}
                     for _, r in top[c].iterrows()]})

    # The finals arithmetic has to be sourceable as prose figures too, not
    # just carried in the top-level finals block, which facts_entries does not
    # read. Subject carries the fixture name so a sentence or heading naming
    # the fixture attributes them.
    fixture_label = "{} v {}".format(home, away)
    for _, r in audit.iterrows():
        for field, tail in (('rows_in', 'rows read'),
                            ('finals_excluded', 'finals rows removed'),
                            ('rows_out', 'rows kept')):
            totals.append({
                'subject': "{} {} from the {} file".format(
                    fixture_label, tail, r['source']),
                'value': int(r[field]), 'source_file': ARCHIVE})

    finals = [{'rows_in': int(r['rows_in']),
               'finals_excluded': int(r['finals_excluded']),
               'rows_out': int(r['rows_out'])} for _, r in audit.iterrows()]

    return {
        'fixture': "{} v {}".format(home, away),
        'round': round_num,
        'raw_round': raw_round,
        'venue': venue_label,
        'source_files': [HISTORY, ARCHIVE, CURRENT, COACHES],
        'finals': finals,
        'totals': totals,
        'rates': rates,
        'ranked_tables': ranked,
    }

# ─────────────────────────────────────────────────────────────
# Rendering
# ─────────────────────────────────────────────────────────────

def _tbl(df, cols=None, limit=None):
    """A markdown table from a frame, or a one-line statement that it is empty."""
    if df is None or not len(df):
        return ["_Nothing qualifies._", ""]
    d = df if cols is None else df[cols]
    d = d if limit is None else d.head(limit)
    head = "| " + " | ".join(str(c) for c in d.columns) + " |"
    sep = "|" + "|".join("---" for _ in d.columns) + "|"
    out = [head, sep]
    for _, r in d.iterrows():
        cells = []
        for v in r:
            if isinstance(v, float):
                cells.append("n/a" if pd.isna(v) else "{:g}".format(round(v, 2)))
            else:
                cells.append("n/a" if v is None or (isinstance(v, float) and pd.isna(v))
                             else str(v))
        out.append("| " + " | ".join(cells) + " |")
    out.append("")
    return out


def render(home, away, venue_strings, venue_label):
    votes, audit = load_votes()
    cur = load_current()
    clubs = [home, away]

    fx = fixture_rows(votes, home, away)
    meetings = int(fx.groupby(['Season', 'Round']).ngroups)

    top = {c: block5_season_totals(cur, c) for c in clubs}
    shortlist = sorted(set(top[home]['ID']) | set(top[away]['ID']))

    L = []
    a = L.append
    a("# Fixture recon: {} v {}".format(home, away))
    a("")
    a("**Home club:** {}. **Ground:** {}, stored as {}.".format(
        home, venue_label, ", ".join("`{}`".format(v) for v in venue_strings)))
    a("")
    a("Everything here is retrospective. Nothing projects, and nothing comments "
      "on the upcoming game. This is review material, not copy.")
    a("")

    a("## Standing scope")
    a("")
    a("- Sources: `{}` concatenated with `{}` for every career and fixture "
      "figure, `{}` for expected votes, `{}` for coaches votes.".format(
          HISTORY, ARCHIVE, CURRENT, COACHES))
    a("- Grouped on fitzRoy `ID`, never on name.")
    a("- Clubs canonicalised through `club_aliases.canonical_club()`.")
    a("- Every career rate excludes {}, because this season's votes are not "
      "public until count night.".format(CURRENT_SEASON))
    a("- Votes per game is computed over vote-eligible games. An unscored game "
      "is null in both archives, so it is dropped rather than counted as a zero.")
    a("- Every player-level record prints meetings played, polls and zero-vote "
      "games as three separate figures.")
    a("")
    a("**Finals excluded, and the exclusion reconciles.**")
    a("")
    L += _tbl(audit)

    a("## Check A, team naming")
    a("")
    for c in clubs:
        seen = {}
        for label, path, cols in (
                ('archive', ARCHIVE, ['Playing.for']),
                ('history', HISTORY, ['Playing.for']),
                ('coaches', COACHES, ['Home.Team', 'Away.Team'])):
            df = pd.read_csv(path, low_memory=False, usecols=cols)
            vals = set()
            for col in cols:
                norm = coaches_club if label == 'coaches' else canonical_club
                vals |= {v for v in df[col].dropna().unique()
                         if norm(v) == c}
            seen[label] = sorted(vals)
        a("- **{}**: ".format(c) + "; ".join(
            "{} {}".format(k, v) for k, v in seen.items()))
    a("")
    a("Matched on the canonical form, never as a substring. A substring match "
      "on Melbourne pulls North Melbourne, and Geelong is spelled Geelong Cats "
      "in the coaches file alone.")
    a("")

    a("## Check B, venue strings")
    a("")
    for v in venue_strings:
        at = votes[votes['Venue'] == v]
        a("- `{}`: {} to {}, {:,} player-game rows.".format(
            v, int(at['Season'].min()), int(at['Season'].max()), len(at)))
    a("")

    rnd, meet = block3_2026_meeting(cur, home, away)
    a("## Check C, {} meeting".format(CURRENT_SEASON))
    a("")
    if rnd is None:
        a("The two clubs have **not met in {}**. Block 3 is empty and this is "
          "their first meeting of the season.".format(CURRENT_SEASON))
    else:
        host = meet['Home.team'].iloc[0]
        a("Met once, raw Round_num {}, {} hosting at {}.".format(
            rnd, host, meet['Venue'].iloc[0]))
    a("")

    a("## Block 1, active streaks in {}".format(CURRENT_SEASON))
    a("")
    b1 = block1_active_streaks(cur, clubs)
    if not len(b1):
        a("**No player at either club** has a run of three or more consecutive "
          "games ranked inside the top three by `Exp_Votes`. Stated explicitly "
          "because an empty block and an unrun block look the same.")
        a("")
    else:
        L += _tbl(b1, ['who', 'club', 'run', 'rounds', 'missed',
                       'active', 'detail'])

    a("## Block 2, actual Brownlow votes in this fixture")
    a("")
    a("{} meetings between the clubs in the archive window, {} to {}. Players "
      "with two or more polls, keyed on ID and club so a player who has "
      "appeared for both sides prints one row per club.".format(
          meetings, int(fx['Season'].min()) if len(fx) else 0,
          int(fx['Season'].max()) if len(fx) else 0))
    a("")
    b2 = block2_fixture_votes(fx)
    L += _tbl(b2, ['who', 'club', 'meetings', 'polls', 'zeros', 'votes',
                   'contiguous', 'detail'], limit=15)

    a("## Block 3, expected votes in the {} meeting".format(CURRENT_SEASON))
    a("")
    if rnd is None:
        a("_No meeting this season, so there is nothing to report._")
        a("")
    else:
        L += _tbl(meet[['Player_Name', 'Playing.for', 'Disposals', 'Goals',
                        'Coaches_Votes', 'Exp_Votes']])

    a("## Block 4, coaches votes in this fixture")
    a("")
    b4 = block4_coaches(home, away, votes)
    a("`{}` holds a row only for a player who polled, so meetings played and "
      "zero-vote games are **not derivable** from it. Totals and poll counts "
      "only; the denominator is unavailable rather than inferred.".format(COACHES))
    a("")
    a("{} rows read, {} finals removed against each season's own home-and-away "
      "ceiling, {} kept, covering {} meetings, {} to {}.".format(
          b4['rows_in'], b4['finals_excluded'], b4['rows_out'], b4['meetings'],
          b4['season_min'], b4['season_max']))
    a("")
    a("2020 duplication check, run against this fixture's rows specifically: "
      + ("**present**, so 2020 is excluded." if b4['dup_2020'] else
         "**not present**, so 2020 is kept."))
    a("")
    L += _tbl(b4['table'])

    a("## Block 5, {} expected-vote totals, top {} per club".format(
        CURRENT_SEASON, TOP_N_2026))
    a("")
    for c in clubs:
        a("**{}**".format(c))
        a("")
        L += _tbl(top[c], ['Player_Name', 'games', 'exp'])

    a("## Block 6, record at {}".format(venue_label))
    a("")
    at, b6 = block6_venue(votes, venue_strings, set(shortlist))
    a("{:,} player-game rows at the ground, {} to {}, all opponents. Listed: "
      "every player with {} or more polls there, plus every player in either "
      "club's {} top {} regardless of poll count.".format(
          len(at), int(at['Season'].min()) if len(at) else 0,
          int(at['Season'].max()) if len(at) else 0, VENUE_POLL_FLOOR,
          CURRENT_SEASON, TOP_N_2026))
    a("")
    L += _tbl(b6, ['who', 'clubs', 'meetings', 'polls', 'zeros', 'votes'],
              limit=20)

    a("## Block 7, record against this opponent, {} top {} of each club".format(
        CURRENT_SEASON, TOP_N_2026))
    a("")
    a("Career scope, not fixture scope: a record earned at another club is "
      "still true, so the club column names every club the meetings were "
      "played at.")
    a("")
    for club, opp in ((home, away), (away, home)):
        a("**{} players, against {}**".format(club, opp))
        a("")
        b7 = block7_droughts(votes, opp, top[club]['ID'].tolist())
        b7 = b7.merge(top[club][['ID', 'Player_Name']], on='ID', how='left')
        b7['who'] = b7['who'].fillna(b7['Player_Name'])
        L += _tbl(b7, ['who', 'clubs', 'meetings', 'polls', 'zeros', 'votes',
                       'last_poll'])
        flagged = b7[(b7['meetings'] >= 3) & (b7['polls'] == 0)]
        if len(flagged):
            a("Three or more meetings and no career poll against {}: {}.".format(
                opp, ", ".join(str(w) for w in flagged['who'])))
            a("")

    a("## Check D, roster")
    a("")
    named = set(b2['ID']) | set(b6['ID'] if len(b6) else []) | set(shortlist)
    now_club = cur.drop_duplicates('ID').set_index('ID')['Playing.for'].to_dict()
    absent, moved = [], []
    hist_club = {}
    for pid, g in votes[votes['ID'].isin(named)].groupby('ID'):
        hist_club[pid] = g.sort_values('Season')['Playing.for'].iloc[-1]
    names = {}
    for pid, g in votes[votes['ID'].isin(named)].groupby('ID'):
        names[pid] = g['Name'].iloc[0]
    for pid in sorted(named):
        if pid not in now_club:
            absent.append(names.get(pid, str(pid)))
        elif pid in hist_club and now_club[pid] != hist_club[pid]:
            moved.append("{} ({} then, {} now)".format(
                names.get(pid, pid), hist_club[pid], now_club[pid]))
    a("{} players named above. **Absent from `{}`**, so retired or delisted: "
      "{}.".format(len(named), CURRENT, ", ".join(absent) if absent else "none"))
    a("")
    a("**At a different club than their archive record shows**, so any copy "
      "must name both: {}.".format(", ".join(moved) if moved else "none"))
    a("")

    a("## Block 8, deep dive on the {} shortlist".format(len(shortlist)))
    a("")
    a("Run on every player in either club's {} top {}. A fixture record means "
      "nothing until it is read against the player's own baseline, so each "
      "player's career rate and the rank of this opponent and this ground "
      "within his own distribution are printed together.".format(
          CURRENT_SEASON, TOP_N_2026))
    a("")
    for pid in shortlist:
        opp = away if pid in set(top[home]['ID']) else home
        d = block8_deep_dive(votes, pid, opp, venue_strings)
        label = cur[cur['ID'] == pid]['Player_Name']
        label = label.iloc[0] if len(label) else str(pid)
        a("### {}".format(d['name'] if d else label))
        a("")
        if d is None:
            a("_No archive rows before {}, so there is no career baseline to "
              "read anything against. Any figure about this player is a "
              "{}-only figure._".format(CURRENT_SEASON, CURRENT_SEASON))
            a("")
            continue
        c = d['career']
        a("Career, home and away, {} excluded: {} games, {} vote-eligible, {} "
          "polls, {} zero-vote games, {:g} votes, {:.2f} per vote-eligible "
          "game. Clubs: {}.".format(
              CURRENT_SEASON, c['meetings'], c['vote_eligible'], c['polls'],
              c['zeros'], c['votes'], c['vpg'], ", ".join(d['composition']['clubs'])))
        a("")
        ot = d['by_opponent']
        if len(ot):
            hit = ot[ot['opponent'] == opp]
            if len(hit):
                rank = int(ot.reset_index(drop=True).index[
                    ot.reset_index(drop=True)['opponent'] == opp][0]) + 1
                a("Against **{}**: {} meetings, {} polls, {} zeros, {:g} votes, "
                  "{:.2f} per game, which is {} of the {} opponents faced {} or "
                  "more times.".format(
                      opp, int(hit['meetings'].iloc[0]), int(hit['polls'].iloc[0]),
                      int(hit['zeros'].iloc[0]), hit['votes'].iloc[0],
                      hit['vpg'].iloc[0], rank, len(ot), RATE_FLOOR))
            else:
                a("Against **{}**: fewer than {} meetings, so the opponent does "
                  "not clear the rate floor and no rate is quoted.".format(
                      opp, RATE_FLOOR))
            a("")
        vt = d['by_venue']
        if len(vt):
            hit = vt[vt['venue'].isin(venue_strings)]
            if len(hit):
                rank = int(vt.reset_index(drop=True).index[
                    vt.reset_index(drop=True)['venue'].isin(venue_strings)][0]) + 1
                a("At **{}**: {} games, {} polls, {:g} votes, {:.2f} per game, "
                  "{} of the {} grounds played {} or more times.".format(
                      venue_label, int(hit['meetings'].iloc[0]),
                      int(hit['polls'].iloc[0]), hit['votes'].iloc[0],
                      hit['vpg'].iloc[0], rank, len(vt), RATE_FLOOR))
            else:
                a("At **{}**: fewer than {} games, so the ground does not clear "
                  "the rate floor.".format(venue_label, RATE_FLOOR))
            a("")
        a("Vote composition against {}: {}. At {}: {}.".format(
            opp, d['composition']['opponent_split'] or "no polls",
            venue_label, d['composition']['venue_split'] or "no polls"))
        a("")

    return L


def main(argv=None):
    p = argparse.ArgumentParser(
        description='Per-fixture player-level recon, blocks 1 to 8.')
    p.add_argument('--teams', nargs=2, required=True,
                   metavar=('HOME', 'AWAY'))
    p.add_argument('--venue', nargs='+', required=True,
                   help='every archive venue string for the ground')
    p.add_argument('--venue-label', default=None)
    p.add_argument('--round', type=int, default=24,
                   help='AFL display round for the fixture')
    p.add_argument('--raw-round', type=int, default=25,
                   help='AFLTables raw Round_num for the fixture')
    p.add_argument('--out-dir', default=OUT_DIR)
    args = p.parse_args(argv)

    home, away = (canonical_club(t) for t in args.teams)
    label = args.venue_label or args.venue[0]
    L = render(home, away, list(args.venue), label)

    os.makedirs(args.out_dir, exist_ok=True)
    path = os.path.join(args.out_dir, "recon_{}_{}.md".format(
        _slug(home), _slug(away)))
    with open(path, 'w', encoding='utf-8') as f:
        f.write("\n".join(L).rstrip() + "\n")
    print("wrote {} ({} lines)".format(path, len(L)))

    facts = build_facts_json(home, away, list(args.venue), label,
                             args.round, args.raw_round)
    fpath = os.path.join(args.out_dir, "preview_{}_{}.facts.json".format(
        _slug(home), _slug(away)))
    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(facts, f, indent=2)
    print("wrote {} ({} total(s), {} rate(s), {} ranked table(s))".format(
        fpath, len(facts['totals']), len(facts['rates']),
        len(facts['ranked_tables'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
