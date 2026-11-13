"""Hold a live stat line against the record book and say what is postable.

Shaped by what actually gets read (memory swamp-tweet-format): a header line
naming the measure and its scope, then a list with the subject in CAPS, or a
rare combination of stats from one game. Narrow club trivia is the floor, so
those tiers still exist but the page hides them by default.

Alert kinds, each a tier:

    ALL-TIME RECORD   the record for a game, every club, every season
    ALL-TIME TOP 10   the value needed to enter the top 10
    COMBO             a line of 2 or 3 stats that has happened 5 times or
                      fewer before (the Jagga Smith post)
    AGE               youngest (or oldest) to have this many in a game: top
                      three, or the youngest since someone 20+ years ago
    EARLY CAREER      most on debut, or most through a player's first 50, 100,
                      150 ... games, career totals inside coverage
    FASTEST           fewest games to a career total (5000 disposals), top 3
    CLUB RECORD       the record for the player's club
    RECORD V OPP      the record against today's opponent      (hidden)
    GROUND RECORD     the record at today's ground              (hidden)
    SEASON HIGH       the season's best game so far             (hidden)
    CAREER HIGH       the player's own best game                (hidden)
    MILESTONE         games from 200, big career totals

Every alert carries `rare`: how many games (or players, for a milestone) in
the archive have matched it, which is what the page sorts by. The rarest
thing happening right now sits at the top whatever its tier.

A single-stat target is DONE once the line reaches it and IN REACH while the
line is on pace for it (value / share of match played), from half time (career
and season highs from three quarter time). FLOOR keeps the desk quiet.
"""
from __future__ import annotations

import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import post_format as pf  # noqa: E402
from features import normalise_name  # noqa: E402

TIERS = ['ALL-TIME RECORD', 'ALL-TIME TOP 10', 'COMBO', 'FASTEST', 'AGE', 'EARLY CAREER', 'CLUB RECORD', 'RECORD V OPP',
         'GROUND RECORD', 'SEASON HIGH', 'CAREER HIGH', 'MILESTONE']

FLOOR = {'Disposals': 30, 'Kicks': 20, 'Handballs': 18, 'Marks': 11, 'Goals': 5,
         'Tackles': 10, 'Clearances': 10, 'Hitouts': 40}
NOUN = {'Disposals': 'disposals', 'Kicks': 'kicks', 'Handballs': 'handballs', 'Marks': 'marks',
        'Goals': 'goals', 'Tackles': 'tackles', 'Clearances': 'clearances', 'Hitouts': 'hitouts',
        'Games': 'games'}
BREAK = {'QT': 'quarter time', 'HT': 'half time', '3QT': 'three quarter time', 'FT': 'full time'}
CAREER_MIN_GAMES = 20

# Combinations: which stats, the step each is rounded down to ("30+", "3+"),
# and the least of each worth naming. Kicks and handballs stay out: they are
# disposals already.
COMBO_STEP = {'Disposals': 5, 'Goals': 1, 'Tackles': 1, 'Clearances': 1, 'Marks': 1, 'Hitouts': 5,
              'Contested Possessions': 5, 'Score Involvements': 1, 'Metres Gained': 50,
              'Intercept Marks': 1, 'Inside 50s': 1, 'Pressure Acts': 5, 'Ground Ball Gets': 1,
              'Goal Assists': 1, 'Rebound 50s': 1, 'Spoils': 1}
COMBO_FLOOR = {'Disposals': 25, 'Goals': 3, 'Tackles': 7, 'Clearances': 7, 'Marks': 8, 'Hitouts': 25}
# Floors for the advanced stats are measured, not chosen: the top 1% of games
# for a single-stat alert, the top 3% for a part of a combination (book p99/p97).
COMBO_RARE = 5      # previous games, at most
COMBO_FROM_HT = 0.5

# Age: rank among players (one entry each, his youngest or oldest such game)
# who reached the same threshold. The top AGE_TOP make the list post; past
# that, only a "since" worth saying: the last younger player AGE_SINCE_GAP
# seasons or more ago.
AGE_TOP = 3
AGE_SINCE_GAP = 20
AGE_MIN_FIELD = 3   # fewer previous players than this and "youngest" means nothing
AGE_FROM_BY = 2003  # stats recorded from this year or earlier (AFLTables'), not the 2012 feed ones
# Early career: running totals people actually count. The rest are in the book.
EARLY_STATS = ['Disposals', 'Kicks', 'Handballs', 'Marks', 'Goals', 'Tackles', 'Clearances', 'Hitouts',
               'Contested Possessions', 'Inside 50s', 'Goal Assists']


class Identity:
    """Feed player -> record book player id, by name and club, then name alone."""

    def __init__(self, players: dict) -> None:
        self.by_name_club, self.by_name, self.by_sur_club = {}, {}, {}
        for pid, p in players.items():
            n = normalise_name(p['name'])
            self.by_name_club.setdefault((n, p['club']), []).append(pid)
            self.by_name.setdefault(n, []).append(pid)
            sur = normalise_name(p['name'].split(' ', 1)[-1])
            self.by_sur_club.setdefault((sur, p['club']), []).append(pid)

    def find(self, name: str, surname: str, club: str) -> str | None:
        n = normalise_name(name)
        for hit in (self.by_name_club.get((n, club)), self.by_name.get(n),
                    self.by_sur_club.get((normalise_name(surname), club))):
            if hit and len(hit) == 1:
                return hit[0]
        return None


class History:
    """Every game in the archive: single-stat rarity and combination counts."""

    def __init__(self, games: pd.DataFrame, book: dict) -> None:
        self.frm = {k: s['from'] for k, s in book['stats'].items()}
        self.season_now = None      # set per snapshot by game_alerts
        self.step = {k: v for k, v in COMBO_STEP.items() if k in book['stats']}
        self.cfloor = {k: COMBO_FLOOR.get(k) or max(self.step[k], int(book['stats'][k]['p97'] // self.step[k] * self.step[k]))
                       for k in self.step}
        self.sorted = {}
        for k, frm in self.frm.items():
            v = games.loc[games.Season >= frm, k].dropna().to_numpy()
            self.sorted[k] = np.sort(v)
        # Ages: only games already at an age alert's lowest threshold.
        self.athr, self.age = {}, {}
        if 'Age' in games.columns:
            for k, frm in self.frm.items():
                if frm > AGE_FROM_BY:
                    continue    # "youngest since 2012" is too short a window to mean much
                step = COMBO_STEP.get(k, 1)
                self.athr[k] = int(np.ceil(floor(book, k) / step) * step)
                f = games[(games.Season >= frm) & games.Age.notna() & (games[k].fillna(0) >= self.athr[k])]
                self.age[k] = f[['ID', 'Player', 'Season', 'Date', 'DOB', 'Age', k]]
        else:
            print('games.pkl has no Age column: rebuild the record book for age alerts')
        # Combinations only ever need games with two stats at their floor.
        c = games[games.Season >= 1965].copy()
        hits = sum((c[k].fillna(0) >= f).astype(int) for k, f in self.cfloor.items())
        self.combo = c[hits >= 2].sort_values(['Season', 'Date'])

    def count_ge(self, stat: str, v: int) -> int:
        a = self.sorted[stat]
        return int(len(a) - np.searchsorted(a, v, side='left'))

    def best_combo(self, line: dict) -> dict | None:
        """The rarest 2 or 3 stat combination in a line, if it is rare enough."""
        th = {k: (line.get(k, 0) // s) * s for k, s in self.step.items()}
        ok = [k for k in self.step if th[k] >= self.cfloor[k]]
        best = None
        for n in (2, 3):
            for ks in combinations(ok, n):
                frm = max(self.frm[k] for k in ks)
                f = self.combo[self.combo.Season >= frm]
                m = np.ones(len(f), dtype=bool)
                for k in ks:
                    m &= f[k].fillna(-1).to_numpy() >= th[k]
                prev = f[m]
                cnt = len(prev)
                # Only a combination rarer than each of its parts alone says
                # anything the single-stat alert does not.
                if cnt > COMBO_RARE or cnt >= min(self.count_ge(k, th[k]) for k in ks):
                    continue
                cand = (cnt, n, {'stats': list(ks), 'th': {k: int(th[k]) for k in ks}, 'count': cnt, 'from': frm,
                                 'prev': [{'player': r.Player, 'club': r['Playing.for'], 'season': int(r.Season)}
                                          for _, r in prev.iterrows()]})
                if best is None or cand[:2] < best[:2]:
                    best = cand
            # A rare pair beats any triple: the more stats a line is cut by,
            # the easier a "first" is to find, and the less it means.
            if best:
                break
        return best[2] if best else None

    def age_rank(self, stat: str, v: int, age: float, me_id) -> list[dict]:
        """Youngest and oldest standing of a line at its threshold (v rounded
        down to the combo step: 54 disposals is judged as 50+)."""
        if stat not in self.age or age is None:
            return []
        step = COMBO_STEP.get(stat, 1)
        th = v // step * step
        if th < self.athr[stat]:
            return []
        f = self.age[stat]
        f = f[f[stat] >= th]
        out = []
        for young in (True, False):
            mine = f[f.ID == me_id] if me_id is not None else f.iloc[:0]
            if young and len(mine) and mine.Age.min() < age:
                continue        # he did it younger himself: nothing new
            others = f[f.ID != me_id] if me_id is not None else f
            per = others.sort_values('Age', ascending=young).drop_duplicates('ID')
            if len(per) < AGE_MIN_FIELD:
                continue
            beat = per[per.Age < age] if young else per[per.Age > age]
            n = len(beat)
            word = 'youngest' if young else 'oldest'
            if not young and n:
                continue        # "2nd oldest" is filler; only the oldest outright
            if n < AGE_TOP:
                state = (word if n == 0 else f'{pf.ordinal(n + 1)} {word}').upper()
                ref = None
            else:
                last = beat.sort_values(['Season', 'Date']).iloc[-1]
                if last.Season > (self.season_now or 9999) - AGE_SINCE_GAP:
                    continue
                state = f'{word} since {int(last.Season)}'.upper()
                ref = {'player': last.Player, 'season': int(last.Season)}
            out.append({'young': young, 'word': word, 'th': int(th), 'n': n, 'state': state, 'ref': ref,
                        'field': len(per), 'list': per.head(AGE_TOP + 2)})
        return out


def holders(rec: dict) -> str:
    by = rec.get('by') or []
    if not by:
        return ''
    seasons: dict[str, list[str]] = {}
    for b in by:
        seasons.setdefault(b['player'], []).append(str(b['season']))
    if len(seasons) > 2:
        return f"{len(seasons)} players"
    joined = lambda xs: xs[0] if len(xs) == 1 else ', '.join(xs[:-1]) + ' and ' + xs[-1]
    return ' and '.join(f"{p}, {joined(s)}" for p, s in seasons.items())


def targets(book: dict, stat: str, club: str, opp: str, venue: str | None,
            season: int, me: dict | None) -> list[dict]:
    s = book['stats'][stat]
    out = []
    if s['all_time']:
        top = s['all_time'][0]
        out.append({'tier': 'ALL-TIME RECORD', 'v': top['v'], 'rec': {'v': top['v'], 'by': [r for r in s['all_time'] if r['v'] == top['v']]}})
    if s.get('top10_cut') is not None:
        out.append({'tier': 'ALL-TIME TOP 10', 'v': s['top10_cut'], 'rec': None})
    for tier, rec in (('CLUB RECORD', s['club'].get(club)), ('RECORD V OPP', s['opponent'].get(opp)),
                      ('GROUND RECORD', s['venue'].get(venue) if venue else None),
                      ('SEASON HIGH', s['season'].get(str(season)))):
        if rec and rec.get('v'):
            out.append({'tier': tier, 'v': rec['v'], 'rec': rec})
    if me and me['games'] >= CAREER_MIN_GAMES and stat in me['best']:
        b = me['best'][stat]
        out.append({'tier': 'CAREER HIGH', 'v': b['v'], 'rec': {'v': b['v'], 'by': [{'player': me['name'], 'season': b['season']}]}})
    return out


def noun(stat: str) -> str:
    return NOUN.get(stat, stat.lower())


def floor(book: dict, stat: str) -> int:
    return FLOOR.get(stat) or int(np.ceil(book['stats'][stat]['p99']))


def judge(v: int, f: float, ts: list[dict], stat: str, fl: int) -> dict | None:
    """The most significant DONE target, else the most significant in reach."""
    if v <= 0 or f <= 0:
        return None
    pace = v / f
    if pace < fl and v < fl:
        return None
    best = None
    for t in ts:
        if v >= t['v']:
            state = 'BROKEN' if v > t['v'] else 'EQUALLED'
            if t['tier'] == 'ALL-TIME TOP 10':
                state = 'ENTERED'
            cand = {**t, 'state': state, 'needs': 0}
        elif f < 1 and pace >= t['v'] and f >= (0.75 if t['tier'] in ('CAREER HIGH', 'SEASON HIGH') else 0.5):
            cand = {**t, 'state': 'IN REACH', 'needs': t['v'] - v}
        else:
            continue
        rank = (TIERS.index(t['tier']), 0 if cand['needs'] == 0 else 1)
        if best is None or rank < best[0]:
            best = (rank, cand)
    return best[1] if best else None


def since(frm: int) -> str:
    return f' since {frm}' if frm > 1897 else ''


def at_label(label: str) -> str:
    return '' if label == 'FT' else f' at {BREAK.get(label, label)}'


def ranked_list(entries: list[dict], live: dict, max_lines: int = 6) -> str:
    """'  54 - Name year' lines with the live player slotted in, in CAPS."""
    rows = [dict(e) for e in entries] + [live]
    rows.sort(key=lambda r: -r['v'])   # stable: the record holders stay ahead on a tie
    i = next(n for n, r in enumerate(rows) if r is live)
    if i < max_lines:
        shown = rows[:max(i + 1, min(4, len(rows)))]
    else:
        shown = rows[:3] + [live]
    lines = []
    for r in shown:
        name = pf.subject(r['player']) if r is live else r['player']
        lines.append(f"  {r['v']} - {name} {r['season']}")
    return '\n'.join(lines)


def tagline(club: str, game: dict) -> str:
    return pf.tags(club, '@AFL', pf.match_tag(game['home'], game['away']))


def record_post(a: dict, stat: str, game: dict, book: dict, season: int) -> str:
    """List shape for the all-time and club tiers, a sentence for the rest."""
    s = book['stats'][stat]
    nn, frm, label = noun(stat), s['from'], a['when']
    live = {'v': a['now'], 'player': a['player'], 'season': season}
    lead = f"{pf.subject(a['player'])} has {a['now']} {nn}{at_label(label)}.\n\n" if a['state'] == 'IN REACH' else ''
    if a['tier'] in ('ALL-TIME RECORD', 'ALL-TIME TOP 10'):
        head = f'Most {nn} in a V/@AFL game{since(frm)}:'
        body = ranked_list(s['all_time'], live)
    elif a['tier'] == 'CLUB RECORD':
        head = f"Most {nn} in a game for {pf.code(a['club'])}{since(frm)}:"
        body = ranked_list(s['club'][a['club']].get('top') or [], live)
    else:
        who = holders(a['rec']) if a.get('rec') else ''
        ctx = {
            'RECORD V OPP': f"The most {nn} in a game against {pf.code(a['opp'])}{since(frm)} is {a['v']} ({who}).",
            'GROUND RECORD': f"The most {nn} in a game at {game['venue_feed']}{since(frm)} is {a['v']} ({who}).",
            'SEASON HIGH': f"The most {nn} in a game this season is {a['v']} ({who}).",
            'CAREER HIGH': f"His career best is {a['v']}.",
        }[a['tier']]
        first = f"{pf.subject(a['player'])}: {a['now']} {nn}{at_label(label)}."
        return pf.clean(f"{first}\n\n{ctx}\n\n{tagline(a['club'], game)}")
    return pf.clean(f"{lead}{head}\n\n{body}\n\n{tagline(a['club'], game)}")


def combo_post(c: dict, player: str, club: str, game: dict, season: int, label: str) -> str:
    parts = [f"{c['th'][k]}+ {noun(k)}" for k in c['stats']]
    crit = ', '.join(parts[:-1]) + ' and ' + parts[-1]
    head = f"V/@AFL games with {crit}{since(c['from'])}:"
    lines = [f"  {p['player']} {p['season']}" for p in c['prev']]
    lines.append(f"  {pf.subject(player)} {season}{' (' + label + ')' if label != 'FT' else ''}")
    return pf.clean(f"{head}\n\n" + '\n'.join(lines) + f"\n\n{tagline(club, game)}")


def ordinal_text(n: int) -> str:
    return pf.ordinal(n)


def age_text(dob: pd.Timestamp, on: pd.Timestamp) -> str:
    """'19y 120d': whole years, then days since the last birthday."""
    y = on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))
    try:
        last = dob.replace(year=dob.year + y)
    except ValueError:          # born 29 February
        last = dob.replace(year=dob.year + y, day=28)
    return f'{y}y {(on - last).days}d'


def game_day(game: dict) -> pd.Timestamp:
    """The match's date in Melbourne, which is the date the archive keeps."""
    t = pd.Timestamp(game.get('utc') or pd.Timestamp.now(tz='UTC'))
    t = t.tz_localize('UTC') if t.tzinfo is None else t
    return t.tz_convert('Australia/Melbourne').tz_localize(None).normalize()


def age_alerts(hist: History, book: dict, pl: dict, me_id, dob, day, base: dict, game: dict,
               season: int, label: str) -> list[dict]:
    """At most one youngest and one oldest alert per player: the stat where
    he ranks highest, the earlier (more read) stat on a tie."""
    if dob is None:
        return []
    age = (day - dob).days / 365.25
    me_txt = age_text(dob, day)
    order = list(book['stats'])
    best = {}
    for stat in order:
        v = pl['stats'].get(stat, 0)
        if v <= 0:
            continue
        for r in hist.age_rank(stat, v, age, me_id):
            key = (r['n'] if r['ref'] is None else AGE_TOP + 1, order.index(stat))
            if r['young'] not in best or key < best[r['young']][0]:
                best[r['young']] = (key, stat, v, r)
    out = []
    for _, stat, v, r in best.values():
        nn, frm = noun(stat), hist.frm[stat]
        crit = f"{r['th']}+ {nn} in a V/@AFL game{since(frm)}"
        if r['ref'] is None:
            rows = [{'age': age_text(x.DOB, pd.Timestamp(x.Date)), 'a': x.Age, 'player': x.Player,
                     'season': int(x.Season)} for x in r['list'].itertuples()]
            rows.append({'age': me_txt, 'a': age, 'player': pf.subject(pl['name']), 'season': season, 'me': True})
            rows.sort(key=lambda x: x['a'], reverse=not r['young'])
            i = next(i for i, x in enumerate(rows) if x.get('me'))
            shown = rows[:max(4, i + 1)]
            body = '\n'.join(f"  {x['age']} - {x['player']} {x['season']}" for x in shown)
            post = f"{r['word'].capitalize()} players with {crit}:\n\n{body}"
            top = rows[1] if i == 0 else rows[0]
            held = f"{top['player']}, {top['age']}"
        else:
            post = (f"{pf.subject(pl['name'])} ({me_txt}) is the {r['word']} player with {crit} "
                    f"since {r['ref']['player']} in {r['ref']['season']}.")
            held = f"{r['ref']['player']}, {r['ref']['season']}"
        out.append({**base, 'tier': 'AGE', 'stat': stat, 'state': r['state'], 'now': v, 'v': f"{r['th']}+",
                    # Ranked like the single-stat alert at this threshold (games
                    # with 40+ hitouts), times his place: youngest of a rare
                    # thing first, never ahead of the record itself.
                    'needs': 0, 'age': me_txt, 'holders': pf.clean(held),
                    'rare': max(1, hist.count_ge(stat, r['th'])) * (r['n'] + 1),
                    'rare_text': (f"{r['state'].lower()} of {r['field'] + 1} players with {r['th']}+ {nn}{since(frm)}, at {me_txt}"
                                  if r['ref'] is None else
                                  f"{r['word']} with {r['th']}+ {nn} since {r['ref']['player']}, {r['ref']['season']}, at {me_txt}"),
                    'post': pf.clean(f"{post}\n\n{tagline(base['club'], game)}")})
    return out


def early_alerts(book: dict, pl: dict, g: int | None, me: dict | None, f: float, base: dict, game: dict,
                 season: int, label: str) -> list[dict]:
    """Most on debut (g = 1), or most through the first g games."""
    early = book.get('early') or {}
    if not g:
        return []
    out = []
    for stat in EARLY_STATS:
        e = early.get(stat)
        lst = (e or {}).get('by_n', {}).get(str(g))
        if not lst:
            continue
        if me and me['debut'] < e['from']:
            continue            # career started before the stat was recorded
        v = pl['stats'].get(stat, 0)
        before = me['totals'].get(stat, 0) if me else 0
        cum, rec = before + v, lst[0]['v']
        if v <= 0:
            continue
        if cum >= rec:
            state, needs = ('BROKEN' if cum > rec else 'EQUALLED'), 0
        elif 0.5 <= f < 1 and before + v / f >= rec:
            state, needs = 'IN REACH', rec - cum
        else:
            continue
        nn, frm = noun(stat), e['from']
        head = (f"Most {nn} on V/@AFL debut{since(frm)}:" if g == 1 else
                f"Most {nn} in a V/@AFL player's first {g} games{since(frm)}:")
        lead = ''
        if state == 'IN REACH':
            lead = (f"{pf.subject(pl['name'])} has {v} {nn} on debut{at_label(label)}.\n\n" if g == 1 else
                    f"{pf.subject(pl['name'])} has {cum} {nn} through {g} games{at_label(label)}.\n\n")
        body = ranked_list(lst, {'v': cum, 'player': pl['name'], 'season': season})
        # 1 for a new record, so it sits beside an all-time record (an
        # equalled one is 1 too) and the tier order puts the all-time first.
        rare = 1 + sum(1 for r in lst if r['v'] >= cum)
        out.append({**base, 'tier': 'EARLY CAREER', 'stat': stat, 'state': state, 'now': cum, 'v': rec,
                    'needs': needs, 'unit': nn if g == 1 else f'{nn}, games 1-{g}',
                    'holders': pf.clean(f"{lst[0]['player']}, {lst[0]['season']}"), 'rare': rare,
                    'rare_text': (f"debut record{since(frm)}" if g == 1 else f"record through {g} games{since(frm)}"),
                    'post': pf.clean(f"{lead}{head}\n\n{body}\n\n{tagline(base['club'], game)}")})
    return out


FASTEST_SHOW = 3    # alert only inside the fastest three
FASTEST_MIN_FIELD = 5   # "fastest of 2 to 9000 hitouts" is a milestone, not a fastest


def fastest_alerts(book: dict, pl: dict, g: int | None, me: dict | None, f: float, base: dict, game: dict,
                   season: int, label: str) -> list[dict]:
    """Fewest games to a career total, when today is the game he gets there
    in and he is among the fastest three."""
    fast = book.get('fastest') or {}
    if not g or not me:
        return []
    out = []
    for stat, marks in fast.items():
        if me['debut'] < marks['from']:
            continue            # career started before the stat was recorded
        v = pl['stats'].get(stat, 0)
        before = me['totals'].get(stat, 0)
        nxt = next((int(m) for m in marks if m != 'from' and int(m) > before), None)
        if nxt is None or v <= 0:
            continue
        cum = before + v
        if cum >= nxt:
            state, needs = 'REACHED', 0
        elif 0.5 <= f < 1 and before + v / f >= nxt:
            state, needs = 'IN REACH', nxt - cum
        else:
            continue
        rec = marks.get(str(nxt))
        if not rec or len(rec['games']) < FASTEST_MIN_FIELD:
            continue
        n = int(np.searchsorted(np.array(rec['games']), g, side='left'))   # strictly fewer games
        if n >= FASTEST_SHOW:
            continue
        tie = n < len(rec['games']) and rec['games'][n] == g
        nn, frm = noun(stat), marks['from']
        rows = [dict(r) for r in rec['top']] + [{'v': g, 'player': pf.subject(pl['name']), 'season': season, 'me': True}]
        rows.sort(key=lambda r: r['v'])       # stable: an equal earlier holder stays ahead
        i = next(i for i, r in enumerate(rows) if r.get('me'))
        body = '\n'.join(f"  {r['v']} - {r['player']} {r['season']}" for r in rows[:max(4, i + 1)])
        lead = (f"{pf.subject(pl['name'])} is {needs} {nn} from {nxt} in game {g}{at_label(label)}.\n\n"
                if state == 'IN REACH' else '')
        # A tie shares the rank: "equal fastest", "=2ND FASTEST", never an
        # outright claim the earlier holder already has.
        word = ('equal ' if tie else '') + ('fastest' if n == 0 else f'{pf.ordinal(n + 1)} fastest')
        state = state if state == 'IN REACH' else ('EQUALLED' if tie and n == 0 else
                                                     ('=' if tie else '') + word.replace('equal ', '').upper())
        out.append({**base, 'tier': 'FASTEST', 'stat': stat, 'state': state, 'now': cum, 'v': f'{nxt} in {g}',
                    'needs': needs, 'unit': f'career {nn}, game {g}',
                    'holders': pf.clean(f"{rec['top'][0]['player']}, {rec['top'][0]['v']} games"),
                    'rare': n + 1,
                    'rare_text': f"{word} of {len(rec['games']) + 1} players to {nxt} {nn}{since(frm)}",
                    'post': pf.clean(f"{lead}Fewest games to {nxt} V/@AFL career {nn}{since(frm)}:\n\n{body}"
                                     f"\n\n{tagline(base['club'], game)}")})
    return out


def milestone_age_note(book: dict, stat: str, m: int, age: float | None, txt: str | None) -> str:
    """', and the youngest to get there (21y 40d)' when he is in the top three."""
    if age is None:
        return ''
    rec = (book.get('milestone_ages') or {}).get(stat, {}).get(str(m))
    if not rec:
        return ''
    ages = np.array(rec['ages'])
    for word, n in (('youngest', int((ages < age).sum())), ('oldest', int((ages > age).sum()))):
        if n < AGE_TOP:
            return f", and the {word if n == 0 else pf.ordinal(n + 1) + ' ' + word} to get there ({txt})"
    return ''


def milestone_alerts(me: dict | None, line: dict, f: float, label: str, base: dict, game: dict,
                     book: dict, age: float | None = None, age_txt: str | None = None) -> list[dict]:
    out = []
    if not me:
        return out
    ms, counts = book.get('milestones', {}), book.get('milestone_counts', {})
    tag = tagline(base['club'], game)
    g = me['games'] + 1
    if g in ms.get('Games', []):
        n = counts.get('Games', {}).get(str(g), 0)
        out.append({**base, 'tier': 'MILESTONE', 'stat': 'Games', 'state': 'TODAY', 'now': g, 'v': g, 'needs': 0,
                    'rare': n, 'rare_text': f'{n} players have reached {g} games',
                    'post': pf.clean(f"{pf.subject(me['name'])} plays game {g} today, the {ordinal_text(n + 1)} V/@AFL player to reach {g}"
                                     f"{milestone_age_note(book, 'Games', g, age, age_txt)}.\n\n{tag}")})
    for stat, marks in ms.items():
        if stat == 'Games' or stat not in line:
            continue
        before = me['totals'].get(stat, 0)
        nxt = next((m for m in marks if m > before), None)
        if nxt is None:
            continue
        now = before + line[stat]
        need = nxt - now
        if need <= 0:
            state = 'REACHED'
        elif 0.5 <= f < 1 and line[stat] / f >= nxt - before:
            state = 'IN REACH'
        else:
            continue
        n = counts.get(stat, {}).get(str(nxt), 0)
        text = (f"{pf.subject(me['name'])} reaches {nxt} career {noun(stat)}{at_label(label)}, the {ordinal_text(n + 1)} V/@AFL player to get there{since(book['stats'][stat]['from'])}"
                f"{milestone_age_note(book, stat, nxt, age, age_txt)}."
                if state == 'REACHED' else
                f"{pf.subject(me['name'])} is {need} {noun(stat)} from {nxt} for his career{at_label(label)}.")
        out.append({**base, 'tier': 'MILESTONE', 'stat': stat, 'state': state, 'now': now, 'v': nxt,
                    'needs': max(need, 0), 'rare': n, 'rare_text': f'{n} players have {nxt}',
                    'post': pf.clean(f"{text}\n\n{tag}")})
    return out


def game_alerts(book: dict, hist: History, ident: Identity, game: dict, lines: list[dict],
                season: int, f: float, label: str, people=None) -> tuple[list[dict], dict]:
    """(alerts, {stat: [top three lines]}) for one match. `people` (feed.People)
    supplies a date of birth and a debut check for players the book lacks."""
    alerts = []
    hist.season_now = season
    day = game_day(game)
    for pl in lines:
        pid = ident.find(pl['name'], pl['surname'], pl['club'])
        me = book['players'].get(pid) if pid else None
        dob = me.get('dob') if me else None
        if dob is None and people is not None and pl.get('feed_id'):
            dob = people.dob(pl['feed_id'])
        dob = pd.Timestamp(dob) if dob else None
        if me:
            g_no = me['games'] + 1
        elif people is not None and pl.get('feed_id') and (people.career_games(pl['feed_id']) or 0) <= 1:
            g_no = 1            # not in the book, and the AFL has him on 0 or 1 games: a debutant
        else:
            g_no = None
        opp = game['away'] if pl['club'] == game['home'] else game['home']
        base = {'player': pl['name'], 'club': pl['club'], 'opp': opp, 'game': game['id'],
                'teams': f"{pf.code(game['home'])} v {pf.code(game['away'])}", 'when': label, 'known': bool(me)}
        for stat in book['stats']:
            v = pl['stats'].get(stat, 0)
            ts = targets(book, stat, pl['club'], opp, game['venue'], season, me)
            j = judge(v, f, ts, stat, floor(book, stat))
            if j:
                a = {**base, **j, 'stat': stat, 'now': v}
                a['post'] = record_post(a, stat, game, book, season)
                a['holders'] = pf.clean(holders(j['rec'])) if j.get('rec') and holders(j['rec']) else ''
                a['rare'] = hist.count_ge(stat, v)
                a['rare_text'] = f"{pf.plural(a['rare'], 'game')} with {v}+ {noun(stat)}{since(book['stats'][stat]['from'])}"
                a.pop('rec', None)
                alerts.append(a)
        if f >= COMBO_FROM_HT:
            c = hist.best_combo(pl['stats'])
            # A combination built on a stat that is already an all-time alert
            # repeats the bigger story; the record post says it better.
            big = {a['stat'] for a in alerts if a['player'] == pl['name'] and a['tier'] in ('ALL-TIME RECORD', 'ALL-TIME TOP 10')}
            if c and not big.intersection(c['stats']):
                crit = ', '.join(f"{c['th'][k]}+ {noun(k)}" for k in c['stats'])
                last = c['prev'][-1] if c['prev'] else None
                alerts.append({**base, 'tier': 'COMBO', 'stat': ' + '.join(c['stats']), 'state': 'DONE',
                               'now': ' / '.join(str(pl['stats'][k]) for k in c['stats']), 'v': crit, 'needs': 0,
                               'holders': pf.clean(f"last: {last['player']}, {last['season']}") if last else 'never before',
                               'rare': c['count'],
                               'rare_text': (f"{ordinal_text(c['count'] + 1)} time{since(c['from'])}" if c['count']
                                             else f"first time{since(c['from'])}"),
                               'post': combo_post(c, pl['name'], pl['club'], game, season, label)})
        age = (day - dob).days / 365.25 if dob is not None else None
        alerts += milestone_alerts(me, pl['stats'], f, label, base, game, book,
                                   age, age_text(dob, day) if dob is not None else None)
        alerts += age_alerts(hist, book, pl, int(pid) if pid else None, dob, day, base, game, season, label)
        alerts += early_alerts(book, pl, g_no, me, f, base, game, season, label)
        alerts += fastest_alerts(book, pl, g_no, me, f, base, game, season, label)
    leaders = {}
    for stat in book['stats']:
        top = sorted(lines, key=lambda p: -p['stats'].get(stat, 0))[:3]
        leaders[stat] = [{'player': p['name'], 'club': p['club'], 'v': p['stats'].get(stat, 0)} for p in top]
    return alerts, leaders


DONE_STATES = ('BROKEN', 'EQUALLED', 'ENTERED', 'REACHED', 'TODAY', 'DONE')


def sort_key(a: dict):
    """Rarest first; on a tie, the more significant tier, then done before in reach."""
    return (a.get('rare', 10**6), TIERS.index(a['tier']), 1 if a['state'] == 'IN REACH' else 0)
