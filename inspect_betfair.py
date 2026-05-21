import requests, re

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-AU,en;q=0.9',
}

url = 'https://www.betfair.com.au/hub/sports/afl/brownlow-medal-predictor/'
r = requests.get(url, headers=headers, timeout=15)
print('Status:', r.status_code)
print('Content-Type:', r.headers.get('Content-Type', ''))
print('Len:', len(r.text))
print()

# Check for tables
tables = re.findall(r'<table[^>]*>.*?</table>', r.text, re.DOTALL | re.IGNORECASE)
print(f'Tables found: {len(tables)}')
for i, t in enumerate(tables[:3]):
    print(f'\nTable {i} (first 500 chars):')
    print(t[:500])

# Check first 3000 chars of body content
body = re.search(r'<body[^>]*>(.*?)</body>', r.text, re.DOTALL | re.IGNORECASE)
if body:
    print('\nBody start:')
    print(body.group(1)[:3000])
else:
    print('\nFirst 3000 chars:')
    print(r.text[:3000])
