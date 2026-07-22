"""
backfill_game_level.py

Backfills Team, Home.team, Away.team, Home.score, Away.score into
predictions/game_level_2007-2025.csv so every season carries the same
match-level columns the 2026 file already has (which is what Game Analysis
renders from).

Sources:
  - Team  : a straight copy of the in-file 'Playing.for' column. No join.
            game_level_2026.csv stores Team in the *alias* form ('GWS',
            'Footscray') and Playing.for in the expanded form ('Greater
            Western Sydney', 'Western Bulldogs'). dashboard.load_game() runs
            _fix_team_names() on read, which maps both columns through
            _TEAM_ALIASES, so the two are equivalent by the time anything
            reads them. Pre-flight A proves that. Copying Playing.for
            therefore produces a Team column the dashboard cannot
            distinguish from 2026's.
  - The four match columns: joined from fitzroy_stats_all.csv on
    Season + Round_num + ID (player id), with a name-based fallback (see
    below). fitzroy 'Round' is a string that includes finals labels
    (QF/EF/SF/PF/GF); it is coerced with pd.to_numeric(..., errors='coerce')
    and NaN rows dropped, exactly as brownlow_model.py builds Round_num.

Join key:
  Primary  : Season + Round_num + ID
  Fallback : Season + Round_num + Playing.for + Player_Name, used only for
             rows the primary key cannot resolve because ID is blank on one
             side or the other. Four 2025 rows need this (Billy Wilson,
             Carlton, rounds 17/23/24/25) - fitzroy carries no ID and no
             Player for them, only First.name/Surname. Both keys are unique
             on the fitzroy side, so neither join can inflate row counts.

Known data conditions, reported but NOT fatal:
  - game_level_2025.csv has 39 players duplicated at Round_num 24 (78 rows).
    Both rows of each pair are the same player-game and take the same match
    values, so the join is well-defined. Reported, not aborted on.

Safety model:
  - Defaults to a DRY RUN. Reports every check below and changes nothing.
  - Applying requires the explicit --apply flag.
  - On --apply, augmented files are written to predictions/_backfill_staging/
    first, EVERY check is re-run against the staged files, and only if all
    pass are the originals overwritten in place.

Run:
    python backfill_game_level.py            # dry run (default)
    python backfill_game_level.py --apply     # write, after staged re-check
"""

import argparse
import os
import shutil

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.abspath(__file__))
PRED_DIR = os.path.join(REPO, "predictions")
FITZ_PATH = os.path.join(REPO, "fitzroy_stats_all.csv")
CONTROL_PATH = os.path.join(REPO, "data_2026", "afltables_2026.csv")
STAGING_DIR = os.path.join(PRED_DIR, "_backfill_staging")

SEASONS = list(range(2007, 2026))          # 2007..2025 inclusive
CONTROL_SEASON = 2026                       # known-good file with all columns

ID_KEYS = ["Season", "Round_num", "ID"]                 # primary join key
NAME_KEYS = ["Season", "Round_num", "_team_key", "_name_key"]   # fallback key
JOIN_COLS = ["Home.team", "Away.team", "Home.score", "Away.score"]
TEAM_COL = "Team"          # copied from Playing.for
SOURCE_TEAM_COL = "Playing.for"
SCORE_COLS = {"Home.score", "Away.score"}   # numeric-compared; others string

# Mirrors dashboard._TEAM_ALIASES exactly. Kept as a local copy so this
# script does not import dashboard.py (which pulls in streamlit).
_TEAM_ALIASES = {
    'Footscray': 'Western Bulldogs',
    'GWS': 'Greater Western Sydney',
    'Kangaroos': 'North Melbourne',
}


def _fix_team_names(df):
    """Mirrors dashboard._fix_team_names(): map both team columns through
    _TEAM_ALIASES. dashboard.load_game() applies this on every read, so any
    comparison that claims to reflect what the dashboard sees must apply it
    first."""
    out = df.copy()
    for col in ('Team', 'Playing.for'):
        if col in out.columns:
            out[col] = out[col].replace(_TEAM_ALIASES)
    return out


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------
def _gl_path(season, base=PRED_DIR):
    return os.path.join(base, f"game_level_{season}.csv")


def _read_verbatim(path):
    """Read a CSV as pure text, preserving every cell exactly as stored.

    This is load-bearing, not a style choice. pandas' default read_csv float
    parser is not correctly-rounded, so parsing a float column to float64 and
    writing it back with to_csv shifts the last ULP on a small fraction of
    rows (measured: 31 of 7,744 in game_level_2007.csv, max abs diff 4.4e-16,
    e.g. 2.6744837133101753 -> 2.6744837133101758). Those columns are inputs
    the model already trained on; rewriting them at all - even by a rounding
    artefact in the 16th significant digit - is out of scope for a backfill
    that is only supposed to ADD columns.

    Reading as str and appending new columns means every pre-existing column
    is written back byte-identical, and the "existing values unchanged" check
    becomes an exact text comparison rather than a float tolerance argument.
    """
    return pd.read_csv(path, dtype=str, keep_default_na=False, low_memory=False)


# Missing-value spellings that survive a verbatim read. fitzroy_stats_all.csv
# and afltables_2026.csv come from R/fitzRoy, which writes the literal token
# NA rather than an empty field, so keep_default_na=False preserves it as the
# four-character string "NA". Every missingness test in this script must go
# through _blank(); comparing against "" alone silently treats those cells as
# real values (it made the name fallback key on the string "NA" and drop from
# 65 resolved rows to 10).
_MISSING_TOKENS = {"", "na", "n/a", "nan", "<na>"}


def _blank(s):
    """True where a verbatim (text) cell is missing, empty, or an NA token."""
    t = s.astype("string").str.strip()
    return t.isna() | t.str.lower().isin(_MISSING_TOKENS)


def _norm_id_keys(df):
    """Coerce the three primary join keys to a common nullable-int dtype so the
    merge lines up regardless of how each file stored them (float/int/str)."""
    out = df.copy()
    for k in ID_KEYS:
        out[k] = pd.to_numeric(out[k], errors="coerce").astype("Int64")
    return out


def _add_name_keys(df, team_col, name_col, first_col=None, surname_col=None):
    """Add the normalised team/name columns the fallback join uses.

    Team goes through _TEAM_ALIASES so the two sides agree on club naming.
    Name falls back to 'First.name Surname' when the combined name column is
    blank - fitzroy leaves Player empty for the Billy Wilson rows but still
    carries First.name and Surname.
    """
    out = df.copy()
    out["_team_key"] = (out[team_col].replace(_TEAM_ALIASES)
                        .astype("string").str.strip())
    if name_col in out.columns:
        name = out[name_col].astype("string").str.strip()
        name = name.mask(_blank(name), pd.NA)    # "" and the literal "NA"
    else:
        name = pd.Series(pd.NA, index=out.index, dtype="string")
    if first_col in out.columns and surname_col in out.columns:
        first = out[first_col].astype("string").str.strip()
        sur = out[surname_col].astype("string").str.strip()
        built = (first.mask(_blank(first), pd.NA) + " "
                 + sur.mask(_blank(sur), pd.NA))
        name = name.fillna(built)
    out["_name_key"] = name
    return out


def _load_source(path, label):
    """Load a match-stats source (fitzroy or afltables_2026) reduced to both
    join keys + the four match columns. Round is coerced the
    brownlow_model.py way (to_numeric, drop NaN).

    Read verbatim so the four match columns carry the source's exact text
    into the target files.
    """
    src = _read_verbatim(path)
    need = ["Season", "Round", "ID", "Playing.for"] + JOIN_COLS
    missing = [c for c in need if c not in src.columns]
    if missing:
        raise SystemExit(f"ABORT: {label} missing columns: {missing}")
    src = src.rename(columns={"Round": "Round_num"})
    src["Round_num"] = pd.to_numeric(src["Round_num"], errors="coerce")
    src = src[src["Round_num"].notna()].copy()      # drop finals / string rounds
    src = _add_name_keys(src, "Playing.for", "Player", "First.name", "Surname")
    src = _norm_id_keys(src)

    by_id = src.dropna(subset=ID_KEYS)[ID_KEYS + JOIN_COLS].copy()
    by_name = src.dropna(subset=["Season", "Round_num"])
    by_name = by_name[by_name["_name_key"].notna()][NAME_KEYS + JOIN_COLS].copy()
    # Both keys are unique on the source side; guard so a future source that
    # breaks that assumption cannot silently inflate the left frame.
    by_id = by_id.drop_duplicates(ID_KEYS)
    by_name = by_name.drop_duplicates(NAME_KEYS)
    return {"by_id": by_id, "by_name": by_name, "raw_rows": len(src)}


def _values_equal(a, b, numeric):
    """Elementwise equality tolerant of dtype: numeric cols compared as floats
    (with NaN==NaN treated equal), string cols compared as stripped strings."""
    a = a.reset_index(drop=True)
    b = b.reset_index(drop=True)
    if numeric:
        an = pd.to_numeric(a, errors="coerce")
        bn = pd.to_numeric(b, errors="coerce")
        return (an == bn) | (an.isna() & bn.isna())
    as_ = a.astype("string").str.strip()
    bs_ = b.astype("string").str.strip()
    return (as_ == bs_) | (as_.isna() & bs_.isna())


def join_match_cols(df, source):
    """Two-stage left join. Returns (values_df, n_fallback).

    values_df holds the four match columns aligned to df's row order.
    n_fallback is the number of rows the primary ID join could not resolve
    that the name fallback did.
    """
    left = _add_name_keys(df, SOURCE_TEAM_COL, "Player_Name")
    left = _norm_id_keys(left)
    left["_row_order"] = np.arange(len(left))

    primary = left[["_row_order"] + ID_KEYS].merge(
        source["by_id"], on=ID_KEYS, how="left")
    primary = primary.sort_values("_row_order").reset_index(drop=True)
    vals = primary[JOIN_COLS].copy()

    unresolved = vals.isna().all(axis=1)
    n_fallback = 0
    if unresolved.any():
        fb = left.loc[unresolved.values, ["_row_order"] + NAME_KEYS].merge(
            source["by_name"], on=NAME_KEYS, how="left")
        fb = fb.sort_values("_row_order").reset_index(drop=True)
        got = fb[JOIN_COLS].notna().any(axis=1)
        n_fallback = int(got.sum())
        for c in JOIN_COLS:
            vals.loc[unresolved.values, c] = fb[c].values

    return vals.reset_index(drop=True), n_fallback


def build_augmented(df, source):
    """Return (out_df, stats). out_df = df + Team + the four match cols.

    df must come from _read_verbatim(), so every pre-existing column is
    carried through as untouched text.
    """
    original_cols = list(df.columns)
    vals, n_fallback = join_match_cols(df, source)

    out = df.reset_index(drop=True).copy()
    for c in JOIN_COLS:
        out[c] = vals[c].values
    out[TEAM_COL] = out[SOURCE_TEAM_COL].values   # copy, no join

    stats = {
        "rows_before": len(df),
        "rows_after": len(out),
        "nulls": {c: int(_blank(out[c]).sum()) for c in JOIN_COLS},
        "team_nulls": int(_blank(out[TEAM_COL]).sum()),
        "fallback": n_fallback,
        # existing columns must be unchanged
        "existing_changed": int(
            (~pd.DataFrame(
                {c: _values_equal(out[c], df[c], False)
                 for c in original_cols}
            ).all(axis=1)).sum()
        ),
        "original_cols": original_cols,
    }
    return out, stats


# ----------------------------------------------------------------------
# pre-flight checks
# ----------------------------------------------------------------------
def preflight_A():
    """Team vs Playing.for in game_level_2026.csv, compared the way the
    dashboard sees them - i.e. after _fix_team_names() has normalised both
    columns, which is what load_game() does on every read.

    Comparing the two columns RAW is the wrong test: it reports an 828-row
    divergence that is entirely GWS/Greater Western Sydney and
    Footscray/Western Bulldogs, an alias difference the dashboard erases
    before any code sees it. Only the post-normalisation count is meaningful,
    and only that count gates the run.
    """
    print("\n[A] Team == Playing.for in game_level_2026.csv, post-_fix_team_names()")
    df = _read_verbatim(_gl_path(CONTROL_SEASON))
    if TEAM_COL not in df.columns or SOURCE_TEAM_COL not in df.columns:
        print(f"    ABORT: 2026 file lacks '{TEAM_COL}' or '{SOURCE_TEAM_COL}'.")
        return False

    raw_eq = _values_equal(df[TEAM_COL], df[SOURCE_TEAM_COL], False)
    raw_diff = int((~raw_eq).sum())
    fixed = _fix_team_names(df)
    eq = _values_equal(fixed[TEAM_COL], fixed[SOURCE_TEAM_COL], numeric=False)
    ndiff = int((~eq).sum())

    print(f"    rows                        : {len(df):,}")
    print(f"    mismatches BEFORE normalise : {raw_diff:,}  (alias-only, not a defect)")
    print(f"    mismatches AFTER  normalise : {ndiff:,}")
    if raw_diff:
        pairs = df.loc[~raw_eq.values,
                       [SOURCE_TEAM_COL, TEAM_COL]].drop_duplicates()
        print("    alias pairs absorbed by _fix_team_names():")
        for _, r in pairs.iterrows():
            print(f"      Playing.for={r[SOURCE_TEAM_COL]!r} <-> Team={r[TEAM_COL]!r}")
    if ndiff == 0:
        print("    OK: identical once normalised. Copy approach is VALID.")
        return True
    print(f"    FAIL: {ndiff} rows still differ after normalising. Copy approach INVALID:")
    diffs = fixed.loc[~eq.values, [SOURCE_TEAM_COL, TEAM_COL]].drop_duplicates()
    for _, r in diffs.iterrows():
        print(f"      Playing.for={r[SOURCE_TEAM_COL]!r}  Team={r[TEAM_COL]!r}")
    return False


def preflight_B():
    """Control: reproduce game_level_2026's known-good match columns from
    data_2026/afltables_2026.csv.

    fitzroy_stats_all.csv covers 2007-2025 only and has no 2026 rows, so it
    cannot serve as the control. afltables_2026.csv carries the same schema
    and is the only available source for a 2026 control.
    """
    print("\n[B] Control join: afltables_2026.csv -> game_level_2026.csv")
    if not os.path.exists(CONTROL_PATH):
        print(f"    ABORT: control source not found: {CONTROL_PATH}")
        return False

    src = _load_source(CONTROL_PATH, "data_2026/afltables_2026.csv")
    df = _read_verbatim(_gl_path(CONTROL_SEASON))
    known = df[JOIN_COLS].copy()
    print(f"    control source rows : {src['raw_rows']:,}")
    print(f"    game_level_2026 rows: {len(df):,}")

    vals, n_fallback = join_match_cols(df, src)
    all_ok = True
    for c in JOIN_COLS:
        eq = _values_equal(vals[c], known[c], c in SCORE_COLS)
        rate = float(eq.mean()) * 100
        flag = "" if rate == 100.0 else "   <-- NOT 100%"
        print(f"    {c:<12} match rate {rate:6.2f}%  ({int(eq.sum()):,}/{len(eq):,}){flag}")
        all_ok = all_ok and rate == 100.0
    print(f"    rows resolved via name fallback: {n_fallback}")
    print("    " + ("Join reproduces the known-good 2026 values exactly."
                    if all_ok else "Join does NOT fully reproduce 2026 values."))
    return all_ok


def preflight_C():
    """Exact player-id column name on each side."""
    print("\n[C] Player ID column name per side")
    gl = pd.read_csv(_gl_path(2015), nrows=0).columns.tolist()
    fz = pd.read_csv(FITZ_PATH, nrows=0).columns.tolist()
    gl_id = "ID" if "ID" in gl else "(missing)"
    fz_id = "ID" if "ID" in fz else "(missing)"
    print(f"    game_level_*.csv      : {gl_id}")
    print(f"    fitzroy_stats_all.csv : {fz_id}")
    return gl_id == "ID" and fz_id == "ID"


def preflight_D(source):
    """Key uniqueness / duplication survey.

    game_level duplicates are REPORTED, not fatal: game_level_2025.csv holds
    39 players duplicated at Round_num 24, and both rows of each pair are the
    same player-game taking the same match values. Source-side duplicates
    would be fatal (they would inflate the left frame), but both source keys
    are de-duplicated in _load_source(), so a left join cannot change row
    counts either way.
    """
    print("\n[D] Duplicate-key survey")
    ok = True

    fdup = source["by_id"][source["by_id"].duplicated(ID_KEYS, keep=False)]
    print(f"    fitzroy by_id key   : "
          f"{'unique' if len(fdup) == 0 else str(len(fdup)) + ' duplicate rows'}")
    if len(fdup):
        ok = False

    total_dup = 0
    for season in SEASONS:
        df = _norm_id_keys(_read_verbatim(_gl_path(season)))
        keyed = df.dropna(subset=ID_KEYS)
        dup = keyed[keyed.duplicated(ID_KEYS, keep=False)]
        if len(dup):
            total_dup += len(dup)
            by_round = {int(k): int(v)
                        for k, v in dup.groupby("Round_num").size().items()}
            print(f"    game_level_{season}.csv : {len(dup)} duplicate-key rows "
                  f"({len(dup.drop_duplicates(ID_KEYS))} distinct keys) "
                  f"by Round_num {by_round}  -- reported, not fatal")
    if total_dup == 0:
        print("    game_level_2007-2025 : key unique in every file.")
    else:
        print(f"    total game_level duplicate-key rows: {total_dup} "
              f"(same player-game, same match values -- continuing)")
    return ok


# ----------------------------------------------------------------------
# per-file dry-run report
# ----------------------------------------------------------------------
def per_file_report(source):
    print("\n[E] Per-file dry-run join report (2007-2025)")
    print(f"    {'season':<7}{'before':>8}{'after':>8}"
          f"{'nHome.t':>9}{'nAway.t':>9}{'nHome.s':>9}{'nAway.s':>9}"
          f"{'nTeam':>7}{'fallbk':>8}{'changed':>9}  flags")
    all_clean = True
    tally = {}
    total_fallback = 0

    for season in SEASONS:
        df = _read_verbatim(_gl_path(season))
        out, s = build_augmented(df, source)
        total_fallback += s["fallback"]
        flags = []
        if s["rows_after"] != s["rows_before"]:
            flags.append("ROWCOUNT")
        if any(s["nulls"][c] for c in JOIN_COLS):
            flags.append("NULLS")
        if s["team_nulls"]:
            flags.append("TEAM_NULLS")
        if s["existing_changed"]:
            flags.append("CHANGED")
        if flags:
            all_clean = False
        print(f"    {season:<7}{s['rows_before']:>8}{s['rows_after']:>8}"
              f"{s['nulls']['Home.team']:>9}{s['nulls']['Away.team']:>9}"
              f"{s['nulls']['Home.score']:>9}{s['nulls']['Away.score']:>9}"
              f"{s['team_nulls']:>7}{s['fallback']:>8}{s['existing_changed']:>9}"
              f"  {','.join(flags) if flags else 'clean'}")

        for col in ("Home.team", "Away.team", TEAM_COL):
            for v, c in out[col].value_counts(dropna=False).items():
                tally[v] = tally.get(v, 0) + int(c)

    print(f"\n    rows resolved via name fallback, all seasons: {total_fallback}")

    print("\n[F] Distinct Home.team / Away.team / Team values across 2007-2025 "
          "(pooled, sorted)")
    for v in sorted(tally, key=lambda x: str(x)):
        print(f"    {str(v):<26} {tally[v]:>8,}")

    return all_clean


# ----------------------------------------------------------------------
# apply
# ----------------------------------------------------------------------
def run_all_checks(source):
    return {
        "A": preflight_A(),
        "B": preflight_B(),
        "C": preflight_C(),
        "D": preflight_D(source),
        "E": per_file_report(source),
    }


def apply_backfill(source):
    """Stage every augmented file, re-verify against the staged copies, then
    overwrite the originals only if all staged checks pass."""
    print(f"\n[APPLY] staging directory: {STAGING_DIR}")
    if os.path.exists(STAGING_DIR):
        shutil.rmtree(STAGING_DIR)
    os.makedirs(STAGING_DIR)

    for season in SEASONS:
        df = _read_verbatim(_gl_path(season))
        out, _ = build_augmented(df, source)
        out.to_csv(_gl_path(season, base=STAGING_DIR), index=False)
    print(f"[APPLY] wrote {len(SEASONS)} staged files.")

    print("[APPLY] re-checking staged files:")
    staged_ok = True
    for season in SEASONS:
        orig = _read_verbatim(_gl_path(season))
        staged = _read_verbatim(_gl_path(season, base=STAGING_DIR))
        problems = []
        if len(staged) != len(orig):
            problems.append("ROWCOUNT")
        for c in JOIN_COLS + [TEAM_COL]:
            if c not in staged.columns:
                problems.append(f"MISSING:{c}")
            elif _blank(staged[c]).any():
                problems.append(f"NULL:{c}")
        for c in orig.columns:
            if not _values_equal(staged[c], orig[c], False).all():
                problems.append(f"CHANGED:{c}")
        if problems:
            staged_ok = False
        print(f"    game_level_{season}.csv : "
              f"{'clean' if not problems else ','.join(problems)}")

    if not staged_ok:
        print("[APPLY] ABORT: staged files failed re-check. Originals untouched.")
        print(f"[APPLY] staged files left for inspection: {STAGING_DIR}")
        return False

    for season in SEASONS:
        shutil.copy2(_gl_path(season, base=STAGING_DIR), _gl_path(season))
    print(f"[APPLY] overwrote {len(SEASONS)} originals in predictions/.")
    print(f"[APPLY] staging path: {STAGING_DIR}")
    return True


# ----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="write changes (default is a dry run)")
    ap.add_argument("--dry-run", action="store_true",
                    help="report only, change nothing (default)")
    args = ap.parse_args()
    apply_mode = args.apply and not args.dry_run

    print("=" * 78)
    print(f"backfill_game_level.py  -  {'APPLY' if apply_mode else 'DRY RUN'}")
    print("=" * 78)

    for p in (PRED_DIR, FITZ_PATH, CONTROL_PATH):
        if not os.path.exists(p):
            raise SystemExit(f"ABORT: required path not found: {p}")

    source = _load_source(FITZ_PATH, "fitzroy_stats_all.csv")
    print(f"fitzroy lookup rows (Round coerced, NaN dropped): {source['raw_rows']:,}")
    print(f"  keyed by ID   : {len(source['by_id']):,}")
    print(f"  keyed by name : {len(source['by_name']):,}")

    checks = run_all_checks(source)
    print("\n" + "-" * 78)
    print("CHECK SUMMARY: " + "  ".join(f"{k}={'PASS' if v else 'FAIL'}"
                                        for k, v in checks.items()))

    if not apply_mode:
        print("\nDRY RUN complete. No files changed. Re-run with --apply to write.")
        return

    if not all(checks.values()):
        raise SystemExit("\nABORT: not all checks passed; refusing to --apply.")
    apply_backfill(source)


if __name__ == "__main__":
    main()
