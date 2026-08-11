"""Regression runner for the player-name join in features.py.

Usage:
    python tests/run_name_join_tests.py

Five feeds spell the same player five ways and AFLTables is not consistently on
either side of any convention. Left unhandled that cost 297 Wheelo rows and 66
coaches rows carrying 280 real votes, all merging as zero.

The collision that matters most is Bailey Williams, who exists twice at two
clubs. Every layer keeps team in the key so the two can never meet, and the
first two checks below assert exactly that.

No network and no model: normalise_name, first_names_compatible and
resolve_feed_names are pure.
"""

import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import features as feat                      # noqa: E402

FAILURES = []


def _safe(text):
    """Windows consoles default to cp1252, which cannot encode the accented
    fixture below. Labels are diagnostics, not data, so degrade rather than
    crash the run."""
    return str(text).encode("ascii", "replace").decode("ascii")


def check(name, got, want):
    if got == want:
        print(f"  PASS  {_safe(name)}")
    else:
        print(f"  FAIL  {_safe(name)}\n          got:  {_safe(repr(got))}"
              f"\n          want: {_safe(repr(want))}")
        FAILURES.append(_safe(name))


# ── Layer 1: the five conventions, plus initials and suffixes ────────────────
print("\nnormalise_name: conventions collapse to one key")

CONVENTIONS = [
    ("apostrophe",           "Connor OSullivan",   "Connor O'Sullivan"),
    ("apostrophe (curly)",   "Connor OSullivan",   "Connor O’Sullivan"),
    ("apostrophe",           "Massimo DAmbrosio",  "Massimo D'Ambrosio"),
    ("internal capitals",    "Harry McKay",        "Harry Mckay"),
    ("internal capitals",    "Hugh McCluggage",    "Hugh Mccluggage"),
    ("internal capitals",    "Connor Macdonald",   "Connor MacDonald"),
    ("lowercase particle",   "Jacob van Rooyen",   "Jacob Van Rooyen"),
    ("lowercase particle",   "Jordan de Goey",     "Jordan De Goey"),
    ("hyphen",               "Jason Horne-Francis", "Jason Horne Francis"),
    ("hyphen",               "Alex Neal-Bullen",   "Alex Neal Bullen"),
    ("middle initial",       "Bailey Williams",    "Bailey J. Williams"),
    ("middle initial",       "Bailey Williams",    "Bailey J Williams"),
    ("generational suffix",  "Malcolm Rosas",      "Malcolm Rosas Jr"),
    ("generational suffix",  "Malcolm Rosas",      "Malcolm Rosas Jnr"),
    ("accent",               "Nakia Cockatoo",     "Nakia Cóckatoo"),
]
for label, aflt, feed in CONVENTIONS:
    check(f"{label}: {feed!r} -> {aflt!r}",
          feat.normalise_name(feed), feat.normalise_name(aflt))

# Layer 1 must NOT collapse a diminutive: that needs team and round context.
check("Layer 1 leaves Harry/Harrison distinct",
      feat.normalise_name("Harry Petty") == feat.normalise_name("Harrison Petty"),
      False)
check("Layer 1 leaves Leo/Leonardo distinct",
      feat.normalise_name("Leo Lombard") == feat.normalise_name("Leonardo Lombard"),
      False)
check("blank name is handled", feat.normalise_name(None), "")

# Multi-word surnames must survive the initial-stripping rule.
check("van Rooyen keeps its particle",
      feat.name_parts("Jacob van Rooyen"), ("jacob", "vanrooyen"))
check("Horne-Francis stays one surname",
      feat.name_parts("Jason Horne-Francis"), ("jason", "hornefrancis"))
check("middle initial dropped, surname intact",
      feat.name_parts("Bailey J. Williams"), ("bailey", "williams"))


# ── The first-name rule, both directions of diminutive ───────────────────────
print("\nfirst_names_compatible")

for a, b in [("harry", "harrison"), ("leo", "leonardo"), ("josh", "joshua"),
             ("mitch", "mitchell"), ("cam", "cameron"), ("brad", "bradley"),
             ("dan", "daniel"), ("will", "william"), ("matt", "matthew")]:
    check(f"{a}/{b} accepted", feat.first_names_compatible(a, b), True)
    check(f"{b}/{a} accepted (reverse)", feat.first_names_compatible(b, a), True)

# The deliberate near-miss. Jack and Jacob share only three characters.
check("jack/jacob REJECTED", feat.first_names_compatible("jack", "jacob"), False)
check("zac/zane REJECTED", feat.first_names_compatible("zac", "zane"), False)
check("empty name REJECTED", feat.first_names_compatible("", "harrison"), False)

# Pins the threshold: raising it to 5 silently breaks Harry/Harrison, which is
# a live 2026 case (AFLTables Harry Petty against the coaches feed's Harrison).
check("threshold is 4, as validated by the same-surname sweep",
      feat.FIRST_NAME_PREFIX_MIN, 4)
check("threshold of 5 would break Harry/Harrison",
      feat.first_names_compatible("harry", "harrison", prefix_min=5), False)


# ── Layers 1 and 2 end to end, including the Bailey Williams collision ───────
print("\nresolve_feed_names")

TARGET = pd.DataFrame([
    # name, team, round
    ("Bailey Williams", "West Coast", 23),
    ("Bailey Williams", "Western Bulldogs", 23),
    ("Harry Petty", "Melbourne", 23),
    ("Leo Lombard", "Gold Coast", 23),
    ("Connor OSullivan", "Geelong", 23),
    ("Jacob van Rooyen", "Melbourne", 23),
    ("Jordan de Goey", "Collingwood", 23),
    ("Harry McKay", "Carlton", 23),
    ("Jason Horne-Francis", "Port Adelaide", 23),
    ("Jack Williams", "Carlton", 23),
    ("Jacob Williams", "Carlton", 23),
], columns=["Player_Name", "Playing.for", "Round_num"])

FEED = pd.DataFrame([
    ("Bailey J. Williams", "West Coast", 23),        # -> West Coast, not WB
    ("Bailey Williams", "Western Bulldogs", 23),     # -> WB, unchanged
    ("Harrison Petty", "Melbourne", 23),             # diminutive, needs layer 2
    ("Leonardo Lombard", "Gold Coast", 23),          # diminutive, needs layer 2
    ("Connor O'Sullivan", "Geelong", 23),            # apostrophe, layer 1
    ("Jacob Van Rooyen", "Melbourne", 23),           # particle, layer 1
    ("Jordan De Goey", "Collingwood", 23),           # particle, layer 1
    ("Harry Mckay", "Carlton", 23),                  # internal capitals, layer 1
    ("Jason Horne Francis", "Port Adelaide", 23),    # hyphen, layer 1
    ("Jacob Williams", "Carlton", 23),               # exact; must NOT take Jack
], columns=["Player", "Team", "Round"])

out, unmatched = feat.resolve_feed_names(
    FEED, TARGET, feed_name_col="Player", feed_team_col="Team",
    feed_round_col="Round", label="test", verbose=False)
got = dict(zip(FEED["Player"], out["Player"]))

check("nothing left unmatched", len(unmatched), 0)
check("apostrophe resolves", got["Connor O'Sullivan"], "Connor OSullivan")
check("internal capitals resolve", got["Harry Mckay"], "Harry McKay")
check("lowercase particle resolves", got["Jacob Van Rooyen"], "Jacob van Rooyen")
check("hyphen resolves", got["Jason Horne Francis"], "Jason Horne-Francis")
check("diminutive short->full resolves", got["Harrison Petty"], "Harry Petty")
check("diminutive full->short resolves", got["Leonardo Lombard"], "Leo Lombard")

# The collision. Both must survive, mapped to their own club.
check("Bailey J. Williams -> WEST COAST",
      (got["Bailey J. Williams"], out.loc[0, "Team"]),
      ("Bailey Williams", "West Coast"))
check("Bulldogs Bailey Williams stays at the Bulldogs",
      (got["Bailey Williams"], out.loc[1, "Team"]),
      ("Bailey Williams", "Western Bulldogs"))

# Jack and Jacob Williams share a surname AND a team AND a round, so the
# uniqueness guard must refuse layer 2 outright. The exact-name match still
# works, and Jack must not be touched.
check("Jacob Williams matches himself exactly",
      got["Jacob Williams"], "Jacob Williams")
check("Jack Williams is never produced",
      "Jack Williams" in out["Player"].tolist(), False)

# Same surname, same team, same round, incompatible first names: refuse.
COLLIDE_FEED = pd.DataFrame([("Jackson Williams", "Carlton", 23)],
                            columns=["Player", "Team", "Round"])
out2, unmatched2 = feat.resolve_feed_names(
    COLLIDE_FEED, TARGET, feed_name_col="Player", feed_team_col="Team",
    feed_round_col="Round", label="test", verbose=False)
check("ambiguous surname within team+round refuses to guess", len(unmatched2), 1)

# Team is load-bearing: the right surname at the wrong club must not match.
WRONG_TEAM = pd.DataFrame([("Harrison Petty", "Carlton", 23)],
                          columns=["Player", "Team", "Round"])
out3, unmatched3 = feat.resolve_feed_names(
    WRONG_TEAM, TARGET, feed_name_col="Player", feed_team_col="Team",
    feed_round_col="Round", label="test", verbose=False)
check("wrong club does not match", len(unmatched3), 1)


# ── Layer 2b: the explicit override map ─────────────────────────────────────
# One case per entry. Each of these is a first-name pair the prefix rule cannot
# bridge, so a regression in either mechanism shows up here.
print("\noverride map (layer 2b)")

OVERRIDES = [
    ("tom/thomas",     "Tom Edwards",     "Thomas Edwards",   "Essendon"),
    ("ollie/oliver",   "Ollie Greeves",   "Oliver Greeves",   "Hawthorn"),
    ("nick/nicholas",  "Nick Madden",     "Nicholas Madden",  "Greater Western Sydney"),
    ("joe/joseph",     "Joe Fonti",       "Joseph Fonti",     "Greater Western Sydney"),
    ("talor/taylor",   "Talor Byrne",     "Taylor Byrne",     "Carlton"),
]

for label, aflt, feed_spelling, team in OVERRIDES:
    tgt = pd.DataFrame([(aflt, team, 23)],
                       columns=["Player_Name", "Playing.for", "Round_num"])
    fd = pd.DataFrame([(feed_spelling, team, 23)],
                      columns=["Player", "Team", "Round"])
    out_o, unm_o = feat.resolve_feed_names(
        fd, tgt, feed_name_col="Player", feed_team_col="Team",
        feed_round_col="Round", label="test", verbose=False)
    check(f"{label}: {feed_spelling!r} -> {aflt!r}", out_o.loc[0, "Player"], aflt)
    check(f"{label}: nothing left unmatched", len(unm_o), 0)
    # Bidirectional: the same pair with the two sides swapped.
    tgt_r = pd.DataFrame([(feed_spelling, team, 23)],
                         columns=["Player_Name", "Playing.for", "Round_num"])
    fd_r = pd.DataFrame([(aflt, team, 23)], columns=["Player", "Team", "Round"])
    out_r, _ = feat.resolve_feed_names(
        fd_r, tgt_r, feed_name_col="Player", feed_team_col="Team",
        feed_round_col="Round", label="test", verbose=False)
    check(f"{label}: resolves in reverse too", out_r.loc[0, "Player"], feed_spelling)

# The map is a fallback, not a parallel path: names the prefix rule already
# handles must NOT be in it, or two mechanisms compete on the same name.
for already in ["josh", "joshua", "mitch", "mitchell", "cam", "cameron",
                "harry", "harrison", "leo", "leonardo"]:
    check(f"{already!r} is absent from the override map",
          already in feat.FIRST_NAME_ALIASES, False)

# Symmetric by construction, and never self-matching.
check("aliases are bidirectional",
      (feat.first_names_aliased("tom", "thomas"),
       feat.first_names_aliased("thomas", "tom")), (True, True))
check("alias does not fire on an identical name",
      feat.first_names_aliased("tom", "tom"), False)
check("alias does not fire across groups",
      feat.first_names_aliased("tom", "oliver"), False)

# THE re-assert: Jack/Jacob must still not match with the map in place.
check("jack/jacob still rejected by the prefix rule",
      feat.first_names_compatible("jack", "jacob"), False)
check("jack/jacob is not in the override map",
      feat.first_names_aliased("jack", "jacob"), False)
JJ_TGT = pd.DataFrame([("Jack Williams", "Carlton", 23)],
                      columns=["Player_Name", "Playing.for", "Round_num"])
JJ_FEED = pd.DataFrame([("Jacob Williams", "Carlton", 23)],
                       columns=["Player", "Team", "Round"])
_, jj_unm = feat.resolve_feed_names(
    JJ_FEED, JJ_TGT, feed_name_col="Player", feed_team_col="Team",
    feed_round_col="Round", label="test", verbose=False)
check("Jacob Williams does NOT resolve onto Jack Williams", len(jj_unm), 1)


# ── Layer 3 reports what it could not resolve ───────────────────────────────
print("\nunmatched reporting")

MYSTERY = pd.DataFrame([("Someone Entirely New", "Carlton", 23)],
                       columns=["Player", "Team", "Round"])
out4, unmatched4 = feat.resolve_feed_names(
    MYSTERY, TARGET, feed_name_col="Player", feed_team_col="Team",
    feed_round_col="Round", label="test", verbose=False)
check("unknown player is reported, not dropped", len(unmatched4), 1)
check("unmatched frame carries feed/player/team/round",
      sorted(unmatched4.columns.tolist()), ["Player", "Round", "Team"])
check("unresolved name passes through unchanged",
      out4.loc[0, "Player"], "Someone Entirely New")

print()
if FAILURES:
    print(f"{len(FAILURES)} check(s) failed: {', '.join(FAILURES)}")
    sys.exit(1)
print("All checks passed.")
sys.exit(0)
