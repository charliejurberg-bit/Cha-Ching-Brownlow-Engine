"""features.py — the one definition of the model's feature construction.

brownlow_model.py (train), predict_2026.py (in-season predict) and backtest.py
(walk-forward) all build the same features and must agree exactly: the model is
fitted on what this produces and reads what this produces. They used to hold
three copies of that logic, and it cost two audit findings — a whole-season
momentum leak that was fixed in training while backtest.py silently kept
measuring the leaked version, and merge keys that dropped team in one script but
not the others.

The three scripts differ in ways that are real and are parameterised here rather
than duplicated:

  group_keys        training and backtest span many seasons and group by
                    ['Season','Player_Name']; predict is one season and groups
                    by ['Player_Name'].
  fill_missing      predict zero-fills a rank triplet whose source stat is
                    absent, because it must return a row for every player;
                    training and backtest drop incomplete rows instead.
  include_coaches   the NO_COACHES variant omits the six same-game coaches
                    features.
  include_momentum_cv  whether the variant also drops momentum_cv, which is
                    built from Coaches_Votes but reads prior rounds only.

Anything NOT parameterised is meant to be identical everywhere. If a script
needs to diverge, add a parameter — do not fork the function.
"""

import re
import unicodedata

import numpy as np
import pandas as pd

# ── Merge keys ───────────────────────────────────────────────
# Team is part of both keys and must stay there. Dropping it lets two players
# who share a name take each other's data: a West Coast Bailey Williams was
# reading a Western Bulldogs Bailey Williams's Wheelo ratings for seven rounds
# before this was caught.
COACHES_MERGE_KEYS = ['Season', 'Round_num', 'Player_Name', 'Playing.for']
WHEELO_MERGE_KEYS = ['Player_Name', 'Playing.for', 'Season', 'Round_num']

# Coaches CSVs carry the club as a bracketed abbreviation in Player.Name
# ("Justin McInerney (SYD)"); the stats frame uses full names in Playing.for.
TEAM_ABBREV = {
    'ADEL': 'Adelaide', 'BL': 'Brisbane Lions', 'CARL': 'Carlton',
    'COLL': 'Collingwood', 'ESS': 'Essendon', 'FRE': 'Fremantle',
    'GCFC': 'Gold Coast', 'GEEL': 'Geelong', 'GWS': 'Greater Western Sydney',
    'HAW': 'Hawthorn', 'MELB': 'Melbourne', 'NMFC': 'North Melbourne',
    'PORT': 'Port Adelaide', 'RICH': 'Richmond', 'STK': 'St Kilda',
    'SYD': 'Sydney', 'WB': 'Western Bulldogs', 'WCE': 'West Coast',
}
# Wheelo's own spelling, normalised before it meets Playing.for.
WHEELO_TEAM_FIXES = {'Brisbane': 'Brisbane Lions'}

# Betfair's, same job. Only two differ; the period in 'St. Kilda' is the whole
# difference there. Team spelling is load-bearing for the name reconciliation:
# an unmapped club blocks the surname+team fallback, so Cam Rayner never meets
# Betfair's 'Cameron Rayner'.
BETFAIR_TEAM_FIXES = {'Brisbane': 'Brisbane Lions', 'St. Kilda': 'St Kilda'}

# The coaches feed's spelling of clubs in its Home.Team/Away.Team columns,
# normalised before those meet the AFLTables fixture columns. Only the six that
# differ; the other twelve already agree and pass through .replace() untouched.
#
# NOT interchangeable with TEAM_ABBREV above. That maps the code bracketed in
# Player.Name, which says who polled. This maps the fixture columns, which say
# who played whom, and the feed spells those as marketing names. No suffix rule
# reconciles them: 'GWS Giants' has to become 'Greater Western Sydney'.
COACHES_TEAM_FIXES = {
    'Adelaide Crows': 'Adelaide',
    'Geelong Cats': 'Geelong',
    'Gold Coast Suns': 'Gold Coast',
    'GWS Giants': 'Greater Western Sydney',
    'Sydney Swans': 'Sydney',
    'West Coast Eagles': 'West Coast',
}

# ── Player name normalisation ────────────────────────────────
# Five feeds spell the same player five ways, and AFLTables is not consistently
# on either side of any of them:
#
#   apostrophe        AFLTables OSullivan   others O'Sullivan
#   internal capital  AFLTables McKay       others Mckay (title-cased)
#   particle case     AFLTables van Rooyen  others Van Rooyen
#   hyphen            AFLTables Horne-Francis  others Horne Francis
#   diminutive        AFLTables Josh Rachele / Harry Petty / Cam Mackenzie
#                     but AFLTables Bradley Hill against others' Brad Hill
#
# plus middle initials (Bailey J. Williams) and generational suffixes
# (Malcolm Rosas Jr against AFLTables' Malcolm Rosas).
#
# Left unhandled this cost 297 Wheelo rows and, worse, 66 coaches rows carrying
# 280 real votes that merged as zero. A coaches zero is the modal value, so that
# failure passes every sanity check that a missing rating would trip.
#
# Normalising BOTH sides is deliberate: a lookup table of known names would need
# a new entry for every debutant with an apostrophe. The only thing a table is
# kept for is a true nickname no prefix rule can bridge, and there is currently
# no such case in 2026.

_NAME_SUFFIXES = {'jr', 'jnr', 'sr', 'snr', 'ii', 'iii', 'iv'}


def _name_tokens(name):
    """Lowercase name tokens with spelling conventions stripped.

    Apostrophes are DELETED rather than turned into a separator, because
    AFLTables deletes them too: O'Sullivan is stored as OSullivan, so splitting
    on the apostrophe would leave a stray single-letter "o" that the middle
    initial rule below then eats, yielding connorsullivan against AFLTables'
    connorosullivan. Hyphens and periods do become separators, since those are
    written as spaces elsewhere (Horne-Francis against Horne Francis).
    """
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return []
    text = unicodedata.normalize('NFKD', str(name))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = text.replace("'", '').replace('’', '')
    text = re.sub(r'[.\-_]', ' ', text)
    tokens = [t for t in text.lower().split() if t]
    tokens = [t for t in tokens if t not in _NAME_SUFFIXES]
    if len(tokens) > 2:
        # Lone middle initial: "bailey j williams" -> "bailey williams". Only a
        # single character qualifies, so "van rooyen" and "horne francis"
        # survive intact.
        tokens = [tokens[0]] + [t for t in tokens[1:-1] if len(t) > 1] + [tokens[-1]]
    return tokens


def normalise_name(name):
    """Canonical join key for a player name, spelling conventions removed.

    Case, accents, apostrophes, periods, hyphens and spaces all go, so
    O'Sullivan/OSullivan, McKay/Mckay, de Goey/De Goey and
    Horne-Francis/Horne Francis each collapse to one key. Generational suffixes
    and lone middle initials are dropped.

    Deliberately does NOT touch first-name length: Leo/Leonardo stay distinct
    here, because collapsing them safely needs team and round context that this
    function does not have. That is what match_by_surname_context is for.
    """
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return ''
    return ''.join(_name_tokens(name))


def name_parts(name):
    """(first, surname) of a normalised name, for the Layer 2 context match.

    Splits on the ORIGINAL token boundaries rather than the joined key, so
    multi-word surnames stay whole: 'Jacob van Rooyen' -> ('jacob', 'vanrooyen').
    """
    tokens = _name_tokens(name)
    if not tokens:
        return '', ''
    if len(tokens) == 1:
        return '', tokens[0]
    first = tokens[0]
    rest = [t for t in tokens[1:] if len(t) > 1] or tokens[1:]
    return first, ''.join(rest)


# Minimum shared prefix for two first names to be treated as the same person.
#
# Four, and it cannot be raised: Harry/Harrison share exactly four characters
# ("harr"), so five rejects Harry Petty against the coaches feed's Harrison
# Petty, which is one of the cases this exists to fix.
#
# Validated rather than assumed. Sweeping every pair of distinct players (by
# fitzRoy ID) sharing a normalised surname within a team and round across 2026:
# 142 such collision groups, and this rule accepts NONE of them, at four, five
# or six. The only pair it accepts league-wide is the two Bailey Williamses,
# who are at different clubs and so never meet once team is in the key. The
# threshold therefore buys no safety at the scope it runs at, and costs a
# required match above four. Rows with a missing fitzRoy ID have to be excluded
# from that sweep or a player reads as colliding with themselves.
FIRST_NAME_PREFIX_MIN = 4


def first_names_compatible(a, b, prefix_min=FIRST_NAME_PREFIX_MIN):
    """Whether two first names plausibly denote one person.

    True when either is a prefix of the other (Leo/Leonardo, Josh/Joshua,
    Mitch/Mitchell, Cam/Cameron, Brad/Bradley, Matt/Matthew) or when they share
    at least prefix_min characters (Harry/Harrison). Never used on its own: the
    caller must already have matched surname, team and round, and must have
    established that the surname is unique within that team and round on both
    sides.
    """
    if not a or not b:
        return False
    if a == b:
        return True
    if a.startswith(b) or b.startswith(a):
        return True
    shared = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            break
        shared += 1
    return shared >= prefix_min


# ── First-name overrides (layer 2b) ──────────────────────────
# The irreducible residue, and ONLY that. Every entry here is a first-name pair
# that first_names_compatible cannot bridge, verified against the 2026 feeds:
#
#   tom/thomas      share 1 character
#   ollie/oliver    share 2
#   joe/joseph      share 2
#   talor/taylor    share 2   (a spelling variant, not a diminutive)
#   nick/nicholas   share 3
#
# BIDIRECTIONAL. Each entry is an unordered equivalence class, so it does not
# matter which side of a merge spells the name which way, and no entry has to
# be written twice.
#
# Consulted ONLY after layers 1 and 2 have both failed, never before. That is
# what keeps two mechanisms off the same name: josh/joshua, mitch/mitchell,
# cam/cameron and the rest already resolve on the prefix rule and never reach
# this map, so there is deliberately no entry for them. Adding one would be
# dead weight that looks load-bearing.
#
# Every hit is logged with feed, player, team and round. An entry that stops
# firing has stopped being needed, and the log is how you find that out.
_FIRST_NAME_ALIAS_GROUPS = [
    {'tom', 'thomas'},
    {'ollie', 'oliver'},
    {'nick', 'nicholas'},
    {'joe', 'joseph'},
    {'talor', 'taylor'},
]
FIRST_NAME_ALIASES = {n: i for i, g in enumerate(_FIRST_NAME_ALIAS_GROUPS)
                      for n in g}


def first_names_aliased(a, b):
    """Whether an explicit override pairs these two first names.

    Symmetric. Returns False for names the prefix rule already handles, because
    they are not in the map: this is the fallback, not a parallel path.
    """
    if not a or not b or a == b:
        return False
    ga, gb = FIRST_NAME_ALIASES.get(a), FIRST_NAME_ALIASES.get(b)
    return ga is not None and ga == gb


def resolve_feed_names(feed, target, feed_name_col, feed_team_col,
                       feed_round_col, target_name_col='Player_Name',
                       target_team_col='Playing.for',
                       target_round_col='Round_num', label='feed',
                       verbose=True):
    """Map a feed's player names onto the AFLTables spelling, then report.

    Three layers, applied in order, each only to what the previous left over:

      1. Canonical key (normalise_name) on both sides. Removes case, accents,
         apostrophes, periods, hyphens, spaces, generational suffixes and lone
         middle initials.
      2. Surname + team + round, accepted only when that surname is unique
         within the team and round ON BOTH SIDES and the first names pass
         first_names_compatible. Team and round are doing the work that string
         normalisation cannot: roughly 23 players per team per round, so a
         surname is almost always unique, and where it is not the uniqueness
         test refuses rather than guessing.
      3. Whatever is left is logged per row and tallied per feed.

    Two players sharing a name at different clubs can never merge, because team
    is part of the key at every layer. The West Coast and Western Bulldogs
    Bailey Williamses stay distinct, and Wheelo's "Bailey J. Williams" resolves
    onto the West Coast one via layer 1's middle-initial rule.

    Returns (feed_with_resolved_names, unmatched_frame). The feed's name column
    is rewritten in place to the AFLTables spelling, so every existing merge
    keeps its keys and its semantics.
    """
    feed = feed.copy()
    feed['_norm'] = feed[feed_name_col].map(normalise_name)
    target = target.copy()
    target['_norm'] = target[target_name_col].map(normalise_name)

    # ── Layer 1 ──
    # Team-keyed first, because that is the only thing separating two players
    # who share a name at different clubs.
    canon = (target.drop_duplicates(subset=['_norm', target_team_col])
                   .set_index(['_norm', target_team_col])[target_name_col])
    idx = pd.MultiIndex.from_arrays([feed['_norm'], feed[feed_team_col]])
    resolved = pd.Series(canon.reindex(idx).values, index=feed.index)

    # Then team-agnostic, but ONLY for a normalised name that maps to exactly
    # one target spelling league-wide. Without this a feed that spells clubs its
    # own way ("Brisbane" for "Brisbane Lions", "GWS Giants" for "Greater
    # Western Sydney") loses players whose names were never in doubt, which is
    # worse than not keying on team at all. Uniqueness is what keeps it safe: a
    # name shared by two players falls through to the team-keyed result only.
    by_name = target.groupby('_norm')[target_name_col].unique()
    unique_names = {k: v[0] for k, v in by_name.items() if len(v) == 1}
    if resolved.isna().any():
        fallback = feed.loc[resolved.isna(), '_norm'].map(unique_names)
        resolved.loc[fallback.index] = fallback.values
    n_layer1 = int(resolved.notna().sum())

    # ── Layer 2 ──
    tparts = target[target_name_col].apply(name_parts)
    target['_first'] = [p[0] for p in tparts]
    target['_surname'] = [p[1] for p in tparts]
    fparts = feed[feed_name_col].apply(name_parts)
    feed['_first'] = [p[0] for p in fparts]
    feed['_surname'] = [p[1] for p in fparts]

    # Unique surname within team+round, on the target side. feed_round_col=None
    # scopes on team alone, for a feed that carries no fixture context (the
    # season-level leaderboards). The uniqueness test still applies, and the
    # 2026 sweep found 14 surname collisions at team+season scope and zero
    # accepts among them, so the weaker scope is not a weaker guarantee here.
    tkey = ([target_team_col, target_round_col, '_surname'] if feed_round_col
            else [target_team_col, '_surname'])
    tuniq = (target.drop_duplicates(subset=tkey + [target_name_col])
                   .groupby(tkey)
                   .filter(lambda g: g[target_name_col].nunique() == 1)
                   .drop_duplicates(subset=tkey)
                   .set_index(tkey)[[target_name_col, '_first']])

    # ...and on the feed side, so a feed listing two same-surname players in one
    # team and round cannot collapse both onto the single target player.
    fkey = ([feed_team_col, feed_round_col, '_surname'] if feed_round_col
            else [feed_team_col, '_surname'])
    fdupe = (feed.groupby(fkey)[feed_name_col].transform('nunique') > 1)

    def _context_match(compat):
        """Surname+team(+round) match, gated by a first-name test.

        Runs against whatever is still unresolved, so layer 2b sees only what
        layer 2's prefix rule already refused.
        """
        pending = resolved.isna() & ~fdupe
        if not pending.any() or not len(tuniq):
            return pd.Series(dtype=object)
        sub = feed.loc[pending]
        look = pd.MultiIndex.from_arrays(
            [sub[feed_team_col], sub[feed_round_col], sub['_surname']]
            if feed_round_col else [sub[feed_team_col], sub['_surname']])
        cand = tuniq.reindex(look)
        ok = cand[target_name_col].notna().values & [
            compat(f, t)
            for f, t in zip(sub['_first'], cand['_first'].fillna(''))
        ]
        return pd.Series(cand[target_name_col].values, index=sub.index)[ok]

    accepted = _context_match(first_names_compatible)
    resolved.loc[accepted.index] = accepted.values
    n_layer2 = int(len(accepted))

    # ── Layer 2b: explicit overrides, last resort ──
    aliased = _context_match(first_names_aliased)
    resolved.loc[aliased.index] = aliased.values
    n_alias = int(len(aliased))

    # ── Layer 3 ──
    _cols = [feed_name_col, feed_team_col] + ([feed_round_col] if feed_round_col else [])
    unmatched = feed.loc[resolved.isna(), _cols].copy()
    _scope = 'surname+team+round' if feed_round_col else 'surname+team'
    if verbose:
        print(f"  [{label}] names resolved: {n_layer1} exact/canonical, "
              f"{n_layer2} via {_scope}, {n_alias} via override map, "
              f"{len(unmatched)} unmatched")
        # Every override hit, so the map's usage stays visible. An entry that
        # has stopped firing has stopped being needed.
        for _i in aliased.index:
            _rd = f", round {feed.loc[_i, feed_round_col]}" if feed_round_col else ""
            print(f"    OVERRIDE {label}: {feed.loc[_i, feed_name_col]!r} -> "
                  f"{aliased[_i]!r} ({feed.loc[_i, feed_team_col]}{_rd})")
        if len(unmatched):
            shown = (unmatched.groupby(
                [feed_name_col, feed_team_col]).size()
                .sort_values(ascending=False))
            for (nm, tm), cnt in shown.items():
                if feed_round_col:
                    rounds = sorted(unmatched.loc[
                        (unmatched[feed_name_col] == nm)
                        & (unmatched[feed_team_col] == tm), feed_round_col].unique())
                    print(f"    UNMATCHED {label}: {nm!r} ({tm}) "
                          f"x{cnt} round(s) {rounds}")
                else:
                    print(f"    UNMATCHED {label}: {nm!r} ({tm}) x{cnt}")

    out = feed.drop(columns=['_norm', '_first', '_surname'])
    out[feed_name_col] = resolved.where(resolved.notna(), feed[feed_name_col])
    return out, unmatched


def resolve_names_simple(feed, target_names, feed_name_col, label='feed',
                         verbose=True):
    """Layer 1 only, for feeds carrying no team or round column.

    The season-level Betfair / ESPN / AFL Predictor leaderboards are one row per
    player with no fixture context, so layer 2 has nothing to key on. Layer 1
    still fixes every apostrophe, Mc/Mac, particle, hyphen, initial and suffix
    case, which is what those three feeds actually suffer from.
    """
    feed = feed.copy()
    canon = {}
    for nm in target_names:
        canon.setdefault(normalise_name(nm), nm)
    resolved = feed[feed_name_col].map(lambda n: canon.get(normalise_name(n)))
    unmatched = feed.loc[resolved.isna(), [feed_name_col]].copy()
    if verbose:
        print(f"  [{label}] names resolved: {int(resolved.notna().sum())}, "
              f"{len(unmatched)} unmatched")
        for nm in sorted(unmatched[feed_name_col].astype(str).unique()):
            print(f"    UNMATCHED {label}: {nm!r}")
    feed[feed_name_col] = resolved.where(resolved.notna(), feed[feed_name_col])
    return feed, unmatched


# ── Row-local derived stats ──────────────────────────────────
# Everything computable from a single player-game row, in the exact order the
# three scripts built it. Centralised because it was NOT before: predict_2026.py
# carried a stale four-term Impact_Score (Goals/Clearances/Contested/Kicks) while
# training and backtest used the six-term formula below, so the model was scored
# on an Impact_Score it had never been trained on. One definition now, imported
# by all three, so that can't recur — see the module docstring.

# Coerced to numeric (missing columns tolerated) before the ratios/Impact build.
NUMERIC_STATS = ['Kicks', 'Handballs', 'Disposals', 'Goals', 'Marks', 'Tackles',
                 'Hit.Outs', 'Clearances', 'Contested.Possessions',
                 'Uncontested.Possessions', 'Contested.Marks', 'Marks.Inside.50',
                 'Goal.Assists', 'Inside.50s', 'Rebounds', 'One.Percenters', 'Clangers']

# LabelEncoder classes for Margin_Bucket. Already sorted, so a fresh fit and the
# pickled encoder agree; the encoder itself stays script-side (fit in training,
# unpickled at predict).
MARGIN_BUCKETS = ['big_loss', 'big_win', 'close_loss', 'close_win',
                  'comfortable_loss', 'comfortable_win', 'draw', 'unknown']


def get_outcome(row):
    """W/L/D and signed margin from the player's team's perspective."""
    h, a = row['Home.score'], row['Away.score']
    if pd.isna(h) or pd.isna(a):
        return pd.Series({'Outcome': 'U', 'Margin': 0})
    margin = h - a if row['Home.Away'] == 'Home' else a - h
    return pd.Series({'Outcome': 'W' if margin > 0 else ('L' if margin < 0 else 'D'), 'Margin': margin})


def margin_bucket(m):
    """Signed margin -> a MARGIN_BUCKETS label (never 'unknown'; that's for NaN)."""
    if m > 0:
        return 'close_win' if m <= 15 else ('comfortable_win' if m <= 40 else 'big_win')
    elif m < 0:
        return 'close_loss' if m >= -15 else ('comfortable_loss' if m >= -40 else 'big_loss')
    return 'draw'


def add_row_stats(df):
    """All single-row derived stats, in the scripts' original order.

    Outcome/Margin/Abs_Margin/Is_Win/Is_Loss, then numeric coercion, the four
    ratios, Score_Involvements, the six-term Impact_Score, and the Margin_Bucket
    string. Margin_Bucket_enc is left to the caller: its LabelEncoder is fit in
    training but unpickled at predict, so the source differs by script.

    Assumes Home.score / Away.score / Home.Away already coerced upstream, as all
    three scripts do immediately before calling this.
    """
    df[['Outcome', 'Margin']] = df.apply(get_outcome, axis=1)
    df['Abs_Margin'] = df['Margin'].abs()
    df['Is_Win'] = (df['Outcome'] == 'W').astype(int)
    df['Is_Loss'] = (df['Outcome'] == 'L').astype(int)

    for col in NUMERIC_STATS:
        df[col] = pd.to_numeric(df.get(col, 0), errors='coerce').fillna(0)

    df['Kick_to_HB_ratio'] = df['Kicks'] / (df['Handballs'] + 1)
    df['Contested_rate'] = df['Contested.Possessions'] / (df['Disposals'] + 1)
    df['Disposal_efficiency'] = (df['Disposals'] - df['Clangers']) / (df['Disposals'] + 1)
    df['Score_Involvements'] = (df['Goals'] + df['Goal.Assists'] +
                                df['Marks.Inside.50'] + df['Inside.50s'])
    df['Impact_Score'] = (df['Contested.Possessions'] * 2.85 + df['Hit.Outs'] * 1.51 +
                          df['Marks'] * 3.5 + df['Marks.Inside.50'] * 3.81 +
                          df['Score_Involvements'] * 1.65 + df['Tackles'] * 2.93)

    df['Margin_Bucket'] = df['Margin'].apply(margin_bucket)
    return df


# ── Feature groups ───────────────────────────────────────────
BASE_FEATURES = ['Kicks', 'Handballs', 'Disposals', 'Goals', 'Marks', 'Tackles', 'Hit.Outs',
                 'Clearances', 'Contested.Possessions', 'Uncontested.Possessions',
                 'Contested.Marks', 'Marks.Inside.50', 'Goal.Assists', 'Inside.50s',
                 'Rebounds', 'One.Percenters', 'Clangers', 'Kick_to_HB_ratio',
                 'Contested_rate', 'Disposal_efficiency', 'Score_Involvements',
                 'Impact_Score', 'Is_Win', 'Is_Loss', 'Margin', 'Abs_Margin',
                 'Coaches_Votes', 'Season', 'Margin_Bucket_enc']

RANK_STATS_BASE = ['Disposals', 'Goals', 'Contested.Possessions', 'Clearances',
                   'Kicks', 'Impact_Score', 'Score_Involvements', 'Coaches_Votes', 'Tackles']
RANK_STATS_WHEELO = ['RatingPoints', 'ExpVotes']

WHEELO_COLS = ['RatingPoints', 'ExpVotes', 'Rating_Q1', 'Rating_Q2', 'Rating_Q3', 'Rating_Q4',
               'Equity_PreClearance', 'Equity_PostClearance', 'Equity_Possession', 'Equity_BallUse',
               'GroundBallGets', 'HitoutsToAdvantage', 'ScoreLaunches', 'FirstPossessions',
               'Supercoach', 'TimeOnGround', 'DisposalEfficiency', 'CentreBounceAttendancePercentage']

# The six same-game coaches features. The NO_COACHES variant omits exactly these.
COACHES_FEATURES = ['Coaches_Votes', 'Coaches_Votes_game_rank', 'Coaches_Votes_game_pct',
                    'Coaches_Votes_game_z', 'Top3_Coaches', 'BOG_Coaches']

# ── Momentum ─────────────────────────────────────────────────
# Point-in-time: shift(1) first so the current game is never part of its own
# feature, then trailing windows over strictly prior rounds. The version this
# replaced took the last six games of the COMPLETED season minus the first six
# and broadcast one value onto every row, so a round-2 row carried round-23
# information. That leak was invisible to GroupKFold because it lived in the
# features, not the split.
MOM_RECENT = 6
MOM_MIN_EARLIER = 2


def pit_momentum(s):
    """Trailing recent-minus-earlier for one player-season, in round order.

    recent  = mean of the previous MOM_RECENT games
    earlier = mean of every game before those
    Needs MOM_RECENT + MOM_MIN_EARLIER prior games; NaN below that.
    """
    prior = s.shift(1)
    recent_sum = prior.rolling(MOM_RECENT, min_periods=MOM_RECENT).sum()
    recent_mean = recent_sum / MOM_RECENT
    all_sum = prior.expanding(min_periods=1).sum()
    all_cnt = prior.expanding(min_periods=1).count()
    earlier_sum = all_sum - recent_sum
    earlier_cnt = all_cnt - MOM_RECENT
    ok = earlier_cnt >= MOM_MIN_EARLIER
    earlier_mean = earlier_sum.where(ok) / earlier_cnt.where(ok)
    return recent_mean - earlier_mean


# ── Construction ─────────────────────────────────────────────
def rank_stats_for(df):
    """The stats ranked within each game — Wheelo's two only when present."""
    stats = list(RANK_STATS_BASE)
    if 'RatingPoints' in df.columns:
        stats += RANK_STATS_WHEELO
    return stats


# Rank stats whose source can be entirely absent within a game. Wheelo began in
# 2015 (ExpVotes only exists for 2026); coaches votes are missing for 50 training
# games — whole rounds the fitzRoy source never covered (2011 R24, recent seasons'
# final H&A round, the 2025 Opening Round), NOT games where no votes were awarded.
# A game with an all-zero source has no real ranking, so its rank/pct/flags are
# neutralised to NaN — see build_game_rank_features. Base stats (Disposals etc.)
# are never all-zero and so never trigger it. (Predict handles the same coaches
# gap differently, by routing whole games to the NO_COACHES variant.)
ZERO_SOURCE_GUARD_STATS = set(RANK_STATS_WHEELO) | {'Coaches_Votes'}


def build_game_rank_features(df, rank_stats, fill_missing=False):
    """Per-game rank / percentile / z-score for each stat.

    Within-game only, so no cross-season leakage: these describe how a player
    compared to the 43 others in the game whose votes are being predicted.

    All-zero-source guard (ZERO_SOURCE_GUARD_STATS): when a guarded source is
    entirely absent/zero within a game — every pre-2015 game for RatingPoints,
    every pre-2026 game for ExpVotes, 50 missing-data games for Coaches_Votes —
    the "rank" is a meaningless tie: rank 1
    for all 44 players, pct a game-size proxy (~0.5114), z 0. That asserts every
    player led the game. The raw value and its rank/pct/z are set to NaN instead,
    so XGBoost learns a default direction rather than a false leader. Same defect,
    same fix as the coaches-vote degeneracy.

    fill_missing=True leaves a triplet NaN when its source stat is absent from the
    whole frame — the predict path needs a row for every player and cannot drop
    them, and NaN (not 0) is the correct neutral value here too.
    """
    for stat in rank_stats:
        if stat in df.columns:
            g = df.groupby('Game_ID')[stat]
            df[f'{stat}_game_rank'] = g.rank(ascending=False, method='min')
            df[f'{stat}_game_pct'] = g.rank(pct=True)
            df[f'{stat}_game_z'] = g.transform(lambda x: (x - x.mean()) / (x.std() + 0.001))
            if stat in ZERO_SOURCE_GUARD_STATS:
                dead = g.transform(lambda x: x.abs().max()).fillna(0).eq(0)
                if dead.any():
                    df.loc[dead, [stat, f'{stat}_game_rank',
                                  f'{stat}_game_pct', f'{stat}_game_z']] = np.nan
        elif fill_missing:
            df[f'{stat}_game_rank'] = np.nan
            df[f'{stat}_game_pct'] = np.nan
            df[f'{stat}_game_z'] = np.nan
    return df


def _rank_flag(df, rank_col, threshold):
    """(rank <= threshold) as float, but NaN where the rank itself is NaN — so an
    all-zero-source game does not claim every player as BOG/Top3."""
    r = df[rank_col]
    out = (r <= threshold).astype(float)
    out[r.isna()] = np.nan
    return out


def build_rank_flags(df, include_coaches=True):
    """Top-3 and best-on-ground flags off the game ranks."""
    # Assignment order is deliberate: it reproduces the column order the scripts
    # produced before this module existed, so the output CSVs stay byte-identical
    # across the refactor rather than differing only by column position.
    # rank == 1 and rank <= 1 coincide (ranks are >= 1), so BOG uses threshold 1.
    _cv = include_coaches and 'Coaches_Votes_game_rank' in df.columns
    df['Top3_Disposals'] = _rank_flag(df, 'Disposals_game_rank', 3)
    if _cv:
        df['Top3_Coaches'] = _rank_flag(df, 'Coaches_Votes_game_rank', 3)
    df['Top3_Impact'] = _rank_flag(df, 'Impact_Score_game_rank', 3)
    df['BOG_Disposals'] = _rank_flag(df, 'Disposals_game_rank', 1)
    if _cv:
        df['BOG_Coaches'] = _rank_flag(df, 'Coaches_Votes_game_rank', 1)
    df['BOG_Impact'] = _rank_flag(df, 'Impact_Score_game_rank', 1)
    if 'RatingPoints_game_rank' in df.columns:
        df['BOG_Rating'] = _rank_flag(df, 'RatingPoints_game_rank', 1)
        df['Top3_Rating'] = _rank_flag(df, 'RatingPoints_game_rank', 3)
    return df


def wheelo_derived_features(df):
    """Feature names derived from a Wheelo source and present in df: the base
    Wheelo columns plus the RatingPoints/ExpVotes rank triplets and Rating flags.

    These are legitimately NaN in all-zero-source games (every pre-2015 game, and
    every training game for ExpVotes), so the trainer must keep them OUT of its
    dropna subset or it silently deletes every pre-Wheelo row — turning the fix
    into "train on 2015+ only". Base stats and coaches features stay in dropna."""
    cols = [c for c in WHEELO_COLS if c in df.columns]
    cols += [c for c in ('Rating_Q4_premium', 'Best_quarter_rating') if c in df.columns]
    for s in RANK_STATS_WHEELO:
        cols += [f'{s}_game_rank', f'{s}_game_pct', f'{s}_game_z']
    cols += ['BOG_Rating', 'Top3_Rating']
    return [c for c in dict.fromkeys(cols) if c in df.columns]


def build_form_features(df, group_keys, include_momentum_cv=True):
    """late_form_ewm + momentum, both strictly prior-round.

    group_keys is ['Season','Player_Name'] across seasons, ['Player_Name'] for a
    single-season frame. Caller must have sorted by those keys plus Round_num.

    late_form_ewm reads ExpVotes (Wheelo) when available. The Coaches_Votes
    fallback does not fire on current data — wheelo_all_seasons.csv carries
    ExpVotes for every season — so this feature is Wheelo-derived, not
    coaches-derived, and stays in the NO_COACHES variant.
    """
    src = 'ExpVotes' if 'ExpVotes' in df.columns else 'Coaches_Votes'
    if src in df.columns:
        df['late_form_ewm'] = (
            df.groupby(group_keys)[src]
            .transform(lambda x: x.shift(1).ewm(span=5, min_periods=1).mean())
            .fillna(0)
        )
    else:
        df['late_form_ewm'] = 0

    specs = [('Coaches_Votes', 'momentum_cv'), ('Disposals', 'momentum_disp')]
    if not include_momentum_cv:
        specs = [(s, o) for s, o in specs if o != 'momentum_cv']
    for src_col, out_col in specs:
        df[out_col] = (df.groupby(group_keys)[src_col]
                         .transform(pit_momentum)
                         .fillna(0))
    return df


def form_feature_names(df):
    return [f for f in ('late_form_ewm', 'momentum_cv', 'momentum_disp') if f in df.columns]


def assemble_features(df, rank_stats, wheelo_features, form_features,
                      include_coaches=True, include_momentum_cv=True):
    """The final ordered feature list, filtered to what the frame actually has.

    include_coaches=False is the NO_COACHES variant. The assertion is the point:
    a coaches feature surviving into that variant would be trained on data that
    does not exist at predict time, and nothing downstream would say so.
    """
    relative = (
        [f'{s}_game_rank' for s in rank_stats if f'{s}_game_rank' in df.columns] +
        [f'{s}_game_pct' for s in rank_stats if f'{s}_game_pct' in df.columns] +
        [f'{s}_game_z' for s in rank_stats if f'{s}_game_z' in df.columns] +
        ['Top3_Disposals', 'Top3_Coaches', 'Top3_Impact',
         'BOG_Disposals', 'BOG_Coaches', 'BOG_Impact']
    )
    if 'BOG_Rating' in df.columns:
        relative += ['BOG_Rating', 'Top3_Rating']

    features = list(dict.fromkeys(
        BASE_FEATURES + list(wheelo_features) + relative + list(form_features)))
    features = [f for f in features if f in df.columns]

    if not include_coaches:
        features = [f for f in features if 'Coaches' not in f]
        if not include_momentum_cv:
            features = [f for f in features if f != 'momentum_cv']
        leaked = [f for f in features if 'Coaches' in f]
        if not include_momentum_cv:
            leaked += [f for f in features if f == 'momentum_cv']
        assert not leaked, f"NO_COACHES feature set still carries: {leaked}"
    return features
