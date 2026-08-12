"""Club-string canonicalisation for cross-era recon, 1990-2025.

AFLTables records a club under whatever name it carried at the time, so the
same franchise appears under several strings across the archive. Any query that
spans eras (opponent splits, head-to-head records, venue histories) has to
canonicalise first or it silently undercounts.

RECON ONLY. This module must not be imported by features.py, brownlow_model.py
or predict_2026.py. The model trains on raw `Playing.for` / `Home.team` /
`Away.team` values and its encoders are fitted on those exact strings; folding
aliases underneath it would change the feature space without a retrain.

Franchise timelines this covers:

    North Melbourne   1990-1998  ->  North Melbourne
    Kangaroos         1999-2007  ->  North Melbourne
    North Melbourne   2008-2025  ->  North Melbourne

    Footscray         1990-1996  ->  Western Bulldogs
    Western Bulldogs  1997-2025  ->  Western Bulldogs

    Brisbane Bears    1990-1996  ->  Brisbane Lions
    Brisbane Lions    1997-2025  ->  Brisbane Lions

    South Melbourne   1965-1981  ->  Sydney
    Sydney            1982-2025  ->  Sydney

Fitzroy is deliberately NOT folded into Brisbane Lions. The 1996 merger created
a new entity; treating 1990-1996 Fitzroy games as Brisbane Lions games would
attribute one club's vote history to another. Fitzroy canonicalises to itself
and terminates in 1996.

The mapping is by string, not by season. Every alias above is unambiguous on
its own (no string ever refers to two different franchises), so the caller does
not need to pass a year. Unknown strings pass through unchanged, which keeps
the function safe to apply blanket-fashion to a whole column.
"""

__all__ = ["canonical_club", "CLUB_ALIASES"]


CLUB_ALIASES = {
    "Kangaroos": "North Melbourne",
    "Footscray": "Western Bulldogs",
    "Brisbane Bears": "Brisbane Lions",
    # Relocated and renamed after 1981. No row in this repository is earlier
    # than 1990, so nothing currently reaches this entry; it is here so a
    # window that widens past 1982 does not silently gain a 19th club.
    "South Melbourne": "Sydney",
    # Not an AFLTables string, but non-AFLTables feeds in this repo (and
    # dashboard._TEAM_ALIASES) abbreviate it, so recon that mixes sources needs it.
    "GWS": "Greater Western Sydney",
}


def canonical_club(club):
    """Return the canonical club name for a raw club string.

    Unrecognised names, including Fitzroy, are returned unchanged apart from
    surrounding whitespace. Non-string input (None, NaN) is returned as-is so
    the function can be mapped over a column with missing values.

    >>> canonical_club("Kangaroos")
    'North Melbourne'
    >>> canonical_club("Footscray")
    'Western Bulldogs'
    >>> canonical_club("Brisbane Bears")
    'Brisbane Lions'
    >>> canonical_club("Fitzroy")
    'Fitzroy'
    >>> canonical_club("Hawthorn")
    'Hawthorn'
    """
    if not isinstance(club, str):
        return club
    name = club.strip()
    return CLUB_ALIASES.get(name, name)
