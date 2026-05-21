"""
fetch_wheelo_historical.py
Downloads Wheelo Brownlow guide PDFs (2021-2025), parses the top-20 player
rankings, then writes data_2026/historical_model_comparison.csv with columns:
  Season, Actual_Winner, CC_Rank, Wheelo_Rank, Betfair_Rank, ESPN_Rank
Run from the brownlow_engine directory.
"""

import io
import os
import re
import requests
import pdfplumber
import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────
ACTUAL_WINNERS = {
    2021: "Ollie Wines",
    2022: "Patrick Cripps",
    2023: "Lachie Neale",
    2024: "Patrick Cripps",
    2025: "Matt Rowell",
}

PDF_URLS = {
    yr: f"https://www.wheeloratings.com/src/docs/wheelo-brownlow-guide-{yr}.pdf"
    for yr in range(2021, 2026)
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,*/*;q=0.8",
    "Referer": "https://www.wheeloratings.com/",
}

BACKTEST_PATH = "predictions/backtest_results.csv"
OUT_CSV       = "data_2026/historical_model_comparison.csv"

# ── Helpers ───────────────────────────────────────────────────────────────
def normalise(name: str) -> str:
    """Lowercase, strip hyphens/apostrophes/punctuation for fuzzy matching."""
    name = name.lower().strip()
    name = re.sub(r"['''\-]", " ", name)
    name = re.sub(r"[^a-z ]", "", name)
    return re.sub(r"\s+", " ", name).strip()


def best_match_rank(candidates: list[tuple[str, int]], target: str) -> int | None:
    """Return the rank of the best name match for target in candidates list."""
    tn = normalise(target)
    tn_words = set(tn.split())
    best_rank, best_score = None, 0
    for name, rank in candidates:
        nn = normalise(name)
        nn_words = set(nn.split())
        # Exact match
        if nn == tn:
            return rank
        # Shared word count (require at least 2 shared and ≥50% overlap)
        shared = tn_words & nn_words
        score = len(shared) / max(len(tn_words), len(nn_words))
        if len(shared) >= 2 and score > best_score:
            best_score, best_rank = score, rank
    return best_rank if best_score >= 0.5 else None


_AFL_STAT_WORDS = {
    "Acts", "Possessions", "Involvements", "Gets", "Receives",
    "History", "Rating", "Votes", "Rank", "Mtrs", "Gnd",
    "Coaches", "Polling", "Pressure", "Uncontested", "Contested",
    "Clearances", "Disposals", "Tackles", "Handballs", "Marks",
    "Goals", "Behinds", "Kicks", "Intercepts", "Rebounds",
}


def is_valid_player_name(cell: str) -> bool:
    """True if a PDF cell looks like a real AFL player name (not a percentage, label, or rank)."""
    cell = cell.strip()
    if not cell or len(cell) < 4:
        return False
    if "%" in cell:                         # probability values like "12.5%"
        return False
    if re.search(r"\d", cell):              # any digit → not a name
        return False
    if cell.isupper():                      # all-caps labels like "ELITE", "BROWNLOW"
        return False
    words = cell.split()
    if len(words) < 2:                      # need at least first + last name
        return False
    if any(w in _AFL_STAT_WORDS for w in words):  # stat labels like "Pressure Acts"
        return False
    for word in words:
        if not word[0].isupper():           # each word capitalised
            return False
        if not re.fullmatch(r"[A-Za-z'\-]+", word):  # letters, hyphens, apostrophes only
            return False
    return True


def extract_top20_from_pdf(pdf_bytes: bytes, season: int) -> list[tuple[str, int]]:
    """
    Parse the Wheelo PDF and return [(player_name, rank), ...] for the top 20.

    Strategy A (preferred): find cells matching a rank digit (1-20), then scan
    remaining cells in the same row for the first valid player name.  Skips
    non-name cells (percentages, tier labels, column headers) automatically
    because they don't pass is_valid_player_name().  Handles the 2025 layout
    where probability values appear between the rank and the name.

    Strategy B (fallback): raw text line regex scanning.
    """
    results: dict[int, str] = {}   # rank → name, first-wins on duplicate ranks

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        # ── Strategy A: rank-anchored table scan ─────────────────
        for page in pdf.pages:
            for tbl in page.extract_tables():
                if not tbl:
                    continue
                for row in tbl:
                    # Normalise: flatten multi-line cell content, strip whitespace
                    cells = [
                        re.sub(r"\s+", " ", str(c)).strip() if c else ""
                        for c in row
                    ]
                    # Find a rank digit in this row, then hunt for a valid name
                    for i, cell in enumerate(cells):
                        if not re.fullmatch(r"\d{1,2}", cell):
                            continue
                        rank_val = int(cell)
                        if not (1 <= rank_val <= 20) or rank_val in results:
                            continue
                        # Scan remaining cells for first valid player name
                        for j in range(i + 1, len(cells)):
                            if is_valid_player_name(cells[j]):
                                results[rank_val] = cells[j]
                                break

        if len(results) >= 18:
            return [(name, rank) for rank, name in sorted(results.items())]

        # ── Strategy B: raw text line regex ──────────────────────
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
                        if is_valid_player_name(name_val):
                            results[rank_val] = name_val

    return [(name, rank) for rank, name in sorted(results.items())]


# ── CC ranks from backtest ────────────────────────────────────────────────
def get_cc_ranks(winners: dict) -> dict:
    if not os.path.exists(BACKTEST_PATH):
        print(f"WARNING: {BACKTEST_PATH} not found — CC_Rank will be blank")
        return {}
    bt = pd.read_csv(BACKTEST_PATH)
    cc_ranks = {}
    for season, winner in winners.items():
        s = bt[bt["Season"] == season]
        wn = normalise(winner)
        match = s[s["Player"].apply(normalise) == wn]
        if not match.empty:
            cc_ranks[season] = int(match.iloc[0]["Rank_Predicted"])
        else:
            # fuzzy fallback
            best = best_match_rank(
                [(row["Player"], int(row["Rank_Predicted"])) for _, row in s.iterrows()],
                winner,
            )
            cc_ranks[season] = best
            if best is None:
                print(f"WARNING: {winner} ({season}) not found in backtest data")
    return cc_ranks


# ── Main ─────────────────────────────────────────────────────────────────
def main():
    session = requests.Session()
    session.headers.update(HEADERS)

    cc_ranks = get_cc_ranks(ACTUAL_WINNERS)
    wheelo_ranks = {}

    for season in sorted(PDF_URLS):
        url = PDF_URLS[season]
        winner = ACTUAL_WINNERS[season]
        print(f"\n{'='*60}")
        print(f"Season {season}  —  Actual winner: {winner}")
        print(f"URL: {url}")

        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            print(f"Downloaded {len(resp.content):,} bytes")
        except Exception as e:
            print(f"ERROR downloading: {e}")
            wheelo_ranks[season] = None
            continue

        top20 = extract_top20_from_pdf(resp.content, season)

        if not top20:
            print("WARNING: No top-20 data extracted from PDF")
            wheelo_ranks[season] = None
            continue

        print(f"\nTop 20 extracted ({len(top20)} entries):")
        print(f"  {'Rank':<6} {'Player'}")
        print(f"  {'----':<6} {'------'}")
        for name, rank in top20:
            marker = "  <-- WINNER" if normalise(name) == normalise(winner) else ""
            print(f"  {rank:<6} {name}{marker}")

        rank = best_match_rank(top20, winner)
        wheelo_ranks[season] = rank
        if rank:
            print(f"\n  => {winner} ranked #{rank} by Wheelo in {season}")
        else:
            print(f"\n  => WARNING: {winner} not found in top 20 (ranked outside top 20)")

    # ── Build and write CSV ───────────────────────────────────────
    rows = []
    for season in sorted(ACTUAL_WINNERS):
        rows.append({
            "Season":       season,
            "Actual_Winner": ACTUAL_WINNERS[season],
            "CC_Rank":      cc_ranks.get(season, ""),
            "Wheelo_Rank":  wheelo_ranks.get(season, ""),
            "Betfair_Rank": "",
            "ESPN_Rank":    "",
        })

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    print(f"\n{'='*60}")
    print(f"Written: {OUT_CSV}")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
