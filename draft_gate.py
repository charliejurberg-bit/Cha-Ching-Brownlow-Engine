"""Draft gate — refuses to let an unsourced post draft through.

Usage:
    python draft_gate.py drafts/<name>.md

Reads the draft and its sibling drafts/<name>.facts.json, then runs three
checks. Any failure prints the offending line and exits 1. All three passing
exits 0 with a one-line summary.

    CHECK 1  superlative   a superlative claim needs a well-formed ranked
                           table behind it
    CHECK 2  denominator   every rate declares what it is a rate *of*, and no
                           total smuggles a denominator in
    CHECK 3  attribution   every figure in the prose traces back to a facts
                           entry whose subject is named alongside it
    CHECK 4  depth         a superlative declares the set it won, how far
                           clear it is, and whether its threshold was chosen
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

SUPERLATIVES = ("only", "no other", "best", "worst", "highest", "lowest")

SUPERLATIVE_RE = re.compile(
    "|".join(rf"\b{w.replace(' ', r'\s+')}\b" for w in SUPERLATIVES),
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
    "threshold_chosen_to_fit",
    "source_file",
)

TOP5_ROW_FIELDS = ("rank", "name", "value")

# Five is the depth a reader needs to see the near misses. A smaller set shows
# all of itself instead, because there is nothing being held back.
TOP5_DEPTH = 5

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
NAME_TOKEN_RE = re.compile(r"\b[A-Z][A-Za-z'\-]{2,}\b")

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
                    "threshold_chosen_to_fit"):
            if key in entry and not isinstance(entry[key], bool):
                problems.append(
                    f'{where}: "{key}" must be true or false, got '
                    f"{type(entry[key]).__name__}."
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
    """A superlative claim is a ranking claim. Rank it or drop it."""
    ranked = facts.get("ranked_tables") or []

    # Shape first: an unsound table must not be allowed to silence anything.
    problems = validate_ranked_tables(ranked)
    if problems:
        fail(
            "CHECK 1 ranked_tables shape",
            f"malformed ranked_tables in {facts_path}:\n"
            + "\n".join(f"        {problem}" for problem in problems),
        )

    if ranked:
        report_ranked_tables(ranked)
        return

    match = SUPERLATIVE_RE.search(draft_text)
    if not match:
        return

    lineno, line = line_of(draft_text, match.start())
    sentence = sentence_of(draft_text, match.start(), match.end())
    fail(
        "CHECK 1 superlative",
        f'superlative "{match.group(0)}" with no ranked_tables to back it.\n'
        f"      sentence: {sentence}",
        lineno,
        line,
        draft_path,
    )


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

    # The round is a fact about the fixture, not a claim needing a source, and
    # a draft cites both the AFL's number and AFLTables' raw one.
    exempt = set()
    for key in ("round", "raw_round"):
        value = facts.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            exempt.add(float(value))

    # Hashtag digits are decoration, not claims — blank them before scanning.
    scannable = HASHTAG_RE.sub(lambda m: " " * len(m.group(0)), draft_text)

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


def check_superlative_depth(draft_text, facts, facts_text, facts_path):
    """A superlative is a ranking claim, and a ranking claim has a depth.

    CHECK 1 asks whether a ranking exists. This asks what the ranking is worth:
    how large the set was, how far clear rank 1 is of rank 2, and whether the
    threshold that defines the set survives being moved in either direction. A
    claim that is true only at one threshold is a claim about the threshold.

    Where the entry admits the threshold was chosen to fit, the copy has to say
    so: both the threshold and the size of the set it produced must appear in
    the prose, so the reader sees the claim was cut to shape.

    claim_id is validated as a field but is not yet bound to a sentence, so a
    draft that declares no superlatives at all still passes here. CHECK 1 owns
    the unbacked case; this check owns the depth of what is declared.
    """
    if not SUPERLATIVE_RE.search(draft_text):
        return

    if "superlatives" not in facts:
        return

    supers = facts["superlatives"]

    problems = validate_superlatives(supers)
    if problems:
        fail(
            "CHECK 4 superlative depth",
            f"malformed superlatives in {facts_path}:\n"
            + "\n".join(f"        {problem}" for problem in problems),
        )

    prose_numbers = set(numbers_in(draft_text))

    for i, entry in enumerate(supers):
        if not entry["threshold_chosen_to_fit"]:
            continue

        undisclosed = [
            f"{label} ({value})"
            for label, value in (
                ("threshold", entry["threshold"]),
                ("set_size", entry["set_size"]),
            )
            if float(value) not in prose_numbers
        ]
        if not undisclosed:
            continue

        lineno, line = find_in_facts(facts_text, str(entry["claim_id"]))
        fail(
            "CHECK 4 undisclosed threshold",
            f'superlatives[{i}] "{entry["claim_id"]}" declares '
            f"threshold_chosen_to_fit, but the prose does not disclose "
            f"{', '.join(undisclosed)}. A superlative that holds only at a "
            f"threshold picked for it must print that threshold and the size "
            f"of the set it produced, or the reader cannot see the claim was "
            f"cut to shape.",
            lineno,
            line,
            facts_path,
        )

    report_superlatives(supers)


# ---------------------------------------------------------------- entry

def main(argv):
    if len(argv) != 2:
        print("usage: python draft_gate.py drafts/<name>.md", file=sys.stderr)
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
    check_superlative_depth(draft_text, facts, facts_text, facts_path)

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
        f"superlative, denominator, orphan-number and depth checks all clear."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
