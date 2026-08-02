# Cha Ching — Project Brief

> Do not paste full source files. Locate code by function name, never by line number.
> Last corrected: 29 July 2026, against a full-file recon pass over the live repo.
>
> **This file and the Project Knowledge copy must be kept in sync.** On 29 July they
> had diverged badly: the repo copy was several sessions stale and asserted three
> things that recon disproved (`_NAV_BROWNLOW` existing, a `BH_PASSWORD` gate, Polls
> a Vote inside `_BH_PAGES`). After any edit here, re-upload to Project Knowledge.

## Project overview

AFL Brownlow predictor + betting research tool. Streamlit dashboard deployed on
Streamlit Cloud from GitHub (`charliejurberg-bit/Cha-Ching-Brownlow-Engine`).
Persistence via Supabase. Live since Round 10 2026.
Location: `C:\Users\charl\Python\brownlow_engine\`

Separate Vercel landing page repo: `C:\Users\charl\web\cha-ching-brownlow\`
(GitHub `cha-ching-brownlow`, domain `chachingbrownlow.com`). Always open and
commit from that path, never from inside `brownlow_engine`.

**Strategy:** free public launch targeting AFL betting forums. Build a
timestamped public track record through Brownlow night, 21 September 2026.
Monetisation later via bookmaker affiliate links. No paywall, no paid tips.
Betting Hub is private/personal; the public product is the Brownlow section only.

Twitter/X: `@ChaChingBrwnlow` (no "o" in Brwnlow).

## Tech stack

- **Python 3.13 local / 3.10 on Cloud**, Streamlit 1.57 local / 1.59 Cloud.
  This version gap has caused multiple production failures. Verify on the
  deployed app, never on local alone.
- `requirements.txt` pins `streamlit==1.59.2` **exact, not `>=1.57`**. Also pins
  `supabase==2.30.0` and carries `extra-streamlit-components==0.1.81`.
- XGBoost, pandas, numpy, scikit-learn, plotly, requests
- **Supabase** — cloud persistence for bets, Cha Ching tips, Polls-a-Vote
  watchlist, player props. Source of truth; local CSV fallback. RLS deny-all
  baseline on all four private tables.
- **Playwright** — live Betfair + ESPN fetch inside `dashboard.py`
- **undetected_chromedriver** — Oddschecker scraper (`scraper_odds.py`, local only)
- **R** — `data_pull.py` and `scripts/build_history.R` (fitzRoy)
- Data sources: fitzRoy, Wheelo ratings, Oddschecker, Betfair, ESPN,
  AFL Predictor API, Squiggle API, AFL public API

## Model

XGBoost v4.0. 23 H&A rounds modelled per season.

**Training range: 2015–2025.** Settled 29 July 2026. `brownlow_model.py`'s
docstring is authoritative and recon confirms it. The 2008–2023 backtest cut is
not a contradiction — those are the out-of-sample seasons, which by definition
sit outside the training range. The Vercel "a decade of AFL data" line covers
eleven seasons and is defensible, but "trained on seasons since 2015" is
preferred because it is exact.

**Do not cite accuracy percentages in any public-facing copy.** No top-10
accuracy figure, no variant of it. The "~86% top-10" and "~50% medallist top-3"
figures that appeared in an older brief have **no source anywhere in the repo**
and must not be used. If a number is needed for a forum post or marketing, it
comes from the calibration table below or from Charlie directly.

Honest out-of-sample figures, from `accuracy_report.py` against
`backtest_game_level.csv`, 2008–2023 cut, 3,054 games:

| Projected votes | % that poll 3 votes |
|---|---|
| 2.0–2.2 | 50.4% |
| 2.2–2.4 | 56.5% |
| 2.4–2.6 | 65.1% |
| 2.6–2.8 | 78.8% |
| 2.8–3.0 | 89.2% |

Mean actual tracks mean projected within 0.05 in every bucket above 2.0. No thin
buckets. This is the checkable, defensible claim — a projection of 2.4+ polls
three votes 65% of the time, on seasons the model never trained on.

In-sample inflation was severe: exact top-three order 22.23% fitted against
8.38% honest. Never quote in-sample figures.

**MAE figures: UNRESOLVED. Do not quote any of them.**

`brownlow_model.py:249` states that the v1–v4 MAE figures (0.0954 / 0.0910 /
0.0902 / 0.0904) were all measured with a momentum leak in place and none is
comparable. The current printed baseline at line 248 is **0.0953 full model,
0.1013 no-coaches**.

A separate set attributed to a Wheelo alignment fix (2023 0.1022, 2024 0.0971,
2025 0.0985, overall 0.0969) appears in the brief's history. It is not known
whether that set predates the 2026 audit and therefore carries the same leak.
Resolve by re-running against the current model before any MAE figure is used
anywhere, public or internal.

## File structure

```
brownlow_engine/
├── dashboard.py              # Main app — page dispatch, Brownlow pages, hub router, global CSS
├── betting_hub.py            # Betting Hub module — imported by dashboard.py
├── user_auth.py              # Supabase auth (1,110 lines); is_admin() drives the whole
│                             #   private/public split. Docstring carries two security
│                             #   invariants on client caching and st.cache_data keying.
├── theme.py                  # Shared design tokens
├── features.py               # Single shared feature pipeline (both training and prediction)
├── club_aliases.py           # canonical_club() over a module-level dict, 1990–2025
├── brownlow_model.py         # XGBoost training — once per season
├── brownlow_medallists.py    # Medallist reference data
├── predict_2026.py           # In-season predictions — weekly after each round
├── update.py                 # One-click update chain
├── backtest.py               # Walk-forward backtest; emits backtest_game_level.csv
├── backfill_game_level.py    # Historical game-level backfill
├── merge_wheelo.py           # Wheelo merge
├── streaks.py                # Streak computation for post drafts
├── draft_posts.py            # Templated post generator — step 7 of update.py, no LLM pass
│
├── scraper_odds.py           # Oddschecker (undetected_chromedriver) — sole writer of implied_prob
├── scraper_betfair.py        # Betfair consensus (JSON API)
├── scraper_espn.py           # ESPN consensus (Playwright) — writes espn_round_votes.csv
├── scraper_afl.py            # AFL Predictor votes (award API)
├── scraper_stats.py          # Squiggle player stats
├── scraper_wheelo.py         # Wheelo ratings
├── update_wheelo_2026.py     # 2026 Wheelo update
├── data_pull.py              # Historical fetch (fitzRoy/R)
│
├── scripts/
│   └── build_history.R       # Producer for the 1990–2006 archive. Run from repo root.
│
├── data_2026/                # Live season data (22 files)
├── data_wheelo/              # Wheelo 2015–2026 + wheelo_all_seasons.csv (16 files)
├── data_betting/             # Betting Hub local fallback CSVs (4 files)
├── data_history/
│   └── brownlow_votes_1990_2006.csv   # 124,171 rows, 10 cols, recon-only, git-tracked
├── predictions/              # Model artifacts + output CSVs — git-tracked (75 files)
├── page_modules_wip/         # DEAD half-refactor, 13 .py files, nothing imports it
├── supabase/                 # SQL / config
├── assets/
├── drafts/                   # gitignored — generated post drafts, unreviewed
├── _tmp/                     # gitignored — throwaway scripts
├── .github/                  # Actions workflows, incl. keep-alive cron
├── .streamlit/config.toml
└── requirements.txt
```

There is **no `pages/` directory.** Earlier briefs listed one; the dead refactor
is `page_modules_wip/` and nothing imports it.

Also present at top level, unmentioned in earlier briefs: `fitzroy_stats_all.csv`,
`fitzroy_stats_2007_2014.csv`, `fitzroy_stats_2015_2025.csv`, `coaches_votes_all.csv`,
`brownlow_votes_2015_2025.csv`, `brownlow_predictions_2025.csv`,
`game_level_predictions_2025.csv`, `feature_importance.csv`, `supabase_setup.sql`.

Untracked working-tree analysis scripts: `accuracy_report.py`,
`betting_edge_report.py`, plus their `*.csv` output. Both are offline CLI,
imported by nothing, unreachable from the dashboard by any route.
`betting_edge_report.py` is **not** a page — there is no "Betting Edge" page.

Other docs: `CLAUDE.md`, `CLAUDE_CODE_BRIEF.md`, `fixture_recon_spec.md`,
`draft_formats_spec.md`, `landing_spec.md`. `landing_spec.md` describes the
Vercel landing page and probably belongs in the other repo.

Debris to ignore: one-off dev scripts, duplicate snapshots (`dashboard 2.0.py`),
a stale nested clone `cha-ching-brownlow-engine/`, five `*_debug*.html`,
`grid_out.txt`, `grid_err.txt`, `.Rhistory`.

## Page structure

**`_NAV_BROWNLOW` and `_NAV_BETTING` do not exist.** Zero hits across all `.py`
files. Any prompt referencing them will send Claude Code hunting for nothing.

The real constant:

```python
_BH_PAGES = {'Performance', 'Predictions', 'Bet Tracker',
             'Cha Ching Tips', 'Trends & Analysis'}   # module level, dashboard.py
```

Five pages, not six. **Polls a Vote has left `_BH_PAGES`** and now sits in the
Brownlow strip, scoped by RLS rather than by the gate. This matters on three
surfaces, not one: `_BH_PAGES` also drives the responsible-gambling footer guard
and `_show_controls` visibility.

`_snav_pages` is a local plain list, rebuilt each run from `_hub`:

- Brownlow branch: Leaderboard, Player Profile, Stat Filter, Game Analysis,
  Model Comparison, Live Tracker, Polls a Vote
- Betting branch: the five `_BH_PAGES`

**There is no Landing page.** **There is no "Player Comparison" page** — that
string is absent from `dashboard.py`; comparison is a tab inside Player Profile.

**Pages are not render functions.** `dashboard.py` dispatches with module-level
`if _page == '<Name>':` blocks. Only `_render_stat_filter` and
`render_polls_a_vote` are real page functions, and `render_polls_a_vote` lives
in `dashboard.py`, not `betting_hub.py`. When prompting, say "the
`if _page == 'X':` block", not "the X render function".

Predictions renders inline; the other Betting Hub pages route via
`betting_hub.render_page()`.

**Function tables are deliberately omitted.** Two previous briefs carried them
and both went stale — the last recon found one false entry in the `dashboard.py`
table and six in the `betting_hub.py` table (the watchlist and polls functions
had relocated to `dashboard.py` and `user_auth.py`). Rebuild from a recon pass
when actually needed.

## Access model

`_is_admin = user_auth.is_admin()`, mirrored into
`st.session_state["cc_is_admin"]`.

`user_auth.is_admin()` matches `current_user()` (i.e. `st.session_state["cc_user"]`)
against `st.secrets["ADMIN_UID"]`. Fails closed on every path: no user, no id,
no secret, any exception.

**This is an admin-account check, not a password gate.** `bh_authed` and
`st.secrets["BH_PASSWORD"]` survive only in historical comments. The shared
password was removed because it authenticated a string rather than a person.
There is no password input anywhere in the flow. Any reference to
`hmac.compare_digest` password gates describes a superseded state.

The one surviving password is `TIPS_EDIT_PASSWORD`, read in `betting_hub.py`,
and it gates editing rather than access.

Three layers, all verified:

1. `_render_hub_tabs()` is called under `if _is_admin:`. Anonymous users see two
   nav rows, never three, and have no control that writes `active_hub`.
2. `_hub` defaults to `"brownlow"`; the only writers of `active_hub` are the two
   pills inside `_render_hub_tabs()`.
3. `if _page in _BH_PAGES and not _is_admin:` renders a private panel and calls
   `st.stop()`. `betting_hub.render_page()` carries an independent backstop on
   `cc_is_admin`.

Anonymous reach is exactly the Brownlow `_snav_pages` list.

## Model-vs-market surfaces

Every site that puts a model number against a market number normalises
`Exp_Total_Votes` into a share. **No win probability exists anywhere in the
repo.** `season_projection_2026.csv` holds independent per-player Monte Carlo
floor/ceiling bands only; because players are simulated independently, no winner
distribution is derivable from it.

| Site | Page | Anonymous | What it actually is |
|---|---|---|---|
| Model Edge chip | Predictions | No | market rank − model rank |
| Value Finder / Auto Odds | Predictions | No | top-30 vote share − raw implied % |
| Value Finder / Manual | Predictions | No | same, user-entered odds |
| Leaderboard odds cols | Leaderboard | Yes | no edge, raw display |
| Compare market section | Player Profile | Yes | two shares, side by side, not differenced |
| Model Comparison `_edge_for` | Model Comparison | Yes | rank delta vs 4 rival models, no odds |
| BH market tab | Cha Ching Tips | No | season avg − posted line, props only |

The two Value Finder sites divide by a top-30 constant, which mechanically
prints negative edge on favourites and positive edge on longshots. Admin-gated,
so not a launch risk, but the output is an artefact and should not be trusted
for personal betting either.

As of commits `a4d0037` and `813bd90`, the Compare tab shows "Model vote share",
"Best odds", "Market win share" and no edge figure. The MODEL LEANS banner is
gone. The two quantities are deliberately not differenced — vote share is a
ratio of totals, market implied is a conditional win probability, and they are
on different scales.

## Averages — three displayed values, one known trap

The same player can show 0.66, 0.60 and 0.56. All five live paths are in
`dashboard.py`; `betting_hub.py` has none.

- 0.66 — actual votes over vote-eligible games
- 0.60 — `Exp_Votes` over all rows including 2026
- 0.56 — `Exp_Votes` for 2026 alone
- 0.5743 — actual votes over all rows including 2026. Displayed nowhere, and is
  what any new surface built on `load_game_career()` without the vote-sum filter
  would produce.

Labels were fixed by relabel only, no arithmetic touched: Profile tab is
"Avg exp votes", DNA tab is "Avg votes polled".

**Null versus zero.** Same 7,866 games, opposite encoding:

```
data_2026/afltables_2026.csv      7,866 null, 0 zero, .mean() → NaN
predictions/game_level_2026.csv   0 null, 7,866 zero, .mean() → 0.0
fitzroy_stats_all.csv finals      7,658 null, dropped by .mean()
```

Recon reads the first, the app reads the third. Finals get dropped; 2026 rows get
counted and drag career averages down. **Any votes-per-game figure must state
which file it came from.**

**Still open:** 2026 inclusion is decided three different ways across four
actual-votes paths, none shared. `predict_2026.py` computes
`Avg_Predicted_Per_Game` into `season_projection_2026.csv` where nothing reads
it — a sixth display waiting to be wired to a field whose name says "predicted"
for a retrospective quantity. Rename while it is free.

## Odds data — known characteristics

`scraper_odds.py` takes `max(vals, key=vals.get)`, the longest price across eight
bookmakers, so stored `implied_prob` is a best-of-eight composite, not any single
book's line. `BETFAIR_MIN_BACK = 1.5` filters lay prices.

- 116 quoted players. **60 of them sit at 980 or 1001**, every one stored as
  `implied_prob` 0.1. That is a board floor, not an opinion. Over half the field
  carries no market view.
- Book sums to 127.89% across all quoted; 121.89% excluding the 980/1001 tail.
- Six exact-join failures against `season_2026.csv`, none resolved by
  `normalise_name()` (it does no nickname mapping): Matthew/Matt Rowell,
  Samuel/Sam Lalor, Lachlan/Lachie Ash, Jack/Josh Rachele (bookmaker typo).
  Rowell is the only material one, 4.67 expected votes at 501. "Nic Martin" and
  "Tom Green" have no counterpart in the model universe at all.
- Jason Horne-Francis is genuinely unquoted, rank 11 by expected votes.
- **`scraper_odds.py` overwrites on every run.** No `_prev`, no timestamped
  filenames. Git history holds 12 clean distinct snapshots for 2026 — the only
  price history that will ever exist for this season.

## Data integrity rules

- `Exp_Votes` is **retrospective only.** Copy must never imply forward
  prediction. Never say a player is "projected to poll" a 3, 2 or 1 in an
  upcoming game.
- **Player identity is keyed by ID, never by name.** Zero IDs map to more than
  one name across 286,541 rows, but eight names are shared by multiple qualifying
  players. Gary Ablett Sr (ID 567) and Jr (ID 1105) fuse into a 33-meeting player
  at 1.000 that never existed if keyed by name, and it looks plausible enough to
  ship.
- **Two Bailey Williamses exist in 2026** (Western Bulldogs and West Coast).
  `Player_Name` carries a disambiguating parenthetical suffix that must never be
  stripped.
- **Finals exclusion is right for rates and wrong for counts.** Vote rates need
  vote-eligible denominators, home and away only. Meeting counts, streaks and
  appearance records need every match played. The Toby Greene line lost its
  strongest form (17 meetings, not 16) to a filter correct in another context.
- **Superlatives require enumeration.** Any claim containing *only*, *no other*,
  *best*, *worst*, *highest* or *lowest* must print the full ranked table it is
  drawn from. This rule exists because a Sam Walsh claim went public and was
  wrong: Geelong 1.14 and Port 1.11 also cleared 1.00.
- **Every figure in a report is computed in the run that reports it.** No figure
  carried forward, no figure hand-summed.
- **Raw counts are sourced like everything else.** A total in a facts file
  carries a source file, same as a rate; it is exempt from the denominator, not
  from provenance.
- **Extending a range can kill a claim rather than strengthen it.** Ablett
  dropped from 2nd to 11th on eight extra meetings and one extra vote when the
  archive went back to 1990. Ask what a wider denominator would do before
  publishing a superlative.
- The 1990 floor is a hard truncation, not a career boundary. Pre-1990 debutants
  have only their post-1990 tail counted. This caveat must accompany any
  all-time ranking.
- `coaches_votes_all.csv` holds rows only for players who polled, and is missing
  2024 R25 (Hawks–North). Reconciliation against fitzRoy fixture counts is
  mandatory, not diagnostic.
- **Three copies of overlapping club-alias truth exist:** `club_aliases.py`,
  `dashboard._TEAM_ALIASES`, and a deliberate copy in `backfill_game_level.py`.
  Neither of the older two has Brisbane Bears. Not consolidated.
- Fitzroy stays Fitzroy. Deliberate. Folding it into Brisbane Lions corrupts
  opponent counts for every club that played both.

## UI theme — Midnight Turf

- `bg #0a1017`, `surface #101a24`, `text #e9eef3`, `emerald #34d399`,
  `gold #f0b429`, `muted red #ef7a6d`, `border #1a2632`, `muted #7e8c99`
- **Archivo** display headings, **Sora** UI text, **DM Mono** numerics
  (weights 400/500 only; faux bold clamped to 500). Not IBM Plex Mono.
- `config.toml`: `base=dark`, `primaryColor=#34d399`, `backgroundColor=#0a1017`,
  `secondaryBackgroundColor=#101a24`, `textColor=#e9eef3`

**Laws:**

- Colour encodes information, never decoration.
- Red `#ef7a6d` is for losses and negative P&L only. Never model errors,
  validation nudges, or status indicators.
- No em dashes in user-facing copy.
- Displayed round = `Round_num − 1` at render only, for seasons from 2024 onward
  (AFLTables numbers Opening Round as Round 1). All data and filtering uses the
  raw `Round_num`. `_display_round` is defined in **three** places —
  `dashboard.py`, `draft_posts.py` and `streaks.py` — each with its own
  `_OPENING_ROUND_FROM = 2024`. Change one, change all three.
- **CSS scoping uses the `st-key-<name>` pattern** (from `st.container(key=...)`).
  This supersedes the marker-div `:has()` idiom. The nav has fully migrated (32
  `st-key-ccnav` rules), but `:has()` still appears 28 times in `dashboard.py`
  and 75 times in `betting_hub.py`. Those selectors were accidentally
  load-bearing for specificity, so flat replacements need deliberate specificity
  matching.
- Streamlit selectbox is React Aria, not BaseWeb. `data-baseweb` selectors match
  zero elements app-wide. Verified: `[data-testid="stSelectbox"]
  .react-aria-ComboBox > div` (closed), `[data-testid="stSelectboxVirtualDropdown"]`
  (portal, mounts as bare body child), `[role="option"]` rows.
- Nav CSS changes require live verification on a BH-routed page.
- Animated/JS content lives in `st.iframe` (5 call sites in `dashboard.py`).
  `components.html()` is gone; the only surviving reference is a test mock in
  `test_espn.py`.

## Environment gotchas

- Streamlit Cloud hot-update only re-executes `dashboard.py`; the import cache
  retains old module objects. **Changes to imported modules need a manual app
  reboot.**
- `st.context.cookies` is blind under Cloud's iframe embedding (SameSite=Strict).
  Cookie reads must go client-side via the component's `getAll`.
- Screenshot verification is unreliable for this app. `get_page_text` and log
  inspection are more trustworthy.
- `st.iframe` rejects `height=0` — use `height=1`.
- **PowerShell 5.1 only, no `pwsh` 7.x.** `-Encoding utf8` writes a BOM, which
  breaks pandas merges on column 0 by silently producing `\ufeffPlayer_Name`.
  `>` and `Out-File` write UTF-16LE. Commit messages with quoted strings require
  `git commit -F` from a temp file.
- `git show <rev>:<path> --output=<file>` does not work for blobs here — it
  creates a 0-byte file and writes to stdout. Use
  `[System.IO.File]::WriteAllText` instead.
- `scripts/build_history.R` uses repo-root-relative paths. Run it as
  `Rscript scripts/build_history.R` from the root, never from inside `scripts/`.

## Conventions

- Locate code by function name, never line number.
- **Recon first. Stop and report before any changes.**
- `py_compile` before every commit. Atomic commits on master.
- **Push is granted.** `.claude/settings.local.json` grants `git push` in three
  places; `.claude/settings.json` is silent on it. Earlier briefs said "do not
  push, Charlie pushes via GitHub Desktop" — that convention is retired, and no
  statement of it survives anywhere in the repo. Claude Code may push to master.
- Do not run the app. Do not touch Supabase or secrets.
- One task per session, one specific task per prompt.
- Do not ask which task to do next — make a reasonable assumption.
- Visual changes need mockup approval before Code touches anything.
- Verification gate: identical-output or diff-check before committing any fix.
- Close files in VS Code while Claude Code is working, to avoid stale buffers.

**Shell.** PowerShell and `Select-String`, never `grep` or bash — **except in
autonomous mode**, where `fixture_recon_spec.md` permits throwaway Python scripts
written to `_tmp/` with literal relative paths, run as `python _tmp/name.py`.
Never `$env:TEMP`. The two modes are defined in that spec; interactive is the
default and is read-only.

## Content pipeline

`draft_posts.py` is a **templated** generator with no LLM pass, wired in as step
7 of `update.py`. This was deliberate: templated output cannot invent an accuracy
claim. Keep it that way unless the decision is revisited explicitly.

`fixture_recon_spec.md` governs per-fixture recon: eight blocks, existence checks
A–D, a judgment pass, finals filter, club canonicalisation, script hygiene. It
carries four unsettled scoping questions (career vs fixture scope on block 7;
name-level vs name-and-club grouping on block 6; club alias merging;
current-season exclusion from career rates) and a stale `Status:` line.

Copy rules, permanent:

- No accuracy percentages unless Charlie supplies the number.
- No forward-looking vote claims. `exp` preferred over "projected votes".
- "Projected first for votes" beats "projected 3 votes" — avoids readers asking
  how a decimal becomes a 3.
- Do not round 0.01 to 0.00. It misrepresents data and undermines a checkable
  record.
- Round number in every post.
- Two hashtags: the AFL's official match tag plus `#Brownlow`. The official
  format is `#AFL` followed by both clubs' nickname stems, with the home club
  first: `#AFLSunsDees`, `#AFLPowerGiants`, `#AFLBluesLions`. Do not invent an
  abbreviation format such as `#GCvMelb`, it carries no traffic. If the official
  tag for a fixture is not known, check the AFL's own posts rather than
  constructing one. Non-match posts take `#AFL` plus `#Brownlow`.
- Link on the last tweet of a thread only.
- No paid tips language, ever.
- Model-first framing: lead with the insight, not the statline.
- Fewer, cleaner picks outperform speculative volume.
- Restriction and tagging angles are not computable from any file. Manual
  judgment only.

## Current priorities

1. **Keep-alive GitHub Actions cron.** Workflow file exists; runs never confirmed
   firing. Check the Actions tab. Launch blocker, outstanding four sessions.
2. Superlative and denominator gates: a script that fails the build when a draft
   makes a superlative claim without a ranked table, or states a per-game rate
   without a denominator and source file.
3. `scraper_odds.py` append-with-timestamp instead of overwrite.
4. Remove the Streamlit landing page — Vercel is the front door.
5. Script the deterministic post-round chain (`update.py`, `draft_posts.py`,
   `streaks.py`) with exit-code checks, stopping on failure.
6. Forum post and first weekly scorecard, built on the calibration table.
7. Resolve the MAE question above.
8. Result posts for the Mullin and Bontempelli previews. Three handovers
   outstanding. Previews without results are the half of the record that does not
   count.
9. Resend SMTP wiring, once the custom domain is live.

## Known deferred, non-blocking

CSV re-import duplication; `_load_bets` CSV shadowing; dead
`_add_bet_dialog`/`_insert_bet` path; dead `POLLS_CSV`/`PROPS_CSV`; `_save_tip`
traceback-in-UI; `uuid[:8]` on import paths; `ADMIN_UID` silent-lockout
mitigation. Consolidate the three club-alias copies. Rename
`Avg_Predicted_Per_Game`. Resolve 2026 inclusion across the four actual-votes
paths. Prune the allow list in `.claude/settings.local.json`. `.claude/` is
listed twice in `.gitignore`.

Pre-count-night: drop `fetch_live_brownlow_data` TTL and auto-refresh sleep
together, 300 → ~60.

Modelling backlog: 16 non-rank Wheelo features, composite-vs-raw Impact_Score,
round-index interaction, Kangaroos alias.

Off-season: retrain, widen the `brownlow_model.py` column projection, Wheelo
merge guard, relabel MatchId 20252410, full Next.js rebuild, backfill snapshots
for rounds 1–19 from weekly data-update commits.

## Closed research questions — do not reopen

- **Late-season form and momentum.** All temporal form features showed near-zero
  importance once the pipeline was clean. Negative result, settled.
- **Season-fade betting edge.** Does not reach zero at any threshold; floor is
  1.088%. Every games-band refinement is retrospective only, degrading 3x to 10x
  when hindsight is removed.
- **Duplicate feature pipelines.** Root cause of multiple bugs. `features.py` is
  the single shared pipeline; keep it that way.
- **Pre-2007 archive value for active players.** Extending to 1990 left the 2026
  list ranking byte-for-byte identical. No player on a 2026 list debuted before
  2007. The payoff is entirely in all-time claims; future active-player rankings
  can run on `fitzroy_stats_all.csv` alone.
