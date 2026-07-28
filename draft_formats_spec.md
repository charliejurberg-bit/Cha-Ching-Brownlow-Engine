# `draft_posts.py` output formats, spec and rationale

Handover for the weekly post copy. The formats below were settled by iterating on
real round 20 output and posting the results, so the reasoning matters as much as
the templates. Anything not recorded here gets re-litigated.

Status: implemented in `7ecc26b`, `24c89c7`, `87212b0` and `fae1220`. All on
origin/master except `fae1220`. Verified against a real run of round 20,
including an idempotent re-run diff.

---

## Hard constraints

**Twitter renders proportional.** Any padding, alignment or column header collapses
on paste. Every generated row must be self-describing with single spaces only.
Forums render monospace and would hold alignment, but the script emits one format,
and that format has to be the one that survives both.

**280 characters, domain counts as 23** regardless of length.

**No em dashes** anywhere in generated copy. Hyphen in the movers title is a hyphen.

**Never state an accuracy percentage.** Existing rule, unchanged.

---

## 1. Movers

`SITE_URL = "chachingbrownlow.com"` at module level, used at every link site.

### Outside the fences, review context only

```
Round 20. Pool is the top 50 by Exp_Total_Votes now or in the previous snapshot.
Movement is measured across the full field.
```

This is not post copy. It explains why a player is or is not in the list when
reviewing a draft. It was removed once by mistake and restored in `24c89c7` with a
comment marking it as review context. Leave it.

Emitted as two separate `out.append()` calls, split after "snapshot." A single
append over implicitly-concatenated f-string fragments collapses both sentences
onto one line, which is the bug `fae1220` fixed. The fragments still look like
separate lines in the source, so merging them back would silently reintroduce it.

### Inside each fence

```
Round 20 Movement - Biggest Risers

Jarman Impey +21 from 70 to 49
Jye Amiss +13 from 52 to 39
Ed Richards +12 from 33 to 21
Jack Gunston +10 from 44 to 34
Zac Bailey +8 from 32 to 24

See the full leaderboard at chachingbrownlow.com
```

Fallers use the identical row template, the sign carries direction:

```
Round 20 Movement - Biggest Fallers

Harley Reid -4 from 24 to 28
```

Row shape: name, signed delta, `from`, previous rank, `to`, current rank.
Sign always printed, including `+`. Rendered from the delta itself via `:+d`, so
`_block()` takes no sign argument.

The link goes inside **both** fences, since each block is pasted as its own post.

### Rejected, do not reintroduce

| Rejected | Why |
|---|---|
| Team in parentheses | Redundant on a leaderboard movement list |
| `Exp_Total_Votes` on each row | Noise, the rank movement is the story |
| Aligned columns with padding | Dies on paste to Twitter |
| A `Player / Rank / Up / Votes` header row | Same, and the header cannot align either |
| The word `spots` | Redundant once the ranks are shown |
| `up 21` / `down 4` in words | The sign already carries direction |
| `#70 to #49` | The `from ... to` phrasing reads better than symbols |
| `Season rank since R19` subtitle | Depended on the previous round resolving, and was cut |

---

## 2. The 3/2/1 blocks

One fence per game, nine per round.

```
Round 20 Predicted Votes
Sydney v Greater Western Sydney
3. Errol Gulden (Sydney) 2.32
2. Chad Warner (Sydney) 1.66
1. James Rowbottom (Sydney) 0.78

See them all on the Game Analysis tab at chachingbrownlow.com
```

Only the first line changed, from `Round 20 projected votes`. Fixture line, the
three numbered rows and the two-decimal `Exp_Votes` are unchanged.

**Team stays here**, unlike movers. In a single-game 3/2/1 the reader needs to know
which side a player was on.

### Resolved defect

`Player_Name` already carries a disambiguating suffix for same-name players, and the
template appended `({Playing.for})` on top:

```
1. Bailey Williams (Western Bulldogs) (Western Bulldogs) 0.11
```

Two Bailey Williamses exist in 2026, one at the Western Bulldogs and one at West
Coast, so the CSV stores the suffix in the name.

Fixed in `87212b0` by `_label_with_team(player_name, team)`, a module-level helper
backed by `_TEAM_SUFFIX_RE = re.compile(r"\([^()]*\)$")`. It appends `({team})` only
when the name does not already end in a parenthetical, detected on the name alone.
Where the stored suffix disagrees with `Playing.for`, the stored name wins and prints
once. Verified on the real r20 draft: `Bailey Williams (Western Bulldogs)` prints a
single team.

---

## 3. Spotlight

Not a draft. A review shortlist that gets hand-written into a post, so no title or
link is generated.

Thresholds, all module-level:

```python
SPOTLIGHT_VOTE_RANK = 2        # Exp_Votes rank 1 or 2 in the game
SPOTLIGHT_DISPOSAL_RANK = 10   # was 4
SPOTLIGHT_MIN_VOTES = 1.4      # new
```

Reasoning: rank 1 or 2 in a game means nothing when the value is under 1.0, and a
disposal rank of 4 admitted players on 26 disposals, which is not the low-volume
profile the section exists to find.

**Verified against a hand-picked set.** Round 20 went from six rows to exactly
Gunston, Amiss and Neale, which is the set chosen manually before the thresholds
were changed. Neale clears the floor by 0.02, so 1.4 is doing real work and should
not be nudged without rechecking.

The preamble line states all three conditions.

---

## 4. What the script does not produce

The spotlight post for round 20 was written by hand from the table, reframed as a
key-forwards story rather than a list. That is the intended pattern: the script
emits raw material, some posts are composed from it.

Posted copy for reference:

```
Three of nine games had a key forward projected first for votes.

Jack Gunston 2.53 exp from 16 disposals, 7 goals
Jye Amiss 1.72 exp from 15 disposals, 5 goals
Shannon Neale 1.42 exp from 13 disposals, 5 goals

See them all on the Game Analysis tab at chachingbrownlow.com
```

Two vocabulary decisions worth keeping:

- **`exp`, not `projected votes`.** It is the site's own label, so the tweet and the
  page use the same word.
- **`projected first for votes`, not `projected 3 votes`.** Readers query how 1.42
  becomes a 3. Saying the player topped the ground states a rank, which is what the
  model actually produces.

---

## 5. Images

Nine game screenshots composited into three images, three games each, one tweet.
Twitter allows four per tweet, so 3x3 gives equal dimensions and fits.

Capture the **full game card including the header bar**, `GAME 8 - ROUND 20` plus
teams, score and margin. The first attempt cropped the headers out and the result
was unreadable. With headers, no labels need adding.

All nine trimmed to exactly 1120x250 before stacking, which means the site layout is
stable enough to make this repeatable weekly.

**No text is drawn onto the images.** Archivo, Sora and DM Mono are not available in
the container, so anything synthetic would be off-brand. Every glyph is the site's
own rendering, and the domain goes in the tweet body.

The risers and fallers blocks do **not** get images. Five short lines fit a tweet, so
an image would restate readable text and lose copy-paste and accessibility.

---

## 6. Untouched by any of this

`MOVERS_N = 5`, `MOVERS_POOL_RANK = 50`, both delta filters, the fallers
`isin(played)` filter, both `sort_values` calls, `_OPENING_ROUND_FROM`, the snapshot
logic, round numbering.

Selection logic and presentation are separate concerns. Every change in this
document is presentation, except the three spotlight thresholds, which are
selection and were verified against known-good output before being accepted.
