"""Find club-site articles in an id window by title, for recovering AFLW votes.

    python aflw/scan_club_articles.py <first id> <last id> [club domain ...]

Every AFL club site runs on one platform with one shared article-id sequence,
and each site serves only its own ids (anything else returns the generic
"Official AFL Website of ..." title with HTTP 200). So the articles a club
published on a count night sit in a narrow id window across all 18 sites, and
scanning that window per site by title finds them. Prints id, domain and title
for every title that mentions votes, W Awards or best and fairest. Eight
requests in flight at most.
"""
import html
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import requests

CLUBS = ["afc.com.au", "lions.com.au", "carltonfc.com.au", "collingwoodfc.com.au",
         "essendonfc.com.au", "fremantlefc.com.au", "geelongcats.com.au", "goldcoastfc.com.au",
         "gwsgiants.com.au", "hawthornfc.com.au", "melbournefc.com.au", "nmfc.com.au",
         "portadelaidefc.com.au", "richmondfc.com.au", "saints.com.au", "sydneyswans.com.au",
         "westcoasteagles.com.au", "westernbulldogs.com.au"]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140 Safari/537.36"}
KEEP = re.compile(r"(?i)vote|w awards|best (and|&) fairest|fairest (and|&) best|b&f|polled|club champion")


def title(domain, i):
    """(id, domain, title), retried with backoff: under load the sites drop
    connections and answer 429/5xx, which the first scan silently lost."""
    import time
    for attempt in range(4):
        try:
            r = requests.get(f"https://www.{domain}/news/{i}/x", headers=UA, timeout=20)
            if r.status_code == 200:
                m = re.search(r"<title>(.*?)</title>", r.text, re.S)
                return i, domain, html.unescape(m.group(1).strip()) if m else ""
        except requests.RequestException:
            pass
        time.sleep(2 * (attempt + 1))
    return i, domain, "ERR"


def main():
    lo, hi = int(sys.argv[1]), int(sys.argv[2])
    clubs = sys.argv[3:] or CLUBS
    jobs = [(d, i) for d in clubs for i in range(lo, hi + 1)]
    with ThreadPoolExecutor(8) as ex:
        for i, d, t in ex.map(lambda a: title(*a), jobs):
            if t and not t.startswith("Official AFL Website") and KEEP.search(t):
                print(f"{i}\t{d}\t{t}", flush=True)


if __name__ == "__main__":
    main()
