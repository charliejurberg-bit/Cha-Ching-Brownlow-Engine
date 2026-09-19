"""Turn the weekly injury lists into a per-club injury ladder for a season.

    python scripts/build_injury_ladder.py                 # 2026
    python scripts/build_injury_ladder.py --season 2026

Reads the tracked `data_injury/injury_list_<season>.csv` written by
`scripts/fetch_injury_lists.py`, crosses it against who actually played, and
writes two tracked files:

    data_injury/injury_detail_<season>.csv   one row per player per round listed
    data_injury/injury_ladder_<season>.csv   one row per club

A GAME IS MISSED ONLY IF THE PLAYER WAS LISTED *AND* DID NOT PLAY
The published list is not a list of absentees. 686 of 2026's 3,760 entries read
"Test" as the estimated return and 265 of those players passed the test and
played. Counting the list alone charges those games to injury and inflates
every club that reports its doubtfuls diligently, which is a reporting artefact
rather than an injury toll. The cross-check against the archive is what makes
this an injury count.

NON-INJURY REASONS ARE DROPPED, BECAUSE SEPARATING THEM IS THE WHOLE POINT
The same table carries Suspension, Personal reasons, Managed and Unavailable:
100 entries in 2026. "Conditioning" (21) is kept as injury-adjacent; dropping
it moves no club more than one place.

THE ARCHIVE ONLY HOLDS PLAYERS WHO PLAYED, WHICH INVERTS THE USUAL NAME PROBLEM
A season-ending injury makes a player invisible to the stats file: Tom Green
reads "Knee / Season" every week of 2026 and appears in no row of
`afltables_2026.csv`. So an unmatched name is the EXPECTED case here, not an
error, and it cannot be waved through either, because a first-name variant
looks identical to it. `features.resolve_feed_names` runs first; whatever it
leaves is checked against the club's own season roster by surname, and accepted
only when exactly one roster player has that surname AND the first names pass
`first_names_compatible` or `first_names_aliased`. In 2026 that separated 22
real variants (Dan/Daniel, Ollie/Oliver, Harry/Harrison) from 99 genuine
never-played cases, and correctly refused West Coast's "Tylah Williams" against
a roster holding Bailey and Jack Williams.

EXPERIENCE IS WEIGHTED AT THE MOMENT OF THE ABSENCE, AND IS CONFOUNDED BY LIST AGE
`Experience_missed` weights each missed game by the player's career games then,
so a club's per-match figure reads as "games of experience missing from the
side each week": a 200-gamer out all year reads 200. It is the measure the
newspaper injury ladders use. It is ALSO the measure that stops correlating
with anything. On 2026, games missed runs r = -0.602 against wins (p = 0.008);
weighting by experience takes that to r = -0.039 (p = 0.88), because an
experienced list cannot lose anyone cheaply and a rebuilding one cannot lose
anyone expensively. North Melbourne top the experience ladder having lost
Jackson Archer (26 career games), Toby Pink (37) and George Wardlaw (52), and
finished 14th. Publish the experience figure as an experience figure. It does
not answer "who was hardest hit".

PLAYER IDENTITY IS THE fitzRoy ID, WHICH SURVIVES A CLUB CHANGE
Career games are summed by ID across all three archives, finals included,
because a career tally includes finals. The blank-ID rows in the current season
(92 in 2026, all recruits and debutants) are backfilled from the same
club-and-name rows that carry an ID, then from the historical archive by a
name that is unique league-wide (this is how Charlie Cameron, Jack Graham and
Jack Ross keep their careers), and only then fall back to club-plus-name for a
genuine debutant. Skipping that last hop is not harmless: Billy Wilson played
15 games for Carlton in 2026 under a blank ID, and without the fallback every
one of them reads as zero experience.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from features import (  # noqa: E402
    first_names_aliased, first_names_compatible, normalise_name, resolve_feed_names,
)

DATA_DIR = ROOT / 'data_injury'
HISTORY = ROOT / 'data_history' / 'fitzroy_stats_1965_2006.csv.gz'
ARCHIVE = ROOT / 'fitzroy_stats_all.csv'

NON_INJURY = {
    'suspension', 'suspended', 'personal reasons', 'managed', 'management',
    'unavailable',
}

# arty/arthur shares three characters against features.FIRST_NAME_PREFIX_MIN of
# four, and is not in features.FIRST_NAME_ALIASES because no model feed has
# needed it. Local to this feed rather than pushed into features.py, which the
# trained model depends on.
EXTRA_ALIASES = [{'arty', 'arthur'}]


def _aliased(a: str, b: str) -> bool:
    if first_names_aliased(a, b):
        return True
    return any(a in group and b in group for group in EXTRA_ALIASES)


def _load_stats(season: int) -> pd.DataFrame:
    path = ROOT / f'data_{season}' / f'afltables_{season}.csv'
    if not path.exists():
        raise SystemExit(f'missing {path.relative_to(ROOT)}')
    stats = pd.read_csv(path)
    stats['First.name'] = stats['First.name'].str.strip()
    stats['Surname'] = stats['Surname'].str.strip()
    stats['Player_Name'] = stats['First.name'] + ' ' + stats['Surname']
    stats['Round_num'] = stats['Round'].astype(int)
    stats['_n'] = stats['Player_Name'].map(normalise_name)
    return stats


def _merge_name_variants(stats: pd.DataFrame) -> tuple[dict, dict]:
    """Canonical map for one player listed under two first-name forms.

    Found rather than hardcoded: among rows with no ID, a club carrying two
    spellings of one surname whose first names are compatible is one player.
    Sydney's "Will Green" and "William Green" are the 2026 case, and left
    unmerged they count as two players and two careers.

    Returns (normalised -> normalised, normalised -> display name). The second
    is not decoration: the played-set is keyed on the display spelling, so
    merging only the lookup key leaves the two forms as two entries there and
    the result depends on which row `drop_duplicates` happened to keep.
    """
    canon: dict[str, str] = {}
    display: dict[str, str] = {}
    blank = stats[stats['ID'].isna()]
    for (_club, surname), group in blank.groupby(['Playing.for', 'Surname']):
        forms = sorted(set(group['First.name']), key=len)
        if len(forms) < 2:
            continue
        keep = forms[0]
        for other in forms[1:]:
            if first_names_compatible(keep.lower(), other.lower()) or _aliased(
                    keep.lower(), other.lower()):
                target = normalise_name(f'{keep} {surname}')
                canon[normalise_name(f'{other} {surname}')] = target
                display[target] = f'{keep} {surname}'
                print(f'  name variant merged: {other} {surname} -> {keep} {surname}')
    return canon, display


def _career_tables(stats: pd.DataFrame, canon: dict[str, str]):
    """Career games before the current season, plus a unique-name index."""
    cols = ['Season', 'ID', 'First.name', 'Surname']
    frames = []
    for path in (HISTORY, ARCHIVE):
        frame = pd.read_csv(path, usecols=cols, low_memory=False)
        frame['First.name'] = frame['First.name'].str.strip()
        frame['Surname'] = frame['Surname'].str.strip()
        frame['_n'] = (frame['First.name'] + ' ' + frame['Surname']).map(normalise_name)
        frames.append(frame)
    prior = pd.concat(frames, ignore_index=True)
    prior['_n'] = prior['_n'].replace(canon)
    games = prior.dropna(subset=['ID']).groupby('ID').size()
    by_name = prior.dropna(subset=['ID']).groupby('_n')['ID'].unique()
    unique = {n: v[0] for n, v in by_name.items() if len(v) == 1}
    ambiguous = {n for n, v in by_name.items() if len(v) > 1}
    return games, unique, ambiguous


def _season_keys(stats: pd.DataFrame, unique: dict):
    """One key per player for the current season. See the docstring's ID note."""
    lookup = (stats.dropna(subset=['ID']).drop_duplicates(['Playing.for', '_n'])
                   .set_index(['Playing.for', '_n'])['ID'])
    idx = pd.MultiIndex.from_frame(stats[['Playing.for', '_n']])
    stats['K'] = stats['ID'].fillna(pd.Series(idx.map(lookup), index=stats.index))
    stats['K'] = stats['K'].astype(object)
    gap = stats['K'].isna()
    stats.loc[gap, 'K'] = stats.loc[gap, '_n'].map(unique)
    gap = stats['K'].isna()
    stats.loc[gap, 'K'] = stats.loc[gap, 'Playing.for'] + '|' + stats.loc[gap, '_n']
    if stats['K'].isna().any():
        raise SystemExit('unkeyed rows in the season stats')
    return stats


def build(season: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    listed = pd.read_csv(DATA_DIR / f'injury_list_{season}.csv')
    stats = _load_stats(season)
    canon, display = _merge_name_variants(stats)
    stats['_n'] = stats['_n'].replace(canon)
    stats['Player_Name'] = stats['_n'].map(display).fillna(stats['Player_Name'])

    before = len(listed)
    listed = listed[~listed['Injury'].str.strip().str.lower().isin(NON_INJURY)].copy()
    print(f'  {before:,} entries -> {len(listed):,} after dropping '
          f'{before - len(listed)} non-injury')

    resolved, _ = resolve_feed_names(
        listed, stats, 'Player_as_published', 'Club', 'Round_num', label='injury list')

    games, unique, ambiguous = _career_tables(stats, canon)
    stats = _season_keys(stats, unique)
    played = set(zip(stats['Round_num'], stats['Playing.for'], stats['Player_Name']))
    club_key = (stats.drop_duplicates(['Playing.for', '_n'])
                     .set_index(['Playing.for', '_n'])['K'].to_dict())
    club_name = (stats.drop_duplicates(['Playing.for', '_n'])
                      .set_index(['Playing.for', '_n'])['Player_Name'].to_dict())

    # Surname index over each club's own season roster. This is the fallback
    # `resolve_feed_names` cannot supply here: its layer 2 is scoped to the
    # round, and a player absent that round is by definition not in it. Without
    # this hop "Dan Curtin" never reaches "Daniel Curtin", and he is then
    # counted as missing the rounds he actually played AND as having no career.
    roster: dict[tuple, list[tuple[str, str]]] = {}
    for club_, first, surname, full in stats[
            ['Playing.for', 'First.name', 'Surname', 'Player_Name']
    ].drop_duplicates().itertuples(index=False):
        roster.setdefault((club_, normalise_name(surname)), []).append(
            (first.lower(), full))

    season_games = stats.groupby(['K', 'Round_num']).size().rename('n').reset_index()
    running: dict[object, list[tuple[int, int]]] = {}
    for key, group in season_games.groupby('K'):
        group = group.sort_values('Round_num')
        running[key] = list(zip(group['Round_num'], group['n'].cumsum()))

    def played_before(key, rnd: int) -> int:
        total = 0
        for rn, cumulative in running.get(key, []):
            if rn < rnd:
                total = cumulative
            else:
                break
        return total

    cache: dict[tuple, tuple] = {}

    def resolve_player(club: str, player: str):
        """The club's own spelling of this player, or None if he never played.

        None is the expected answer for a season-ending injury, not a failure.
        """
        name = canon.get(normalise_name(player), normalise_name(player))
        if (club, name) in club_name:
            return club_name[(club, name)], name
        parts = player.split()
        if len(parts) >= 2:
            first = parts[0].lower()
            hits = [full for cand_first, full in roster.get(
                (club, normalise_name(parts[-1])), [])
                if first_names_compatible(first, cand_first) or _aliased(first, cand_first)]
            if len(hits) == 1:
                return hits[0], normalise_name(hits[0])
        return None, name

    def identify(club: str, player: str):
        full, name = resolve_player(club, player)
        if full is not None:
            return full, club_key[(club, name)], 'played this season'
        if name in unique:
            return player, unique[name], 'career, no game this season'
        if name in ambiguous:
            return player, None, 'AMBIGUOUS'
        return player, None, 'uncapped'

    rows = []
    for row in resolved.itertuples(index=False):
        ident = (row.Club, row.Player_as_published)
        if ident not in cache:
            cache[ident] = identify(*ident)
        name, key, source = cache[ident]
        missed = (row.Round_num, row.Club, name) not in played
        experience = 0 if key is None else (
            int(games.get(key, 0)) + played_before(key, row.Round_num))
        rows.append({
            'Round_num': row.Round_num, 'Club': row.Club,
            'Player': name, 'Injury': row.Injury,
            'Missed': missed, 'Career_games_at_time': experience,
            'Career_source': source,
        })

    detail = pd.DataFrame(rows).sort_values(['Club', 'Round_num', 'Player'])
    if (detail['Career_source'] == 'AMBIGUOUS').any():
        bad = detail[detail['Career_source'] == 'AMBIGUOUS'][['Club', 'Player']]
        raise SystemExit(f'ambiguous career names, resolve before writing:\n{bad}')

    hit = detail[detail['Missed']]
    ladder = (hit.groupby('Club')
                 .agg(Games_missed=('Missed', 'size'),
                      Players_injured=('Player', 'nunique'),
                      Experience_missed=('Career_games_at_time', 'sum'))
                 .reset_index())
    club_games = stats.groupby('Playing.for')['Round_num'].nunique()
    ladder['Club_games'] = ladder['Club'].map(club_games)
    ladder['Experience_per_match'] = (
        ladder['Experience_missed'] / ladder['Club_games']).round(0).astype(int)
    ladder['Players_used'] = ladder['Club'].map(stats.groupby('Playing.for')['K'].nunique())
    ladder['Games_missed_rank'] = ladder['Games_missed'].rank(method='min').astype(int)
    ladder['Experience_rank'] = ladder['Experience_missed'].rank(method='min').astype(int)
    ladder = ladder.sort_values('Games_missed').reset_index(drop=True)
    return detail, ladder


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--season', type=int, default=2026)
    args = ap.parse_args()

    print(f'Injury ladder, {args.season}')
    detail, ladder = build(args.season)

    # Refuse to write on a failed cross-check, the way
    # build_score_involvements.py refuses below its match rate.
    hit = detail[detail['Missed']]
    if len(ladder) != 18:
        raise SystemExit(f'{len(ladder)} clubs, expected 18')
    if int(hit['Career_games_at_time'].sum()) != int(ladder['Experience_missed'].sum()):
        raise SystemExit('experience total disagrees between detail and ladder')
    if int(hit['Missed'].sum()) != int(ladder['Games_missed'].sum()):
        raise SystemExit('games missed disagrees between detail and ladder')

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    d_out = DATA_DIR / f'injury_detail_{args.season}.csv'
    l_out = DATA_DIR / f'injury_ladder_{args.season}.csv'
    detail.to_csv(d_out, index=False)
    ladder.to_csv(l_out, index=False)

    print(f'\n  listed {len(detail):,} rows, {int(hit["Missed"].sum()):,} missed')
    print(f'  experience missed {int(ladder["Experience_missed"].sum()):,}')
    print(f'  -> {d_out.relative_to(ROOT)}')
    print(f'  -> {l_out.relative_to(ROOT)}\n')
    show = ladder[['Club', 'Games_missed', 'Players_injured',
                   'Experience_missed', 'Experience_per_match']]
    print(show.to_string(index=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
