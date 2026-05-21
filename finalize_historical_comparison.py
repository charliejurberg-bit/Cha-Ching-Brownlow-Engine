"""
finalize_historical_comparison.py

Final step: add Betfair ranks retrieved from Wayback Machine snapshots
(Betfair 2024 pre-count, 2025 pre-count), then print the completed table.

Verified Betfair Wayback ranks:
  2024: Patrick Cripps #2  (snapshot 20240910 — pre-count)
  2025: Matt Rowell   #9   (snapshot 20250913 — pre-count)

Data gaps with reasons:
  Wheelo 2021/2022 — PDFs 404 on wheeloratings.com, no Wayback Machine copy
  Betfair 2021     — no Wayback Machine snapshot for Sep/Oct 2021
  Betfair 2022/2023 — Wayback snapshots captured only the static HTML shell;
                      per-game vote tables were JS-rendered and not archived

Run from the brownlow_engine directory.
"""

import re
import time
import requests
import pandas as pd
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

# Wayback Machine snapshots for Betfair predictor page
# These are pre-count (before the September/October Brownlow ceremony)
BETFAIR_WAYBACK = {
    2024: "https://web.archive.org/web/20240910203322/https://www.betfair.com.au/hub/sports/afl/brownlow-medal-predictor/",
    2025: "https://web.archive.org/web/20250913170011/https://www.betfair.com.au/hub/sports/afl/brownlow-medal-predictor/",
}


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


def fetch_betfair_wayback(url: str, winner: str) -> int | None:
    headers = {"User-Agent": _UA}
    try:
        resp = requests.get(url, headers=headers, timeout=40)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ERROR fetching: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    votes: dict[str, float] = {}

    for table in soup.find_all("table"):
        for row in table.find_all("tr")[1:]:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            player = cells[0].get_text(strip=True)
            for cell in cells[1:]:
                val_str = cell.get_text(strip=True)
                try:
                    v = float(val_str)
                    if 0 < v <= 3 and re.search(r"[A-Za-z]{2,}\s[A-Za-z]{2,}", player):
                        pt = player.title().strip()
                        if " " in pt:
                            votes[pt] = votes.get(pt, 0) + v
                    break
                except ValueError:
                    continue

    if not votes:
        print(f"  WARNING: no vote data found")
        return None

    ranked = sorted(votes.items(), key=lambda x: -x[1])
    print(f"  Players: {len(votes)}  Top 5: {[(n, f'{v:.1f}') for n, v in ranked[:5]]}")
    candidates = [(name, i + 1) for i, (name, _) in enumerate(ranked)]
    rank = best_match_rank(candidates, winner)
    return rank


def main():
    print("=" * 65)
    print("FINALIZE HISTORICAL MODEL COMPARISON")
    print("=" * 65)

    df = pd.read_csv(OUT_CSV)
    df["Season"] = df["Season"].astype(int)
    df = df.set_index("Season")

    # Fetch Betfair from Wayback Machine for seasons that are missing
    betfair_needed = [
        s for s in sorted(BETFAIR_WAYBACK)
        if s in df.index and pd.isna(df.loc[s, "Betfair_Rank"])
    ]
    print(f"\nBetfair Wayback needed: {betfair_needed or 'none'}")
    for season in betfair_needed:
        winner = ACTUAL_WINNERS[season]
        url = BETFAIR_WAYBACK[season]
        print(f"\n[Betfair {season}] {url[:80]}")
        rank = fetch_betfair_wayback(url, winner)
        df.loc[season, "Betfair_Rank"] = rank
        if rank:
            print(f"  => {winner} ranked #{rank}")
        else:
            print(f"  => WARNING: {winner} not found in predictions")
        time.sleep(1)

    # Save
    df = df.reset_index().sort_values("Season")
    df.to_csv(OUT_CSV, index=False)

    # Summary
    print(f"\n{'='*65}")
    print(f"Written: {OUT_CSV}")
    print()
    print("DATA AVAILABILITY NOTES:")
    print("  Wheelo 2021/2022 : PDFs removed from wheeloratings.com; not in Wayback Machine")
    print("  Betfair 2021     : No Wayback Machine snapshot for Sep-Oct 2021")
    print("  Betfair 2022/2023: Wayback snapshots missing JS-rendered vote tables")
    print()

    # Pretty-print the final table
    disp = df.copy()
    for col in ["CC_Rank", "Wheelo_Rank", "Betfair_Rank", "ESPN_Rank"]:
        if col in disp.columns:
            disp[col] = pd.to_numeric(disp[col], errors="coerce").astype("Int64")

    disp.columns = [
        c.replace("CC_Rank", "CC")
         .replace("Wheelo_Rank", "Wheelo")
         .replace("Betfair_Rank", "Betfair")
         .replace("ESPN_Rank", "ESPN")
        for c in disp.columns
    ]
    print(disp.to_string(index=False))
    print()
    print("Legend: rank of actual winner in each model's pre-count predictions")
    print("        NaN = data not available for that year/model combination")


if __name__ == "__main__":
    main()
