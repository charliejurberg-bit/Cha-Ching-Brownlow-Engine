"""Draft gate — refuses to let an unsourced post draft through.

Usage:
    python draft_gate.py drafts/<name>.md

Reads the draft and its sibling drafts/<name>.facts.json, then runs three
checks. Any failure prints the offending line and exits 1. All three passing
exits 0 with a one-line summary.

    CHECK 1  superlative   a superlative claim needs a well-formed ranked
                           table behind it
    CHECK 2  denominator   every rate declares what it is a rate *of*
    CHECK 3  orphan number every figure in the prose traces back to the facts
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

RANKED_TABLE_FIELDS = ("subject", "window", "rows")

# A superlative is a claim about a set, and one row does not establish a
# ranking. Two is the floor the gate can defend: it cannot know the true size
# of the set, so it must not demand more.
MIN_RANKED_ROWS = 2

SUPERLATIVES = ("only", "no other", "best", "worst", "highest", "lowest")

YEAR_MIN, YEAR_MAX = 1990, 2026

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

    pattern = re.compile(
        "|".join(rf"\b{w.replace(' ', r'\s+')}\b" for w in SUPERLATIVES),
        re.IGNORECASE,
    )
    match = pattern.search(draft_text)
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
    unavailable denominator, and vote rates must use a vote-eligible one."""
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
    """Every figure in the prose must trace back to the facts file, the round,
    a hashtag, or be a plain year."""
    sourced = set()
    harvest_numbers(facts, sourced)

    rnd = facts.get("round")
    if isinstance(rnd, (int, float)) and not isinstance(rnd, bool):
        sourced.add(float(rnd))

    # Hashtag digits are decoration, not claims — blank them before scanning.
    scannable = HASHTAG_RE.sub(lambda m: " " * len(m.group(0)), draft_text)

    for match in NUMBER_RE.finditer(scannable):
        value = float(match.group(0).replace(",", ""))

        if value in sourced:
            continue
        if value.is_integer() and YEAR_MIN <= value <= YEAR_MAX:
            continue

        lineno, line = line_of(draft_text, match.start())
        sentence = sentence_of(draft_text, match.start(), match.end())
        fail(
            "CHECK 3 orphan numbers",
            f'unsourced figure "{match.group(0)}": not a value in the facts '
            f"file, not the round, not in a hashtag, not a year "
            f"{YEAR_MIN}-{YEAR_MAX}.\n"
            f"      sentence: {sentence}",
            lineno,
            line,
            draft_path,
        )


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

    n_rates = len(facts.get("rates") or [])
    n_tables = len(facts.get("ranked_tables") or [])
    print(
        f"PASS  {draft_path.name}: "
        f"{facts.get('fixture', '?')}, round {facts.get('round', '?')}, "
        f"{n_rates} rate(s), {n_tables} ranked table(s), "
        f"{len(facts.get('source_files') or [])} source file(s); "
        f"superlative, denominator and orphan-number checks all clear."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
