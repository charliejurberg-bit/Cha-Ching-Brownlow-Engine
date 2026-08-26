"""Join footywire's real Score Involvements onto this repo's player identity.

    python build_score_involvements.py

Reads every data_advanced/advanced_<season>.csv written by scraper_advanced.py,
joins each to the matching game_level_<season>.csv, and writes one narrow file:

    data_advanced/score_involvements.csv
        Season, Round_num, ID, Score_Involvements_Actual,
        Metres_Gained, Intercepts, Time_On_Ground_Pct

Keyed on Season + Round_num + fitzRoy ID, which is what the dashboard already
groups by, so the merge downstream is three columns and no name matching.

Three decisions worth arguing with rather than rediscovering:

  - **Round numbers are mapped positionally, per season, never by a constant
    offset.** footywire calls Opening Round "Round 0", so from 2024 its number
    runs one behind the AFLTables `Round_num` this repo uses, and before 2024
    it does not. Rather than carry that rule and a season constant, each
    season's sorted distinct footywire rounds are mapped onto its sorted
    distinct `Round_num` values and the two are required to be the same length.
    A season where they are not is reported and skipped, because a positional
    map over unequal lists silently shifts an entire season by one round.

  - **Names join in three passes, each looser than the last, each scoped to one
    round and one club.** Pass one is the full normalised name, which separates
    Chad Warner from Corey Warner. Pass two is first initial plus surname, which
    recovers Cam Mackenzie against footywire's Cameron Mackenzie. Pass three
    emits one key per surname token, which recovers the middle names and
    suffixes footywire carries and the archive does not: Gary Jnr Ablett, Josh P
    Kennedy, Jasper Mcmillan Pittard. Passes two and three accept only a key
    unique on BOTH sides, so the Warners can never resolve through either.
    Together they reach 100% on every season measured; anything left is an
    alias, and aliases are enumerated rather than guessed at.

    Pass three's keys must carry the round and club prefix. Without it
    "g|ablett" repeats in every round he played, the uniqueness filter reads
    that as ambiguous, and the pass silently recovers almost nothing while still
    looking like it ran.

  - **Finals are dropped from the footywire side before anything else.** The
    game_level files are home and away only, so a finals row has nothing to
    join to and would only depress the match rate it is measured by.

The engineered `Score_Involvements` column is not touched anywhere. It stays a
model feature under its own name; this file carries the real stat under a
different one.
"""

import os
import re
import sys

import pandas as pd

ADV_DIR = "data_advanced"
GAME_LEVEL_DIRS = ("predictions", "data_history")
OUT_PATH = os.path.join(ADV_DIR, "score_involvements.csv")
CARRY = ('Score_Involvements_Actual', 'Metres_Gained', 'Intercepts',
         'Time_On_Ground_Pct')

# Below this, something structural is wrong and the file must not be written.
# Every season measured matches at 100%, so the floor is not there to absorb
# ordinary slop: it is sized to catch the structural failures seen so far, one
# club mis-slugged (6% of a season) and one season's rounds shifted (most of
# it). It stays loose enough that a single new alias in a future season reports
# itself without blocking the build, which is what the sub-100% note below is
# for.
MIN_MATCH_RATE = 0.98

# Any of these above zero means the player took the field. Used to exclude
# unused substitutes from the match rate; they are named in the archive with
# zeroes throughout and are rightly absent from footywire's stats table.
PLAYED_COLS = ('Disposals', 'Marks', 'Tackles', 'Goals', 'Hit.Outs')


def _norm(s):
    return re.sub(r'[^a-z]', '', str(s).lower())


# Names no normalisation rule can reach: one footywire typo, and five players
# footywire files under a former or given name. A fuzzy matcher would catch
# them and is far too dangerous to point at 50,000 rows, so they are enumerated.
#
# Applied to the FOOTYWIRE side only. Applying it to the archive side too would
# let a genuinely different player carrying one of these names be rewritten into
# someone else, and pass one has no uniqueness guard to catch that.
#
# Every entry was found by inspecting a season's unmatched rows and then
# confirmed by checking the two names played the identical set of rounds for the
# same club, not by the names looking alike.
FEED_NAME_ALIASES = {
    'jeffgartlett': 'jeffgarlett',            # footywire typo
    'heritierobrien': 'heritierlumumba',      # former name
    'brianharris': 'brianlake',               # former name
    'anguslitherland': 'angusdewar',          # former name
    'ianhill': 'bobbyhill',                   # given name vs known-as
    'edwardmchenry': 'nedmchenry',            # given name vs known-as
}


def _clean(name):
    """Strip the archive's '(Team)' suffix and footywire's disambiguating digit.

    footywire appends a bare number to separate two players sharing a name:
    'Matthew Kennedy 1', 'Josh Deluca Cardillo 1', 'Joel Smith 1'.
    """
    s = re.sub(r'\s*\([^)]*\)\s*$', '', str(name))
    return re.sub(r'\s+\d+\s*$', '', s).strip()


def _full_key(name):
    """Whole name, normalised, with the archive's '(Team)' suffix removed."""
    return _norm(_clean(name))


def _feed_key(name):
    """_full_key plus the footywire-side alias map. Feed side only."""
    k = _full_key(name)
    return FEED_NAME_ALIASES.get(k, k)


def _initial_key(name):
    """First initial plus surname. Survives Cam against Cameron, 'van Rooyen',
    hyphens, and the disambiguation suffix."""
    toks = _clean(name).split()
    if not toks:
        return ''
    first = _norm(toks[0])[:1]
    last = _norm(' '.join(toks[1:]))
    return f"{first}|{last or first}"


def _token_keys(name):
    """One key per surname token: first initial plus that token.

    Pass three. footywire carries middle names and suffixes the archive does
    not: 'Gary Jnr Ablett', 'Jasper Mcmillan Pittard', 'Josh P  Kennedy',
    'Josh Deluca Cardillo'. Whole-name and initial-plus-full-surname keys both
    miss every one of them, but the two forms always share at least one surname
    token, so emitting a key per token and requiring the shared one to be
    unique on both sides recovers them without loosening into fuzzy matching.
    """
    toks = _clean(name).split()
    if len(toks) < 2:
        return []
    first = _norm(toks[0])[:1]
    return [f"{first}|{_norm(t)}" for t in toks[1:] if _norm(t)]


def _game_level_path(season):
    for d in GAME_LEVEL_DIRS:
        p = os.path.join(d, f"game_level_{season}.csv")
        if os.path.exists(p):
            return p
    return None


def _assign_rounds(adv, gl, season, rmap):
    """Round_num per match, from the FIXTURE rather than the round label.

    The positional label map is right for eleven of the twelve seasons, and
    wrong for 2025, where two rescheduled games (Brisbane v Geelong, Essendon v
    Gold Coast) sit under different round numbers in the two sources. Trusting
    the label there put 103 player-games in a round the archive says they were
    not in, and they simply failed to join. Silently, and only for those games.

    So each match is placed by looking up the club pair it actually was. A pair
    that played once in the season has exactly one candidate round and the label
    is irrelevant. A pair that met twice keeps the label if the label is one of
    the two, which is what stops a double-up being reassigned on a whim, and
    otherwise takes the nearer candidate.

    A candidate round is claimed at most once. Two matches of the same club pair
    are two different games, so putting both on one Round_num does not merge
    them, it makes them indistinguishable: the round-club-name key collides and
    drop_duplicates('kf') then hands the round whichever game happened to sort
    first. 2025 is the case. footywire carries an Essendon v Gold Coast match
    dated 2025-08-27 under its Round 24 that the archive has no fixture for at
    all; nearest-candidate placement dropped it onto Round_num 18, where the
    genuine meeting already sat, and 30 of the 32 players appearing in both
    carried different score involvements. Half of that round's Essendon and Gold
    Coast numbers were therefore wrong, silently, with the build still passing.

    So a match with no unclaimed candidate is DROPPED and named, rather than
    forced into an occupied round. The archive is the authority on which games
    happened: a footywire match it holds no fixture for cannot be placed, and
    guessing is worse than the gap.
    """
    pair_rounds = {}
    fx = gl[['Round_num', 'Home.team', 'Away.team']].drop_duplicates()
    for _, r in fx.iterrows():
        key = frozenset((r['Home.team'], r['Away.team']))
        pair_rounds.setdefault(key, []).append(int(r['Round_num']))

    # A match whose own label is already a real candidate is placed first, so it
    # always keeps its slot and can never be evicted by one that has to be
    # relocated. Without the ordering, which of the two wins depends on mid.
    def _settled_first(item):
        mid, d = item
        label = rmap.get(str(d['Round_fw'].iloc[0]))
        return (0 if label in pair_rounds.get(frozenset(d['Team'].unique()), [])
                else 1, mid)

    out, moved, dropped, claimed = {}, 0, [], set()
    for mid, d in sorted(adv.groupby('mid'), key=_settled_first):
        label = rmap.get(str(d['Round_fw'].iloc[0]))
        key = frozenset(d['Team'].unique())
        cand = pair_rounds.get(key, [])
        if not cand:
            out[mid] = label
            continue
        if label in cand and (label, key) not in claimed:
            pick = label
        else:
            free = [c for c in cand if (c, key) not in claimed]
            if not free:
                out[mid] = None
                dropped.append((mid, str(d['Date'].iloc[0]), sorted(key)))
                continue
            pick = min(free, key=lambda c: abs(c - label) if label else c)
            moved += 1
        out[mid] = pick
        claimed.add((pick, key))
    if moved:
        print(f"  NOTE {season}: {moved} match(es) placed by fixture rather "
              f"than by footywire's round label, which disagreed with the "
              f"archive. Rescheduled games do this.")
    for mid, date, teams in dropped:
        print(f"  DROP {season}: footywire match {mid} ({date}, "
              f"{' v '.join(teams)}) has no unclaimed round in the archive's "
              f"fixture list; every candidate already holds a different match "
              f"of this pair. Dropped rather than placed over one.")
    return out


def _round_map(adv, gl, season):
    """footywire round label to this repo's Round_num, positionally."""
    fw = sorted({int(m.group(1)) for r in adv['Round_fw'].dropna().unique()
                 for m in [re.match(r'^Round (\d+)$', str(r))] if m})
    gl_rounds = sorted(int(r) for r in gl['Round_num'].dropna().unique())
    if len(fw) != len(gl_rounds):
        raise ValueError(
            f"{season}: {len(fw)} footywire home-and-away rounds against "
            f"{len(gl_rounds)} in the game_level file, so a positional map "
            f"would shift the season. fw={fw[:3]}..{fw[-3:]} "
            f"gl={gl_rounds[:3]}..{gl_rounds[-3:]}")
    return {f"Round {a}": b for a, b in zip(fw, gl_rounds)}


def build_season(season, report):
    adv_path = os.path.join(ADV_DIR, f"advanced_{season}.csv")
    gl_path = _game_level_path(season)
    if gl_path is None:
        raise FileNotFoundError(f"{season}: no game_level file in {GAME_LEVEL_DIRS}")

    adv = pd.read_csv(adv_path)
    adv = adv[adv['Round_fw'].astype(str).str.match(r'^Round \d+$')].copy()
    gl = pd.read_csv(gl_path, usecols=lambda c: c in
                     ('ID', 'Round_num', 'Player_Name', 'Playing.for', 'Team',
                      'Home.team', 'Away.team') or c in PLAYED_COLS)
    gl = gl[gl['ID'].notna()].copy()
    gl['ID'] = gl['ID'].astype(int)

    # One row per Round_num + ID, because that is the identity everything here
    # is keyed on. predictions/game_level_2025.csv carries 78 exactly-duplicated
    # round-24 rows, every Essendon and Gold Coast player in that round listed
    # twice, and a duplicate does two kinds of damage. It reaches the output,
    # where it sits on the RIGHT side of the dashboard's left merge and
    # multiplies the left row rather than annotating it. And it defeats passes
    # two and three here: both accept only a key unique on BOTH sides, so a
    # player named twice in one round for one club reads as ambiguous and is
    # refused. That is why Lachie Weller and Sam Collins failed to match in
    # round 24 while matching everywhere else.
    #
    # Only exact duplicates are dropped. Two rows sharing the key but differing
    # anywhere are a real conflict about what a player did, not a repeat, and
    # are reported rather than silently resolved to whichever sorted first.
    before = len(gl)
    gl = gl.drop_duplicates()
    if len(gl) < before:
        print(f"  {season}: dropped {before - len(gl)} exactly-duplicated "
              f"row(s) from {os.path.basename(gl_path)}")
    clash = gl.duplicated(['Round_num', 'ID'], keep=False)
    if clash.any():
        print(f"  WARN {season}: {int(clash.sum())} row(s) share Round_num + ID "
              f"but differ in their stats; keeping the first of each. Inspect "
              f"{os.path.basename(gl_path)} before trusting this season.")
        gl = gl.drop_duplicates(['Round_num', 'ID'], keep='first')

    rmap = _round_map(adv, gl, season)
    adv['Round_num'] = adv['mid'].map(_assign_rounds(adv, gl, season, rmap))
    # A dropped match carries no Round_num and cannot be keyed; the astype(int)
    # below would raise on it. Removed here so the rate is measured against the
    # games the archive says were played, which is what is being joined to.
    adv = adv[adv['Round_num'].notna()].copy()

    club_gl = gl['Playing.for'] if 'Playing.for' in gl.columns else gl['Team']
    adv['club'] = adv['Team'].map(_norm)
    gl = gl.assign(club=club_gl.map(_norm))

    adv['kf'] = (adv['Round_num'].astype(int).astype(str) + '|' + adv['club']
                 + '|' + adv['Player_fw'].map(_feed_key))
    gl['kf'] = (gl['Round_num'].astype(int).astype(str) + '|' + gl['club']
                + '|' + gl['Player_Name'].map(_full_key))
    adv['ki'] = (adv['Round_num'].astype(int).astype(str) + '|' + adv['club']
                 + '|' + adv['Player_fw'].map(_initial_key))
    gl['ki'] = (gl['Round_num'].astype(int).astype(str) + '|' + gl['club']
                + '|' + gl['Player_Name'].map(_initial_key))

    take = ['kf', 'ki'] + [c for c in CARRY if c in adv.columns]
    merged = gl.merge(adv[take].drop_duplicates('kf'), on='kf', how='left',
                      suffixes=('', '_adv'))

    # Passes two and three, each on the rows the previous one left, and each
    # only where the looser key is unique on both sides. A key carried twice
    # anywhere resolves to nobody, which is what keeps Chad and Corey Warner
    # apart under pass two and stops a shared surname token resolving under
    # pass three.
    carry = [c for c in CARRY if c in adv.columns]

    def _fill(colname, adv_keys, gl_keys):
        need = merged['Score_Involvements_Actual'].isna()
        if not need.any():
            return 0
        a = adv.assign(_k=adv_keys).explode('_k') if adv_keys.map(
            lambda v: isinstance(v, list)).any() else adv.assign(_k=adv_keys)
        g = merged.assign(_k=gl_keys).explode('_k') if gl_keys.map(
            lambda v: isinstance(v, list)).any() else merged.assign(_k=gl_keys)
        a = a[a['_k'].notna() & ~a['_k'].duplicated(keep=False)]
        g_ok = set(g.loc[g['_k'].notna() & ~g['_k'].duplicated(keep=False), '_k'])
        fill = a[a['_k'].isin(g_ok)].drop_duplicates('_k').set_index('_k')[carry]
        idx = merged.index[need]
        keys = g.loc[g.index.isin(idx) & g['_k'].isin(fill.index)]
        keys = keys[~keys.index.duplicated(keep='first')]
        if keys.empty:
            return 0
        for c in carry:
            merged.loc[keys.index, c] = fill.loc[keys['_k'], c].to_numpy()
        return len(keys)

    # Pass three's keys carry the same round and club prefix as the other two.
    # Without it "g|ablett" repeats in every round he played, the uniqueness
    # filter reads that as ambiguous and drops it, and the pass silently
    # recovers almost nothing.
    def _prefixed(df, round_col, club_col, name_col):
        pre = df[round_col].astype(int).astype(str) + '|' + df[club_col] + '|'
        return [[p + k for k in _token_keys(n)]
                for p, n in zip(pre, df[name_col])]

    n2 = _fill('ki', adv['ki'], merged['ki'])
    n3 = _fill('kt',
               pd.Series(_prefixed(adv, 'Round_num', 'club', 'Player_fw'),
                         index=adv.index),
               pd.Series(_prefixed(merged, 'Round_num', 'club', 'Player_Name'),
                         index=merged.index))
    report_extra = {'pass2': n2, 'pass3': n3}

    # The rate is measured over players who actually took the field. An unused
    # medical substitute is named in the archive with zeroes across every stat
    # and is simply absent from footywire's table, correctly: he has no score
    # involvements because he had no game. Counting those as misses put 2021 at
    # 97.8% and failed the build on data that was completely right.
    have = [c for c in PLAYED_COLS if c in merged.columns]
    played = merged[have].fillna(0).sum(axis=1) > 0 if have else pd.Series(
        True, index=merged.index)
    n_bench = int((~played).sum())
    matched = int(merged.loc[played, 'Score_Involvements_Actual'].notna().sum())
    rate = matched / int(played.sum()) if played.any() else 0.0
    if n_bench:
        print(f"  {season}: {n_bench} row(s) are named but never took the "
              f"field (no disposal, mark, tackle, goal or hit-out); excluded "
              f"from the rate and left null")
    report.append({'Season': season, 'rows': int(played.sum()), 'matched': matched,
                   'rate': round(rate, 4)})
    if int(played.sum()) - matched > 0:
        miss = merged[played & merged['Score_Involvements_Actual'].isna()]
        names = miss['Player_Name'].astype(str).value_counts()
        print(f"  NOTE {season}: {len(miss)} row(s) unmatched, "
              f"{len(names)} player(s). Each is an alias footywire files under "
              f"a different name; add to FEED_NAME_ALIASES after confirming "
              f"both names played the same rounds for the same club.")
        for nm, c in names.head(10).items():
            print(f"       {nm} ({c} games)")

    if rate < MIN_MATCH_RATE:
        unmatched = merged[merged['Score_Involvements_Actual'].isna()]
        names = sorted(unmatched['Player_Name'].astype(str).unique())[:15]
        raise ValueError(
            f"{season}: only {rate:.1%} of {len(merged):,} rows matched, below "
            f"the {MIN_MATCH_RATE:.0%} floor. First unmatched names: {names}")

    cols = ['Round_num', 'ID'] + [c for c in CARRY if c in merged.columns]
    out = merged[cols].copy()
    out.insert(0, 'Season', season)
    return out


def main(argv):
    if not os.path.isdir(ADV_DIR):
        print(f"FAIL  {ADV_DIR} does not exist. Run scraper_advanced.py first.")
        return 1
    seasons = sorted(int(m.group(1)) for f in os.listdir(ADV_DIR)
                     for m in [re.match(r'^advanced_(\d{4})\.csv$', f)] if m)
    if not seasons:
        print(f"FAIL  no advanced_<season>.csv in {ADV_DIR}.")
        return 1

    report, frames, failed = [], [], []
    for season in seasons:
        try:
            frames.append(build_season(season, report))
        except Exception as exc:
            failed.append(str(exc))
            print(f"FAIL  {exc}")

    print("\nseason  rows    matched  rate")
    for r in report:
        print(f"{r['Season']}   {r['rows']:6,}  {r['matched']:6,}  {r['rate']:.4f}")

    if failed:
        print(f"\n{len(failed)} season(s) failed; nothing written.")
        return 1

    out = pd.concat(frames, ignore_index=True)
    out.to_csv(OUT_PATH, index=False)
    print(f"\nwrote {OUT_PATH}: {len(out):,} rows, seasons "
          f"{out['Season'].min()} to {out['Season'].max()}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
