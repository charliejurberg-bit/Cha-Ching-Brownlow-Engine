"""check_site_parity.py — does the exported site JSON match the Streamlit page?

    python scripts/check_site_parity.py              2026 and 2025, both boards
    python scripts/check_site_parity.py 2019 2007    other seasons

Renders dashboard.py's Leaderboard headless (streamlit AppTest), reads its table
straight out of the page HTML, and compares the first 200 rows cell for cell
with site/data/leaderboard/<season>.json: rank order, name, club, games, total,
actual votes and every round cell. Game Analysis is checked the same way for
its default view. Run from the repo root after
export_site.py. Exits 1 on any difference.

It exists because site_data.py is a copy of the dashboard's loaders (see its
header): while both apps are live, this is what proves the copy still agrees.
"""

import html
import json
import os
import re
import sys

from streamlit.testing.v1 import AppTest

# dashboard.py imports its siblings (betting_hub, user_auth, features); run from
# scripts/, the repo root is not on the path unless put there.
sys.path.insert(0, os.getcwd())

SHOW = 200
_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_TAG = re.compile(r"<[^>]+>")


def _page_rows(season, mode):
    at = AppTest.from_file("dashboard.py", default_timeout=600)
    at.session_state["page"] = "Leaderboard"
    at.session_state["active_hub"] = "brownlow"
    at.session_state["season_by_page"] = {"Leaderboard": season}
    at.session_state["lb_vote_mode"] = mode
    at.run()
    if at.exception:
        raise SystemExit(f"page raised: {at.exception[0].value}")
    show = next(s for s in at.selectbox if s.label == "SHOW")
    show.set_value(SHOW)
    at.run()
    tbl = next(m.value for m in at.markdown if 'class="lb-tbl"' in m.value)
    body = tbl.split("<tbody>", 1)[1]
    rows = []
    for tr in _ROW.findall(body):
        cells = _CELL.findall(tr)
        name = re.search(r'lb-pname">(.*?)</span>', tr).group(1)
        rows.append({
            "name": html.unescape(name),
            "cells": [html.unescape(_TAG.sub("", c)).strip() for c in cells],
        })
    return rows


def _fmt(v, dp):
    """A round cell: blank for no game, a dot for a game that drew nothing."""
    if v is None:
        return ""
    if v < 0.05:
        return "·"
    return f"{v:.{dp}f}"


def check(season, mode):
    data = json.load(open(f"site/data/leaderboard/{season}.json", encoding="utf-8"))
    board = data["boards"]["rounded" if mode == "3-2-1" else "decimal"]
    dp = 0 if mode == "3-2-1" else 1
    page = _page_rows(season, mode)
    want = board["players"][:SHOW]
    bad = []
    if len(page) != len(want):
        bad.append(f"row count page {len(page)} vs json {len(want)}")
    for i, (p, w) in enumerate(zip(page, want), start=1):
        c = p["cells"]
        mv = w.get("move", 0)
        arrow = f"▲{mv}" if mv > 0 else (f"▼{-mv}" if mv < 0 else "")
        exp = [str(i) + arrow, w["name"], str(w["games"]), f'{w["votes"]:.{dp}f}']
        got = [c[0], p["name"], c[2], c[3]]
        tail = c[4:]
        if not data["live"]:
            exp += [str(w["actual"]), format(w["votes"] - w["actual"], f"+.{dp}f")]
            # The page subtracts from the unrounded total, so a zero gap can
            # print as -0.0 there. Same number; the site shows +0.0.
            got += [tail[0], tail[1].replace("-0.0", "+0.0")] if len(tail) > 1 else tail
            tail = tail[2:]
        elif "ceiling" in w or any("ceiling" in x for x in want):
            tail = tail[1:]            # Floor-Ceiling cell, a bar drawn from the same numbers
        exp += [_fmt(v, dp) for v in w["rounds"]]
        got += tail
        if got != exp:
            diff = [(k, g, e) for k, (g, e) in enumerate(zip(got, exp)) if g != e]
            bad.append(f"row {i} {w['name']}: {diff[:4]}")
    tag = f"{season} {mode:>7}"
    if bad:
        print(f"FAIL {tag}: {len(bad)} differences")
        for b in bad[:10]:
            print("   ", b)
    else:
        print(f"ok   {tag}: {len(want)} rows identical")
    return not bad


def check_games(season):
    """Game Analysis, default view (the season's last round): every card's
    heading, podium order and first ten table rows against games/<season>.json."""
    data = json.load(open(f"site/data/games/{season}.json", encoding="utf-8"))
    last = max(g["round"] for g in data["games"])
    want = [g for g in data["games"] if g["round"] == last]
    at = AppTest.from_file("dashboard.py", default_timeout=600)
    at.session_state["page"] = "Game Analysis"
    at.session_state["active_hub"] = "brownlow"
    at.session_state["season_by_page"] = {"Game Analysis": season}
    at.run()
    if at.exception:
        raise SystemExit(f"page raised: {at.exception[0].value}")
    cards = [m.value for m in at.markdown if 'class="ga-game"' in m.value]
    bad = []
    if len(cards) != len(want):
        bad.append(f"cards page {len(cards)} vs json {len(want)}")
    for i, (c, w) in enumerate(zip(cards, want), start=1):
        body = c.split("<tbody>", 1)[1]
        for j, (tr, p) in enumerate(zip(_ROW.findall(body), w["players"][:10]), start=1):
            cells = [html.unescape(_TAG.sub("", x)).strip() for x in _CELL.findall(tr)]
            name = html.unescape(re.search(r'ga-pname">(.*?)</span>', tr).group(1))
            got = [name] + cells[1:]
            exp = [p[0], f"{p[2]:.2f}", f"{round(p[3])}%"] + [str(v) for v in p[4:]]
            if got != exp:
                bad.append(f"game {i} row {j}: {[(g, e) for g, e in zip(got, exp) if g != e][:3]}")
    tag = f"{season} games"
    print(f"FAIL {tag}: {len(bad)} differences" if bad else f"ok   {tag}: {len(want)} games of round {last} identical")
    for b in bad[:10]:
        print("   ", b)
    return not bad


def main(argv):
    seasons = [int(a) for a in argv] or [2026, 2025]
    ok = all([check(s, m) for s in seasons for m in ("Decimal", "3-2-1")]
             + [check_games(s) for s in seasons])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONHASHSEED", "0")
    main(sys.argv[1:])
