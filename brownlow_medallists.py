"""Canonical Brownlow medallists — single source of truth for the actual-winner
ground truth used by the backtest accuracy metrics (Model Insights tab + backtest.py).

The actual winner must NOT be derived from vote totals in the data: groupby on
player name alone collides same-name players (e.g. the two Josh Kennedys, two Scott
Thompsons) and inflates the wrong row to rank 1. Each season maps to a list of
(player_name, team) tuples so a winner can be matched back to a single player row by
name AND team.

Hazards encoded here:
- 2012 is a JOINT medal. Jobe Watson originally won but was stripped in 2016 and the
  medal reallocated to Sam Mitchell and Trent Cotchin — both are returned.
- 2014 / 2015: name-only matching returns "Josh Kennedy" (collision). The real winners
  are Matt Priddis (West Coast, 2014) and Nat Fyfe (Fremantle, 2015).

Team strings match the `Team` column in predictions/backtest_results.csv.
"""

BROWNLOW_MEDALLISTS = {
    2008: [("Adam Cooney", "Western Bulldogs")],
    2009: [("Gary Ablett", "Geelong")],
    2010: [("Chris Judd", "Carlton")],
    2011: [("Dane Swan", "Collingwood")],
    2012: [("Sam Mitchell", "Hawthorn"), ("Trent Cotchin", "Richmond")],  # joint
    2013: [("Gary Ablett", "Gold Coast")],
    2014: [("Matt Priddis", "West Coast")],
    2015: [("Nat Fyfe", "Fremantle")],
    2016: [("Patrick Dangerfield", "Geelong")],
    2017: [("Dustin Martin", "Richmond")],
    2018: [("Tom Mitchell", "Hawthorn")],
    2019: [("Nat Fyfe", "Fremantle")],
    2020: [("Lachie Neale", "Brisbane Lions")],
    2021: [("Ollie Wines", "Port Adelaide")],
    2022: [("Patrick Cripps", "Carlton")],
    2023: [("Lachie Neale", "Brisbane Lions")],
    2024: [("Patrick Cripps", "Carlton")],
    2025: [("Matt Rowell", "Gold Coast")],
}


def get_medallists(season):
    """Return the list of (name, team) canonical medallists for a season.

    Returns an empty list for seasons not in the table, so callers can render an
    em-dash rather than crash.
    """
    try:
        return BROWNLOW_MEDALLISTS.get(int(season), [])
    except (TypeError, ValueError):
        return []
