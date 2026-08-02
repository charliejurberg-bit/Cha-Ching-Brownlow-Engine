"""Draft gate — refuses to let an unsourced post draft through.

Usage:
    python draft_gate.py drafts/<name>.md

Reads the draft and its sibling drafts/<name>.facts.json, then runs the checks
below. Any failure prints the offending line and exits 1. All of them passing
exits 0 with a one-line summary.

    CHECK 1  superlative   a superlative claim needs a well-formed ranked
                           table behind it
    CHECK 2  denominator   every rate declares what it is a rate *of*, and no
                           total smuggles a denominator in
    CHECK 3  attribution   every figure in the prose traces back to a facts
                           entry whose subject is named alongside it
    CHECK 4  depth         a superlative declares the set it won, how far
                           clear it is, and whether its threshold was chosen
    CHECK 5  finals        a finals decision reconciles: rows in, minus finals
                           excluded, equals rows out
    CHECK 6  base rate     a claim that something has not happened carries the
                           odds that it would not have, and clears the ceiling
    CHECK 7  multi-club    a record split across clubs names every one of them
                           in the window of every entry that uses it
    CHECK 8  subject drift two spellings of one subject, which bind as two
                           different subjects and silently reach nothing
"""

import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- config

DENOMINATOR_TYPES = {
    "vote_eligible_games",
    "games_played",
    "matches_between_clubs",
    "player_games",
    "unavailable",
}

# A player accrues votes only in games the umpires polled, so a vote rate has
# exactly two defensible bases: the vote-eligible games themselves, or the
# meetings between the two clubs. Everything else in the enum either counts
# games no votes were available in, or admits it does not know the count.
VOTE_ELIGIBLE = {"vote_eligible_games", "matches_between_clubs"}
NOT_VOTE_ELIGIBLE = DENOMINATOR_TYPES - VOTE_ELIGIBLE

RATE_FIELDS = ("subject", "value", "denominator", "denominator_type", "source_file")

# A total is a raw count — career games, polls, votes — and carries no base,
# because it is the base. The two keys a rate needs are exactly the two a total
# must not have: anything divided by something is a rate and belongs in rates.
TOTALS_FIELDS = ("subject", "value", "source_file")
TOTALS_FORBIDDEN_FIELDS = ("denominator", "denominator_type")

RANKED_TABLE_FIELDS = ("subject", "window", "rows")

# A superlative is a claim about a set, and one row does not establish a
# ranking. Two is the floor the gate can defend: it cannot know the true size
# of the set, so it must not demand more.
MIN_RANKED_ROWS = 2

SUPERLATIVES = (
    "only", "no other", "best", "worst", "highest", "lowest", "most", "fewest",
)

# "the most recent meeting" is a date, not a ranking. Same treatment as the
# zero-vote lookahead and for the same reason: a compound where the trigger
# word does different work. Every other use of "most" still triggers.
SUPERLATIVE_LOOKAHEAD = {"most": r"(?!\s+recent\b)"}

SUPERLATIVE_RE = re.compile(
    "|".join(
        rf"\b{w.replace(' ', r'\s+')}\b" + SUPERLATIVE_LOOKAHEAD.get(w, "")
        for w in SUPERLATIVES
    ),
    re.IGNORECASE,
)

# A ranked table shows that a ranking exists. These fields show how much the
# ranking is worth: how big the set was, how far clear the winner is, and
# whether the threshold defining the set was chosen to fit or survived a move
# in both directions.
SUPERLATIVE_FIELDS = (
    "claim_id",
    "subject",
    "scale",
    "window",
    "threshold",
    "threshold_unit",
    "set_size",
    "top5",
    "gap_to_rank_2",
    "stricter_threshold",
    "survives_stricter",
    "looser_threshold",
    "survives_looser",
    "at_set_ceiling",
    "threshold_chosen_to_fit",
    "source_file",
)

TOP5_ROW_FIELDS = ("rank", "name", "value")

# A finals decision is only checkable if the run says what it did: rows read,
# rows dropped, rows kept. The three share whatever unit the entry counts in,
# matches for a figure about matches, player rows for a ranking over players.
FINALS_FIELDS = ("rows_in", "finals_excluded", "rows_out")

FINALS_RE = re.compile(r"\bfinals?\b", re.IGNORECASE)

# A claim that something has not happened is a claim about a probability, and
# these are the words the copy reaches for to make one.
ABSENCE_TOKENS = (
    "never",
    "no votes",
    "yet to",
    "zero",
    "without a",
    "drought",
    "hasn't polled",
    "has not polled",
)

# "zero-vote games" is the count label the three-number rule in the standing
# preamble requires of every player record, and a denominator is not a claim
# that anything is absent. The token stops short of that compound and of
# nothing else: every other use of "zero" still triggers.
ABSENCE_LOOKAHEAD = {"zero": r"(?![-\s]vote)"}

# re.escape leaves a straight apostrophe alone, so swapping it on the escaped
# pattern is safe and picks up the typographic form a draft carries in from a
# word processor.
ABSENCE_RE = re.compile(
    "|".join(
        r"\b"
        + r"\s+".join(re.escape(word) for word in token.split()).replace(
            "'", "['’]"
        )
        + r"\b"
        + ABSENCE_LOOKAHEAD.get(token, "")
        for token in ABSENCE_TOKENS
    ),
    re.IGNORECASE,
)

BASE_RATE_FIELDS = (
    "claim_id",
    "subject",
    "event",
    "base_rate",
    "base_rate_window",
    "trials",
    "observed_count",
    "p_observed",
    "source_file",
)

# An absence is worth writing about when the record did not predict it. At even
# odds the record predicted it exactly, so half is the line: at or above it the
# silence is the most likely single outcome, and the claim is arithmetic
# dressed as a story.
P_OBSERVED_CEILING = 0.50

# Slack between the declared probability and the one base_rate and trials
# imply. Wide enough for a probability quoted to two decimal places, which is
# how the copy prints it, and still far narrower than the step between adjacent
# trial counts, so a p_observed computed over a different number of meetings
# than the entry declares does not fit through.
P_OBSERVED_TOLERANCE = 0.005

CLUB_SPLIT_FIELDS = ("subject", "window", "splits", "source_file")

SPLIT_ROW_FIELDS = ("club", "rows", "polls", "votes")

# Totals a club_splits entry may declare for itself. Each is optional, and each
# one present is an arithmetic claim the splits have to satisfy.
SPLIT_TOTAL_FIELDS = ("rows", "polls", "votes")

# Every group that names what its entries are about. A subject in any of them
# binds by exact string, so all of them are compared against each other.
SUBJECT_GROUPS = (
    "rates",
    "totals",
    "ranked_tables",
    "superlatives",
    "base_rates",
    "club_splits",
)

# Possessives go before punctuation, or the apostrophe is stripped first and
# "Dawson's" normalises to "dawsons" instead of "dawson".
POSSESSIVE_RE = re.compile(r"['’]s\b")

# Punctuation becomes a space rather than nothing, so "2014-2025" normalises to
# two numbers rather than one, and "vote-eligible" agrees with "vote eligible".
PUNCTUATION_RE = re.compile(r"[^\w\s]")

WHITESPACE_RE = re.compile(r"\s+")

# Five is the depth a reader needs to see the near misses. A smaller set shows
# all of itself instead, because there is nothing being held back.
TOP5_DEPTH = 5

# Slack between the declared gap and the one the rows imply. Wide enough for
# rounding in the facts file, narrow enough that a gap taken from a different
# table than the one printed does not fit through.
GAP_TOLERANCE = 0.001

# <!-- claim: merrett-adelaide-best-vpg --> on the line above what it governs.
CLAIM_COMMENT_RE = re.compile(r"<!--\s*claim:\s*([A-Za-z0-9][A-Za-z0-9_-]*)\s*-->")

# A whole claim comment line, for stripping before the copy is posted. The
# optional "> " matters: a sentence-scoped claim inside a tweet needs its
# comment inside the blockquote, or the unquoted line breaks the quote. Such a
# comment is still a whole line and the whole line goes.
CLAIM_COMMENT_LINE_RE = re.compile(
    r"[ \t]*>?[ \t]*<!--\s*claim:\s*[A-Za-z0-9][A-Za-z0-9_-]*\s*-->[ \t]*\n?"
)

# A markdown heading needs the space: "#AFLBombersCrows" is a hashtag, and a
# blockquoted hashtag starts with ">" so it never reaches column zero anyway.
HEADING_RE = re.compile(r"^#{1,6}\s", re.MULTILINE)

YEAR_MIN, YEAR_MAX = 1990, 2026

# Words that look like names and identify nobody. Every subject in the file
# carries some of them ("Zach Merrett career Brownlow votes per game"), so a
# match on one would attribute a figure to any entry at all.
SUBJECT_STOP_TOKENS = {
    "Brownlow", "AFL", "Round", "Votes", "Vote", "Exp", "Medal", "Total", "Avg",
}

# A capitalised word of three or more characters, which is how a subject names
# the thing it is about: a player, a club, a venue. Sentence-initial capitals
# can match one of these by accident, and so can a stray heading word, which
# clears a figure that attribution never earned. That is a false clear, and it
# is the accepted direction of error: this check may not fail correct copy in
# order to catch incorrect copy.
#
# The apostrophe is deliberately outside the class. A subject reading "Jordan
# Dawson's lowest ..." would otherwise yield the token "Dawson's", which never
# matches prose that says "Dawson". Stopping at the apostrophe yields "Dawson"
# from the possessive and "Brien" from "O'Brien", and both are substrings of the
# name as the copy writes it.
NAME_TOKEN_RE = re.compile(r"\b[A-Z][A-Za-z\-]{2,}\b")

# What a ranked_tables row calls the thing it describes, in preference order.
ROW_LABEL_KEYS = ("player", "opponent", "venue")

# 1,200 / 17 / 1.20 — commas grouped, optional decimal tail.
NUMBER_RE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
HASHTAG_RE = re.compile(r"#[A-Za-z0-9_]+")


# ---------------------------------------------------------------- helpers

def fail(check, message, lineno=None, line=None, path=None):
    """Print a failure and exit 1."""
    print(f"FAIL  {check}")
    print(f"      {message}")
    if line is not None:
        loc = f"{path}:{lineno}" if path else f"line {lineno}"
        print(f"      {loc}: {line.strip()}")
    sys.exit(1)


def line_of(text, offset):
    """1-indexed line number and line content for a character offset."""
    lineno = text.count("\n", 0, offset) + 1
    start = text.rfind("\n", 0, offset) + 1
    end = text.find("\n", offset)
    if end == -1:
        end = len(text)
    return lineno, text[start:end]


def sentence_of(text, start, end):
    """The sentence surrounding a match, with line wrapping flattened."""
    left = max(
        text.rfind(". ", 0, start),
        text.rfind("! ", 0, start),
        text.rfind("? ", 0, start),
        text.rfind("\n\n", 0, start),
    )
    left = 0 if left == -1 else left + 1

    right = len(text)
    for term in (". ", "! ", "? ", "\n\n"):
        hit = text.find(term, end)
        if hit != -1:
            right = min(right, hit + 1)

    return " ".join(text[left:right].split())


def find_in_facts(facts_text, needle):
    """Locate a needle in the raw facts JSON so we can cite a line."""
    for i, line in enumerate(facts_text.splitlines(), start=1):
        if needle in line:
            return i, line
    return None, None


def numbers_in(s):
    """Every number in a string, as floats."""
    return [float(m.group(0).replace(",", "")) for m in NUMBER_RE.finditer(s)]


def is_number(value):
    """A real number. Booleans are ints in Python and are not numbers here."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_integer(value):
    """A whole number of rows. Booleans are ints in Python and are not."""
    return isinstance(value, int) and not isinstance(value, bool)


def harvest_numbers(node, sink):
    """Walk the facts JSON and collect every number, including those inside
    strings (so "17 meetings" and 17 both count)."""
    if isinstance(node, bool):
        return
    if isinstance(node, (int, float)):
        sink.add(float(node))
    elif isinstance(node, str):
        sink.update(numbers_in(node))
    elif isinstance(node, dict):
        for value in node.values():
            harvest_numbers(value, sink)
    elif isinstance(node, list):
        for item in node:
            harvest_numbers(item, sink)


def facts_entries(facts):
    """Every attributable entry in the facts file, as (label, subject, values).

    One entry per rate, per total, per ranked table header, and one per ranked
    table row. A row's values belong to the row alone and are not folded into
    the parent table, so a figure traces to the line it came from rather than
    to the whole table.
    """
    entries = []

    for i, rate in enumerate(facts.get("rates") or []):
        values = set()
        harvest_numbers(rate, values)
        subject = rate.get("subject", "") if isinstance(rate, dict) else ""
        entries.append((f"rates[{i}]", str(subject), values))

    for i, total in enumerate(facts.get("totals") or []):
        values = set()
        harvest_numbers(total, values)
        subject = total.get("subject", "") if isinstance(total, dict) else ""
        entries.append((f"totals[{i}]", str(subject), values))

    # A base rate sources figures like any other entry. It has to, because the
    # sentence CHECK 6 governs is usually the one that prints the trial count:
    # "no votes in 6 meetings" cites the entry's own trials, and without this
    # the figure the check demands would orphan under CHECK 3.
    for i, entry in enumerate(facts.get("base_rates") or []):
        values = set()
        harvest_numbers(entry, values)
        subject = entry.get("subject", "") if isinstance(entry, dict) else ""
        entries.append((f"base_rates[{i}]", str(subject), values))

    # A superlative entry sources figures like any other. It has to, because
    # CHECK 4 makes a chosen threshold disclose itself in the prose, and a
    # figure the copy is required to print must have somewhere to come from.
    for i, claim in enumerate(facts.get("superlatives") or []):
        if not isinstance(claim, dict):
            continue

        subject = str(claim.get("subject", ""))
        header = {k: v for k, v in claim.items() if k != "top5"}
        values = set()
        harvest_numbers(header, values)
        entries.append((f"superlatives[{i}]", subject, values))

        for j, row in enumerate(claim.get("top5") or []):
            values = set()
            harvest_numbers(row, values)
            name = str(row.get("name", "")) if isinstance(row, dict) else ""
            entries.append((
                f"superlatives[{i}].top5[{j}]",
                f"{name} {subject}".strip(),
                values,
            ))

    for i, table in enumerate(facts.get("ranked_tables") or []):
        if not isinstance(table, dict):
            continue

        subject = str(table.get("subject", ""))
        header = {k: v for k, v in table.items() if k != "rows"}
        values = set()
        harvest_numbers(header, values)
        entries.append((f"ranked_tables[{i}]", subject, values))

        rows = table.get("rows")
        if not isinstance(rows, list):
            continue

        for j, row in enumerate(rows):
            values = set()
            harvest_numbers(row, values)
            label = ""
            if isinstance(row, dict):
                for key in ROW_LABEL_KEYS:
                    if key in row:
                        label = str(row[key])
                        break
            entries.append((
                f"ranked_tables[{i}].rows[{j}]",
                f"{label} {subject}".strip(),
                values,
            ))

    return entries


def claim_values(facts):
    """Every number each superlatives entry carries, keyed by claim_id.

    A claim comment is an explicit statement that a sentence belongs to a claim.
    That is stronger evidence than a capitalised word appearing in both, so a
    figure inside a claim's scope and carried by that claim's entry is
    attributed by declaration rather than by resemblance.
    """
    carried = {}

    for claim in facts.get("superlatives") or []:
        if not isinstance(claim, dict):
            continue
        values = set()
        harvest_numbers(claim, values)
        carried.setdefault(str(claim.get("claim_id", "")), set()).update(values)

    return carried


def subject_tokens(subject):
    """The words in a subject that actually name something."""
    return set(NAME_TOKEN_RE.findall(subject)) - SUBJECT_STOP_TOKENS


def heading_above(text, offset):
    """The nearest markdown heading at or before an offset, without its newline."""
    start = text.rfind("\n#", 0, offset)
    if start == -1:
        if not text.startswith("#"):
            return ""
        start = 0
    else:
        start += 1
    end = text.find("\n", start)
    return text[start:end if end != -1 else len(text)]


def claim_scopes(draft_text):
    """Every claim comment and the span of prose it governs.

    A scope opens at the end of the comment's own line and closes at the first
    sentence terminator after it, so a comment governs one sentence and not the
    section it happens to sit in. A comment therefore belongs immediately above
    the sentence making the claim, not above the block containing it.

    A claim spanning a sentence pair is covered only where no terminator falls
    between the two, which is to say where they are really one sentence. A claim
    that genuinely needs two sentences is written as two comments sharing a
    claim_id, and the scope is their union: every reader of these scopes either
    tests membership across all of them or gathers the ones matching a slug.
    """
    scopes = []

    for comment in CLAIM_COMMENT_RE.finditer(draft_text):
        line_end = draft_text.find("\n", comment.end())
        start = len(draft_text) if line_end == -1 else line_end + 1

        # The same terminators sentence_of breaks on, so a scope and a quoted
        # sentence never disagree about where the sentence ended.
        end = len(draft_text)
        for term in (". ", "! ", "? ", "\n\n"):
            hit = draft_text.find(term, start)
            if hit != -1:
                end = min(end, hit + 1)

        scopes.append((comment.group(1), start, max(start, end)))

    return scopes


def strip_claim_comments(text):
    """The draft with its claim comments removed, for posting."""
    return CLAIM_COMMENT_LINE_RE.sub("", text)


def blank_claim_comments(text):
    """The draft with claim comments blanked to spaces, offsets preserved.

    A comment is scaffolding, not copy, and its slug must not be read as either
    kind of claim: "merrett-adelaide-best-vpg" is not a superlative and the 10
    in "dawson-essendon-lowest-at-10" is not a figure. Offsets survive because
    scopes and line numbers are measured against the same text.
    """
    return CLAIM_COMMENT_RE.sub(lambda m: " " * len(m.group(0)), text)


def is_table_row(line):
    """Whether a line is a markdown table row, which is its own unit of claim."""
    return line.lstrip().startswith("|")


def attribution_context(text, start, end):
    """The text a figure's subject has to appear in for it to be attributed.

    A markdown table row is matched against its own line and nothing else. The
    row label sits on that line, so attribution inside a table is exact and a
    figure swapped between two rows of one table is caught.

    Prose is matched against the sentence plus the nearest heading above it,
    because copy names its subject in the section header and does not repeat it
    in every sentence.
    """
    _, line = line_of(text, start)
    if is_table_row(line):
        return line
    return f"{sentence_of(text, start, end)}\n{heading_above(text, start)}"


def name_carriers(carriers):
    """Name the entries that hold a value, for a failure message."""
    subjects = [subject for _, subject, _ in carriers]
    if len(subjects) <= 3:
        return "; ".join(subjects)
    return f"{subjects[0]}; and {len(subjects) - 1} others"


# ---------------------------------------------------------------- checks

def validate_ranked_tables(ranked):
    """Shape-check every ranked_tables entry.

    Returns a list of problem strings in entry order, empty if all are sound.
    Collects every offence rather than stopping at the first, so one run tells
    the author everything that needs fixing.

    This exists because the mere presence of a ranked table silences a
    superlative. Before it, an entry of {} silenced the check while proving
    nothing at all.
    """
    # Name the real fault before iterating. A bare string enumerates into one
    # phantom problem per character, a bare object into one per key, and a
    # number is not iterable at all.
    if not isinstance(ranked, list):
        return [
            f"ranked_tables must be a list of table objects, got "
            f"{type(ranked).__name__}."
        ]

    problems = []

    for i, entry in enumerate(ranked):
        where = f"ranked_tables[{i}]"

        if not isinstance(entry, dict):
            problems.append(
                f"{where}: must be an object carrying "
                f"{', '.join(RANKED_TABLE_FIELDS)}, got "
                f"{type(entry).__name__}."
            )
            continue

        # subject and window are the reviewer's only handle on what was
        # ranked and over what period, so neither may be blank.
        for key in ("subject", "window"):
            if key not in entry:
                problems.append(f'{where}: missing key "{key}".')
            elif not isinstance(entry[key], str):
                problems.append(
                    f'{where}: "{key}" must be a non-empty string, got '
                    f"{type(entry[key]).__name__}."
                )
            elif not entry[key].strip():
                problems.append(f'{where}: "{key}" is an empty string.')

        if "rows" not in entry:
            problems.append(f'{where}: missing key "rows".')
        else:
            rows = entry["rows"]
            if not isinstance(rows, list):
                problems.append(
                    f'{where}: "rows" must be a list, got '
                    f"{type(rows).__name__}."
                )
            elif len(rows) < MIN_RANKED_ROWS:
                plural = "row" if len(rows) == 1 else "rows"
                problems.append(
                    f'{where}: "rows" has {len(rows)} {plural}, and a ranking '
                    f"needs at least {MIN_RANKED_ROWS}."
                )

    return problems


def validate_totals(totals):
    """Shape-check every totals entry.

    Returns a list of problem strings in entry order, empty if all are sound.
    Collects every offence rather than stopping at the first, so one run tells
    the author everything that needs fixing.

    A total exists so a rate has something to be read against: block 8c's career
    games, polls and votes sit here while votes per game sits in rates. The slot
    earns its keep only if the two stay separate, which is why a denominator
    appearing on a total is fatal rather than ignored.
    """
    # Name the real fault before iterating, for the same reason
    # validate_ranked_tables does: a bare string enumerates into one phantom
    # problem per character, and a number is not iterable at all.
    if not isinstance(totals, list):
        return [
            f"totals must be a list of total objects, got "
            f"{type(totals).__name__}."
        ]

    problems = []

    for i, entry in enumerate(totals):
        where = f"totals[{i}]"

        if not isinstance(entry, dict):
            problems.append(
                f"{where}: must be an object carrying "
                f"{', '.join(TOTALS_FIELDS)}, got {type(entry).__name__}."
            )
            continue

        missing = [
            f for f in TOTALS_FIELDS if f not in entry or entry[f] in (None, "")
        ]
        if missing:
            problems.append(
                f"{where}: missing or empty required field(s): "
                f"{', '.join(missing)}."
            )

        smuggled = [f for f in TOTALS_FORBIDDEN_FIELDS if f in entry]
        if smuggled:
            problems.append(
                f"{where}: carries {', '.join(smuggled)}. A total is a raw "
                f"count and has no denominator. A figure that needs one is a "
                f"rate and belongs in rates, where the denominator checks can "
                f"see it."
            )

    return problems


def validate_superlatives(supers):
    """Shape-check every superlatives entry.

    Returns a list of problem strings in entry order, empty if all are sound.
    Collects every offence rather than stopping at the first, so one run tells
    the author everything that needs fixing.
    """
    if not isinstance(supers, list):
        return [
            f"superlatives must be a list of claim objects, got "
            f"{type(supers).__name__}."
        ]

    problems = []

    for i, entry in enumerate(supers):
        where = f"superlatives[{i}]"

        if not isinstance(entry, dict):
            problems.append(
                f"{where}: must be an object carrying "
                f"{', '.join(SUPERLATIVE_FIELDS)}, got {type(entry).__name__}."
            )
            continue

        missing = [
            f
            for f in SUPERLATIVE_FIELDS
            if f not in entry
            or entry[f] is None
            or (isinstance(entry[f], str) and not entry[f].strip())
        ]
        if missing:
            problems.append(
                f"{where}: missing or empty required field(s): "
                f"{', '.join(missing)}."
            )

        # A survival flag read from a string is always truthy, so "false" would
        # silently report that the claim held.
        for key in ("survives_stricter", "survives_looser",
                    "threshold_chosen_to_fit", "at_set_ceiling"):
            if key in entry and not isinstance(entry[key], bool):
                problems.append(
                    f'{where}: "{key}" must be true or false, got '
                    f"{type(entry[key]).__name__}."
                )

        # Rank 1 at the ceiling cannot be dislodged by moving the threshold,
        # because there is nothing above it to move to. An entry claiming the
        # ceiling and a failed survival is describing two different rankings.
        if entry.get("at_set_ceiling") is True:
            broken = [
                key
                for key in ("survives_stricter", "survives_looser")
                if entry.get(key) is False
            ]
            if broken:
                problems.append(
                    f"{where}: at_set_ceiling is true but "
                    f"{' and '.join(broken)} "
                    f"{'is' if len(broken) == 1 else 'are'} false. A rank 1 at "
                    f"the maximum attainable value survives every threshold, so "
                    f"either the ceiling claim or the survival flag is wrong."
                )

        if "gap_to_rank_2" in entry and not is_number(entry["gap_to_rank_2"]):
            problems.append(
                f'{where}: "gap_to_rank_2" must be a number, got '
                f"{type(entry['gap_to_rank_2']).__name__}."
            )

        # threshold is compared against the prose when the claim admits its
        # threshold was chosen, so it has to be a figure rather than prose.
        if "threshold" in entry and not is_number(entry["threshold"]):
            problems.append(
                f'{where}: "threshold" must be a number, got '
                f"{type(entry['threshold']).__name__}."
            )

        set_size = entry.get("set_size")
        set_size_ok = isinstance(set_size, int) and not isinstance(set_size, bool)
        if "set_size" in entry and not set_size_ok:
            problems.append(
                f'{where}: "set_size" must be an integer, got '
                f"{type(set_size).__name__}."
            )

        if "top5" not in entry:
            continue

        top5 = entry["top5"]
        if not isinstance(top5, list):
            problems.append(
                f'{where}: "top5" must be a list, got {type(top5).__name__}.'
            )
            continue

        if set_size_ok:
            wanted = set_size if set_size < TOP5_DEPTH else TOP5_DEPTH
            if len(top5) != wanted:
                plural = "row" if len(top5) == 1 else "rows"
                problems.append(
                    f'{where}: "top5" has {len(top5)} {plural}, and a set of '
                    f"{set_size} requires {wanted}."
                )

        for j, row in enumerate(top5):
            if not isinstance(row, dict):
                problems.append(
                    f"{where}: top5[{j}] must be an object carrying "
                    f"{', '.join(TOP5_ROW_FIELDS)}, got {type(row).__name__}."
                )
                continue
            row_missing = [
                f
                for f in TOP5_ROW_FIELDS
                if f not in row
                or row[f] is None
                or (isinstance(row[f], str) and not row[f].strip())
            ]
            if row_missing:
                problems.append(
                    f"{where}: top5[{j}] missing or empty field(s): "
                    f"{', '.join(row_missing)}."
                )

        # The gap is the whole point of declaring rank 2, so it is checked
        # against the rows rather than taken on trust. A declared gap that
        # disagrees with the table it was drawn from is the same defect as a
        # window describing a population the rows do not hold: a slot in the
        # schema exists to be verified, not believed.
        top_two = top5[:2]
        if (
            is_number(entry.get("gap_to_rank_2"))
            and len(top_two) == 2
            and all(isinstance(row, dict) for row in top_two)
            and all(is_number(row.get("value")) for row in top_two)
        ):
            implied = abs(top_two[0]["value"] - top_two[1]["value"])
            declared = entry["gap_to_rank_2"]
            if abs(implied - declared) > GAP_TOLERANCE:
                problems.append(
                    f'{where}: "gap_to_rank_2" is {declared}, but top5 rank 1 '
                    f"({top_two[0]['value']}) and rank 2 "
                    f"({top_two[1]['value']}) are {implied:g} apart."
                )

    return problems


def report_superlatives(supers):
    """Print the depth behind each superlative, so a reviewer can judge the
    claim without opening the facts file."""
    for i, entry in enumerate(supers):
        print(
            f"SUPER superlatives[{i}]: {entry['subject']} "
            f"| window: {entry['window']} "
            f"| threshold: {entry['threshold']} {entry['threshold_unit']} "
            f"| set: {entry['set_size']} "
            f"| gap to rank 2: {entry['gap_to_rank_2']}"
        )
        if entry.get("at_set_ceiling") is True:
            print(
                f"CEIL  superlatives[{i}]: rank 1 sits at the ceiling of the "
                f"set, the maximum attainable value rather than the highest "
                f"observed, so survives_stricter and survives_looser are "
                f"trivially true and are not evidence for the claim."
            )


def report_ranked_tables(ranked):
    """Print what the superlative was checked against, so a reviewer can judge
    the ranking without opening the facts file."""
    for i, entry in enumerate(ranked):
        rows = len(entry["rows"])
        print(
            f"TABLE ranked_tables[{i}]: {entry['subject']} "
            f"| window: {entry['window']} "
            f"| {rows} rows"
        )


def check_superlative(draft_text, facts, draft_path, facts_path):
    """A superlative claim is a ranking claim. Rank the thing it claims.

    A non-empty ranked_tables used to satisfy this check for a whole draft, so
    eight tables and a ninth unbacked claim passed: the question asked was
    whether a ranking existed somewhere in the file, not whether one ranked the
    thing being claimed. Backing now binds by subject, the exact-string rule
    CHECK 7 uses, so a claim is backed only by an entry about its own subject.

    A claim's own superlatives entry does not back it. That entry is the claim,
    and CHECK 4 already makes it carry its depth; letting it satisfy this check
    too would make the check vacuous for every claim CHECK 4 passes.

    Two cases are left to CHECK 4, which reports them better than this can: a
    superlative token outside every claim scope, and a scope whose claim_id has
    no superlatives entry.
    """
    ranked = facts.get("ranked_tables") or []
    supers = facts.get("superlatives") or []

    # Shape first: an unsound table must not be allowed to silence anything.
    problems = validate_ranked_tables(ranked)
    if problems:
        fail(
            "CHECK 1 ranked_tables shape",
            f"malformed ranked_tables in {facts_path}:\n"
            + "\n".join(f"        {problem}" for problem in problems),
        )

    scannable = blank_claim_comments(draft_text)
    first = SUPERLATIVE_RE.search(scannable)

    # Nothing to rank against at all, which is the whole-draft case: no table
    # exists for any claim to bind to, so subject matching cannot even start.
    if first and not ranked:
        lineno, line = line_of(draft_text, first.start())
        fail(
            "CHECK 1 superlative",
            f'superlative "{first.group(0)}" with no ranked_tables to back '
            f"it.\n"
            f"      sentence: "
            f"{sentence_of(draft_text, first.start(), first.end())}",
            lineno,
            line,
            draft_path,
        )

    scopes = claim_scopes(draft_text)
    by_claim = {}
    for i, entry in enumerate(supers):
        if isinstance(entry, dict):
            by_claim.setdefault(str(entry.get("claim_id", "")), (i, entry))

    for match in SUPERLATIVE_RE.finditer(scannable):
        owned = None
        for slug, start, end in scopes:
            if start <= match.start() < end and slug in by_claim:
                owned = (slug,) + by_claim[slug]
                break
        if owned is None:
            continue

        slug, index, entry = owned
        subject = str(entry.get("subject", ""))
        if not subject:
            continue

        backing = [
            f"{group}[{j}]"
            for group, items in (("ranked_tables", ranked),
                                 ("superlatives", supers))
            for j, other in enumerate(items)
            if isinstance(other, dict)
            and not (group == "superlatives" and j == index)
            and str(other.get("subject", "")) == subject
        ]
        if backing:
            continue

        lineno, line = line_of(draft_text, match.start())
        fail(
            "CHECK 1 unbacked superlative",
            f'superlative "{match.group(0)}" is claimed by "{slug}", whose '
            f'subject is "{subject}", and no ranked_tables or superlatives '
            f"entry carries that subject. A ranking somewhere in the file is "
            f"not a ranking of the thing being claimed. Give the claim a table "
            f"about its own subject, or make the subjects agree if one already "
            f"ranks it.\n"
            f"      sentence: "
            f"{sentence_of(draft_text, match.start(), match.end())}",
            lineno,
            line,
            draft_path,
        )

    if ranked:
        report_ranked_tables(ranked)


def check_denominator(facts, facts_text, facts_path):
    """Every rate must say what it is a rate of, no rate may rest on an
    unavailable denominator, vote rates must use a vote-eligible one, and a
    total must not carry a denominator at all."""
    if "totals" in facts:
        problems = validate_totals(facts["totals"])
        if problems:
            fail(
                "CHECK 2 totals shape",
                f"malformed totals in {facts_path}:\n"
                + "\n".join(f"        {problem}" for problem in problems),
            )

    for i, rate in enumerate(facts.get("rates") or []):
        subject = rate.get("subject", f"rates[{i}]")

        missing = [f for f in RATE_FIELDS if f not in rate or rate[f] in (None, "")]
        if missing:
            lineno, line = find_in_facts(facts_text, str(subject))
            fail(
                "CHECK 2 denominator",
                f'rate "{subject}" is missing required field(s): '
                f"{', '.join(missing)}.",
                lineno,
                line,
                facts_path,
            )

        dtype = rate["denominator_type"]
        if dtype not in DENOMINATOR_TYPES:
            lineno, line = find_in_facts(facts_text, str(dtype))
            fail(
                "CHECK 2 denominator",
                f'rate "{subject}" has denominator_type "{dtype}", which is not '
                f"in the enum ({', '.join(sorted(DENOMINATOR_TYPES))}).",
                lineno,
                line,
                facts_path,
            )

        # 2b. An unavailable denominator is not a denominator. This fires for
        # every rate, vote or not: if the base is unknown the rate is unknown.
        if dtype == "unavailable":
            lineno, line = find_in_facts(facts_text, str(dtype))
            fail(
                "CHECK 2b denominator unavailable",
                f'rate "{subject}" carries denominator_type "unavailable". A '
                f"rate cannot be printed on an unavailable denominator, because "
                f"the figure has no base to be a rate of. State in the copy that "
                f"the denominator is unavailable rather than publish a rate.",
                lineno,
                line,
                facts_path,
            )

        is_vote_rate = "vote" in f"{subject} {rate['denominator']}".lower()
        if is_vote_rate and dtype in NOT_VOTE_ELIGIBLE:
            lineno, line = find_in_facts(facts_text, str(dtype))
            fail(
                "CHECK 2 denominator",
                f'rate "{subject}" is a vote rate but carries denominator_type '
                f'"{dtype}". Vote rates require vote-eligible denominators: a '
                f"player can only poll in games the umpires voted on, so "
                f'"{dtype}" is the wrong base. Use one of '
                f"{', '.join(sorted(VOTE_ELIGIBLE))}.",
                lineno,
                line,
                facts_path,
            )


def check_orphan_numbers(draft_text, facts, draft_path):
    """Every figure in the prose must trace back to a facts entry whose subject
    is named alongside it, not merely to a value sitting somewhere in the file.

    The guarantee this gives is deliberately uneven.

    A table row is strong. It is matched against its own line, where the row
    label lives, so a figure swapped between two rows of the same table fails.

    Prose is weak. It is matched against the sentence plus the nearest heading,
    so a name in a heading clears every number underneath it: a "Supporting
    figures." paragraph listing twenty figures is attributed by its section
    header alone. That laundering path is deliberate. Requiring the subject in
    the sentence itself failed 22 correct figures on an already-verified draft,
    because copy names its subject once and then writes normally.
    """
    entries = facts_entries(facts)
    scopes = claim_scopes(draft_text)
    carried_by_claim = claim_values(facts)

    # The round is a fact about the fixture, not a claim needing a source, and
    # a draft cites both the AFL's number and AFLTables' raw one.
    exempt = set()
    for key in ("round", "raw_round"):
        value = facts.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            exempt.add(float(value))

    # Hashtag digits are decoration and claim-comment digits are scaffolding.
    # Neither is a claim, so blank both before scanning.
    scannable = HASHTAG_RE.sub(
        lambda m: " " * len(m.group(0)), blank_claim_comments(draft_text)
    )

    for match in NUMBER_RE.finditer(scannable):
        value = float(match.group(0).replace(",", ""))

        if value in exempt:
            continue
        if value.is_integer() and YEAR_MIN <= value <= YEAR_MAX:
            continue

        lineno, line = line_of(draft_text, match.start())
        carriers = [e for e in entries if value in e[2]]

        # A markdown table holds no blank line, so sentence_of returns the whole
        # table for a figure inside one, twenty rows wide to report one cell.
        # There the row is the claim, and fail() already echoes it with its file
        # and line number, so the quote is left to that rather than repeated.
        quoted = (
            ""
            if is_table_row(line)
            else "\n      sentence: "
            + sentence_of(draft_text, match.start(), match.end())
        )

        if not carriers:
            fail(
                "CHECK 3 orphan numbers",
                f'unsourced figure "{match.group(0)}": not a value in the facts '
                f"file, not the round, not in a hashtag, not a year "
                f"{YEAR_MIN}-{YEAR_MAX}.{quoted}",
                lineno,
                line,
                draft_path,
            )

        # Attribution by declaration: the draft has said, with a claim comment,
        # that this sentence belongs to this claim. A figure the claim carries
        # needs no name to repeat itself inside its own scope.
        if any(
            start <= match.start() < end
            and value in carried_by_claim.get(slug, ())
            for slug, start, end in scopes
        ):
            continue

        context = attribution_context(draft_text, match.start(), match.end())
        if any(
            token in context
            for _, subject, _ in carriers
            for token in subject_tokens(subject)
        ):
            continue

        fail(
            "CHECK 3 misattributed number",
            f'figure "{match.group(0)}" is in the facts file, but nothing here '
            f"names what it belongs to. A value existing somewhere in the facts "
            f"is not a source for the sentence it was printed in."
            f"{quoted}\n"
            f"      carried by: {name_carriers(carriers)}",
            lineno,
            line,
            draft_path,
        )


def check_superlative_depth(draft_text, facts, facts_text, draft_path, facts_path):
    """A superlative is a ranking claim, and a ranking claim has a depth.

    CHECK 1 asks whether a ranking exists. This asks what the ranking is worth:
    how large the set was, how far clear rank 1 is of rank 2, and whether the
    threshold that defines the set survives being moved in either direction. A
    claim that is true only at one threshold is a claim about the threshold.

    Where the entry admits the threshold was chosen to fit, the copy has to say
    so: both the threshold and the size of the set it produced must appear in
    the prose, so the reader sees the claim was cut to shape.

    claim_id binds an entry to the prose it governs. Binding runs both ways: an
    entry with no claim comment is a claim the copy never makes, a comment with
    no entry is a claim with no depth behind it, and a superlative token sitting
    outside every scope is a claim nobody declared at all. That last case is why
    omitting the superlatives field entirely no longer passes.
    """
    scannable = blank_claim_comments(draft_text)
    if not SUPERLATIVE_RE.search(scannable):
        return

    supers = facts.get("superlatives") or []

    problems = validate_superlatives(supers)
    if problems:
        fail(
            "CHECK 4 superlative depth",
            f"malformed superlatives in {facts_path}:\n"
            + "\n".join(f"        {problem}" for problem in problems),
        )

    scopes = claim_scopes(draft_text)
    declared = [str(entry["claim_id"]) for entry in supers]
    bound = [slug for slug, _, _ in scopes]

    unbound = [slug for slug in declared if slug not in set(bound)]
    undeclared = [slug for slug in dict.fromkeys(bound) if slug not in set(declared)]
    if unbound or undeclared:
        lines = [
            f'"{slug}" is declared in the facts but never appears in the draft '
            f"as <!-- claim: {slug} -->."
            for slug in unbound
        ] + [
            f'<!-- claim: {slug} --> governs prose in the draft, but no '
            f"superlatives entry declares that claim_id."
            for slug in undeclared
        ]
        fail(
            "CHECK 4 claim binding",
            f"the facts and the draft disagree about which claims exist:\n"
            + "\n".join(f"        {line}" for line in lines),
        )

    # A superlative outside every scope is the gap that used to let a draft
    # declare no superlatives at all and pass: nothing forced the claim to
    # carry its depth, because nothing tied the claim to the sentence.
    for match in SUPERLATIVE_RE.finditer(scannable):
        if any(start <= match.start() < end for _, start, end in scopes):
            continue
        lineno, line = line_of(draft_text, match.start())
        fail(
            "CHECK 4 unclaimed superlative",
            f'superlative "{match.group(0)}" sits outside every claim scope, so '
            f"no superlatives entry carries its depth. Open a scope above it "
            f"with <!-- claim: slug --> and declare the matching entry.\n"
            f"      sentence: "
            f"{sentence_of(draft_text, match.start(), match.end())}",
            lineno,
            line,
            draft_path,
        )

    for i, entry in enumerate(supers):
        if not entry["threshold_chosen_to_fit"]:
            continue

        # Scoped, not document-wide. A threshold printed in another section is
        # not a disclosure to the reader of this claim.
        slug = str(entry["claim_id"])
        in_scope = set()
        for scope_slug, start, end in scopes:
            if scope_slug == slug:
                in_scope.update(numbers_in(scannable[start:end]))

        undisclosed = [
            f"{label} ({value})"
            for label, value in (
                ("threshold", entry["threshold"]),
                ("set_size", entry["set_size"]),
            )
            if float(value) not in in_scope
        ]
        if not undisclosed:
            continue

        lineno, line = find_in_facts(facts_text, str(entry["claim_id"]))
        fail(
            "CHECK 4 undisclosed threshold",
            f'superlatives[{i}] "{entry["claim_id"]}" declares '
            f"threshold_chosen_to_fit, but its scope does not disclose "
            f"{', '.join(undisclosed)}. A superlative that holds only at a "
            f"threshold picked for it must print that threshold and the size "
            f"of the set it produced, or the reader cannot see the claim was "
            f"cut to shape.",
            lineno,
            line,
            facts_path,
        )

    report_superlatives(supers)


def needs_finals_reconciliation(entry):
    """Whether an entry has to account for what its finals filter did.

    Either it rests on matches between two clubs, where a final is a match that
    either counts or does not and the answer moves the figure, or its window
    says something about finals, in which case a decision was taken and the
    arithmetic behind it has to be shown.
    """
    if not isinstance(entry, dict):
        return False
    if entry.get("denominator_type") == "matches_between_clubs":
        return True
    window = entry.get("window")
    return isinstance(window, str) and bool(FINALS_RE.search(window))


def validate_finals_reconciliation(facts):
    """Check every finals decision against its own arithmetic.

    Returns a list of problem strings, empty if all reconcile. The identity
    exists because a filter can drop rows it never meant to touch and still
    report an honest-looking zero: a season-to-max-round map built from a file
    that started a year late mapped 2006 to nothing, so every 2006 row compared
    false in both directions and vanished. 24 meetings went in, 23 came out, and
    the run reported no finals excluded. Nothing in the output was wrong on its
    face. Only the arithmetic disagreed, and only because it was checked.
    """
    problems = []

    for group in ("rates", "totals", "ranked_tables", "superlatives"):
        for i, entry in enumerate(facts.get(group) or []):
            if not needs_finals_reconciliation(entry):
                continue

            where = f"{group}[{i}]"

            missing = [f for f in FINALS_FIELDS if f not in entry]
            if missing:
                problems.append(
                    f"{where}: states a finals filter but does not reconcile "
                    f"it, missing {', '.join(missing)}."
                )
                continue

            bad = [f for f in FINALS_FIELDS if not is_integer(entry[f])]
            if bad:
                problems.append(
                    f"{where}: "
                    + ", ".join(
                        f'"{f}" must be an integer number of rows, got '
                        f"{type(entry[f]).__name__}"
                        for f in bad
                    )
                    + "."
                )
                continue

            rows_in, excluded, rows_out = (entry[f] for f in FINALS_FIELDS)
            unaccounted = (rows_in - excluded) - rows_out
            if unaccounted:
                problems.append(
                    f"{where}: rows_in {rows_in} minus finals_excluded "
                    f"{excluded} is {rows_in - excluded}, but rows_out is "
                    f"{rows_out}. {abs(unaccounted)} row(s) "
                    f"{'left' if unaccounted > 0 else 'entered'} the population "
                    f"without being counted as finals, which is what a silently "
                    f"dropped season looks like."
                )

    return problems


def check_finals_reconciliation(facts, facts_path):
    """Finals exclusion is right for rates and wrong for counts, so a run has
    to say which it did and prove the rows add up either way."""
    problems = validate_finals_reconciliation(facts)
    if problems:
        fail(
            "CHECK 5 finals reconciliation",
            f"unreconciled finals filter in {facts_path}:\n"
            + "\n".join(f"        {problem}" for problem in problems),
        )


def validate_base_rates(rates):
    """Shape-check every base_rates entry, and recompute the ones that can be.

    Returns a list of problem strings in entry order, empty if all are sound,
    the same collect-everything contract validate_superlatives keeps.

    Only the zero case is recomputed. At observed_count 0 the two readings of
    "how unlikely was this" agree, because P(X = 0) and P(X <= 0) are the same
    number, (1 - base_rate) ** trials, so there is one answer to check against.
    Above zero they diverge, an exact count and a tail are different figures,
    and the entry does not say which one it holds. A gate cannot verify a
    number whose definition it would have to guess, so it does not pretend to:
    non-zero entries are still shape-checked and still face the ceiling, but
    their p_observed is taken on trust and the reviewer is told the figure by
    report_base_rates rather than told it is correct.
    """
    if not isinstance(rates, list):
        return [
            f"base_rates must be a list of claim objects, got "
            f"{type(rates).__name__}."
        ]

    problems = []

    for i, entry in enumerate(rates):
        where = f"base_rates[{i}]"

        if not isinstance(entry, dict):
            problems.append(
                f"{where}: must be an object carrying "
                f"{', '.join(BASE_RATE_FIELDS)}, got {type(entry).__name__}."
            )
            continue

        missing = [
            f
            for f in BASE_RATE_FIELDS
            if f not in entry
            or entry[f] is None
            or (isinstance(entry[f], str) and not entry[f].strip())
        ]
        if missing:
            problems.append(
                f"{where}: missing or empty required field(s): "
                f"{', '.join(missing)}."
            )

        # A rate written as a percentage is how a probability leaves [0, 1]:
        # 12 meant as 12% raised to any power is astronomical, and an absence
        # would read as miraculous rather than routine.
        for key in ("base_rate", "p_observed"):
            if key not in entry:
                continue
            if not is_number(entry[key]):
                problems.append(
                    f'{where}: "{key}" must be a number between 0 and 1, got '
                    f"{type(entry[key]).__name__}."
                )
            elif not 0 <= entry[key] <= 1:
                problems.append(
                    f'{where}: "{key}" is {entry[key]}, which is not a '
                    f"probability. Give a proportion between 0 and 1 rather "
                    f"than a percentage."
                )

        for key in ("trials", "observed_count"):
            if key in entry and not is_integer(entry[key]):
                problems.append(
                    f'{where}: "{key}" must be a whole count, got '
                    f"{type(entry[key]).__name__}."
                )

        # The declared probability is checked against the two numbers it was
        # computed from, the way gap_to_rank_2 is checked against the rows it
        # was drawn from. A slot in the schema exists to be verified, not
        # believed, and a p_observed that disagrees with its own base rate is
        # a figure carried over from a different window.
        if (
            is_number(entry.get("base_rate"))
            and is_number(entry.get("p_observed"))
            and is_integer(entry.get("trials"))
            and is_integer(entry.get("observed_count"))
            and 0 <= entry["base_rate"] <= 1
            and entry["trials"] >= 0
            and entry["observed_count"] == 0
        ):
            implied = (1 - entry["base_rate"]) ** entry["trials"]
            declared = entry["p_observed"]
            if abs(implied - declared) > P_OBSERVED_TOLERANCE:
                problems.append(
                    f'{where}: "p_observed" is {declared}, but a base rate of '
                    f"{entry['base_rate']} over {entry['trials']} trial(s) "
                    f"implies {implied:.4g}."
                )

    return problems


def report_base_rates(rates):
    """Print the arithmetic behind each absence, so a reviewer can judge the
    angle without opening the facts file."""
    for i, entry in enumerate(rates):
        print(
            f"BASE  base_rates[{i}]: {entry['subject']} "
            f"| event: {entry['event']} "
            f"| base rate: {entry['base_rate']} "
            f"over {entry['base_rate_window']} "
            f"| observed {entry['observed_count']} in {entry['trials']} "
            f"| p: {entry['p_observed']}"
        )


def check_base_rate(draft_text, facts, facts_text, draft_path, facts_path):
    """A claim that something has not happened is a claim about a probability.

    "Never", "yet to", "drought" all assert that a record is quiet, and none of
    them says whether the quiet is surprising. That depends entirely on how
    often the thing happens and how many chances there were: a player who polls
    in one game in twenty and has not polled in four meetings has done nothing
    at all, because silence was the overwhelmingly likely outcome. The claim is
    true and it is not an angle.

    So an absence token must sit inside a claim scope, as a superlative must
    under CHECK 4, and the claim it names must carry the arithmetic: the base
    rate, the window that rate was measured over, the number of chances, what
    was observed, and the probability of seeing that little. Where the
    probability is at or above the ceiling the draft is stopped, because the
    record predicted the silence and the sentence is describing the base rate
    rather than the player.
    """
    scannable = blank_claim_comments(draft_text)
    if not ABSENCE_RE.search(scannable):
        return

    rates = facts.get("base_rates") or []

    problems = validate_base_rates(rates)
    if problems:
        fail(
            "CHECK 6 base rate",
            f"malformed base_rates in {facts_path}:\n"
            + "\n".join(f"        {problem}" for problem in problems),
        )

    scopes = claim_scopes(draft_text)
    declared = {str(entry["claim_id"]) for entry in rates}

    for match in ABSENCE_RE.finditer(scannable):
        owners = [
            slug for slug, start, end in scopes if start <= match.start() < end
        ]
        lineno, line = line_of(draft_text, match.start())
        quoted = sentence_of(draft_text, match.start(), match.end())

        if not owners:
            fail(
                "CHECK 6 unclaimed absence",
                f'"{match.group(0)}" asserts that something has not happened, '
                f"but sits outside every claim scope, so no base_rates entry "
                f"carries the probability that it would not have. Open a scope "
                f"above it with <!-- claim: slug --> and declare the matching "
                f"entry.\n"
                f"      sentence: {quoted}",
                lineno,
                line,
                draft_path,
            )

        if not any(slug in declared for slug in owners):
            named = ", ".join(f'"{slug}"' for slug in dict.fromkeys(owners))
            fail(
                "CHECK 6 missing base rate",
                f'"{match.group(0)}" is governed by {named}, but no base_rates '
                f"entry declares that claim_id. An absence with no base rate "
                f"behind it is a claim nobody has checked against how often the "
                f"thing happens.\n"
                f"      sentence: {quoted}",
                lineno,
                line,
                draft_path,
            )

    for i, entry in enumerate(rates):
        if entry["p_observed"] < P_OBSERVED_CEILING:
            continue
        lineno, line = find_in_facts(facts_text, str(entry["claim_id"]))
        fail(
            "CHECK 6 unremarkable absence",
            f'base_rates[{i}] "{entry["claim_id"]}": {entry["subject"]} has a '
            f"p_observed of {entry['p_observed']}, at or above "
            f"{P_OBSERVED_CEILING}. At a base rate of {entry['base_rate']} over "
            f"{entry['trials']} chance(s), observing {entry['observed_count']} "
            f"is the most likely outcome, not a departure from it. An absence "
            f"that is the most likely outcome is not an angle: the sentence is "
            f"describing the base rate rather than the subject.",
            lineno,
            line,
            facts_path,
        )

    report_base_rates(rates)


def validate_club_splits(entries):
    """Shape-check every club_splits entry and reconcile its splits.

    Returns a list of problem strings in entry order, empty if all are sound.

    Where the entry declares a total for rows, polls or votes, the splits must
    sum to it. This is the identity CHECK 5 applies to a finals filter, aimed
    at the other way a population goes missing: a career record broken across
    clubs loses a club silently, and the remaining split still looks like a
    complete record because nothing in it says what it is a part of. Each total
    is optional and each one present is checked, so an entry can reconcile the
    meetings it is sure of without inventing a vote count it never derived.
    """
    if not isinstance(entries, list):
        return [
            f"club_splits must be a list of split objects, got "
            f"{type(entries).__name__}."
        ]

    problems = []

    for i, entry in enumerate(entries):
        where = f"club_splits[{i}]"

        if not isinstance(entry, dict):
            problems.append(
                f"{where}: must be an object carrying "
                f"{', '.join(CLUB_SPLIT_FIELDS)}, got {type(entry).__name__}."
            )
            continue

        missing = [
            f
            for f in CLUB_SPLIT_FIELDS
            if f not in entry
            or entry[f] is None
            or (isinstance(entry[f], str) and not entry[f].strip())
        ]
        if missing:
            problems.append(
                f"{where}: missing or empty required field(s): "
                f"{', '.join(missing)}."
            )

        splits = entry.get("splits")
        if not isinstance(splits, list):
            if "splits" in entry:
                problems.append(
                    f'{where}: "splits" must be a list of per-club objects, '
                    f"got {type(splits).__name__}."
                )
            continue

        if not splits:
            problems.append(
                f'{where}: "splits" is empty. A club split with no clubs in it '
                f"is not a split."
            )
            continue

        sound = True
        for j, split in enumerate(splits):
            if not isinstance(split, dict):
                problems.append(
                    f"{where}: splits[{j}] must be an object carrying "
                    f"{', '.join(SPLIT_ROW_FIELDS)}, got "
                    f"{type(split).__name__}."
                )
                sound = False
                continue

            split_missing = [
                f
                for f in SPLIT_ROW_FIELDS
                if f not in split
                or split[f] is None
                or (isinstance(split[f], str) and not split[f].strip())
            ]
            if split_missing:
                problems.append(
                    f"{where}: splits[{j}] missing or empty field(s): "
                    f"{', '.join(split_missing)}."
                )
                sound = False

            for key in ("rows", "polls", "votes"):
                if key in split and not is_integer(split[key]):
                    problems.append(
                        f'{where}: splits[{j}] "{key}" must be a whole count, '
                        f"got {type(split[key]).__name__}."
                    )
                    sound = False

        if not sound:
            continue

        for key in SPLIT_TOTAL_FIELDS:
            if key not in entry:
                continue
            if not is_integer(entry[key]):
                problems.append(
                    f'{where}: "{key}" must be a whole count, got '
                    f"{type(entry[key]).__name__}."
                )
                continue
            summed = sum(split[key] for split in splits)
            if summed != entry[key]:
                clubs = ", ".join(
                    f"{split['club']} {split[key]}" for split in splits
                )
                problems.append(
                    f'{where}: "{key}" is {entry[key]}, but the splits sum to '
                    f"{summed} ({clubs}). A split that does not add up to its "
                    f"own total has lost a club or double-counted one."
                )

    return problems


def report_club_splits(entries):
    """Print each club split, so a reviewer can see a career record broken
    across clubs without opening the facts file."""
    for i, entry in enumerate(entries):
        shown = " | ".join(
            f"{split['club']}: {split['rows']} rows, {split['polls']} polls, "
            f"{split['votes']} votes"
            for split in entry["splits"]
        )
        print(f"SPLIT club_splits[{i}]: {entry['subject']} | {shown}")


def check_club_scope(facts, facts_text, facts_path):
    """A record earned at two clubs has to say so wherever it is used.

    A player who changed clubs carries a career record assembled from both, and
    a window that names only the current club describes a different population
    than the figure was computed over. The record is still true and still
    usable; what it cannot do is appear under a window that quietly excludes
    half of where it came from.

    So any subject split across more than one club must have every one of those
    clubs named in the window of every ranked_tables and superlatives entry
    sharing that subject. Subjects are matched exactly, because a subject
    string is the entry's own name for what it is about and a near match is a
    different claim.
    """
    entries = facts.get("club_splits") or []
    if not entries:
        return

    problems = validate_club_splits(entries)
    if problems:
        fail(
            "CHECK 7 club splits",
            f"malformed club_splits in {facts_path}:\n"
            + "\n".join(f"        {problem}" for problem in problems),
        )

    for entry in entries:
        splits = entry["splits"]
        if len(splits) < 2:
            continue

        subject = str(entry["subject"])
        clubs = [str(split["club"]) for split in splits]

        for group in ("ranked_tables", "superlatives"):
            for i, other in enumerate(facts.get(group) or []):
                if not isinstance(other, dict):
                    continue
                if str(other.get("subject", "")) != subject:
                    continue

                window = str(other.get("window") or "")
                unnamed = [c for c in clubs if c.lower() not in window.lower()]
                if not unnamed:
                    continue

                lineno, line = find_in_facts(facts_text, subject)
                fail(
                    "CHECK 7 multi-club scope",
                    f'"{subject}" is split across '
                    f"{', '.join(clubs)}, but {group}[{i}] states a window "
                    f"that never names {', '.join(unnamed)}. A record earned "
                    f"at more than one club is still true and still usable, "
                    f"and the window has to say where it came from or the "
                    f"entry describes a population the figure was not "
                    f"computed over.\n"
                    f"      window: {window}",
                    lineno,
                    line,
                    facts_path,
                )

    report_club_splits(entries)


def normalise_subject(subject):
    """A subject reduced to the form two spellings of one subject share.

    Lowercased, possessives dropped, punctuation replaced by a space, runs of
    whitespace collapsed. Punctuation becomes a space rather than nothing so
    that "vote-eligible" and "vote eligible" agree while "2014-2025" stays two
    numbers.
    """
    text = POSSESSIVE_RE.sub("", subject.lower())
    text = PUNCTUATION_RE.sub(" ", text)
    return WHITESPACE_RE.sub(" ", text).strip()


def harvest_subjects(facts):
    """Every subject string in the facts file, as (label, subject)."""
    found = []

    for group in SUBJECT_GROUPS:
        for i, entry in enumerate(facts.get(group) or []):
            if not isinstance(entry, dict):
                continue
            subject = entry.get("subject")
            if isinstance(subject, str) and subject.strip():
                found.append((f"{group}[{i}]", subject))

    return found


def check_subject_drift(facts, facts_text, facts_path):
    """Two spellings of one subject are a defect, because subjects bind exactly.

    CHECK 7 reaches a ranked_tables or superlatives entry only when its subject
    matches a club_splits subject character for character. Drift therefore does
    not fail anything on its own: the binding silently does not happen and a
    check that would have fired stays quiet. This catches the drift instead of
    the missed binding, because a missed binding leaves no evidence.

    Normalisation, not name tokens. Comparing the names in two subjects reaches
    further by guessing which entries are about the same thing, and the guess is
    wrong far more often than it is right: across the Essendon v Adelaide facts
    that rule flags 25 of 30 subjects. Six of them are Zach Merrett's, and they
    are a game count, a poll count, a vote count, a rate and two tables, which
    are six quantities that must differ as strings because they measure
    different things. Same player is not same subject. Normalising instead
    compares what the author actually wrote, so it fires only where two
    spellings really do denote one subject.
    """
    seen = {}

    for label, subject in harvest_subjects(facts):
        seen.setdefault(normalise_subject(subject), []).append((label, subject))

    for carriers in seen.values():
        spellings = list(dict.fromkeys(subject for _, subject in carriers))
        if len(spellings) < 2:
            continue

        written = "\n".join(
            f'        {label}: "{subject}"' for label, subject in carriers
        )
        lineno, line = find_in_facts(facts_text, spellings[0])
        fail(
            "CHECK 8 subject drift",
            f"{len(spellings)} spellings of one subject. Subjects bind "
            f"exactly, so these entries read as different subjects and no "
            f"club_splits entry can reach more than one of them. Pick one "
            f"string and use it in every entry about this subject.\n"
            + written,
            lineno,
            line,
            facts_path,
        )


# ---------------------------------------------------------------- entry

def main(argv):
    # Claim comments are scaffolding for the gate and must never reach a post.
    # There is no generated draft-to-post path to hook: draft_posts.py writes
    # drafts rather than reading them, and posting is a manual copy out of the
    # blockquotes. So the strip is offered here, next to the thing that
    # requires the comments in the first place.
    if len(argv) == 3 and argv[1] == "--strip":
        draft_path = Path(argv[2])
        if not draft_path.is_file():
            print(f"FAIL  draft not found: {draft_path}", file=sys.stderr)
            return 1
        sys.stdout.write(
            strip_claim_comments(draft_path.read_text(encoding="utf-8"))
        )
        return 0

    if len(argv) != 2:
        print(
            "usage: python draft_gate.py [--strip] drafts/<name>.md",
            file=sys.stderr,
        )
        return 2

    draft_path = Path(argv[1])
    if not draft_path.is_file():
        print(f"FAIL  draft not found: {draft_path}")
        return 1

    facts_path = draft_path.with_suffix("").with_suffix(".facts.json")
    if draft_path.suffix == ".md":
        facts_path = draft_path.with_suffix(".facts.json")

    if not facts_path.is_file():
        print("FAIL  missing facts file")
        print(f"      {draft_path} has no sibling {facts_path.name}.")
        print("      Every draft must ship with its facts. No facts, no gate, no post.")
        return 1

    draft_text = draft_path.read_text(encoding="utf-8")
    facts_text = facts_path.read_text(encoding="utf-8")

    try:
        facts = json.loads(facts_text)
    except json.JSONDecodeError as exc:
        print("FAIL  facts file is not valid JSON")
        print(f"      {facts_path}:{exc.lineno}: {exc.msg}")
        return 1

    check_superlative(draft_text, facts, draft_path, facts_path)
    check_denominator(facts, facts_text, facts_path)
    check_orphan_numbers(draft_text, facts, draft_path)
    check_superlative_depth(draft_text, facts, facts_text, draft_path, facts_path)
    check_finals_reconciliation(facts, facts_path)
    check_base_rate(draft_text, facts, facts_text, draft_path, facts_path)
    check_club_scope(facts, facts_text, facts_path)
    check_subject_drift(facts, facts_text, facts_path)

    n_rates = len(facts.get("rates") or [])
    n_totals = len(facts.get("totals") or [])
    n_tables = len(facts.get("ranked_tables") or [])
    n_supers = len(facts.get("superlatives") or [])
    print(
        f"PASS  {draft_path.name}: "
        f"{facts.get('fixture', '?')}, round {facts.get('round', '?')}, "
        f"{n_rates} rate(s), {n_totals} total(s), {n_tables} ranked table(s), "
        f"{n_supers} superlative(s), "
        f"{len(facts.get('source_files') or [])} source file(s); "
        f"superlative, denominator, orphan-number, depth, finals, base-rate, "
        f"club-scope and subject-drift checks all clear."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
