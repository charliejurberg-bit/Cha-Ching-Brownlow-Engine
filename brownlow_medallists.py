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
- A season's medallists are NOT always its highest polling players, so this table can
  never be derived from vote totals. Three seasons prove it: 1997 (Chris Grant led on
  27 and was ineligible through suspension, so Robert Harvey won on 26), 1996 (Corey
  McKernan tied on 21 and was ineligible, so only Michael Voss and James Hird are
  returned) and 2012 (Jobe Watson led on 30 and was stripped). Every other season's
  medallist set does equal its top-poller set, which is asserted rather than assumed.

TEAM STRING CONTRACT, 1984-2025
Team strings are the **era-correct raw `Playing.for` value**, not a canonical
franchise name. Pre-1997 entries therefore carry the club's name at the time:
"Footscray" (1985, 1990, 1992) rather than Western Bulldogs, and "Brisbane Bears"
(1996) rather than Brisbane Lions. "Kangaroos" is the same trap for 1999-2007 should a
North Melbourne winner ever be added there.

Consumers MUST pass the stored string through `club_aliases.canonical_club()` before
matching it against a canonicalised club column. That function is idempotent over
every raw string in the archive, so canonicalising is safe whether the entry is an
era name or already canonical. For 2008-2025 the two coincide, which is why the
original 18 entries did not have to make the distinction; they still match the `Team`
column in predictions/backtest_results.csv (itself 2008-2025 only) unchanged.

MEDALLIST_IDS carries the same winners keyed on fitzRoy player `ID`, resolved by
script against the all_time_tables.py frame and never typed by hand. It is a parallel
dict rather than a third tuple element on purpose: six sites in backtest.py and
dashboard.py unpack these tuples as exactly two values, and a 3-tuple raises
"too many values to unpack (expected 2)" in all six.
"""

BROWNLOW_MEDALLISTS = {
    1984: [("Peter Moore", "Melbourne")],
    1985: [("Brad Hardie", "Footscray")],
    1986: [("Robert DiPierdomenico", "Hawthorn"), ("Greg Williams", "Sydney")],  # joint
    1987: [("Tony Lockett", "St Kilda"), ("John Platten", "Hawthorn")],  # joint
    1988: [("Gerard Healy", "Sydney")],
    1989: [("Paul Couch", "Geelong")],
    1990: [("Tony Liberatore", "Footscray")],
    1991: [("Jim Stynes", "Melbourne")],
    1992: [("Scott Wynd", "Footscray")],
    1993: [("Gavin Wanganeen", "Essendon")],
    1994: [("Greg Williams", "Carlton")],
    1995: [("Paul Kelly", "Sydney")],
    1996: [("Michael Voss", "Brisbane Bears"), ("James Hird", "Essendon")],  # joint
    1997: [("Robert Harvey", "St Kilda")],
    1998: [("Robert Harvey", "St Kilda")],
    1999: [("Shane Crawford", "Hawthorn")],
    2000: [("Shane Woewodin", "Melbourne")],
    2001: [("Jason Akermanis", "Brisbane Lions")],
    2002: [("Simon Black", "Brisbane Lions")],
    2003: [("Nathan Buckley", "Collingwood"), ("Adam Goodes", "Sydney"), ("Mark Ricciuto", "Adelaide")],  # joint
    2004: [("Chris Judd", "West Coast")],
    2005: [("Ben Cousins", "West Coast")],
    2006: [("Adam Goodes", "Sydney")],
    2007: [("Jimmy Bartel", "Geelong")],
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


# The same winners keyed on fitzRoy player `ID`, in the same order as the tuples
# above. Resolved by script against the all_time_tables.py frame by matching name
# and canonicalised team within the season, asserting exactly one matching row per
# tuple across all 42 seasons. Never typed by hand: an ID mistyped here is
# invisible, where a mistyped name fails the match loudly.
#
# A parallel dict rather than a third tuple element, because six sites in
# backtest.py and dashboard.py unpack the tuples above as exactly two values.
MEDALLIST_IDS = {
    1984: [2000],  # Peter Moore
    1985: [1300],  # Brad Hardie
    1986: [1350, 142],  # Robert DiPierdomenico & Greg Williams
    1987: [990, 636],  # Tony Lockett & John Platten
    1988: [1366],  # Gerard Healy
    1989: [565],  # Paul Couch
    1990: [426],  # Tony Liberatore
    1991: [702],  # Jim Stynes
    1992: [424],  # Scott Wynd
    1993: [303],  # Gavin Wanganeen
    1994: [142],  # Greg Williams
    1995: [993],  # Paul Kelly
    1996: [102, 312],  # Michael Voss & James Hird
    1997: [930],  # Robert Harvey
    1998: [930],  # Robert Harvey
    1999: [633],  # Shane Crawford
    2000: [725],  # Shane Woewodin
    2001: [119],  # Jason Akermanis
    2002: [1083],  # Simon Black
    2003: [217, 1012, 4],  # Nathan Buckley & Adam Goodes & Mark Ricciuto
    2004: [1122],  # Chris Judd
    2005: [1051],  # Ben Cousins
    2006: [1012],  # Adam Goodes
    2007: [1106],  # Jimmy Bartel
    2008: [3940],  # Adam Cooney
    2009: [1105],  # Gary Ablett
    2010: [1122],  # Chris Judd
    2011: [1460],  # Dane Swan
    2012: [1135, 11666],  # Sam Mitchell & Trent Cotchin
    2013: [1105],  # Gary Ablett
    2014: [4186],  # Matt Priddis
    2015: [11834],  # Nat Fyfe
    2016: [11700],  # Patrick Dangerfield
    2017: [11794],  # Dustin Martin
    2018: [12196],  # Tom Mitchell
    2019: [11834],  # Nat Fyfe
    2020: [12055],  # Lachie Neale
    2021: [12150],  # Ollie Wines
    2022: [12261],  # Patrick Cripps
    2023: [12055],  # Lachie Neale
    2024: [12261],  # Patrick Cripps
    2025: [12768],  # Matt Rowell
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


def get_medallist_ids(season):
    """Return the list of fitzRoy player IDs for a season's medallists.

    Same order as get_medallists(), and an empty list for seasons not in the
    table, so callers can render a placeholder rather than crash. Prefer this
    over matching on name and team when the caller already has an ID column:
    it cannot collide same-name players and needs no club canonicalisation.
    """
    try:
        return MEDALLIST_IDS.get(int(season), [])
    except (TypeError, ValueError):
        return []
