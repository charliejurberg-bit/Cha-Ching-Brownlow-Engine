# Handover, 2026-08-02 session b

Scope: draft_gate.py went from 4 checks to 8, CHECK 1 was rewritten to bind by
subject, claim binding narrowed to the sentence, and the gate acquired a tracked
regression suite. 10 commits, 5ef1fcb through bd23385, 84 files, 3335
insertions.

Read this alongside fixture_recon_spec.md, which now documents the schema and
block 9. This file carries what the spec does not: what was learned, and what
is still open.

## What shipped

| Commit | What |
|---|---|
| 5ef1fcb | CHECK 5, finals reconciliation |
| acac6a0 | CHECK 3 attribution by claim declaration |
| 88c1cdb | CHECK 6, zero-count base rate |
| a236125 | Note recording the 5ef1fcb / acac6a0 commit-order gap |
| f651bf7 | tests/run_gate_tests.py and 22 fixtures |
| 2d49e07 | CHECK 7, multi-club scope |
| ab3d7cf | CHECK 8, subject drift |
| f5f02d7 | The live Essendon v Adelaide draft as fixture 27 |
| 467eb9e | CHECK 1 rewritten to bind by subject, most and fewest added |
| bd23385 | The meeting-cap claim backed, live subjects reconciled |

Sentence-scoped claim binding landed just before this session in e1d6ab1 and is
load-bearing for everything after it. A claim comment governs from itself to the
first sentence terminator, not to the next heading. Every check that reads a
scope depends on that narrowness. The CHECK 3 attribution path in acac6a0 would
have been unsafe under the old section scope: it clears figures inside a scope,
and a scope that covered a whole tweet block would have cleared every figure in
it.

## Findings

**An absence needs a base rate before it is an angle.** "Never", "yet to",
"drought" all assert that a record is quiet and none of them says whether the
quiet is surprising. That depends only on how often the event happens and how
many chances there were. Four Adelaide claims were drafted and declined on this:
Rachele at p 0.93, Milera at 0.90, Fogarty at 0.78, and only Rankine at 0.46
survived. Three of the four were describing the base rate rather than the
player. CHECK 6 now enforces the same 0.50 line the judgment used, so the
reasoning is in the gate rather than in whoever is drafting that week.

**A filter can drop rows it never meant to touch and still report zero.** The
season-to-max-round map used to separate home and away rounds from finals was
built from fitzroy_stats_all.csv, which starts in 2007. 2006 mapped to nothing,
so every 2006 row compared false in both directions and vanished. 24 meetings
went in, 23 came out, and the run reported 0 finals excluded. Nothing in the
output looked wrong. Only the arithmetic disagreed, and only because it was
checked. This is the sharpest lesson of the session: the failure was invisible
to every check that reads output, and visible only to one that reads the
population going in against the population coming out.

**Same player is not same subject.** CHECK 7 binds club_splits to other entries
by exact subject string, and the obvious way to make that reach further is to
compare the names in two subjects instead. It was measured before it was built:
across the 30 subjects in the Essendon v Adelaide facts, name-token comparison
flags 25. Six are Zach Merrett's, and they are a game count, a poll count, a
vote count, a rate and two tables, which are six quantities that must differ as
strings because they measure different things. The rule treats one player as one
subject, and no facts file with more than one figure per player survives it.
CHECK 8 compares normalised subjects instead, which fires only where two
spellings really do denote one subject.

**A check that asks whether a ranking exists is not asking whether it ranks the
claim.** CHECK 1 returned as soon as ranked_tables was non-empty and well
formed. Read quickly it looks like it does its job: a superlative needs a table,
and here is a table. What it actually asked was whether the author had produced
any ranking at all, anywhere in the file. The Essendon draft carried eight
tables, so every superlative in it was cleared by tables about other players.
Binding by subject, the exact-string rule CHECK 7 already used, is what turns
the question into the one worth asking.

The cost of closing it is worth knowing before the next check is written. Four
of the five superlatives in the draft failed immediately, all for the same
reason: a superlatives subject phrased the claim ("Zach Merrett's best career
votes per game against any opponent") while the table that ranked it phrased the
population ("Zach Merrett career Brownlow votes per vote-eligible game by
opponent"). Both are correct descriptions and neither is wrong; they just are
not the same string. The fix was to make every superlatives subject name the
population and let the claim phrasing live in scale, window and the prose. That
is a real loss: a reader scanning subjects alone can no longer tell a ranking
from a superlative over it, and that is the price of a binding rule strict
enough to be checkable.

**Widening a trigger list finds things, and the first thing it found was real.**
Adding "most" and "fewest" surfaced "the most by anyone currently listed is well
below that" in the meeting-cap section, a ranking claim over a population
nothing in the facts file described. It had been in the draft since it was
written and no check had ever seen it, because the trigger list did not carry
"most" and CHECK 1 was satisfied by the eight unrelated tables. Two independent
gaps had to close before one sentence became visible.

It survived on the numbers: among players listed at Essendon or Adelaide in
2026, the most meetings in this fixture is 14, shared by Taylor Walker and Rory
Laird, against Dustin Fletcher's 22 all time. The computation was validated
before its output was used, by reproducing two figures the draft already
carried, 44 total meetings and the all-time top three. A claim that survives
checking is worth more than one that was never checked, and it now has rt[8] and
sup[4] behind it.

The same widening produced two false positives, both "the most recent meeting",
which is a date. Handled the way zero-vote was, with a negative lookahead. The
pattern recurs often enough to expect it: a trigger word doing different work
inside a fixed compound.

**Uniqueness clearing a number was clause 1 reintroduced.** The original CHECK 3
proposal carried a clause that cleared a figure unconditionally whenever exactly
one facts entry held that value. It reads as obviously safe: one carrier means
no ambiguity about where the number came from, so why demand the subject be
named as well.

It was measured and dropped before it was implemented. One carrier is not the
ambiguous case, it is the checkable case, and the clause exempted precisely the
cleanest instance of misattribution: a figure that traces to exactly one entry
and is printed in a sentence about something else. Unambiguous provenance in the
file is not stated provenance in the sentence. The measurement settled it, since
31 of the 32 unique-carrier numbers in the draft already satisfied the
subject-match rule on their own, so the escape would have bought almost nothing
while removing the check from the one case that needed it.

The finding generalises, and it is the pattern this session kept hitting: an
escape written for convenience clears the case the check exists for. Clause 1 is
the clean example because it was caught before shipping. The heading path in
CHECK 3 is the same shape and was kept, and it is worth being clear-eyed that
the trade there went the other way: it exists because requiring the subject in
the sentence itself failed 22 correct figures, and what it clears is a dense
block of numbers under a heading that names the player, which is exactly the
shape a misattributed figure hides in. It is documented and deliberate rather
than accidental, but it is the widest path in the gate for the same reason
clause 1 would have been. Any future exemption should be measured the way clause
1 was: not by whether it is convenient, but by what it lets through and how
little it buys.

The related thing this session did ship is acac6a0, which clears a figure inside
a claim scope when the claim's own entry carries it. That is attribution by
declaration rather than by uniqueness, and it survives the clause 1 test only
because the declaration is explicit and sentence-scoped: it needs a comment
binding that sentence to a named entry, so the author has stated the provenance
rather than the gate inferring it.

## Still not enforced

Nothing in the gate checks the facts file against the CSVs it claims to come
from. Every check is internal consistency. A facts file whose numbers were
invented wholesale, and whose prose cites them faithfully, passes all 8 checks.
The gate stops a draft from asserting more than its facts support. It cannot
stop the facts from being wrong.

Stripping is manual. `--strip` removes claim comments before posting, and
nothing enforces that it was run. The tracked live fixture is deliberately the
pre-strip form.

club_splits totals are optional. An entry that omits rows, polls and votes skips
reconciliation entirely and only faces the window-naming rule.

CHECK 6 recomputes p_observed only at observed_count zero, where P(X = 0) and
P(X <= 0) agree. Above zero the entry does not say which figure it holds, so the
number is taken on trust.

Subject drift is caught only where two spellings normalise identically. Two
genuinely different phrasings of one subject, "Dawson career votes by opponent"
against "Dawson opponent splits", read as two subjects to CHECK 7 and CHECK 8
sees nothing wrong. Exact binding remains a convention the author has to keep;
CHECK 8 narrows the failure surface rather than closing it.

## Laundering paths

These are the routes by which a figure or a claim reaches posted copy without
the check that nominally covers it having said anything.

**The heading clears the section.** CHECK 3 matches a figure's subject against
its sentence plus the nearest heading, so a name in a heading clears every
number underneath it. A "Supporting figures." paragraph listing twenty figures
is attributed by its section header alone. This is deliberate and documented in
the docstring: requiring the subject in the sentence itself failed 22 correct
figures on an already-verified draft. It is the widest path in the gate, and it
is clause 1's shape surviving into the shipped check. See the findings section.

**The claim scope clears its own figures.** acac6a0 added a second path: inside
a claim scope, any figure that claim's entry carries clears without a name.
Narrower than the heading path, since it needs an explicit comment and stops at
the sentence, but it is a path.

**Years clear unconditionally.** Any number from 1990 to 2026 is exempt from
CHECK 3. A vote count, a meeting count or a rank that happens to land in that
range is never checked. 2025 votes, 2011 disposals, any figure in the window is
invisible.

**Two paths listed here were closed in 467eb9e and bd23385.** One ranked table
no longer silences the superlative check, and "most" and "fewest" are now
triggers. Both are written up in the findings section rather than here, because
what they cost to close is the more useful record.

**A superlative phrased around the trigger list still escapes.** The list is now
eight words: only, no other, best, worst, highest, lowest, most, fewest. It is
still a word list. "Nobody else comes close", "he stands alone", "ahead of every
other opponent" are ranking claims that match nothing. Closing the "most" gap
narrowed the surface; it did not change the mechanism.

**"Most recently" still fires as a superlative.** The lookahead added for "most
recent" is (?!\s+recent\b), and the adverb has no boundary after "recent", so
"most recently" reads as a ranking claim. It appears in no current draft.
Recorded in 467eb9e, not fixed.

**An absence phrased around the trigger list escapes CHECK 6.** The eight tokens
are the only entry point. "His record against them is silent" or "he has gone 11
meetings without troubling the umpires" assert an absence and match nothing.

**A finals filter applied silently escapes CHECK 5.** The check fires on
denominator_type matches_between_clubs or a window mentioning finals. A run that
filters finals and does not say so in the window is never asked to reconcile.

## Open items

The commit-order gap happened twice and is now a pattern, not an incident.
a236125 records the first: 5ef1fcb landed CHECK 5 before acac6a0 landed the
CHECK 3 attribution, so a checkout of 5ef1fcb fails on any draft citing a figure
attributed by declaration. 467eb9e is the second: it rewrites CHECK 1 and fails
the live fixture, which only passes again after bd23385 supplies the facts work
the check forced. 26 of 27 pass at that commit.

Both have the same cause. A check change that invalidates existing fixtures was
committed before the data fix it forced. The standing fix is to order it the
other way, data first with the new material inert until the check catches up, so
every commit passes its own suite. Neither was rewritten, on the view that
rewriting published commits to tidy an intermediate state is a worse trade than
a note saying what the state is.

Block 9a and 9c in the spec are marked unallocated. 9b and 9d are written and
are referenced by letter from draft_gate.py and the commit history, so the
lettering was kept rather than renumbered.

The live fixture covers CHECK 1, 3, 4, 5, 7 and 8 and not 6. It gained CHECK 1 coverage in 467eb9e, where its eight superlative tokens each bind to a table over their own subject. The four never and
drought sites were reworded when CHECK 6 landed, and the zero trigger no longer
fires on zero-vote, so the draft carries no absence tokens at all and
check_base_rate returns early. CHECK 6's only coverage is the four c6_ceiling
fixtures. Anyone reading the live fixture as whole-gate coverage should know
where the hole is.

drafts/ is gitignored as unreviewed generated copy, and f5f02d7 tracks one such
file against that policy. The tracked copy is a snapshot and will not follow the
live draft.

Suite status at bd23385: 27 fixtures, 27 passing. Run it with
`python tests/run_gate_tests.py`. Any change to draft_gate.py runs it, and a
non-zero exit is a failed change.
