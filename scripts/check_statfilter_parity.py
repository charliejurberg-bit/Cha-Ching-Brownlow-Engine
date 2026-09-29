"""check_statfilter_parity.py — the Next.js Stat Filter against the Streamlit one.

    # in the cha-ching-brownlow repo, against this checkout's export:
    ENGINE_LOCAL_DIR=<this repo> npx next build && npx next start -p 3100
    # then, from this repo's root:
    python scripts/check_statfilter_parity.py

Unlike check_site_parity.py this needs the site running, because the Stat
Filter computes in the browser: the export is raw games, not results. For each
filter set below it renders dashboard.py headless (AppTest, slider state
preset) and drives the site with Playwright, then compares matching games,
poll rate, 3-vote rate, average votes, the at-zero baseline, the vote
breakdown and the leading stat. Six sets passed on 28 September 2026.
"""
import os, re, sys, html, json, time, urllib.request

# dashboard.py shows only its "we've moved" screen unless this is set.
os.environ.setdefault("CC_STREAMLIT_LIVE", "1")
sys.path.insert(0, os.getcwd())
from streamlit.testing.v1 import AppTest
from playwright.sync_api import sync_playwright

CASES = [
    ("default", {}, "Either", []),
    ("disp30", {"sf_disp": 30}, "Either", []),
    ("disp30 goals2 win", {"sf_disp": 30, "sf_goals": 2}, "Win only", []),
    ("rating20", {"sf_rating": 20}, "Either", []),
    ("coll disp25", {"sf_disp": 25}, "Either", ["Collingwood"]),
    ("cv8 tackles6 loss", {"sf_cv": 8, "sf_tack": 6}, "Loss only", []),
]
KEYMAP = {"sf_disp": "Min disposals", "sf_goals": "Min goals", "sf_rating": "Min wheelo rating pts",
          "sf_cv": "Min coaches votes", "sf_tack": "Min tackles"}

def pull(txt):
    txt = re.sub(r"\s+", " ", txt)
    def g(p):
        m = re.search(p, txt); return m.group(1) if m else None
    return {
        "games": g(r"Matching games\s*([\d,]+)"), "poll": g(r"Poll rate\s*([\d.]+%)"),
        "three": g(r"3-vote rate\s*([\d.]+%)"), "avg": g(r"Avg votes / game\s*([\d.]+)"),
        "zero": g(r"vs ([\d.]+%) at zero"),
        "bd": g(r"Vote breakdown[^0-9]*([\d,]+ 3-vote [\d,]+ 2-vote [\d,]+ 1-vote [\d,]+ 0-vote [\d,]+ pool)"),
        "title": g(r"(Poll rate rises with [a-z ]+)"),
    }

def streamlit(case):
    name, sl, res, clubs = case
    at = AppTest.from_file("dashboard.py", default_timeout=900)
    at.session_state["page"] = "Stat Filter"; at.session_state["active_hub"] = "brownlow"
    for k, v in sl.items(): at.session_state[k] = v
    at.session_state["sf_result"] = res
    at.session_state["sf_clubs"] = clubs
    at.run()
    if at.exception: return {"error": str(at.exception[0].value)}
    return pull(" ".join(html.unescape(re.sub("<[^>]+>", " ", m.value)) for m in at.markdown))

def site(pg, case):
    name, sl, res, clubs = case
    pg.goto("http://localhost:3100/stat-filter"); pg.wait_for_selector("text=Matching games", timeout=60000)
    for c in clubs:
        pg.locator("input[list='sf-clubs']").fill(c)
    for k, v in sl.items():
        lab = KEYMAP[k]
        inp = pg.locator(f"label:has(span:text-matches('^{lab}', 'i')) input[type=range]")
        inp.evaluate("(el, v) => { const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set; s.call(el, String(v)); el.dispatchEvent(new Event('input', {bubbles:true})); }", v)
    if res != "Either": pg.get_by_label(res).check()
    pg.wait_for_timeout(300)
    return pull(pg.evaluate("() => Array.from(document.querySelector('main').querySelectorAll('*')).filter(e => e.children.length === 0).map(e => e.textContent).join(' ') + ' ' + Array.from(document.querySelector('[class*=breakdown]').children).map(c => c.textContent).join(' ')").replace(" ", " "))

for _ in range(40):
    try: urllib.request.urlopen("http://localhost:3100/stat-filter"); break
    except Exception: time.sleep(1)
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1440, "height": 1200})
    for case in CASES:
        a, s = streamlit(case), site(pg, case)
        diff = {k: (a.get(k), s.get(k)) for k in a if a.get(k) != s.get(k)}
        print(("ok  " if not diff else "DIFF"), case[0], "" if not diff else diff)
        if not diff: print("     ", s["games"], s["poll"], s["three"], s["avg"], "|", s["title"])
    b.close()
