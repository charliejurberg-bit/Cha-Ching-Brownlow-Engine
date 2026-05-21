"""
fill_historical_comparison.py

Fills historical model comparison data for 2021-2025 by scraping:
  1. Wheelo PDFs  (2021, 2022)  – pdfplumber
  2. Betfair hub articles       – requests + pd.read_html
  3. ESPN predictor articles    – undetected_chromedriver

Reads the existing data_2026/historical_model_comparison.csv, fills in
missing values, sorts by Season ascending, and writes it back.
Run from the brownlow_engine directory.
"""

import io
import os
import re
import sys
import time

import pandas as pd
import pdfplumber
import requests
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────

ACTUAL_WINNERS = {
    2021: "Ollie Wines",
    2022: "Patrick Cripps",
    2023: "Lachie Neale",
    2024: "Patrick Cripps",
    2025: "Matt Rowell",
}

OUT_CSV = "data_2026/historical_model_comparison.csv"

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

HTTP_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
    "Referer": "https://www.betfair.com.au/",
}

PDF_HEADERS = {
    "User-Agent": _UA,
    "Accept": "application/pdf,*/*;q=0.8",
    "Referer": "https://www.wheeloratings.com/",
}

WHEELO_PDF_URLS = {
    2021: "https://www.wheeloratings.com/src/docs/wheelo-brownlow-guide-2021.pdf",
    2022: "https://www.wheeloratings.com/src/docs/wheelo-brownlow-guide-2022.pdf",
}

BETFAIR_URLS = {
    2021: "https://www.betfair.com.au/hub/sports/afl/2021-brownlow-medal-predictor/",
    2022: "https://www.betfair.com.au/hub/sports/afl/2022-brownlow-medal-predictor/",
    2023: "https://www.betfair.com.au/hub/sports/afl/2023-brownlow-medal-predictor/",
    2024: "https://www.betfair.com.au/hub/sports/afl/2024-brownlow-medal-predictor/",
    2025: "https://www.betfair.com.au/hub/sports/afl/brownlow-medal-predictor/",
}

ESPN_URLS = {
    2021: (
        "https://www.espn.com.au/afl/story/_/id/30993511/"
        "afl-2021-brownlow-medal-predictor-tracker-leaderboard-odds-every-team-every-player-every-vote-2021"
    ),
    2022: (
        "https://www.espn.com.au/afl/story/_/id/33294207/"
        "afl-2022-ultimate-brownlow-medal-predictor-tracker-leaderboard-odds-every-team-every-player-every-vote-2022"
    ),
    2023: (
        "https://www.espn.com.au/afl/story/_/page/Subway2023Brownlow/"
        "afl-2023-ultimate-brownlow-medal-predictor-tracker-leaderboard-odds-every-team-every-player-every-vote"
    ),
    2024: (
        "https://www.espn.com.au/afl/story/_/page/POINTSBET2024/"
        "afl-2024-ultimate-brownlow-medal-predictor-tracker-leaderboard-odds-every-vote"
    ),
    2025: (
        "https://www.espn.com.au/afl/story/_/page/POINTSBET20242/"
        "afl-2025-ultimate-brownlow-medal-predictor-tracker-leaderboard-odds-every-vote"
    ),
}

# ── Shared helpers ────────────────────────────────────────────────────────────

def normalise(name: str) -> str:
    name = name.lower().strip()
    name = re.sub(r"['''\-]", " ", name)
    name = re.sub(r"[^a-z ]", "", name)
    return re.sub(r"\s+", " ", name).strip()


def best_match_rank(candidates: list[tuple[str, int]], target: str) -> int | None:
    tn = normalise(target)
    tn_words = set(tn.split())
    best_rank, best_score = None, 0
    for name, rank in candidates:
        nn = normalise(name)
        nn_words = set(nn.split())
        if nn == tn:
            return rank
        shared = tn_words & nn_words
        score = len(shared) / max(len(tn_words), len(nn_words))
        if len(shared) >= 2 and score > best_score:
            best_score, best_rank = score, rank
    return best_rank if best_score >= 0.5 else None


# ── Section 1: Wheelo PDFs ────────────────────────────────────────────────────

_AFL_STAT_WORDS = {
    "Acts", "Possessions", "Involvements", "Gets", "Receives",
    "History", "Rating", "Votes", "Rank", "Mtrs", "Gnd",
    "Coaches", "Polling", "Pressure", "Uncontested", "Contested",
    "Clearances", "Disposals", "Tackles", "Handballs", "Marks",
    "Goals", "Behinds", "Kicks", "Intercepts", "Rebounds",
}


def _is_valid_player_name(cell: str) -> bool:
    cell = cell.strip()
    if not cell or len(cell) < 4:
        return False
    if "%" in cell or re.search(r"\d", cell) or cell.isupper():
        return False
    words = cell.split()
    if len(words) < 2:
        return False
    if any(w in _AFL_STAT_WORDS for w in words):
        return False
    for word in words:
        if not word[0].isupper() or not re.fullmatch(r"[A-Za-z'\-]+", word):
            return False
    return True


def _extract_top20_wheelo(pdf_bytes: bytes) -> list[tuple[str, int]]:
    results: dict[int, str] = {}

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        # Strategy A: rank-anchored table scan
        for page in pdf.pages:
            for tbl in page.extract_tables():
                if not tbl:
                    continue
                for row in tbl:
                    cells = [
                        re.sub(r"\s+", " ", str(c)).strip() if c else ""
                        for c in row
                    ]
                    for i, cell in enumerate(cells):
                        if not re.fullmatch(r"\d{1,2}", cell):
                            continue
                        rank_val = int(cell)
                        if not (1 <= rank_val <= 20) or rank_val in results:
                            continue
                        for j in range(i + 1, len(cells)):
                            if _is_valid_player_name(cells[j]):
                                results[rank_val] = cells[j]
                                break

        if len(results) >= 18:
            return [(name, rank) for rank, name in sorted(results.items())]

        # Strategy B: raw text regex
        results = {}
        for page in pdf.pages:
            text = page.extract_text() or ""
            for line in text.splitlines():
                line = line.strip()
                m = re.match(
                    r"^(\d{1,2})[.\s]+([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)+)",
                    line,
                )
                if m:
                    rank_val = int(m.group(1))
                    name_val = m.group(2).strip()
                    if 1 <= rank_val <= 20 and rank_val not in results:
                        if _is_valid_player_name(name_val):
                            results[rank_val] = name_val

    return [(name, rank) for rank, name in sorted(results.items())]


def fetch_wheelo_ranks(seasons: list[int]) -> dict[int, int | None]:
    session = requests.Session()
    session.headers.update(PDF_HEADERS)
    results = {}

    for season in seasons:
        if season not in WHEELO_PDF_URLS:
            print(f"  [Wheelo {season}] No PDF URL configured — skipping")
            continue
        url = WHEELO_PDF_URLS[season]
        winner = ACTUAL_WINNERS[season]
        print(f"\n[Wheelo {season}] Downloading {url}")
        try:
            resp = session.get(url, timeout=40)
            resp.raise_for_status()
            print(f"  Downloaded {len(resp.content):,} bytes")
        except Exception as e:
            print(f"  ERROR: {e}")
            results[season] = None
            continue

        top20 = _extract_top20_wheelo(resp.content)
        if not top20:
            print("  WARNING: No top-20 extracted from PDF")
            results[season] = None
            continue

        print(f"  Top 20 ({len(top20)} entries):")
        for name, rank in top20:
            marker = "  <-- WINNER" if normalise(name) == normalise(winner) else ""
            print(f"    {rank:<4} {name}{marker}")

        rank = best_match_rank(top20, winner)
        results[season] = rank
        print(f"  => {winner} ranked #{rank}" if rank else f"  => WARNING: {winner} not in top 20")

    return results


# ── Section 2: Betfair ────────────────────────────────────────────────────────

def _parse_betfair_html(html: str) -> dict[str, float]:
    """Sum votes per player from per-game tables on a Betfair predictor page."""
    from io import StringIO
    votes: dict[str, float] = {}
    try:
        raw_tables = pd.read_html(StringIO(html))
    except Exception:
        return {}
    if not raw_tables:
        return {}
    combined = pd.concat(raw_tables, ignore_index=True)
    combined.columns = ["Player", "Votes"]
    combined = combined.dropna(subset=["Votes"])
    combined["Votes"] = pd.to_numeric(combined["Votes"], errors="coerce")
    combined = combined.dropna(subset=["Votes"])
    combined["Player"] = combined["Player"].astype(str).str.title().str.strip()
    # Rows without a space are match codes (e.g. "Bl"), not player names
    combined = combined[combined["Player"].str.contains(" ", na=False)]
    # Discard rows that look like game headers (e.g. "Melbourne V Essendon")
    combined = combined[~combined["Player"].str.contains(r"\bV\b", regex=True)]
    for _, row in combined.iterrows():
        v = float(row["Votes"])
        if 0 < v <= 3:
            votes[row["Player"]] = votes.get(row["Player"], 0) + v
    return votes


def _betfair_winner_rank(votes: dict[str, float], winner: str) -> int | None:
    if not votes:
        return None
    ranked = sorted(votes.items(), key=lambda x: -x[1])
    candidates = [(name, i + 1) for i, (name, _) in enumerate(ranked)]
    return best_match_rank(candidates, winner)


def fetch_betfair_ranks(seasons: list[int]) -> dict[int, int | None]:
    session = requests.Session()
    session.headers.update(HTTP_HEADERS)
    results = {}

    for season in seasons:
        url = BETFAIR_URLS.get(season)
        if not url:
            print(f"  [Betfair {season}] No URL configured — skipping")
            continue
        winner = ACTUAL_WINNERS[season]
        print(f"\n[Betfair {season}] GET {url}")
        try:
            resp = session.get(url, timeout=25)
            resp.raise_for_status()
            print(f"  Status {resp.status_code}, {len(resp.text):,} chars")
        except Exception as e:
            print(f"  ERROR: {e}")
            results[season] = None
            continue

        # Quick sanity: does the page look like a Betfair predictor page?
        if "brownlow" not in resp.text.lower():
            print(f"  WARNING: Page doesn't mention 'brownlow' — likely redirected/wrong page")
            results[season] = None
            continue

        votes = _parse_betfair_html(resp.text)
        if not votes:
            print(f"  WARNING: No vote data parsed from tables")
            results[season] = None
            continue

        print(f"  Players with votes: {len(votes)}")
        top10 = sorted(votes.items(), key=lambda x: -x[1])[:10]
        for i, (name, v) in enumerate(top10, 1):
            marker = "  <-- WINNER" if normalise(name) == normalise(winner) else ""
            print(f"    {i:<4} {name:<30} {v:.1f}{marker}")

        rank = _betfair_winner_rank(votes, winner)
        results[season] = rank
        print(f"  => {winner} ranked #{rank}" if rank else f"  => WARNING: {winner} not found in vote tally")

    return results


# ── Section 3: ESPN ───────────────────────────────────────────────────────────

def _uc_driver():
    import undetected_chromedriver as uc
    opts = uc.ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(f"--user-agent={_UA}")
    opts.add_argument("--lang=en-AU")
    return uc.Chrome(options=opts, use_subprocess=True)


# Regex: "3 - Nick Daicos (COLL)" or "2.5 - Marcus Bontempelli (WB)"
_ESPN_VOTE_RE = re.compile(
    r"(\d+\.?\d*)\s*[-–—]\s*"
    r"([A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+)+)"
    r"\s*\([A-Z]{1,4}\)",
)


def _parse_espn_html(html: str, season: int) -> dict[str, float]:
    """Extract player→total votes from an ESPN Brownlow predictor page."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    votes: dict[str, float] = {}

    # Strategy A: per-game vote pattern in text
    for m in _ESPN_VOTE_RE.finditer(text):
        try:
            val = float(m.group(1))
        except ValueError:
            continue
        if not (0 < val <= 3):
            continue
        name = m.group(2).title().strip()
        votes[name] = votes.get(name, 0) + val

    if votes:
        return votes

    # Strategy B: pd.read_html table scan (static older articles)
    from io import StringIO
    try:
        raw_tables = pd.read_html(StringIO(html))
    except Exception:
        raw_tables = []
    for tdf in raw_tables:
        tdf.columns = [str(c).strip().upper() for c in tdf.columns]
        if "PLAYER" not in tdf.columns:
            continue
        vote_cols = []
        for c in tdf.columns:
            if c in ("PLAYER", "TEAM", "VOTES"):
                continue
            num = pd.to_numeric(tdf[c], errors="coerce")
            valid = num.dropna()
            if len(valid) > 0 and float(valid.max()) <= 3.0 and float(valid.min()) >= 0.0:
                vote_cols.append(c)
        if not vote_cols:
            continue
        tdf_v = tdf[["PLAYER"] + vote_cols].copy()
        for c in vote_cols:
            tdf_v[c] = pd.to_numeric(tdf_v[c], errors="coerce").fillna(0)
        tdf_v["_total"] = tdf_v[vote_cols].sum(axis=1)
        for _, row in tdf_v.iterrows():
            player = str(row["PLAYER"]).title().strip()
            if not player or player in ("Nan", "") or row["_total"] <= 0:
                continue
            votes[player] = votes.get(player, 0) + float(row["_total"])

    if votes:
        return votes

    # Strategy C: BeautifulSoup table scan (two-column: player | votes)
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            player_text = cells[0].get_text(strip=True)
            vote_text = cells[-1].get_text(strip=True)
            if not re.search(r"[A-Z][a-z]+ [A-Z][a-z]+", player_text):
                continue
            try:
                v = float(vote_text)
            except ValueError:
                continue
            if 0 < v <= 45:  # total votes column for a season (not per-game)
                name = player_text.title().strip()
                votes[name] = votes.get(name, 0) + v

    return votes


def _espn_winner_rank(votes: dict[str, float], winner: str) -> int | None:
    if not votes:
        return None
    ranked = sorted(votes.items(), key=lambda x: -x[1])
    candidates = [(name, i + 1) for i, (name, _) in enumerate(ranked)]
    return best_match_rank(candidates, winner)


def fetch_espn_ranks(seasons: list[int]) -> dict[int, int | None]:
    results = {}
    driver = None
    try:
        print("\n[ESPN] Starting browser (undetected-chromedriver)...")
        driver = _uc_driver()

        for season in seasons:
            url = ESPN_URLS.get(season)
            if not url:
                print(f"  [ESPN {season}] No URL configured — skipping")
                continue
            winner = ACTUAL_WINNERS[season]
            print(f"\n[ESPN {season}] Loading {url}")

            try:
                driver.get(url)
                time.sleep(5)
                # Scroll to reveal lazy-loaded content
                for pos in range(0, 25000, 600):
                    driver.execute_script(f"window.scrollTo(0, {pos});")
                    time.sleep(0.15)
                time.sleep(5)
                html = driver.page_source
                print(f"  Page source: {len(html):,} chars")
            except Exception as e:
                print(f"  ERROR loading page: {e}")
                results[season] = None
                continue

            # Sanity check
            if season <= 2022:
                year_check = str(season)
                if year_check not in html and "brownlow" not in html.lower():
                    print(f"  WARNING: Page doesn't look like a {season} ESPN Brownlow article")
                    results[season] = None
                    continue

            votes = _parse_espn_html(html, season)
            if not votes:
                print(f"  WARNING: No vote data parsed from page")
                results[season] = None
                continue

            print(f"  Players with votes: {len(votes)}")
            top10 = sorted(votes.items(), key=lambda x: -x[1])[:10]
            for i, (name, v) in enumerate(top10, 1):
                marker = "  <-- WINNER" if normalise(name) == normalise(winner) else ""
                print(f"    {i:<4} {name:<30} {v:.1f}{marker}")

            rank = _espn_winner_rank(votes, winner)
            results[season] = rank
            print(f"  => {winner} ranked #{rank}" if rank else f"  => WARNING: {winner} not in vote data")

    except Exception as e:
        print(f"[ESPN] Browser error: {e}")
    finally:
        if driver:
            driver.quit()
            print("\n[ESPN] Browser closed.")

    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("FILL HISTORICAL MODEL COMPARISON DATA")
    print("=" * 65)

    # Load existing CSV
    df = pd.read_csv(OUT_CSV)
    df["Season"] = df["Season"].astype(int)
    for col in ["Wheelo_Rank", "Betfair_Rank", "ESPN_Rank"]:
        if col not in df.columns:
            df[col] = None
    df = df.set_index("Season")

    # ── 1. Wheelo PDFs (only seasons missing Wheelo_Rank) ─────────────────────
    wheelo_needed = [
        s for s in sorted(ACTUAL_WINNERS)
        if s in WHEELO_PDF_URLS and (
            s not in df.index or pd.isna(df.loc[s, "Wheelo_Rank"])
        )
    ]
    print(f"\n{'-'*65}")
    print(f"WHEELO -- seasons needing update: {wheelo_needed or 'none'}")
    if wheelo_needed:
        wheelo_ranks = fetch_wheelo_ranks(wheelo_needed)
        for season, rank in wheelo_ranks.items():
            if season in df.index:
                df.loc[season, "Wheelo_Rank"] = rank
            else:
                df.loc[season] = {
                    "Actual_Winner": ACTUAL_WINNERS[season],
                    "CC_Rank": None,
                    "Wheelo_Rank": rank,
                    "Betfair_Rank": None,
                    "ESPN_Rank": None,
                }

    # 2. Betfair (all seasons, update if missing)
    betfair_needed = [
        s for s in sorted(ACTUAL_WINNERS)
        if s not in df.index or pd.isna(df.loc[s, "Betfair_Rank"])
    ]
    print(f"\n{'-'*65}")
    print(f"BETFAIR -- seasons needing update: {betfair_needed or 'none'}")
    if betfair_needed:
        betfair_ranks = fetch_betfair_ranks(betfair_needed)
        for season, rank in betfair_ranks.items():
            if season in df.index:
                df.loc[season, "Betfair_Rank"] = rank
            else:
                df.loc[season] = {
                    "Actual_Winner": ACTUAL_WINNERS[season],
                    "CC_Rank": None,
                    "Wheelo_Rank": None,
                    "Betfair_Rank": rank,
                    "ESPN_Rank": None,
                }

    # 3. ESPN (all seasons, update if missing)
    espn_needed = [
        s for s in sorted(ACTUAL_WINNERS)
        if s not in df.index or pd.isna(df.loc[s, "ESPN_Rank"])
    ]
    print(f"\n{'-'*65}")
    print(f"ESPN -- seasons needing update: {espn_needed or 'none'}")
    if espn_needed:
        espn_ranks = fetch_espn_ranks(espn_needed)
        for season, rank in espn_ranks.items():
            if season in df.index:
                df.loc[season, "ESPN_Rank"] = rank
            else:
                df.loc[season] = {
                    "Actual_Winner": ACTUAL_WINNERS[season],
                    "CC_Rank": None,
                    "Wheelo_Rank": None,
                    "Betfair_Rank": None,
                    "ESPN_Rank": rank,
                }

    # ── Save ───────────────────────────────────────────────────────────────────
    df = df.reset_index().sort_values("Season")
    df.to_csv(OUT_CSV, index=False)

    print(f"\n{'='*65}")
    print(f"Written: {OUT_CSV}")
    print()
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
