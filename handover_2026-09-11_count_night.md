# Handover, Brownlow night research pack and count-night engine

Written 11 September 2026. Count night is **21 September 2026**, ten days out.
Branch `chains-per-quarter-stats`, six commits, none pushed at time of writing.

> **DELETE THIS FILE once count night is done and the follow-up work has
> landed.** It is a resume-point for one task with a fixed expiry, not a
> reference document. The durable findings in it belong in `CLAUDE.md` and
> `project_brief.md`; see "Before deleting" at the bottom for the ones that have
> not been moved yet.

## Where we got to

Two goals were agreed:

1. The Live Tracker on the site works when the count begins. **Done, verified
   in a browser on the deployed app 13 September, and pushed.**
2. Tweets come back after each round so Charlie knows what to post. **Built,
   copy not yet signed off.**

Plus a research pack so count-night questions can be answered instantly. **Done.**

## What exists now

| Commit | What |
|---|---|
| `ed01611` | `scripts/night_pack.py` + `night_sections.py`, the research pack |
| `81c904d` | `scripts/coaches_season_card.py`, tracked so the pack reproduces |
| `1cb93a0` | The mirror crossover: three votes, nothing from the coaches |
| `e9d4a31` | `scripts/count_night.py` + the committed predictor snapshot |
| `26ef627` | `dashboard.py` Live Tracker fixes |
| `1446fb3` | `scripts/count_tweets.py`, the per-round tweet drafts |

### The research pack

`python scripts/night_pack.py` rebuilds nine markdown files under
`drafts/brownlow_night/` (gitignored) in about a minute. `INDEX.md` maps a
question to a file. `players.md` is the one the night runs on: a briefing block
per projected top-40 player. Warm rebuild of a single section is seconds; the
pickle cache lives in the scratchpad and `--refresh` rebuilds it.

### The count-night feed

`python scripts/count_night.py status` says what the AFL award endpoint is
serving: PREDICTOR, COUNTING, COUNTED or UNKNOWN. `rounds` prints per-round
votes and refuses while the state is PREDICTOR.

### The tweets

`python scripts/count_tweets.py --dry-run --round all` prints every post for
every round off predictor data, each with a DO NOT POST banner. `--live` refuses
unless the count is running and only drafts rounds it has not already drafted.

## Open decisions, none of them blocking, all cheap now and expensive on the night

1. **Five blocks per round may be too many to post.** 25 rounds x 5 is a lot of
   tweets. Consider two staples plus the rest only when they fire.
2. **A bolter block is missing.** The Live Tracker already carries the concept
   (`BOLTER_MIN_VOTES = 2`, `BOLTER_MODEL_MAX = 0.8`) and "nobody saw this
   coming" is a good count-night post.
3. **Hashtags.** `project_brief.md` requires two per post; these blocks carry
   none, because the official per-match tag does not apply to a round post.
   `#AFL #Brownlow` on all of them, or leave them off.

## Not done, and one of them matters

- ~~The Live Tracker page has not been looked at in a browser.~~ **DONE 13
  September.** The Chrome extension was still not connected, so the page was
  rendered two other ways instead: through Streamlit's own AppTest harness
  locally, replaying the real AFL payload truncated to round N to produce the
  COUNTING state, and then through Playwright against the DEPLOYED app, which
  is the check that mattered given the 1.57-local / 1.59-Cloud gap. All six
  states confirmed: PREDICTOR, COUNTING at nothing / Opening Round / R12,
  COUNTED, UNKNOWN. Zero exceptions on all seven Brownlow pages.
  Four bugs found by doing it, all fixed and deployed:
  "Round 0 of 24 counted" on a zero bar for the whole Opening Round segment;
  a full green "Round 24 of 24 counted" sitting under the banner that says the
  count has not started; an UNVERIFIED pill over a banner asserting the count
  had not started, with live votes on the board; and the one that mattered
  most, below.
  **The SIGNED-IN page was then verified separately, and that is where the
  real defect was.** An anonymous visitor has `_wl_visible` False, so Zone 3,
  the H2H panel, the star set and the watchlist filter never render at all --
  the first pass had verified about half the page. Patching the four
  `user_auth` loaders exposed that the feed's player names do not bridge onto
  the model frame: three 2026 vote-getters (both Bailey Williamses and Matthew
  Carroll) had no model row, and a missing model value reads as ZERO rather
  than absent, so Zone 1 was ready to announce Matt Carroll as a bolter
  "nobody called" when the model had him at 0.86 and 47%. Fixed by reusing
  `features.resolve_feed_names` rather than writing a second resolver.
- ~~Nothing is pushed.~~ **DONE.** `chains-per-quarter-stats` merged to `master`
  and pushed, plus the branch itself. The deploy's app surface was checked
  first: of 27 changed files only `dashboard.py` and the snapshot JSON are
  reachable from the running app.
- **The count-night loop is not wired.** `count_tweets.py --live` is designed to
  be polled but no `/loop` or cron has been set up.
- Charlie's own in-progress work is untouched and uncommitted: `fixture_recon.py`,
  `scraper_advanced.py`, `scripts/club_votes_card.py` modified, plus
  `scripts/bog_share_card.py` and five `data_advanced/advanced_201*.csv`.

## Facts established this session, so they are not re-derived

**The AFL award endpoint serves the predictor, not votes, between counts.**
`aflapi.afl.com.au/afl/v2/compseasons/{id}/award/brownlow`. Measured against two
completed seasons: it says 2025 Dawson 32 where the count was Rowell 39, and
2024 Cripps 33 where the count was Cripps 45. Charlie's position is that it
turns into the live votes on count night; the code is built for that and the
detector confirms it rather than assuming it either way.

**The snapshot is a before-picture that cannot be retaken.**
`data_2026/brownlow_predictor_snapshot.json`, taken 10 September 2026, 630
players, 1,242 votes, Daicos 47. Once the count starts the pre-count payload is
gone from everywhere. Do not overwrite it; `snapshot` refuses without `--force`.

**Timings, measured.** AFL feed exhaustive read 17s (7 pages, 630 players); pack
load from warm cache 0.5s; a records query on the warm frame 11ms. About 18s end
to end. A 60s poll is comfortable against a count that reads a round every five
or six minutes. Unknown until the night: how fast the AFL feed updates against
the broadcast. If it lags, that lag dominates.

**The site's Live Tracker is a separate consumer.** It calls
`fetch_live_brownlow_data()` itself with `@st.cache_data(ttl=60)` and computes
bolters, landed and the leaderboard inside the page. Nothing in `scripts/` feeds
it. Fixing one does not fix the other.

**Other live-vote sources, checked.** Wikipedia's 2026 Brownlow page carries real
final totals (its 2025 page says Rowell 39, matching the archive) but no
round-by-round. AFLTables `brownlow2026rbr.html` already exists as a shell with
all 207 fixtures and no votes, and will fill after the count; same source as the
repo's archive, so the format will match. ESPN's tracker is a predictor with
fractional votes. brownlowtracker.com.au is a fan prediction game.

## Data defects found and handled, worth not rediscovering

- **1976 and 1977 doubled the vote pool.** Two field umpires each awarding
  3-2-1: exactly 1,512 votes against 792 either side. The pre-1984 file labels
  both "3-2-1" like any other season, so a naive all-time season ladder opens
  with Teasdale's 59 and Moss' 48, neither comparable to a modern total.
- **888 rows carry `Age` as 0, not null**, across 1984-2022. `notna()` passes
  every one, so an unguarded youngest-ever list is a list of newborns.
- **`brownlow_medallists.py` starts at 1984**, so "most votes without a medal"
  opened with Gary Dempsey, who won in 1975.
- **The coaches archive holds only 91-95% of 2023, 2024 and 2025.** Game-level
  claims are safe; season totals from those years are floors.
- **The 2026 prediction file spells two clubs differently** ("Footscray", "GWS").
  Unmapped they drop every Bulldogs and Giants player out of the club joins in
  silence.
- **2025 Brisbane v Geelong** is filed by the coaches feed under Round 4 and by
  the archive in Opening Round. Six rows, reported rather than forced.

## Before deleting this file

These have not been written into `CLAUDE.md` or `project_brief.md` yet and are
the parts worth keeping:

1. ~~The award endpoint being a predictor between counts.~~ **DONE.** Written
   into `CLAUDE.md` as "## Count night and the Live Tracker", with the 2024 and
   2025 evidence, the four states, the snapshot-keys comparison, the feed's own
   round numbering and the ttl/sleep pairing.
2. ~~The 1976-77 double vote pool.~~ **DONE 14 September.** In `CLAUDE.md`
   under "Brownlow votes before 1984", re-measured: 1,512 against 756 in 1975
   and 792 in 1978 (not "792 either side").
3. ~~The `Age == 0` trap.~~ **DONE 14 September.** In `project_brief.md` under
   "Data integrity rules", re-measured: 888 rows, 631 players, 1984-2022.
4. ~~`project_brief.md`'s pre-count TTL item.~~ **DONE 14 September.** Removed;
   the change itself landed in `26ef627`.

Nothing durable is left in this file. Delete it after count night.
