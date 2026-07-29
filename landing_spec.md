# Cha Ching — Landing Page Visual Spec

A framework-agnostic description of the public landing page. It describes the
rendered result only — no implementation details. Rebuild it in whatever markup
and CSS your stack uses.

The page is a single centred column on a very dark navy canvas. Blocks stack
vertically in this order, full page width unless a max-width is given:

1. Ticker bar (animated, edge to edge)
2. Account control (small, right-aligned)
3. Hero (animated field line-art + wordmark + top-3 chips)
4. Stat strip (four cells)
5. Two destination cards (side by side)
6. Model footer (thin, centred)
7. Responsible-gambling footer (full-bleed) — see the flagged section

---

## Global design tokens

**Canvas / background:** `#0a1017` (near-black navy). This is the page base behind
everything.

**Palette:**
| Token | Hex / value | Used for |
|---|---|---|
| Background | `#0a1017` | page + stat-strip cells |
| Surface | `#101a24` | chips, cards (top of gradient), account chip |
| Surface-2 | `#0d141d` | ticker bar bg, cards (bottom of gradient) |
| Hairline | `rgba(140,165,185,.14)` | all thin borders / dividers |
| Emerald | `#34d399` | Brownlow accent, leader value, "CHING" gradient start |
| Emerald-dim | `rgba(52,211,153,.12)` | Brownlow tag background |
| Gold | `#f0b429` | betting/live accent, "Votes Clear", ticker digits |
| Gold-dim | `rgba(240,180,41,.12)` | Live-tracking tag background |
| Text | `#e9eef3` | primary values / headings |
| Muted | `#7e8c99` | labels, subtitles, secondary text |

**Standard easing** used by almost every animation: `cubic-bezier(0.23, 1, 0.32, 1)`.

**Fonts (two families only):**
- **Archivo** — a variable sans (weights 400–900, width axis 62.5–125). Used for
  the wordmark, card headings, badges, buttons, big stat values context.
- **IBM Plex Mono** — weights 400 / 500 / 600. Used for all labels, eyebrows,
  chip text, ticker, footer, data rows.

---

## 1. Ticker bar

A single horizontal strip, full page width, **40px tall**, flush to the top.

- Background `#0d141d`; **1px bottom border** `rgba(140,165,185,.14)`. Content clips
  (no visible scrollbar).
- Text: **IBM Plex Mono, 11px, UPPERCASE, letter-spacing 0.08em, colour `#7e8c99`**,
  vertically centred (11px top/bottom padding).
- The whole line scrolls **right-to-left continuously**: it translates from 0 to
  −50% over **38s, linear, infinite loop**. The content string is duplicated
  end-to-end so the wrap is seamless.
- **Leading label** (in **gold `#f0b429`, weight 500**): `MODEL 3-2-1 · R{round}`
  where `{round}` is the live round number.
- Then, per game of the latest round, an item of the form:
  `HOME v AWAY  3 Surname  2 Surname  1 Surname`
  — the team codes are 3-letter uppercase abbreviations; the **digits 3 / 2 / 1 are
  gold `#f0b429`**, the surnames are default `#7e8c99`.
- Items are separated by ` · ` (a gold-free middot with surrounding spaces).
- **Fallback** when there is no game data: the ticker shows just `MODEL 3-2-1 PROJECTIONS`.

## 2. Account control

A small control pinned to the **right** (sits in the right ~40% of the width,
below the ticker). It is either a "Sign in" button, or — when signed in — an
account chip followed by a "Sign out" button. It is **hidden entirely** if auth
isn't configured. Peripheral; style to match but it is not a focal element.

- **Account chip:** background `#101a24`, **1px border `#1a2632`**, fully rounded
  (`border-radius: 999px`), padding `3px 12px 3px 3px`, 8px gap.
  - **Avatar:** 24×24 circle, background `#0f3d31`, colour emerald `#34d399`,
    Archivo 800 / 11px, a single uppercase initial. *Admin variant:* avatar
    background `#3d3110`, colour gold `#f0b429`.
  - **Name:** Archivo 12px / 600, colour `#b8c4ce`, truncates with ellipsis.
  - On narrow screens the name is hidden and only the avatar shows.

## 3. Hero

A tall centred block, **440px tall**, content clipped. Contains an animated
line-drawing of an AFL field behind centred text.

**Background field art (SVG line-art, decorative):**
- Sits absolutely behind the content at **50% opacity**.
- All strokes: `rgba(126,156,178,.32)`, **stroke-width 1.1**, no fill.
- Every shape animates a **"draw-on"**: the stroke dashes in from nothing to full
  over **2.4s** on the standard easing, once (`forwards`). Shapes are grouped and
  staggered by delay: group 1 @ 0s, group 2 @ 0.25s, group 3 @ 0.5s, group 4 @ 0.75s.
- Shapes, in an 1000×600 viewport, centred: a large **ellipse** (outer boundary),
  a **centre square (diamond) + centre circle + centre dot**, two **50m arcs**
  (left and right), and two small **goal-square rectangles** at far left/right.
- Respects reduced-motion: with it on, shapes appear fully drawn, no animation.

**Foreground content** (centred column, max-width 900px, 24px side padding). Each
of the first three elements **rises + fades in** (translateY 14px → 0, opacity
0 → 1) over 650ms, staggered: eyebrow @ 0.2s, wordmark @ 0.32s, subtitle @ 0.44s.

- **Eyebrow:** IBM Plex Mono, **11px, UPPERCASE, letter-spacing 0.34em**, colour
  **emerald `#34d399`**, 8px bottom margin.
  Copy: `BROWNLOW PREDICTOR · THROUGH ROUND {round}`
- **Wordmark:** the words **`CHA CHING`**. Archivo **900**, width axis 122, size
  `clamp(44px, 9vw, 110px)`, line-height 0.94, no wrap.
  - `CHA` fills with a vertical gradient **`linear-gradient(180deg, #ffffff, #9fb3c4)`**
    (white → cool grey), clipped to the text.
  - `CHING` fills with **`linear-gradient(120deg, #34d399, #f0b429)`** (emerald →
    gold), clipped to the text.
- **Subtitle:** 15px, colour `#7e8c99`, margin `14px 0 26px`.
  Copy: `Everything you need for an edge on Brownlow night.`
- **Chips label:** IBM Plex Mono, **10px / 700, UPPERCASE, letter-spacing 0.18em**,
  colour `#7e8c99`, 10px bottom margin, fades in @ 0.4s.
  Copy: `ROUND {round} · MOST LIKELY TO POLL`
- **Three chips** in a centred row, 10px gap, no-wrap (wraps below 700px width).
  Each chip:
  - background `#101a24`, **1px border `rgba(140,165,185,.14)`**, fully rounded
    (`border-radius: 999px`), padding `10px 18px 10px 10px`, 8px internal gap.
  - Chips **animate in** (translateY 10px + scale 0.97 → rest) over 500ms with
    staggered delays: **chip 3 @ 0.6s, chip 2 @ 1.0s, chip 1 @ 1.5s** (rank 1
    lands last). Chips 2 and 3 settle at **opacity 0.85** (dimmed); chip 1 at full.
  - **Rank badge:** 30×30, border-radius 6px, Archivo 800 / 14px.
    - Badge 1: background emerald `#34d399`, text `#0a1017`.
    - Badge 2: background `#3a4753`, text `#e9eef3`.
    - Badge 3: background `#1c2530`, text `#7e8c99`.
  - **Name:** IBM Plex Mono 12px / 600, colour `#e9eef3`. Format is initial + rest
    of name, e.g. `N. Daicos`.
  - **Stats (after name):** IBM Plex Mono 11px, colour `#7e8c99`. Format
    `· TEAM · X.X` — a 3-letter uppercase team code and the projected votes to one
    decimal.

## 4. Stat strip

A **four-cell grid**, one row, max-width 1180px, centred. The 1px grid gap is the
hairline colour `rgba(140,165,185,.14)` showing through (cells sit on a hairline
background), producing thin dividers between cells.

- Each cell: background `#0a1017`, padding `26px 30px`, contents left-aligned in a
  column, 8px gap.
- **Label** (top of cell): IBM Plex Mono, **10px, UPPERCASE, letter-spacing 0.22em**,
  colour `#7e8c99`.
- **Value** (below label): IBM Plex Mono **600, 28px**, colour `#e9eef3`,
  letter-spacing 0.02em — except where noted.
- The four cells, left to right:
  1. **Round** → the round number.
  2. **Current Leader** → leader's full name; **value colour emerald `#34d399`**.
  3. **Predicted Votes** → the leader's projected total, one decimal. This value
     **counts up from `0.0`** to the target over **1400ms (starting after a 700ms
     delay)**, ease-out. With reduced-motion it just shows the final number.
  4. **Votes Clear** → the leader's margin over 2nd, pre-formatted like `+7.5`;
     **value colour gold `#f0b429`**.
- **Below 500px wide:** collapses to a **2-column** grid, cell padding `16px 14px`,
  value size `clamp(18px, 5vw, 28px)`, and the leader name ellipsises rather than
  clipping.

## 5. Destination cards

**Two cards side by side** (equal width, medium gap), stacking on narrow screens.

**Shared card style:**
- Background **`linear-gradient(180deg, #101a24 0%, #0d141d 100%)`**, **1px border
  `rgba(140,165,185,.14)`**, **border-radius 14px**, padding `34px 32px 30px`,
  min-height 360px, content clips, laid out as a column.
- A **2px accent bar across the very top** of the card (full width):
  - Card 1: `linear-gradient(90deg, transparent, #34d399, transparent)` (emerald).
  - Card 2: `linear-gradient(90deg, transparent, #f0b429, transparent)` (gold).
- **Hover** (pointer devices only): lifts `translateY(-4px)`, border tints to the
  card's accent at 0.35 alpha, and gains a soft shadow
  `0 12px 32px rgba(accent,.10)`. Transition 220ms on the standard easing.

**Tag (pill at top of card body):** inline pill, IBM Plex Mono **10px / 700,
UPPERCASE, letter-spacing 0.22em**, padding `5px 11px`, border-radius 99px, 16px
bottom margin. It carries a **6px pulsing dot** on its left (dot is the tag's own
colour, opacity pulses 1 ↔ 0.35 over 2.2s, infinite).
- Card 1 tag: background `rgba(52,211,153,.12)`, colour emerald `#34d399`.
- Card 2 tag: background `rgba(240,180,41,.12)`, colour gold `#f0b429`.

**Heading (h2):** Archivo **800, 30px**, colour `#e9eef3`, 8px bottom margin.

**Description:** colour `#7e8c99`, 14px, line-height 1.6, 18px bottom margin,
max-width 42ch.

**Data row** (near card bottom): a horizontal, wrapping row of label/value pairs,
separated from the description by a **1px top border (hairline)**, 18px top padding,
gaps `8px 26px`, IBM Plex Mono. Each pair is a small column (5px gap):
- Label: 10px, UPPERCASE, letter-spacing 0.18em, colour `#7e8c99`.
- Value: 14px / 600, colour `#e9eef3`.

**Button** (bottom of card): auto-width inline button, padding `12px 22px`,
border-radius 9px, Archivo **700 / 14px**, 16px top margin. A **`→` arrow follows
the label** and nudges 3px right on hover. Pressing scales to 0.97.
- Card 1 button: background emerald `#34d399`, text `#062b1d`; hover brightens ×1.1.
- Card 2 button: background gold `#f0b429`, text `#3a2a05`; hover brightens ×1.08.

**Card 1 — Brownlow Engine** (emerald):
- Tag: `Prediction Engine`
- Heading: `Brownlow Engine`
- Description: `Vote projections for every player in every game. Live leaderboard, player profiles, comparison tools and more.`
- Data row: `Leader` → leader name · `Proj. Votes` → total (1 dp) · `Best Odds` →
  a price like `$1.5` **(see flagged section — this is market data)**.
- Button: `Open Leaderboard`

**Card 2 — Personalised Tracker** (gold):
- Tag: `Live Tracking`
- Heading: `Personalised Tracker`
- Description: `Your picks, your players, live on the night. Track head-to-heads and watch your watchlist settle as the votes are read.`
- Data row: `Brownlow Night` → `Sept 21` · `Countdown` → a value like `62 days`,
  rendered in **gold**.
- Button: `Open Live Tracker`

## 6. Model footer

A thin centred line, separated from the content above by a **1px top border
`rgba(140,165,185,.14)`**, 40px top margin, `14px 0` padding.
- IBM Plex Mono, **11px, UPPERCASE, letter-spacing 0.18em, weight 500**, colour
  `#7e8c99`, centred. Middots (` · `) between segments.
- Copy: `MODEL V4.0 · DATA 2007–2025 · 93 FEATURES · MAE 0.095`
  (the year range is live — see below; the rest is fixed text).

---

## Live data vs hardcoded

**Live / computed at render (do NOT hardcode — wire to a data source):**
- **Round number** — appears in the ticker leading label, the hero eyebrow, the
  hero chips label, and the stat-strip "Round" cell. (Derived from the latest
  round of the current season's data; the displayed number is one less than the
  raw source round.)
- **Ticker game items** — per game of the latest round: the two team codes and the
  model's projected 3-2-1 (three surnames). Falls back to the static text
  `MODEL 3-2-1 PROJECTIONS` when unavailable.
- **Hero chips (top 3)** — the three player names, team codes, and projected-vote
  numbers for the latest round's most-likely pollers. **Placeholder fallback** if
  the latest round has fewer than 3 players: `N. Neale · BRI · 2.4`,
  `K. Pickett · MEL · 1.8`, `L. Morris · BRI · 1.3` (rank 1/2/3 respectively).
- **Stat strip:** Current Leader (name), Predicted Votes (total, animated),
  Votes Clear (margin over 2nd).
- **Card 1 data row:** Leader, Proj. Votes, Best Odds.
- **Card 2 Countdown** — days until Brownlow night (target date 21 Sep 2026);
  shows `N days`, `1 day`, `Tonight`, or an em dash (`—`) once past.
- **Footer year range** (`2007–2025`) — read from the training data's season span.
- **Account control** — presence/content depends on auth + signed-in user.

**Hardcoded (safe to treat as static copy):**
- All labels/eyebrows/headings/descriptions and the two tag texts.
- Wordmark `CHA CHING`; subtitle `Everything you need for an edge on Brownlow night.`
- Chips label `MOST LIKELY TO POLL`; ticker/stat cell labels.
- Card 2 `Brownlow Night` value `Sept 21`.
- Footer fixed segments: `MODEL V4.0`, `93 FEATURES`, `MAE 0.095`.
- Any em dash (`—`) shown when a live value is missing.

Note on empty states: leader/odds/countdown each fall back to an em dash `—` when
their live value is absent, rather than hiding the element.

---

## ⚠️ Betting / gambling / P&L elements — DO NOT fold into the main build

These are the only money/market-adjacent elements. Keep them isolated and treat
each as an explicit product decision, not incidental styling.

1. **"Best Odds" value in Card 1's data row** — a market price (e.g. `$1.5`). This
   is bookmaker odds data, not a model output. It is the one betting-market value
   on the page. If your target build must avoid surfacing odds, omit this single
   data point; the rest of Card 1 stands without it.

2. **Full-bleed responsible-gambling footer** — a separate strip **below** the
   model footer, edge-to-edge, that IS present on this page. Background `#101a24`,
   **1px top border** `rgba(140,165,185,.14)`, padding `16px 20px`, centred,
   IBM Plex Mono, colour `#7e8c99`. Three stacked lines:
   - `18+ · GAMBLE RESPONSIBLY` — 11px, UPPERCASE, letter-spacing 0.18em, weight
     600, colour `#8ca5b9`.
   - `Gambling Help Online · 1800 858 858 · gamblinghelponline.org.au` — 11px.
   - `Cha Ching provides statistical analysis for informational and entertainment
     purposes only. It is not betting advice.` — 10px, colour `#5f6f7d`, max-width 640px.
   If your build carries any odds/betting affordance, this footer (or an
   equivalent) must ship with it.

3. **Card 2 naming vs behaviour — read before wiring.** Card 2's tag colour is
   gold and its internal identifiers use a "betting hub"/"bh" lineage, but the
   card as specified is **not** a betting surface: it is the public "Personalised
   Tracker" (live vote tracking on the night) and its button opens a Live Tracker,
   not a betting hub. **No P&L, no wagers, no balances appear on this card or
   anywhere on the landing page.** An earlier version of this area showed a blurred
   profit/loss figure behind a padlock and a betting-hub card; **that has been
   removed** — do not reintroduce a P&L tile, padlock/locked-teaser, or betting-hub
   entry point when rebuilding. If the destination for Card 2 in your app is a
   gambling feature, that is a new product decision to make explicitly, not a
   default inherited from this spec.
