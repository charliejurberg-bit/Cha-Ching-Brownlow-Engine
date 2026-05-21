import requests, re
from bs4 import BeautifulSoup

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-AU,en;q=0.9',
}

url = 'https://www.betfair.com.au/hub/sports/afl/brownlow-medal-predictor/'
r = requests.get(url, headers=headers, timeout=15)
soup = BeautifulSoup(r.text, 'html.parser')

tables = soup.find_all('table')
print(f'Total tables: {len(tables)}')

# Parse first 5 tables
for i, table in enumerate(tables[:5]):
    rows = table.find_all('tr')
    print(f'\n--- Table {i} ({len(rows)} rows) ---')
    for row in rows:
        cells = row.find_all('td')
        vals = [c.get_text(strip=True) for c in cells]
        print(' | '.join(vals))

# Now try to build a full vote tally
votes = {}
for table in tables:
    rows = table.find_all('tr')
    if not rows:
        continue
    # First row = game header
    for row in rows[1:]:
        cells = row.find_all('td')
        if len(cells) >= 2:
            player = cells[0].get_text(strip=True)
            try:
                v = int(cells[1].get_text(strip=True))
                if v in (1, 2, 3) and player and len(player) > 2:
                    votes[player] = votes.get(player, 0) + v
            except ValueError:
                pass

import pandas as pd
df = pd.DataFrame(list(votes.items()), columns=['Player', 'Betfair_Votes'])
df = df.sort_values('Betfair_Votes', ascending=False).reset_index(drop=True)
print('\n\nTop 20 Betfair predictions:')
print(df.head(20).to_string(index=False))
