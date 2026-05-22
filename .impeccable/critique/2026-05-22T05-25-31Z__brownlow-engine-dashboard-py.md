---
timestamp: 2026-05-22T05-25-31Z
slug: brownlow-engine-dashboard-py
---
# Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | Nav dropdowns never show which page you're on |
| 2 | Match System / Real World | 3 | AFL terminology natural; minor model-stat leakage in body copy |
| 3 | User Control and Freedom | 2 | No current-position indicator; nav resets to null after each use |
| 4 | Consistency and Standards | 1 | Two competing CSS systems; side stripes in six places |
| 5 | Error Prevention | 2 | Good data fallbacks; CURRENT_ROUND hardcoded maintenance trap |
| 6 | Recognition Rather Than Recall | 2 | Dropdowns require memorising what is inside each of six categories |
| 7 | Flexibility and Efficiency | 2 | Streamlit ceiling limits shortcuts |
| 8 | Aesthetic and Minimalist Design | 1 | Eight simultaneous entrance animations; gradient text on banner; CSS war |
| 9 | Error Recovery | 2 | Generic st.error(); cached-data fallback works but messaging is vague |
| 10 | Help and Documentation | 1 | No tooltips, no contextual help, no inline labels |
| **Total** | | **18/40** | **Poor** |

## Anti-Patterns Verdict

Gradient text confirmed: .cha-ching-title (lines 441-458). Side-stripe borders confirmed: six locations. Bounce easing confirmed: cubic-bezier(0.34,1.56,0.64,1) at lines 722, 825, 915. CSS conflict confirmed: inject_global_css() vs old earthy st.markdown() block vs _TABLE_STYLES.

## Priority Issues

[P0] CSS Architecture War — inject_global_css() dark Midnight Turf vs old earthy st.markdown() block (lines 279-919) vs _TABLE_STYLES earthy row colors (line 1635). Three CSS systems competing.

[P1] Gradient Text on Persistent Banner — .cha-ching-title background-clip:text + titleShimmer 5s infinite on every page.

[P1] Side-Stripe Border Proliferation — Six instances: .metric-card-primary, .leader-card, .title-bar, .section-header::before, _apply_team_border(), four inline Home mt-cards.

[P1] Navigation Has No Current-Page State — All six selectboxes reset to index=None after navigation. No orientation.

[P1] Hardcoded CURRENT_ROUND — Line 1881. Should derive from game_df['Round_num'].max().

[P2] Bounce Easing — cubic-bezier(0.34,1.56,0.64,1) on landing-card hover, toastIn, numberPop.

[P2] Animation Saturation — Eight simultaneous entrance animations on every page load.

## Persona Red Flags

Alex: Three interactions per page change; 200px banner on every analysis view; weekly CURRENT_ROUND update trap; animations delay data access.

Sam: prefers-reduced-motion not respected; sidebar contrast ~3.2:1 below WCAG AA; gradient text has zero accessible color; red semantic applied to neutral Round counter.

Riley: Landing cards have cursor:pointer but are not clickable; only the button below works. Animation restarts on every Streamlit rerender.

## Minor Observations

Double "Cha Ching" heading on Home page. Red border on neutral Round metric card. _apply_team_border() adds stripe to every leaderboard row. Scrollbar styles conflict between CSS blocks.
