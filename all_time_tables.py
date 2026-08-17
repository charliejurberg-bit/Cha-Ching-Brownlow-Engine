"""All-time Brownlow vote tables, 1984-2025, from the two fitzRoy archives.

Three builders, each writing one markdown table under drafts/:

    build_pair_season_totals   teammate pairs by combined votes in a club-season
    build_club_season_totals   total votes by club-season
    build_three_vote_games     count of 3-vote games per player-season

RECON / DRAFT OUTPUT ONLY. Like club_aliases, this module must not be imported
by features.py, brownlow_model.py or predict_2026.py: it canonicalises club
strings, which would change the model's feature space without a retrain.

Why the floor is 1984 and not earlier
-------------------------------------
1984 is the earliest season any vote data can be sourced for, measured rather
than assumed. In `fitzroy_stats_1965_2006.csv.gz` every season from 1965 to
1983 carries a `Brownlow.Votes` column that is blank on all 100,560 rows, and
1984 is the first season populated. That boundary is fitzRoy's own coverage and
not an artifact of how the local file was built: a live
`fetch_player_stats_afltables(1983)` returns 5,520 rows with zero non-NA votes
while 1984 returns 5,280 voted rows. `fetch_player_stats_fryzigg` agrees, and
`fetch_awards_brownlow` returns the literal string "No Data Found" for any
pre-1984 season. Stats and player IDs do reach back to at least 1935; votes do
not.

Every season from 1984 on is a clean 3-2-1: across 1984-2006 the only vote
values present are {0,1,2,3} with exactly 3,769 rows of each, one 3, one 2 and
one 1 per home-and-away game with no exceptions.

The two sources
---------------
  data_history/fitzroy_stats_1965_2006.csv.gz, sliced to Season >= 1984
      81 columns, seasons 1965-2006 in the file, 1984-2006 after the slice.
      `Brownlow.Votes` is blank on finals rows and 0 on played-but-unvoted
      rows. This replaces the data_history/game_level_1990.csv .. _2006.csv
      family as a source. Those files are left on disk and are still read by
      other modules; nothing here touches them.

  fitzroy_stats_all.csv
      The same 81 columns, seasons 2007-2025. `Brownlow.Votes` NaN on the 7,658
      finals rows, 0 on played-but-unvoted rows.

Both therefore share one encoding: NaN or blank means "finals, no votes
awarded", and 0 means "home-and-away game, played, polled nothing".

The trap: `Brownlow.Votes != 0` admits every finals row, because NaN compares
unequal to 0. Finals are therefore dropped on the Round coercion and the vote
test is `> 0`, never `!= 0`. Same NaN-vs-zero failure mode CLAUDE.md records
for the coaches routing predicate.

Guards
------
The season ranges must not overlap (1984-2006 against 2007-2025) or a game is
counted twice, and every season from 1984 to 2025 must be present or a table
is silently short. Both raise. Two arithmetic invariants also raise: total
votes must equal 6 x the game count, and the count of 3-vote rows must equal
the game count. Those catch a contaminated round, a finals row that slipped
the coercion, and an unplayed season appended to the newer file.

Player identity is keyed on `ID`, never on name: several name strings in each
family resolve to more than one ID, and the counts are measured at load time
rather than hardcoded here. No ID carries two different name strings. Both
families' name column is `Player` and carries no disambiguating parenthetical,
so every output row prints the ID beside the name rather than inventing one.
"""

import itertools
import os
import sys

import pandas as pd

from club_aliases import canonical_club

# ─────────────────────────────────────────────────────────────
# Sources
# ─────────────────────────────────────────────────────────────

# Forward slash rather than os.path.join: this string is printed verbatim into
# every header, and os.sep would put a Windows backslash in the copy. Matches
# how draft_posts.py writes its own source paths.
ARCHIVE = "data_history/fitzroy_stats_1965_2006.csv.gz"
MODERN = "fitzroy_stats_all.csv"
DRAFTS_DIR = "drafts"

# Earliest season carrying any vote data. See the module docstring: 1965-1983
# are blank in the archive and blank from a live fitzRoy fetch.
SEASON_FLOOR = 1984
# Every season through here must be present or load_frame raises. Seasons past
# it are allowed through; the vote invariants below will fail loudly on an
# unplayed one, which is the intended behaviour rather than a silent pass.
SEASON_REQUIRED_TO = 2025

# One projection, because both files carry the same 81-column fitzRoy schema.
_FITZROY_COLS = ('Season', 'Round', 'Brownlow.Votes', 'ID', 'Player',
                 'Playing.for', 'Home.team', 'Away.team')

VOTE_COL = 'Brownlow.Votes'

# A game is one fixture in one round of one season. Used for the vote
# invariants and for the game counts the headers report.
_GAME_KEY = ['Season', 'Round_num', 'Home.team', 'Away.team']

_ARCHIVE_LABEL = f"{SEASON_FLOOR}-2006"
_MODERN_LABEL = "2007-2025"

# ─────────────────────────────────────────────────────────────
# Header text carried by every table
# ─────────────────────────────────────────────────────────────

# One constant, so all three headers carry byte-identical wording. Editing the
# caveat in one table and not the others is the failure this prevents.
TRUNCATION_CAVEAT = (
    "**1984 truncation caveat.** The archive begins in 1984, so pre-1984 "
    "debutants have only their post-1984 tail counted. Every figure below for "
    "such a player is a floor and not a career total, and a pair or club-season "
    "that includes one is understated by however many votes that player polled "
    "before 1984."
)


def _finals_rule(prov):
    """The finals rule, with this run's measured counts rather than fixed ones."""
    return (
        "**Finals rule.** Finals are dropped on the Round coercion, never on "
        "the vote column, and the vote test is `> 0`. Both sources leave the "
        "vote cell blank or NaN on a finals row, so `!= 0` would admit all "
        f"{prov['finals_dropped_total']:,} of them as voted rows "
        f"({prov['archive_finals_dropped']:,} from {_ARCHIVE_LABEL}, "
        f"{prov['modern_finals_dropped']:,} from {_MODERN_LABEL}); `> 0` after "
        "the coercion does not."
    )


def _identity_note(prov):
    """Identity note, with the name-collision counts measured at load time."""
    return (
        "**Identity.** Players are keyed on `ID`, never on name: "
        f"{prov['archive_ambiguous_names']} name strings in the "
        f"{_ARCHIVE_LABEL} family and {prov['modern_ambiguous_names']} in the "
        f"{_MODERN_LABEL} family resolve to more than one ID, while "
        f"{prov['ids_with_two_names']} IDs carry two different name strings. "
        "Both families' name column is `Player` and carries no disambiguating "
        "parenthetical, so each row prints the ID beside the name rather than "
        "constructing one. Clubs are canonicalised through "
        "`club_aliases.canonical_club()`; Fitzroy stays Fitzroy and is not "
        "folded into Brisbane Lions."
    )


def _season_length_note(prov):
    """Season length, stated as a range because the window is not uniform.

    1984-1986 ran 132 games, later seasons more, and 2020 was cut short. Naming
    every exception dates the file; the measured range does not.
    """
    return (
        f"**Season length varies across this window.** Home-and-away games per "
        f"season range from {prov['games_per_season_min']} to "
        f"{prov['games_per_season_max']} across "
        f"{prov['season_min']}-{prov['season_max']} "
        f"({prov['games']:,} games in total), so a club-season total from a "
        f"short season is not directly comparable with one from a long season, "
        f"and neither is a pair's combined total."
    )


def _pair_exclusion_note(prov, min_pollers, median_pollers):
    return (
        "**Pair eligibility.** Pairs are formed among players who polled at "
        "least one vote in that club-season. A pair whose second member polled "
        "zero has a combined total equal to the first member's own tally, so it "
        "is one player's count wearing a partnership label rather than a "
        f"partnership. Every club-season in this window has at least "
        f"{min_pollers} polling players (median {median_pollers:g}), so no "
        f"club-season is dropped by this rule."
    )


# ─────────────────────────────────────────────────────────────
# Loading
# ─────────────────────────────────────────────────────────────

def _read_family(path, label, prov, season_min=None):
    """One fitzRoy file to an H&A frame, with the finals drop recorded.

    `pd.read_csv` infers gzip from the .gz suffix, so the archive and the plain
    CSV take the same path here.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"{label} source absent: {path}")
    df = pd.read_csv(path, low_memory=False,
                     usecols=lambda c: c in _FITZROY_COLS)
    prov[f'{label}_rows_file'] = len(df)

    df['Season'] = pd.to_numeric(df['Season'], errors='coerce')
    df = df[df['Season'].notna()].copy()
    if season_min is not None:
        df = df[df['Season'] >= season_min].copy()
    df['Season'] = df['Season'].astype(int)
    prov[f'{label}_rows_sliced'] = len(df)

    # The finals drop, on the Round coercion. Never on the vote column.
    df['Round_num'] = pd.to_numeric(df['Round'], errors='coerce')
    prov[f'{label}_finals_dropped'] = int(df['Round_num'].isna().sum())
    df = df[df['Round_num'].notna()].copy()
    prov[f'{label}_rows_ha'] = len(df)

    df = df.rename(columns={'Player': 'Player_Name'}).drop(columns=['Round'])
    df['_family'] = label
    return df


def _ambiguous_name_count(df):
    """Name strings resolving to more than one ID, the reason ID is the key."""
    per_name = df.groupby('Player_Name')['ID'].nunique()
    return int((per_name > 1).sum())


def load_frame(archive=ARCHIVE, modern=MODERN):
    """The combined H&A frame, 1984-2025, plus provenance for the headers.

    Returns (df, prov). df carries Season, Round_num, Votes, ID, Player_Name,
    Club and the fixture columns. prov is the dict of counts every header
    reports, so the numbers in the prose cannot drift from the frame.
    """
    prov = {}
    arch = _read_family(archive, 'archive', prov, season_min=SEASON_FLOOR)
    mod = _read_family(modern, 'modern', prov)
    prov['archive_file'] = os.path.basename(archive)
    prov['modern_file'] = os.path.basename(modern)

    # ---- season range guards, before anything is aggregated ----
    arch_seasons = set(arch['Season'].unique().tolist())
    mod_seasons = set(mod['Season'].unique().tolist())
    overlap = sorted(arch_seasons & mod_seasons)
    if overlap:
        raise ValueError(
            f"the two sources overlap on season(s) {overlap}, which would "
            f"double-count every game in them. {prov['archive_file']} is "
            f"sliced to Season >= {SEASON_FLOOR} and {prov['modern_file']} is "
            f"expected to start at 2007")
    present = arch_seasons | mod_seasons
    missing = [s for s in range(SEASON_FLOOR, SEASON_REQUIRED_TO + 1)
               if s not in present]
    if missing:
        raise ValueError(
            f"{len(missing)} season(s) absent from both sources, so every "
            f"table would be silently short: {missing}. Expected an unbroken "
            f"{SEASON_FLOOR}-{SEASON_REQUIRED_TO}")
    prov['season_overlap'] = overlap
    prov['seasons_archive'] = (min(arch_seasons), max(arch_seasons))
    prov['seasons_modern'] = (min(mod_seasons), max(mod_seasons))

    # Measured before the concat so each family's figure is its own.
    prov['archive_ambiguous_names'] = _ambiguous_name_count(arch)
    prov['modern_ambiguous_names'] = _ambiguous_name_count(mod)

    keep = ['Season', 'Round_num', VOTE_COL, 'ID', 'Player_Name',
            'Playing.for', 'Home.team', 'Away.team', '_family']
    df = pd.concat([arch[keep], mod[keep]], ignore_index=True)

    # Identity is keyed on ID, so a row without one cannot be attributed.
    prov['nan_id_dropped'] = int(df['ID'].isna().sum())
    prov['nan_id_votes'] = float(
        pd.to_numeric(df.loc[df['ID'].isna(), VOTE_COL], errors='coerce')
          .fillna(0).sum())
    df = df[df['ID'].notna()].copy()
    df['ID'] = df['ID'].astype(int)
    df['Round_num'] = df['Round_num'].astype(int)

    # Actual Brownlow votes. Never Exp_Votes: neither source is read for a
    # model column here, and Exp_Votes is not in the projection.
    df['Votes'] = pd.to_numeric(df[VOTE_COL], errors='coerce').fillna(0.0)
    df['Club'] = df['Playing.for'].map(canonical_club)

    # ---- counted after the ID drop, so the two halves sum to prov['rows'] ----
    prov['rows'] = len(df)
    prov['rows_archive'] = int((df['_family'] == 'archive').sum())
    prov['rows_modern'] = int((df['_family'] == 'modern').sum())
    prov['finals_dropped_total'] = (prov['archive_finals_dropped'] +
                                    prov['modern_finals_dropped'])
    prov['season_min'] = int(df['Season'].min())
    prov['season_max'] = int(df['Season'].max())
    prov['season_count'] = int(df['Season'].nunique())
    prov['clubs'] = sorted(df['Club'].dropna().unique().tolist())

    fixtures = df.drop_duplicates(subset=_GAME_KEY)
    prov['games'] = len(fixtures)
    per_season = fixtures.groupby('Season').size()
    prov['games_per_season_min'] = int(per_season.min())
    prov['games_per_season_max'] = int(per_season.max())

    prov['total_votes'] = int(df['Votes'].sum())
    prov['three_vote_rows'] = int((df['Votes'] == 3).sum())
    prov['ids_with_two_names'] = int(
        (df.groupby('ID')['Player_Name'].nunique() > 1).sum())

    # ---- vote invariants. A clean 3-2-1 game awards exactly 3+2+1 = 6. ----
    if prov['total_votes'] != 6 * prov['games']:
        raise ValueError(
            f"vote total {prov['total_votes']:,} does not equal 6 x "
            f"{prov['games']:,} games = {6 * prov['games']:,}. A clean 3-2-1 "
            f"game awards exactly 6 votes, so the frame holds a game with "
            f"missing or duplicated votes, a finals row that survived the "
            f"Round coercion, or an unplayed season whose votes are not in yet")
    if prov['three_vote_rows'] != prov['games']:
        raise ValueError(
            f"{prov['three_vote_rows']:,} rows carry 3 votes but the frame "
            f"holds {prov['games']:,} games. Exactly one best-on-ground is "
            f"awarded per game, so the frame holds a game with no 3-vote row "
            f"or more than one")
    return df, prov


def _player_club_season_votes(df):
    """(Season, Club, ID) to summed votes and a name, keyed on ID throughout.

    Grouped on club as well as ID so a player who turned out for two clubs in
    one season has their votes attributed to the club they were earned at. The
    handful of such player-seasons all polled zero at both clubs, so this
    grouping changes no number here; it is the correct rule regardless.
    """
    g = (df.groupby(['Season', 'Club', 'ID'], dropna=False)
           .agg(votes=('Votes', 'sum'),
                games=('Votes', 'size'),
                Player_Name=('Player_Name', 'first'))
           .reset_index())
    g['votes'] = g['votes'].astype(int)
    return g


# ─────────────────────────────────────────────────────────────
# Formatting
# ─────────────────────────────────────────────────────────────

def _who(name, player_id):
    """Name plus ID. No parenthetical is constructed for either family."""
    label = "unknown" if pd.isna(name) else str(name)
    return f"{label} (ID {int(player_id)})"


def _plural(n, unit):
    """`unit` is given plural; a count of 1 drops the trailing s."""
    return f"{n} {unit[:-1] if n == 1 and unit.endswith('s') else unit}"


def _gap_line(rows, field, unit):
    """The rank 1 to rank 2 gap, stated rather than left to the reader.

    A tie is reported as a tie. Printing "gap 0" alone reads as a rounding
    artefact when it is in fact two entries level on the same total.
    """
    if len(rows) < 2:
        return (f"Only {len(rows)} ranked entr{'y' if len(rows) == 1 else 'ies'}, "
                f"so no rank 1 to rank 2 gap exists.")
    top, second = rows[0], rows[1]
    gap = top[field] - second[field]
    if gap == 0:
        return (f"**Rank 1 and rank 2 are level** on "
                f"{_plural(top[field], unit)}, so the gap is 0.")
    return (f"**Gap between rank 1 and rank 2: {_plural(gap, unit)}** "
            f"({top[field]} against {second[field]}).")


def _provenance_block(prov, computed_from):
    """The header lines every table shares."""
    return [
        f"Source files: `{ARCHIVE}` sliced to Season >= {SEASON_FLOOR} "
        f"({prov['seasons_archive'][0]}-{prov['seasons_archive'][1]}, "
        f"{prov['archive_rows_sliced']:,} rows of the "
        f"{prov['archive_rows_file']:,} in the file) and `{prov['modern_file']}` "
        f"({prov['seasons_modern'][0]}-{prov['seasons_modern'][1]}, "
        f"{prov['modern_rows_file']:,} rows).",
        "",
        f"Seasons covered: {prov['season_min']} to {prov['season_max']} "
        f"({prov['season_count']} seasons, unbroken). **Home and away only.**",
        "",
        f"Row count of the frame this table was computed from: "
        f"**{prov['rows']:,} player-game rows** "
        f"({prov['rows_archive']:,} from {_ARCHIVE_LABEL}, "
        f"{prov['rows_modern']:,} from {_MODERN_LABEL}) across "
        f"**{prov['games']:,} games**, carrying {prov['total_votes']:,} votes. "
        f"{computed_from}",
        "",
        f"Invariants checked before this table was written: total votes "
        f"{prov['total_votes']:,} equals 6 x {prov['games']:,} games "
        f"({6 * prov['games']:,}), and the {prov['three_vote_rows']:,} rows "
        f"carrying 3 votes equal the {prov['games']:,} games, one "
        f"best-on-ground each. Either failing raises rather than publishing.",
        "",
        f"Finals rows dropped on the Round coercion: "
        f"{prov['archive_finals_dropped']:,} from {_ARCHIVE_LABEL}, "
        f"{prov['modern_finals_dropped']:,} from {_MODERN_LABEL}. Rows dropped "
        f"for a missing `ID`: {prov['nan_id_dropped']} "
        f"(carrying {int(prov['nan_id_votes'])} votes between them).",
        "",
        "Actual Brownlow votes throughout. `Exp_Votes` is never read: it is a "
        "model expectation and is not in either source projection.",
        "",
        _finals_rule(prov),
        "",
        _identity_note(prov),
        "",
        _season_length_note(prov),
        "",
        TRUNCATION_CAVEAT,
        "",
    ]


def _write(lines, name, out_dir=DRAFTS_DIR):
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"all_time_{name}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")
    return out_path


def _table(lines, head, rule, body_rows):
    lines.append(head)
    lines.append(rule)
    lines.extend(body_rows)
    lines.append("")


def _assertion_summary(prov):
    """The two invariant values, echoed to stdout after a build."""
    return (f"   invariants: total votes {prov['total_votes']:,} == 6 x "
            f"{prov['games']:,} games ({6 * prov['games']:,}) | 3-vote rows "
            f"{prov['three_vote_rows']:,} == games {prov['games']:,}")


# ─────────────────────────────────────────────────────────────
# Builders
# ─────────────────────────────────────────────────────────────

def build_pair_season_totals(top_n=10, out_dir=DRAFTS_DIR, **kw):
    """Combined votes for every pair of teammates in the same club-season."""
    df, prov = load_frame(**kw)
    pcs = _player_club_season_votes(df)
    pollers = pcs[pcs['votes'] >= 1].copy()

    by_cs = pollers.groupby(['Season', 'Club']).size()
    min_pollers, median_pollers = int(by_cs.min()), float(by_cs.median())

    rows = []
    for (season, club), g in pollers.groupby(['Season', 'Club'], dropna=False):
        # Sorted before pairing so a re-run is byte-identical.
        g = g.sort_values(['votes', 'Player_Name', 'ID'],
                          ascending=[False, True, True]).reset_index(drop=True)
        recs = g.to_dict('records')
        for a, b in itertools.combinations(recs, 2):
            rows.append({
                'season': int(season),
                'club': club,
                'a': _who(a['Player_Name'], a['ID']),
                'a_votes': int(a['votes']),
                'b': _who(b['Player_Name'], b['ID']),
                'b_votes': int(b['votes']),
                'combined': int(a['votes']) + int(b['votes']),
            })

    rows.sort(key=lambda r: (-r['combined'], r['season'], r['club'], r['a'], r['b']))
    shown = rows[:top_n]

    computed_from = (
        f"From it, {len(pollers):,} polling player-club-seasons yield "
        f"{len(rows):,} eligible pairs across {len(by_cs):,} club-seasons.")

    L = ["# All-time teammate pairs by combined votes, one club-season", ""]
    L.append("Every pair of teammates in the same club-season, ranked by their "
             "combined Brownlow votes for that season.")
    L.append("")
    L.extend(_provenance_block(prov, computed_from))
    L.append(_pair_exclusion_note(prov, min_pollers, median_pollers))
    L.append("")
    L.append(_gap_line(shown, 'combined', "combined votes"))
    L.append("")
    L.append(f"Full ranked table to {top_n}, of {len(rows):,} eligible pairs.")
    L.append("")
    _table(
        L,
        "| # | season | club | player 1 | votes | player 2 | votes | combined |",
        "|---|---|---|---|---|---|---|---|",
        ["| " + " | ".join([
            str(i), str(r['season']), str(r['club']),
            r['a'], str(r['a_votes']), r['b'], str(r['b_votes']),
            str(r['combined'])]) + " |"
         for i, r in enumerate(shown, 1)])

    out_path = _write(L, "pairs", out_dir=out_dir)
    print(f"OK wrote {out_path} ({len(rows):,} eligible pairs, top {len(shown)} shown)")
    print("   " + _gap_line(shown, 'combined', "combined votes").replace("**", ""))
    print(_assertion_summary(prov))
    return out_path


def build_club_season_totals(top_n=10, out_dir=DRAFTS_DIR, **kw):
    """Total Brownlow votes by club-season."""
    df, prov = load_frame(**kw)
    pcs = _player_club_season_votes(df)

    agg = (pcs.groupby(['Season', 'Club'], dropna=False)
              .agg(votes=('votes', 'sum'),
                   pollers=('votes', lambda s: int((s >= 1).sum())),
                   players=('ID', 'nunique'))
              .reset_index())
    rows = [{
        'season': int(r['Season']),
        'club': r['Club'],
        'votes': int(r['votes']),
        'pollers': int(r['pollers']),
        'players': int(r['players']),
    } for r in agg.to_dict('records')]
    rows.sort(key=lambda r: (-r['votes'], r['season'], r['club']))
    shown = rows[:top_n]

    computed_from = f"From it, {len(rows):,} club-seasons."

    L = ["# All-time club-season Brownlow vote totals", ""]
    L.append("Total votes polled by every player at one club in one season, "
             "ranked by that total.")
    L.append("")
    L.extend(_provenance_block(prov, computed_from))
    L.append(f"Clubs after canonicalisation: {len(prov['clubs'])} "
             f"({', '.join(prov['clubs'])}).")
    L.append("")
    L.append(_gap_line(shown, 'votes', "votes"))
    L.append("")
    L.append(f"Full ranked table to {top_n}, of {len(rows):,} club-seasons.")
    L.append("")
    _table(
        L,
        "| # | season | club | votes | players polling | players used |",
        "|---|---|---|---|---|---|",
        ["| " + " | ".join([
            str(i), str(r['season']), str(r['club']), str(r['votes']),
            str(r['pollers']), str(r['players'])]) + " |"
         for i, r in enumerate(shown, 1)])

    out_path = _write(L, "clubs", out_dir=out_dir)
    print(f"OK wrote {out_path} ({len(rows):,} club-seasons, top {len(shown)} shown)")
    print("   " + _gap_line(shown, 'votes', "votes").replace("**", ""))
    print(_assertion_summary(prov))
    return out_path


def build_three_vote_games(top_n=10, out_dir=DRAFTS_DIR, **kw):
    """Count of 3-vote games per player-season."""
    df, prov = load_frame(**kw)
    # Equality on 3 rather than a threshold. Votes are exactly {0,1,2,3} in
    # both families once finals are gone, so == 3 is the best-on-ground row.
    threes = df[df['Votes'] == 3].copy()

    agg = (threes.groupby(['Season', 'ID'], dropna=False)
                 .agg(three_vote_games=('Votes', 'size'),
                      Player_Name=('Player_Name', 'first'),
                      clubs=('Club', lambda s: " / ".join(
                          sorted(set(x for x in s if isinstance(x, str))))))
                 .reset_index())
    # Season votes for context, keyed the same way (Season, ID).
    season_votes = (df.groupby(['Season', 'ID'])['Votes'].sum()
                      .astype(int).rename('season_votes').reset_index())
    agg = agg.merge(season_votes, on=['Season', 'ID'], how='left')

    rows = [{
        'season': int(r['Season']),
        'who': _who(r['Player_Name'], r['ID']),
        'club': r['clubs'],
        'three_vote_games': int(r['three_vote_games']),
        'season_votes': int(r['season_votes']),
    } for r in agg.to_dict('records')]
    rows.sort(key=lambda r: (-r['three_vote_games'], -r['season_votes'],
                             r['season'], r['who']))
    shown = rows[:top_n]

    computed_from = (
        f"From it, {len(threes):,} rows are 3-vote games, spread over "
        f"{len(rows):,} player-seasons.")

    L = ["# All-time 3-vote games in one season", ""]
    L.append("Count of best-on-ground games (`Brownlow.Votes` == 3) per "
             "player-season, ranked by that count.")
    L.append("")
    L.extend(_provenance_block(prov, computed_from))
    L.append("Ties on the count are broken by the player's total votes that "
             "season, then season, then name, so a re-run is byte-identical.")
    L.append("")
    L.append(_gap_line(shown, 'three_vote_games', "3-vote games"))
    L.append("")
    L.append(f"Full ranked table to {top_n}, of {len(rows):,} player-seasons "
             f"holding at least one 3-vote game.")
    L.append("")
    _table(
        L,
        "| # | season | player | club | 3-vote games | season votes |",
        "|---|---|---|---|---|---|",
        ["| " + " | ".join([
            str(i), str(r['season']), r['who'], str(r['club']),
            str(r['three_vote_games']), str(r['season_votes'])]) + " |"
         for i, r in enumerate(shown, 1)])

    out_path = _write(L, "three_vote", out_dir=out_dir)
    print(f"OK wrote {out_path} ({len(rows):,} player-seasons, top {len(shown)} shown)")
    print("   " + _gap_line(shown, 'three_vote_games', "3-vote games").replace("**", ""))
    print(_assertion_summary(prov))
    return out_path


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

_BUILDERS = {
    "pairs": build_pair_season_totals,
    "clubs": build_club_season_totals,
    "three-vote": build_three_vote_games,
}

_USAGE = ("usage: python all_time_tables.py <pairs|clubs|three-vote> [top_n]")


def main(argv):
    if len(argv) not in (1, 2):
        print(_USAGE, file=sys.stderr)
        return 2
    name = argv[0]
    if name not in _BUILDERS:
        print(f"unknown table {name!r}, expected one of "
              f"{', '.join(sorted(_BUILDERS))}", file=sys.stderr)
        print(_USAGE, file=sys.stderr)
        return 2
    top_n = 10
    if len(argv) == 2:
        try:
            top_n = int(argv[1])
        except ValueError:
            print(f"top_n must be an integer, got {argv[1]!r}", file=sys.stderr)
            print(_USAGE, file=sys.stderr)
            return 2
        if top_n < 2:
            # Same shape as build_closest_calls' two-row floor: a rank 1 to
            # rank 2 gap cannot be formed from one row.
            print(f"top_n must be at least 2, got {top_n}: the rank 1 to rank "
                  f"2 gap needs two rows", file=sys.stderr)
            return 2
    _BUILDERS[name](top_n=top_n)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
