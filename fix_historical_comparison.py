"""
fix_historical_comparison.py

Targeted fixes for historical_model_comparison.csv:
  1. ESPN 2024  – use numeric-ID URL (POINTSBET2024 now shows 2026 data)
  2. ESPN 2025  – use print/ID URL (POINTSBET20242 now shows 2026 data)
  3. Wheelo 2021/2022 – try Wayback Machine CDX API then download
  4. Clear stale Betfair/ESPN 2025 results that were actually 2026 data

Run from the brownlow_engine directory.
"""

import io
import os
import re
import time

import pandas as pd
import pdfplumber
import requests
from bs4 import BeautifulSoup

OUT_CSV = "data_2026/historical_model_comparison.csv"

ACTUAL_WINNERS = {
    2021: "Ollie Wines",
    2022: "Patrick Cripps",
    2023: "Lachie Neale",
    2024: "Patrick Cripps",
    2025: "Matt Rowell",
}

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

HTTP_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
    "Referer": "https://www.espn.com.au/",
}

# Verified numeric-ID ESPN URLs (these are real archived articles, not live predictor pages)
ESPN_ID_URLS = {
    2024: "https://www.espn.com.au/afl/story/_/id/39188574/afl-2024-ultimate-brownlow-medal-predictor-tracker-leaderboard-odds-every-vote",
    2025: "https://www.espn.com.au/afl/story/_/id/43771739/",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

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


# ── ESPN vote patterns ─────────────────────────────────────────────────────────

_ESPN_VOTE_RE = re.compile(
    r"(\d+\.?\d*)\s*[-–—]\s*"
    r"([A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+)+)"
    r"\s*\([A-Z]{1,4}\)",
)


def _parse_espn_html(html: str) -> dict[str, float]:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    votes: dict[str, float] = {}

    # Strategy A: per-game vote pattern "3 - Nick Daicos (COLL)"
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

    # Strategy B: pd.read_html
    from io import StringIO
    try:
        raw_tables = pd.read_html(StringIO(html))
    except Exception:
        raw_tables = []
    for tdf in raw_tables:
        tdf.columns = [str(c).strip().upper() for c in tdf.columns]
        if "PLAYER" not in tdf.columns:
            continue
        vote_cols = [
            c for c in tdf.columns
            if c not in ("PLAYER", "TEAM", "VOTES") and
            len(pd.to_numeric(tdf[c], errors="coerce").dropna()) > 0 and
            float(pd.to_numeric(tdf[c], errors="coerce").dropna().max()) <= 3.0
        ]
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

    # Strategy C: look for total-votes patterns in text (e.g. "Patrick Cripps 34")
    # Matches "Firstname Lastname  N.N votes" or "N.N  Firstname Lastname"
    tot_re = re.compile(
        r"([A-Z][A-Za-z'\-]+\s+[A-Z][A-Za-z'\-]+)\s+(\d{1,2}\.?\d?)\s*votes?",
        re.IGNORECASE,
    )
    for m in tot_re.finditer(text):
        try:
            val = float(m.group(2))
        except ValueError:
            continue
        if 1 <= val <= 50:
            name = m.group(1).title().strip()
            if name not in votes:
                votes[name] = val

    return votes


def _winner_rank(votes: dict[str, float], winner: str) -> int | None:
    if not votes:
        return None
    ranked = sorted(votes.items(), key=lambda x: -x[1])
    candidates = [(name, i + 1) for i, (name, _) in enumerate(ranked)]
    return best_match_rank(candidates, winner)


# ── ESPN ID-based scraper (via undetected_chromedriver) ───────────────────────

def _uc_driver():
    import undetected_chromedriver as uc
    opts = uc.ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(f"--user-agent={_UA}")
    opts.add_argument("--lang=en-AU")
    return uc.Chrome(options=opts, use_subprocess=True)


def fetch_espn_id_ranks(seasons: list[int]) -> dict[int, int | None]:
    results = {}
    driver = None
    try:
        print("\n[ESPN-ID] Starting browser...")
        driver = _uc_driver()
        for season in seasons:
            url = ESPN_ID_URLS.get(season)
            if not url:
                print(f"  [ESPN-ID {season}] No ID URL — skip")
                continue
            winner = ACTUAL_WINNERS[season]
            print(f"\n[ESPN-ID {season}] Loading {url}")
            try:
                driver.get(url)
                time.sleep(5)
                for pos in range(0, 25000, 600):
                    driver.execute_script(f"window.scrollTo(0, {pos});")
                    time.sleep(0.15)
                time.sleep(5)
                html = driver.page_source
                print(f"  Page source: {len(html):,} chars")
            except Exception as e:
                print(f"  ERROR: {e}")
                results[season] = None
                continue

            # Verify it's not a login wall or generic page
            if "brownlow" not in html.lower() and str(season) not in html:
                print(f"  WARNING: page doesn't look like a {season} Brownlow article")
                results[season] = None
                continue

            votes = _parse_espn_html(html)
            if not votes:
                print(f"  WARNING: no vote data found")

                # Save a debug copy to investigate
                dbg_path = f"espn_debug_{season}.html"
                with open(dbg_path, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"  Saved debug HTML to {dbg_path}")
                results[season] = None
                continue

            print(f"  Players with votes: {len(votes)}")
            top10 = sorted(votes.items(), key=lambda x: -x[1])[:10]
            for i, (name, v) in enumerate(top10, 1):
                marker = "  <-- WINNER" if normalise(name) == normalise(winner) else ""
                print(f"    {i:<4} {name:<30} {v:.1f}{marker}")

            rank = _winner_rank(votes, winner)
            results[season] = rank
            print(f"  => {winner} ranked #{rank}" if rank else f"  => WARNING: {winner} not found")

    except Exception as e:
        print(f"[ESPN-ID] Fatal: {e}")
    finally:
        if driver:
            driver.quit()
            print("\n[ESPN-ID] Browser closed.")
    return results


# ── Wheelo via Wayback Machine ────────────────────────────────────────────────

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
        for page in pdf.pages:
            for tbl in page.extract_tables():
                if not tbl:
                    continue
                for row in tbl:
                    cells = [
                        re.sub(r"\s+", " ", str(c)).strip() if c else "" for c in row
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
                    rv, nv = int(m.group(1)), m.group(2).strip()
                    if 1 <= rv <= 20 and rv not in results and _is_valid_player_name(nv):
                        results[rv] = nv
    return [(name, rank) for rank, name in sorted(results.items())]


def _wayback_pdf_url(original_url: str) -> str | None:
    """Use Wayback Machine CDX API to find the closest snapshot URL for a PDF."""
    cdx = (
        f"https://web.archive.org/cdx/search/cdx"
        f"?url={original_url}&output=json&limit=1&fl=timestamp,original&filter=statuscode:200"
    )
    try:
        resp = requests.get(cdx, timeout=15)
        data = resp.json()
        if len(data) > 1:
            ts, orig = data[1][0], data[1][1]
            return f"https://web.archive.org/web/{ts}if_/{orig}"
    except Exception as e:
        print(f"  CDX API error: {e}")
    return None


def fetch_wheelo_wayback(seasons: list[int]) -> dict[int, int | None]:
    session = requests.Session()
    session.headers.update({
        "User-Agent": _UA,
        "Accept": "application/pdf,*/*;q=0.8",
    })
    results = {}

    for season in seasons:
        winner = ACTUAL_WINNERS[season]
        orig_url = f"https://www.wheeloratings.com/src/docs/wheelo-brownlow-guide-{season}.pdf"
        print(f"\n[Wheelo {season}] Checking Wayback Machine for {orig_url}")

        wb_url = _wayback_pdf_url(orig_url)
        if not wb_url:
            print(f"  No Wayback Machine snapshot found — trying direct download anyway")
            wb_url = orig_url

        print(f"  Trying: {wb_url}")
        try:
            resp = session.get(wb_url, timeout=40, allow_redirects=True)
            resp.raise_for_status()
            # Confirm it's a PDF (not an HTML error page)
            if resp.headers.get("Content-Type", "").startswith("text/html"):
                print(f"  Got HTML instead of PDF — server returned a page, not a PDF")
                results[season] = None
                continue
            print(f"  Downloaded {len(resp.content):,} bytes")
        except Exception as e:
            print(f"  ERROR: {e}")
            results[season] = None
            continue

        top20 = _extract_top20_wheelo(resp.content)
        if not top20:
            print(f"  WARNING: No top-20 extracted")
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


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("FIX HISTORICAL MODEL COMPARISON DATA")
    print("=" * 65)

    df = pd.read_csv(OUT_CSV)
    df["Season"] = df["Season"].astype(int)
    df = df.set_index("Season")

    # ── Step 1: Clear stale 2025 data ────────────────────────────────────────
    # The Betfair and ESPN "2025" URLs now serve 2026 content.
    # Matt Rowell at #44 (Betfair) and #66 (ESPN) are his 2026 predictions, not 2025.
    print("\n[Step 1] Clearing stale 2025 Betfair/ESPN data (those were 2026 predictions)")
    if 2025 in df.index:
        current_bf = df.loc[2025, "Betfair_Rank"]
        current_espn = df.loc[2025, "ESPN_Rank"]
        print(f"  Before: Betfair_Rank={current_bf}, ESPN_Rank={current_espn}")
        # Only clear if they were set in the previous run (44 and 66 are the bad values)
        df.loc[2025, "Betfair_Rank"] = float("nan")
        df.loc[2025, "ESPN_Rank"] = float("nan")
        print(f"  Cleared both to NaN")

    # Also check if 2024 Betfair was set incorrectly (it was skipped as 404, should be fine)

    # ── Step 2: Wheelo 2021/2022 via Wayback Machine ─────────────────────────
    wheelo_needed = [s for s in [2021, 2022] if pd.isna(df.loc[s, "Wheelo_Rank"]) if s in df.index]
    print(f"\n[Step 2] Wheelo via Wayback Machine: {wheelo_needed or 'none needed'}")
    if wheelo_needed:
        wheelo_ranks = fetch_wheelo_wayback(wheelo_needed)
        for season, rank in wheelo_ranks.items():
            df.loc[season, "Wheelo_Rank"] = rank

    # ── Step 3: ESPN 2024/2025 via numeric-ID URLs ────────────────────────────
    espn_id_needed = [
        s for s in [2024, 2025]
        if s in df.index and pd.isna(df.loc[s, "ESPN_Rank"])
    ]
    print(f"\n[Step 3] ESPN numeric-ID URLs: {espn_id_needed or 'none needed'}")
    if espn_id_needed:
        espn_ranks = fetch_espn_id_ranks(espn_id_needed)
        for season, rank in espn_ranks.items():
            df.loc[season, "ESPN_Rank"] = rank

    # ── Save ─────────────────────────────────────────────────────────────────
    df = df.reset_index().sort_values("Season")
    df.to_csv(OUT_CSV, index=False)

    print(f"\n{'='*65}")
    print(f"Written: {OUT_CSV}")
    print()
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
