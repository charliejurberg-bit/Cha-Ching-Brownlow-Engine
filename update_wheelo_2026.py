"""
Quick updater: fetches missing 2026 rounds from wheeloratings.com and
appends to wheelo_2026.csv. Runs much faster than the full scraper.
"""

import os
import io
import time
import glob
import shutil
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

SEASON = 2026
DOWNLOAD_DIR = os.path.abspath("data_wheelo/downloads")
OUTPUT_CSV = "data_wheelo/wheelo_2026.csv"
AFLTABLES_CSV = "data_2026/afltables_2026.csv"
BASE_URL = "https://www.wheeloratings.com/afl_match_stats.html"

# ── Fetch outcomes ───────────────────────────────────────────
# These four are kept distinct on purpose. For the whole 2026 season this step
# collapsed every failure into one "no data" line, so a page that never loaded,
# a page that loaded with nothing on it, and a page whose round could not be
# read were indistinguishable in the console. That silence hid a real gap in
# round 23 (see rounds_needing_fetch) and cost a diagnosis. Any new failure
# mode gets its own status rather than folding into an existing one.
STATUS_OK = "OK"
STATUS_NOT_FETCHED = "NOT_FETCHED"
STATUS_EMPTY = "EMPTY"
STATUS_NO_ROUND = "NO_ROUND"

# ── Round numbering rule ─────────────────────────────────────
# The AFL introduced a standalone "Opening Round" in 2024. Wheelo numbers that
# fixture Round 0, so for any season with an Opening Round every Wheelo round
# sits one behind the AFLTables convention this repo uses everywhere:
#
#     afltables_round = wheelo_round + 1   for 2024, 2025, 2026
#     afltables_round = wheelo_round       for 2015-2023
#
# 2023 does NOT get the +1 — the AFL had no Opening Round that year, and
# wheelo_2023.csv on disk carries no offset, matching fitzroy_stats_all.csv on
# Disposals at 100% (n=7,730) with the round used as-is. The rule was
# previously written as `season >= 2023`, which would have applied a spurious
# +1 to 2023 and broken that alignment on any re-scrape.
#
# This script only ever runs for SEASON = 2026, which is on the +1 side of the
# rule, so the offset is unconditional here. The guard below keeps that
# assumption honest if SEASON is ever bumped or reused.
#
# The offset is a mapping between two numbering conventions, NOT a way of
# working out which round was fetched. That comes from Wheelo's own per-row
# MatchId (see attach_rounds). This distinction matters: the round used to be
# stamped from the loop counter that built the URL, so the stored round was an
# assertion about what the page *should* have contained rather than a reading
# of what it did contain.
OPENING_ROUND_FIRST_SEASON = 2024
ROUND_OFFSET = 1 if SEASON >= OPENING_ROUND_FIRST_SEASON else 0

# Wheelo's own published per-game Brownlow vote predictions. The dashboard's
# Model Comparison sums the 'Votes' column per player to reproduce
# wheeloratings.com's published leaderboard exactly (not our match-stats sum).
BROWNLOW_CSV_URL = "https://www.wheeloratings.com/src/data/wheelo-brownlow-predictions.csv"
BROWNLOW_OUTPUT = "data_2026/wheelo_brownlow_predictions.csv"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def fetch_brownlow_predictions():
    """Download Wheelo's published Brownlow vote predictions (plain CSV, no
    Selenium needed). Independent of the match-stats fetch below."""
    import requests
    try:
        os.makedirs(os.path.dirname(BROWNLOW_OUTPUT), exist_ok=True)
        resp = requests.get(
            BROWNLOW_CSV_URL,
            headers={"User-Agent": "Mozilla/5.0"}, timeout=30,
        )
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        if "Player" not in df.columns or "Votes" not in df.columns:
            print(f"  Brownlow predictions: unexpected columns "
                  f"{list(df.columns)[:6]} — skipped")
            return
        df.to_csv(BROWNLOW_OUTPUT, index=False)
        lead = (df.groupby("Player")["Votes"].sum()
                .sort_values(ascending=False).head(8))
        print(f"  Brownlow predictions: saved {len(df)} rows -> {BROWNLOW_OUTPUT}")
        print("  Top: " + ", ".join(f"{p} {v:.1f}" for p, v in lead.items()))
    except Exception as e:
        print(f"  Brownlow predictions fetch failed: {e}")


# ── Round derivation ─────────────────────────────────────────
def attach_rounds(df, requested_wheelo_round=None, season=SEASON):
    """Stamp Season/Round from Wheelo's OWN MatchId, never from a counter.

    A Wheelo MatchId is SSSSRRGG: 4-digit season, 2-digit Wheelo round, 2-digit
    game index. Opening Round is Wheelo round 0, so its first game is 20260001.
    The round token is page-native, and it is per game rather than per page, so
    a page that quietly serves a different round cannot be silently absorbed.

    Rows whose MatchId is not exactly 8 digits for the expected season are
    dropped rather than guessed at. If that leaves nothing, the caller gets
    STATUS_NO_ROUND and the round is skipped: a round we cannot label is not
    written under a label we invented.

    Returns (status, df, detail).
    """
    if df is None or len(df) == 0:
        return STATUS_EMPTY, None, "zero rows"

    if "MatchId" not in df.columns:
        cols = ", ".join(map(str, list(df.columns)[:6]))
        return STATUS_NO_ROUND, None, f"payload carries no MatchId column (saw: {cols})"

    # Normalise to text before matching. A MatchId column that picked up a NaN
    # becomes float dtype and renders as "20262206.0", which is still valid.
    ids = df["MatchId"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    well_formed = ids.str.fullmatch(r"\d{8}").fillna(False)
    right_season = ids.str[:4] == str(season)
    usable = well_formed & right_season

    if not usable.any():
        sample = ", ".join(repr(v) for v in ids.head(3).tolist())
        if well_formed.any():
            return STATUS_NO_ROUND, None, (
                f"MatchId season token is not {season} (sample: {sample})")
        return STATUS_NO_ROUND, None, (
            f"no MatchId parses as a round label (sample: {sample})")

    out = df[usable].copy()
    wheelo_rounds = ids[usable].str[4:6].astype(int)
    out["Season"] = season
    out["Round"] = wheelo_rounds + ROUND_OFFSET

    notes = [f"{len(out)} rows"]
    dropped = int((~usable).sum())
    if dropped:
        notes.append(f"{dropped} row(s) dropped for an unreadable MatchId")

    found = sorted(wheelo_rounds.unique())
    if len(found) > 1:
        notes.append(f"page spans Wheelo rounds {found}")
    if requested_wheelo_round is not None and found != [requested_wheelo_round]:
        # Trust the payload, flag the disagreement. Overriding the page with the
        # number we asked for is exactly the inferred-counter bug this replaces.
        notes.append(f"requested Wheelo round {requested_wheelo_round} "
                     f"but payload says {found} (payload wins)")

    return STATUS_OK, out, "; ".join(notes)


def expected_games_by_round(path=AFLTABLES_CSV, season=SEASON):
    """AFLTables games per H&A round: the authority on what was actually played.

    Returns {} if the file cannot be read, which makes the completeness test in
    rounds_needing_fetch fall back to its index-gap heuristic rather than block.
    """
    try:
        a = pd.read_csv(path, usecols=["Round", "Home.team", "Away.team"])
    except Exception as e:
        print(f"  (AFLTables fixture list unavailable, "
              f"falling back to index-gap test: {e})")
        return {}
    rn = pd.to_numeric(a["Round"], errors="coerce")   # finals labels -> NaN
    a = a.assign(_rn=rn).dropna(subset=["_rn"])
    a["_rn"] = a["_rn"].astype(int)
    counts = (a.drop_duplicates(subset=["_rn", "Home.team", "Away.team"])
                .groupby("_rn").size())
    return {int(k): int(v) for k, v in counts.items()}


def rounds_needing_fetch(existing, expected):
    """Which Wheelo rounds to pull, tested per GAME rather than per round.

    The old test was round-level: "round 23 is already in the CSV, so round 23
    is done". That permanently freezes any round first fetched while it was
    still being played. 2026 round 23 was stored with 8 of its 9 games and
    could never pick up the ninth (St Kilda v Carlton, MatchId 20262206),
    because its mere presence satisfied the guard every week thereafter.

    A round is refetched when it is absent, when it holds fewer games than
    AFLTables says were played, when its game indices have a hole in them, or
    when it is the newest round we hold and we have no fixture list to check it
    against. Returns [(wheelo_round, reason), ...].
    """
    present = {}
    if existing is not None and not existing.empty:
        ids = existing["MatchId"].astype(str).str.strip()
        game_idx = pd.to_numeric(ids.str[6:], errors="coerce")
        for rnd, grp in existing.assign(_gi=game_idx).groupby("Round"):
            present[int(rnd)] = (int(grp["MatchId"].nunique()),
                                 int(grp["_gi"].max()) if grp["_gi"].notna().any() else 0)

    # Ceiling comes from AFLTables, not a hardcoded 23. The old constant probed
    # Wheelo round 23, which maps to AFLTables round 24 and does not exist in a
    # 23-round season, so every run ended on a "no data" line for a round that
    # was never real.
    max_round = max(expected) if expected else (max(present) if present else 23)
    newest = max(present) if present else None

    todo = []
    for aflt_round in range(1, max_round + 1):
        wheelo_round = aflt_round - ROUND_OFFSET
        if wheelo_round < 0:
            continue
        n_games, max_gi = present.get(aflt_round, (0, 0))
        exp = expected.get(aflt_round)
        if n_games == 0:
            todo.append((wheelo_round, f"R{aflt_round} absent"))
        elif exp is not None and n_games < exp:
            todo.append((wheelo_round,
                         f"R{aflt_round} partial: {n_games} of {exp} games played"))
        elif max_gi and n_games < max_gi:
            todo.append((wheelo_round,
                         f"R{aflt_round} has a hole: {n_games} games "
                         f"but highest game index is {max_gi}"))
        elif exp is None and aflt_round == newest:
            todo.append((wheelo_round,
                         f"R{aflt_round} is the newest stored round and no "
                         f"fixture list is available to confirm it is complete"))
    return todo


def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    options.add_experimental_option("prefs", prefs)
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def clear_downloads():
    for f in glob.glob(os.path.join(DOWNLOAD_DIR, "*.csv")):
        os.remove(f)


def wait_for_download(timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        files = [
            f for f in glob.glob(os.path.join(DOWNLOAD_DIR, "*.csv"))
            if not f.endswith('.crdownload')
        ]
        if files:
            time.sleep(0.5)
            return max(files, key=os.path.getmtime)
        time.sleep(0.5)
    return None


def click_download(driver):
    selectors = [
        "//a[contains(text(),'Download') and contains(text(),'CSV')]",
        "//button[contains(text(),'CSV')]",
        "//a[contains(@href,'csv')]",
        "//a[contains(text(),'Download')]",
        "//*[contains(@class,'download')]",
    ]
    for sel in selectors:
        try:
            btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, sel))
            )
            btn.click()
            return True
        except Exception:
            continue
    # Fallback: any visible CSV element
    try:
        for el in driver.find_elements(By.XPATH, "//*[contains(text(),'CSV')]"):
            if el.is_displayed() and el.is_enabled():
                el.click()
                return True
    except Exception:
        pass
    return False


def parse_table_from_page(driver):
    try:
        for table in driver.find_elements(By.TAG_NAME, "table"):
            html = table.get_attribute('outerHTML')
            dfs = pd.read_html(io.StringIO(html))
            for df in dfs:
                if len(df) > 5 and len(df.columns) > 8:
                    return df
    except Exception:
        pass
    return None


def fetch_round(driver, wheelo_round):
    """Fetch one round page. Returns (status, df, detail).

    Only transport and parsing happen here; the round label is read from the
    payload afterwards by attach_rounds, which keeps that logic free of
    Selenium and therefore testable.
    """
    url = f"{BASE_URL}?id={SEASON}{wheelo_round:02d}"
    try:
        driver.get(url)
    except WebDriverException as e:
        return STATUS_NOT_FETCHED, None, f"navigation failed: {type(e).__name__}: {e}"
    time.sleep(2)

    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )
        saw_table = True
    except Exception:
        saw_table = False

    # Try download first
    clear_downloads()
    if click_download(driver):
        filepath = wait_for_download(timeout=10)
        if filepath:
            try:
                df = pd.read_csv(filepath)
                if len(df):
                    return STATUS_OK, df, f"downloaded {len(df)} rows"
            except Exception as e:
                print(f"    (download parsed badly, falling back to page scrape: {e})")

    # Fallback: parse from page
    df = parse_table_from_page(driver)
    if df is not None and len(df):
        return STATUS_OK, df, f"parsed {len(df)} rows from page"

    if not saw_table:
        return STATUS_EMPTY, None, ("page loaded but served no stats table "
                                    "(round most likely not published yet)")
    return STATUS_EMPTY, None, "stats table present but no rows could be parsed"


def main():
    # Wheelo's published Brownlow leaderboard (drives Model Comparison) — fetch
    # first so it refreshes even if the Selenium match-stats step below fails.
    print("Fetching Wheelo published Brownlow predictions...")
    fetch_brownlow_predictions()

    # Load existing data
    if os.path.exists(OUTPUT_CSV):
        existing = pd.read_csv(OUTPUT_CSV)
        existing_rounds = set(existing['Round'].unique())
    else:
        existing = pd.DataFrame()
        existing_rounds = set()

    print(f"Existing AFLTables rounds: {sorted(existing_rounds)}")

    expected = expected_games_by_round()
    todo = rounds_needing_fetch(existing, expected)
    if todo:
        print("Rounds to fetch:")
        for wheelo_round, reason in todo:
            print(f"  Wheelo R{wheelo_round:02d}  <-  {reason}")
    else:
        print("Every round is complete against the AFLTables fixture list.")
        return

    driver = get_driver()
    new_frames = []
    tally = {STATUS_OK: 0, STATUS_NOT_FETCHED: 0,
             STATUS_EMPTY: 0, STATUS_NO_ROUND: 0}
    consecutive_barren = 0

    try:
        print(f"\nFetching {SEASON} rounds from wheeloratings.com...\n")
        for wheelo_round, _reason in todo:
            status, df, detail = fetch_round(driver, wheelo_round)
            if status == STATUS_OK:
                status, df, detail = attach_rounds(df, wheelo_round)

            label = f"  Wheelo R{wheelo_round:02d}"
            if status == STATUS_OK:
                rounds = sorted(df['Round'].unique())
                print(f"{label}: OK -> AFLTables R{rounds} ({detail})")
                new_frames.append(df)
                consecutive_barren = 0
            elif status == STATUS_NOT_FETCHED:
                print(f"{label}: PAGE NOT FETCHED - {detail}")
                consecutive_barren += 1
            elif status == STATUS_EMPTY:
                print(f"{label}: FETCHED, ZERO ROWS PARSED - {detail}")
                consecutive_barren += 1
            else:
                print(f"{label}: FETCHED, ROUND LABEL UNPARSEABLE - {detail}")
                consecutive_barren += 1
            tally[status] += 1

            if consecutive_barren >= 3:
                print("  3 consecutive rounds yielded nothing - stopping.")
                break
            time.sleep(1)
    finally:
        driver.quit()

    print(f"\nFetch summary: {tally[STATUS_OK]} ok, "
          f"{tally[STATUS_NOT_FETCHED]} not fetched, "
          f"{tally[STATUS_EMPTY]} empty, "
          f"{tally[STATUS_NO_ROUND]} unparseable round label")

    if new_frames:
        new_df = pd.concat(new_frames, ignore_index=True)
        combined = pd.concat([existing, new_df], ignore_index=True) if not existing.empty else new_df
        # keep='last' so a refetched game supersedes the stored copy: this is
        # what lets a round that was first stored mid-play be completed later.
        before = len(combined)
        combined = (combined.drop_duplicates(subset=['MatchId', 'Player'], keep='last')
                            .sort_values(['Round', 'MatchId'])
                            .reset_index(drop=True))
        # Backup and save
        if os.path.exists(OUTPUT_CSV):
            shutil.copy2(OUTPUT_CSV, OUTPUT_CSV.replace('.csv', '_prev.csv'))
        combined.to_csv(OUTPUT_CSV, index=False)
        print(f"\nSaved {len(combined)} total rows to {OUTPUT_CSV}")
        print(f"  Fetched {len(new_df)} rows for AFLTables rounds "
              f"{sorted(new_df['Round'].unique())}; "
              f"{before - len(combined)} superseded or duplicate row(s) collapsed")

        # Show updated leaderboard
        col = next((c for c in ['ExpVotes', 'RatingPoints'] if c in combined.columns), None)
        if col:
            agg = combined.groupby('Player')[col].sum().sort_values(ascending=False).head(10)
            print(f"\nTop 10 by {col}:")
            for p, v in agg.items():
                print(f"  {v:6.2f}  {p}")
    else:
        print("\nNo new data retrieved.")


if __name__ == '__main__':
    main()
