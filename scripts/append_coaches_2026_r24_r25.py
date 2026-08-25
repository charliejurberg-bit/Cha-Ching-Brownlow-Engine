"""Append raw rounds 24 and 25 coaches votes, transcribed from afl.com.au.

fitzRoy's feed stops at raw round 23. The AFL publishes the same votes per
round in its "Coaches' votes, R<n>" articles, where the AFL's official round
number is one BEHIND the AFLTables raw Round_num this repo keys on: the AFL's
R23 is raw 24 and its R24 is raw 25.

Sources, both read in full rather than summarised:
  raw 24  https://www.afl.com.au/news/1594982/coaches-votes-r23-nine-perfect-10s-more-votes-for-daicos
  raw 25  https://www.afl.com.au/news/1594993/coaches-votes-r24-daicos-finishes-on-incredible-tally-three-perfect-games

Written in the feed's own schema and spelling. predict_2026.py reconciles feed
spellings against AFLTables via features.resolve_feed_names() and reports what
it cannot match, so names are transcribed as published rather than pre-fixed.
"""

import sys
import pandas as pd

ABBR = {'Adelaide Crows': 'ADEL', 'Brisbane Lions': 'BL', 'Carlton': 'CARL',
        'Collingwood': 'COLL', 'Essendon': 'ESS', 'Fremantle': 'FRE',
        'Geelong Cats': 'GEEL', 'Gold Coast Suns': 'GCFC', 'GWS Giants': 'GWS',
        'Hawthorn': 'HAW', 'Melbourne': 'MELB', 'North Melbourne': 'NMFC',
        'Port Adelaide': 'PORT', 'Richmond': 'RICH', 'St Kilda': 'STK',
        'Sydney Swans': 'SYD', 'West Coast Eagles': 'WCE',
        'Western Bulldogs': 'Western Bulldogs'}
ABBR['Western Bulldogs'] = 'WB'

# (home, away, [(player, club, votes), ...])
R24 = [
    ('Fremantle', 'Adelaide Crows', [
        ('Caleb Serong', 'Fremantle', 10), ('Izak Rankine', 'Adelaide Crows', 8),
        ('Jye Amiss', 'Fremantle', 5), ('Shai Bolton', 'Fremantle', 5),
        ('Josh Treacy', 'Fremantle', 1), ('Jordan Dawson', 'Adelaide Crows', 1)]),
    ('Richmond', 'St Kilda', [
        ('Max Hall', 'St Kilda', 10), ('Bradley Hill', 'St Kilda', 8),
        ('Hugo Garcia', 'St Kilda', 5), ('Mitch Owens', 'St Kilda', 5),
        ('Jack Macrae', 'St Kilda', 2)]),
    ('North Melbourne', 'Geelong Cats', [
        ('Tanner Bruhn', 'Geelong Cats', 10), ('Shaun Mannagh', 'Geelong Cats', 8),
        ('Mark Blicavs', 'Geelong Cats', 5), ('Tristan Xerri', 'North Melbourne', 3),
        ('Jy Simpkin', 'North Melbourne', 3), ('Oliver Dempsey', 'Geelong Cats', 1)]),
    ('Brisbane Lions', 'Gold Coast Suns', [
        ('Will Ashcroft', 'Brisbane Lions', 10), ('Matt Rowell', 'Gold Coast Suns', 4),
        ('Levi Ashcroft', 'Brisbane Lions', 4), ('Zac Bailey', 'Brisbane Lions', 4),
        ('Ned Moyle', 'Gold Coast Suns', 3), ('Touk Miller', 'Gold Coast Suns', 2),
        ('Dayne Zorko', 'Brisbane Lions', 2), ('Logan Morris', 'Brisbane Lions', 1)]),
    ('Hawthorn', 'Collingwood', [
        ('Beau McCreery', 'Collingwood', 10), ('Nick Daicos', 'Collingwood', 7),
        ('Josh Ward', 'Hawthorn', 5), ('Jarman Impey', 'Hawthorn', 3),
        ('Harry Morrison', 'Hawthorn', 2), ('Samuel Swadling', 'Collingwood', 2),
        ('Edward Allan', 'Collingwood', 1)]),
    ('Port Adelaide', 'Melbourne', [
        ('Kade Chandler', 'Melbourne', 10), ('Max Gawn', 'Melbourne', 6),
        ('Bayley Fritsch', 'Melbourne', 5), ('Koltyn Tholstrup', 'Melbourne', 4),
        ('Jack Steele', 'Melbourne', 3), ('Bailey Laurie', 'Melbourne', 2)]),
    ('GWS Giants', 'West Coast Eagles', [
        ('Lachie Ash', 'GWS Giants', 10), ('Lachie Whitfield', 'GWS Giants', 8),
        ('Connor Idun', 'GWS Giants', 5), ('Toby Greene', 'GWS Giants', 3),
        ('Harvey Thomas', 'GWS Giants', 2), ('Callum Brown', 'GWS Giants', 2)]),
    ('Western Bulldogs', 'Carlton', [
        ('Ed Richards', 'Western Bulldogs', 10), ('Tom Liberatore', 'Western Bulldogs', 5),
        ('Patrick Cripps', 'Carlton', 5), ('Oliver Florent', 'Carlton', 4),
        ("James O'Donnell", 'Western Bulldogs', 3), ('Blake Acres', 'Carlton', 3)]),
    ('Essendon', 'Sydney Swans', [
        ('Isaac Heeney', 'Sydney Swans', 10), ('Chad Warner', 'Sydney Swans', 7),
        ('Errol Gulden', 'Sydney Swans', 7), ('Brodie Grundy', 'Sydney Swans', 4),
        ('Will Setterfield', 'Essendon', 2)]),
]

R25 = [
    ('St Kilda', 'Gold Coast Suns', [
        ('Matt Rowell', 'Gold Coast Suns', 9), ('Noah Anderson', 'Gold Coast Suns', 8),
        ('Touk Miller', 'Gold Coast Suns', 4), ('John Noble', 'Gold Coast Suns', 3),
        ('Ned Moyle', 'Gold Coast Suns', 2), ('Bodhi Uwland', 'Gold Coast Suns', 2),
        ('Leo Lombard', 'Gold Coast Suns', 1), ('Max Hall', 'St Kilda', 1)]),
    ('Collingwood', 'Brisbane Lions', [
        ('Logan Morris', 'Brisbane Lions', 10), ('Lachie Neale', 'Brisbane Lions', 8),
        ('Conor McKenna', 'Brisbane Lions', 4), ('Josh Dunkley', 'Brisbane Lions', 4),
        ('Jordan De Goey', 'Collingwood', 3), ('Sam Draper', 'Brisbane Lions', 1)]),
    ('Carlton', 'Fremantle', [
        ('Sam Walsh', 'Carlton', 9), ('Francis Evans', 'Carlton', 7),
        ('Jagga Smith', 'Carlton', 7), ('Ben Ainsworth', 'Carlton', 4),
        ('Oliver Florent', 'Carlton', 3)]),
    ('Melbourne', 'Western Bulldogs', [
        ('Harrison Petty', 'Melbourne', 8), ('Ed Richards', 'Western Bulldogs', 8),
        ('Max Gawn', 'Melbourne', 8), ('Marcus Bontempelli', 'Western Bulldogs', 3),
        ('Matthew Kennedy', 'Western Bulldogs', 2), ('Aaron Naughton', 'Western Bulldogs', 1)]),
    ('Geelong Cats', 'Richmond', [
        ('Bailey Smith', 'Geelong Cats', 10), ('Shaun Mannagh', 'Geelong Cats', 8),
        ('Patrick Dangerfield', 'Geelong Cats', 5), ('Oliver Dempsey', 'Geelong Cats', 4),
        ('Tim Taranto', 'Richmond', 3)]),
    ('Adelaide Crows', 'GWS Giants', [
        ('Izak Rankine', 'Adelaide Crows', 10), ('Jordan Dawson', 'Adelaide Crows', 8),
        ('Taylor Walker', 'Adelaide Crows', 6), ('Jake Stringer', 'GWS Giants', 4),
        ('Riley Thilthorpe', 'Adelaide Crows', 1), ('Ben Keays', 'Adelaide Crows', 1)]),
    ('Essendon', 'Port Adelaide', [
        ('Jase Burgoyne', 'Port Adelaide', 9), ('Nate Caddy', 'Essendon', 8),
        ('Mitch Georgiades', 'Port Adelaide', 7), ('Will Setterfield', 'Essendon', 2),
        ('Ollie Wines', 'Port Adelaide', 2), ('Jordon Sweet', 'Port Adelaide', 1),
        ('Zach Merrett', 'Essendon', 1)]),
    ('Sydney Swans', 'North Melbourne', [
        ('Brodie Grundy', 'Sydney Swans', 9), ('Errol Gulden', 'Sydney Swans', 9),
        ('Callum Mills', 'Sydney Swans', 5), ('Braeden Campbell', 'Sydney Swans', 4),
        ('Tom McCartin', 'Sydney Swans', 2), ('Jesse Dattoli', 'Sydney Swans', 1)]),
    ('West Coast Eagles', 'Hawthorn', [
        ('Will Day', 'Hawthorn', 9), ('Connor MacDonald', 'Hawthorn', 9),
        ('Jack Gunston', 'Hawthorn', 5), ('Josh Ward', 'Hawthorn', 4),
        ('Milan Murdock', 'West Coast Eagles', 2), ('Blake Hardwick', 'Hawthorn', 1)]),
]

# Published season leaderboards, used as the acceptance test rather than as data.
LEADER_R24 = {'Nick Daicos': 147, 'Marcus Bontempelli': 106, 'Max Gawn': 91,
              'Will Ashcroft': 91, 'Isaac Heeney': 84, 'Patrick Cripps': 81,
              'Luke Jackson': 77, 'Jason Horne-Francis': 75, 'Bailey Smith': 75,
              'Jai Newcombe': 74, 'Kysaiah Pickett': 73}
LEADER_R25 = {'Nick Daicos': 147, 'Marcus Bontempelli': 109, 'Max Gawn': 99,
              'Will Ashcroft': 91, 'Bailey Smith': 85, 'Isaac Heeney': 84,
              'Patrick Cripps': 81, 'Jordan Dawson': 80, 'Brodie Grundy': 79,
              'Luke Jackson': 77}


def rows_for(rnd, games):
    out = []
    for home, away, votes in games:
        total = sum(v for _, _, v in votes)
        if total != 30:
            raise ValueError(f"round {rnd} {home} v {away}: votes sum to {total}, "
                             f"not 30. AFLCA awards 5-4-3-2-1 from each of two "
                             f"coaches, so every game totals exactly 30")
        for player, club, v in votes:
            out.append({'Season': 2026, 'Round': rnd, 'Home.Team': home,
                        'Away.Team': away,
                        'Player.Name': f"{player} ({ABBR[club]})",
                        'Coaches.Votes': v})
    return out


def main():
    new = pd.DataFrame(rows_for(24, R24) + rows_for(25, R25))
    cur = pd.read_csv('data_2026/coaches_votes_2026.csv')
    if cur['Round'].max() >= 24:
        print(f"FAIL  file already holds round {int(cur['Round'].max())}; refusing "
              f"to append a second copy")
        return 1

    out = pd.concat([cur, new], ignore_index=True)
    tot = (out.assign(n=out['Player.Name'].str.extract(r'^(.+?)\s*\(')[0].str.strip())
              .groupby('n')['Coaches.Votes'].sum())

    bad = []
    for who, want in LEADER_R25.items():
        got = int(tot.get(who, 0))
        if got != want:
            bad.append(f"{who}: built {got}, AFL published {want}")
    thru24 = (out[out['Round'] <= 24]
              .assign(n=lambda d: d['Player.Name'].str.extract(r'^(.+?)\s*\(')[0].str.strip())
              .groupby('n')['Coaches.Votes'].sum())
    for who, want in LEADER_R24.items():
        got = int(thru24.get(who, 0))
        if got != want:
            bad.append(f"[thru r24] {who}: built {got}, AFL published {want}")

    if bad:
        print("FAIL  built totals disagree with the published leaderboard:")
        for b in bad:
            print('   ', b)
        return 1

    out.to_csv('data_2026/coaches_votes_2026.csv', index=False)
    print(f"OK  appended {len(new)} rows for rounds 24 and 25 "
          f"({len(out)} total, rounds {out['Round'].min()} to {out['Round'].max()})")
    print(f"    every game totals 30; all {len(LEADER_R24) + len(LEADER_R25)} "
          f"published leaderboard figures reconcile exactly")
    return 0


if __name__ == '__main__':
    sys.exit(main())
