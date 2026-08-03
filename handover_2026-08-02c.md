# Handover, 2026-08-02 session c

Scope: the keep-alive cron closed, the repo topology established, and CLAUDE.md
audited against project_brief.md and the code. 12 commits, 648c6a7 through
024bfe2, 5 files net, 801 insertions and 62 deletions. The last two commits carry
an 08-03 date; the session ran through midnight.

No model, dashboard or gate code changed. Every commit here is documentation,
configuration, or a revert, with one exception: 0260462 tracks
betting_edge_report.py, which existed untracked in the working tree.

Read this alongside project_brief.md, which now carries the repo topology table
and the corrected keep-alive entry. This file carries what the brief does not:
why the wrong claims survived as long as they did.

## What shipped

| Commit | What |
|---|---|
| 648c6a7 | Keep-alive ping moved off `/~/+/` to the bare URL with a cookie jar, plus header dumps on failure |
| 7e86a3d | Keep-alive moved from priority one to closed |
| 0bd5d8a | landing_spec.md cherry-picked in (reverted below) |
| 84fd3a4 | Report CSVs ignored, three stale gitignore rules dropped |
| 0260462 | betting_edge_report.py tracked |
| 915afd8 | Brief corrected on script tracking and the second clone (shipped a wrong claim, see below) |
| 09e49d4 | Dead nested-clone entry dropped, recon and edit dates split |
| afb0598 | Revert of 0bd5d8a |
| 09647a5 | Brief corrected again: there is a second repo, and it owns the spec |
| 756cd4a | landing_spec.md gitignored |
| 349ac86 | Eight contradicted claims fixed in CLAUDE.md |
| 024bfe2 | Seven more fixed, including two 349ac86 left behind |

## Findings

**The keep-alive was never a launch blocker, and eight days of priority one were
spent not opening a browser tab.** The brief listed it first, marked "Launch
blocker, outstanding four sessions", on the strength of "runs never confirmed
firing. Check the Actions tab." Nobody checked the Actions tab. The workflow
landed 26 July in ee16ab1 and the entry survived until 2 August, resolved in
7e86a3d by looking. Runs 82 to 104 are all labelled Scheduled and mostly green.

Two things are worth carrying forward. GitHub delivers the cron roughly hourly
against a requested 15 minutes, because short intervals get dropped under load,
so the interval is a target and not a promise. And the intermittent 400s are
endpoint flake rather than a broken workflow: the app is healthy when they fire.

648c6a7 is hardening, not a repair. The `/~/+/` suffix was returning 400 from
GitHub runners while the same suffix answered 200 in 0 hops from a home
connection, three times running, so the fault was never reproducible locally and
the workflow was never broken. The ping now uses the bare URL with `curl -c/-b`
against a temp jar, which completes Streamlit's cookie handshake and lands on 200
in 3 hops, and dumps every hop's headers on any non-2xx so the next failure
diagnoses itself from the notification email.

The generalisable part is not about cron. A priority that says "check X" and is
carried forward unchecked is not a priority, it is a note. Four sessions of
carrying it cost more than the check would have.

**Three directories hold two repositories, and conflating them cost two rounds of
wrong corrections.** The layout, now recorded in the brief as a table:

- `Python\brownlow_engine\`, repo `Cha-Ching-Brownlow-Engine`, root 6d08fbc. This
  repo.
- `Python\vercel\`, the *same* repo, same root 6d08fbc. A second clone, despite
  the directory name. Its origin URL differs from this one only in case, so both
  resolve to the same master. It held one unpushed commit and is now reset to
  origin.
- `web\cha-ching-brownlow\`, repo `cha-ching-brownlow`, root 165cbfa. A genuinely
  different repository: the Next.js 16.2.6 front end on branch `main`, deployed
  to Vercel, and the live front door.

landing_spec.md belongs to the third and was already tracked there, added in
b12873d, blob 6e8aa1b, with `app/page.tsx` and two landing components citing it
as their source of truth. A copy was cherry-picked into this repo in 0bd5d8a on
the finding that no other repo owned it, and reverted the same day in afb0598
once the front end was found. The path is now gitignored here (756cd4a), because
this repo has produced two stray copies already: the cherry-pick, and before it a
corrupted paste that sat untracked for four days with indentation cascading to
262 leading spaces on one line.

**A search scope is a denominator.** 915afd8 shipped the claim that there is no
other repo and no Next.js front-end source anywhere on this machine. The search
behind it covered `C:\Users\charl\Python\` only. The front end has never been
under `Python\`, so the claim was true over the set searched and false as
published.

This is the same defect class the gate exists to catch. A rate needs its
denominator stated; a superlative needs the population it ranks over printed. An
existence claim is the same shape: "no X exists" is meaningful only against a
stated search scope, and generalising from the set searched to a wider set is
exactly the move that makes a superlative wrong. The gate enforces this for
figures in drafts and nothing enforces it for prose in the briefs, which is where
it happened.

The brief now records the scope rule alongside the corrected topology: state the
scope searched next to the finding, and search `web\` as well as `Python\` before
asserting absence. Worth noting that the correction itself needed correcting.
915afd8 fixed one wrong claim by asserting a wider one.

**CLAUDE.md had been asserting things no part of the repo supported.** Two passes,
349ac86 (eight claims) and 024bfe2 (seven), each item verified against the code
immediately before editing rather than taken from the audit list. The four worst:

A nine-value "Earthy colour palette", phrased as **never change these**, whose
every value returns zero matches repo-wide. The live theme is Midnight Turf, dark,
and `.streamlit/config.toml` has said `base = "dark"` throughout.

MAE figures (0.0904 and the v1 to v3 series) stated as fact, where the brief says
"UNRESOLVED. Do not quote any of them" and `brownlow_model.py` prints the same
numbers under the label "Pre-2026-audit figures", all measured with a momentum
leak in place.

A password gate on the Betting Hub keyed on `bh_authed`. The real gate is an
admin-account check against `ADMIN_UID`; `bh_authed` and `BH_PASSWORD` exist only
in two prose comments and are never read or written.

An instruction that the brief "contains accurate line numbers for every function".
The brief contains none, deliberately: it says "locate code by function name,
never by line number" and records that two earlier briefs carried function tables
and both went stale, the last recon finding one false entry for `dashboard.py` and
six for `betting_hub.py`. CLAUDE.md was directing readers to the one practice both
files forbid.

**Two of the second pass's findings were self-inflicted.** 349ac86 corrected the
palette and the bets storage model in one section and left the same claims
standing in another: the Plotly tech-stack row still said chart backgrounds match
the earthy palette, and the project tree still called `data_betting/` persistent
storage. Both were found by the second audit as though they were pre-existing.

The lesson is procedural. Fixing a claim in the section that owns it does not fix
the claim, because a document repeats itself. 024bfe2 closed with a sweep of the
whole file for every claim fixed in both commits; the only surviving mentions are
refutations that say the claim is false. That sweep should be the last step of any
documentation fix, not an afterthought two commits later.

One correction broke arithmetic that had worked by accident. The Wheelo feature
group is 20, per `wheelo_features.pkl`, not the 18 the file claimed. With 18 the
four listed groups summed to exactly 93; with the correct 20 they sum to 95
against a verified total of 93. Base and Relative game are backed by no artifact,
so rather than invent a split the breakdown is now flagged as approximate with
the artifact-backed counts named.

## Still open

Nine Tier 3 CLAUDE.md items, all single-source. They were found by one agent
whose adversarial verifier died mid-run on a session limit, so nothing has
checked them: the Cha Ching definition (the live checklist flags on a "Take it"
verdict, not on `>= CC_THRESHOLD`), its six named criteria against eight live
ones, seven market types against ten, seven bookmakers against eight, the CSS
"one large block" claim, the card box-shadow, the section-header spec, the
scrollbar colours, and the metric-label weight. Each needs a second read before
it is acted on.

CLAUDE.md's tree and tech stack carry omissions that were left alone
deliberately, being omissions rather than contradictions. The tree omits
`user_auth.py`, 1,110 lines that the brief says drives the entire public/private
split, along with `theme.py`, `features.py`, `club_aliases.py`, four scrapers,
`scripts/`, `data_history/`, `page_modules_wip/` and `.github/`. The tech stack
omits Supabase, which the brief calls the source of truth, plus Playwright and
the Python 3.13-local against 3.10-Cloud version gap the brief says has caused
multiple production failures.

The feature-count breakdown does not sum to 93. Only the total, Wheelo (20) and
Form/Momentum (3) are artifact-backed. Settling Base and Relative game needs a
read of `features.py`, which no session has done.

`data_pull.py` is 0 bytes. CLAUDE.md now says so; **project_brief.md still
describes it as a fetcher in two places**, in the tech-stack R bullet and in the
file-structure tree. The brief is the authority and is currently wrong about it.

token_guide.md exists only in Project Knowledge, not in any of the three repos or
anywhere on this machine. It is stale on three counts by report: a line-number
reference table, a page model naming pages that do not exist, and a
paste-into-chat session model. It cannot be rewritten until it is in the repo.

The Project Knowledge copy of project_brief.md is now several commits behind. The
brief's own header requires re-upload after any edit, and this session edited it
four times.

## What is next

Nothing here blocks launch, and nothing did.

Result posts for the Mullin and Bontempelli previews, three handovers
outstanding. Previews without results are the half of the record that does not
count.

Forum post and the first weekly scorecard, built on the calibration table, which
is the only defensible accuracy surface in the repo.

`fixture_recon_spec.md` carries four unsettled scoping questions: career against
fixture scope on block 7, name-level against name-and-club grouping on block 6,
club alias merging, and current-season exclusion from career rates. They still
block unattended runs.
