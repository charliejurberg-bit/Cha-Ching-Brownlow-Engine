"""Game Day Desk: one command runs the live poller and serves the page.

    python desk/desk.py                     # this round, live, every 60s
    python desk/desk.py --replay 2026:5     # a finished round, played back
    python desk/desk.py --every 30          # poll faster

Open the printed address on the PC, or the LAN one on a phone on the same
wifi (Windows asks once to let Python through the firewall: allow Private).

Replay plays a finished round back through the same alert code: it takes
each game's final lines and steps through QT, HT, 3QT and FT, scaling every
stat by the share of the match played. That is a test of the plumbing and the
page, not of the alerts' judgement: real games are not linear.

Writes desk/data/live.json, which the page polls. Nothing here posts.
"""
from __future__ import annotations

import argparse
import http.server
import json
import socket
import socketserver
import threading
import time
import traceback
from datetime import datetime, timezone
from functools import partial
from pathlib import Path

import pandas as pd

import alerts as al
from feed import DONE, LIVE, Feed, People, elapsed

HERE = Path(__file__).resolve().parent
DATA = HERE / 'data'
BOOK = DATA / 'record_book.json'
LIVE_JSON = DATA / 'live.json'


def write(payload: dict) -> None:
    tmp = LIVE_JSON.with_suffix('.tmp')
    tmp.write_text(json.dumps(payload))
    tmp.replace(LIVE_JSON)


def load_book() -> tuple[dict, al.History, al.Identity]:
    book = json.loads(BOOK.read_text())
    games = pd.read_pickle(BOOK.with_name(BOOK.stem.replace('record_book', 'games') + '.pkl'))
    return book, al.History(games, book), al.Identity(book['players'])


def snapshot(feed: Feed, book: dict, hist: al.History, ident: al.Identity, season: int, rnd: int, games: list[dict],
             states: dict, lines: dict, mode: str, scale: float | None = None) -> dict:
    out_games, out_alerts = [], []
    for g in games:
        st = states[g['id']]
        if scale is not None:
            f, label = scale, {0.25: 'QT', 0.5: 'HT', 0.75: '3QT', 1.0: 'FT'}[scale]
            pl = [{**p, 'stats': {k: int(round(v * scale)) for k, v in p['stats'].items()}} for p in lines.get(g['id'], [])]
        else:
            f, label = elapsed(st)
            pl = lines.get(g['id'], [])
        card = {'id': g['id'], 'home': g['home'], 'away': g['away'], 'venue': g['venue_feed'],
                'label': label if pl else ('PRE' if (st.get('status') or '').upper() not in DONE else 'FT'),
                'utc': g['utc'], 'score': None if scale is not None else st.get('score'), 'leaders': {}}
        if pl:
            if not hasattr(feed, 'people'):
                feed.people = People(feed)
            a, leaders = al.game_alerts(book, hist, ident, g, pl, season, f, label, feed.people)
            card['leaders'] = leaders
            out_alerts += a
        out_games.append(card)
    out_alerts.sort(key=al.sort_key)
    return {'generated': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'mode': mode, 'season': season, 'round': games[0]['round_name'] if games else f'Round {rnd}',
            'book_through': book['through'], 'games': out_games, 'alerts': out_alerts}


def poll(feed: Feed, book: dict, hist: al.History, ident: al.Identity, season: int, rnd: int | None) -> dict:
    rnd, games = feed.round_matches(season, rnd)
    states, lines = {}, {}
    for g in games:
        status = (g['status'] or '').upper()
        if status in LIVE or status in DONE or status not in ('SCHEDULED', 'UNCONFIRMED_TEAMS', 'CONFIRMED_TEAMS'):
            try:
                states[g['id']] = feed.match_state(g['id'])
                lines[g['id']] = feed.players(g['id'])
            except Exception as e:  # one bad match must not blank the desk
                print(f"  {g['home']} v {g['away']}: {e}")
                states[g['id']] = {'status': status}
        else:
            states[g['id']] = {'status': status}
    return snapshot(feed, book, hist, ident, season, rnd, games, states, lines, 'live')


def run_live(season: int, rnd: int | None, every: int) -> None:
    feed = Feed()
    book, hist, ident = load_book()
    while True:
        try:
            snap = poll(feed, book, hist, ident, season, rnd)
            write(snap)
            print(f"{datetime.now():%H:%M:%S}  {len(snap['games'])} games, {len(snap['alerts'])} alerts")
        except Exception:
            traceback.print_exc()
        time.sleep(every)


def run_replay(season: int, rnd: int, step: int) -> None:
    feed = Feed()
    book, hist, ident = load_book()
    rnd, games = feed.round_matches(season, rnd)
    states = {g['id']: feed.match_state(g['id']) for g in games}
    lines = {g['id']: feed.players(g['id']) for g in games}
    unknown = sum(1 for ls in lines.values() for p in ls if not ident.find(p['name'], p['surname'], p['club']))
    total = sum(len(ls) for ls in lines.values())
    print(f'replaying {games[0]["round_name"]} {season}: {len(games)} games, '
          f'{total - unknown}/{total} players matched to the record book')
    while True:
        for scale in (0.25, 0.5, 0.75, 1.0):
            snap = snapshot(feed, book, hist, ident, season, rnd, games, states, lines, 'replay', scale)
            write(snap)
            print(f"  {snap['games'][0]['label'] if snap['games'] else ''}: {len(snap['alerts'])} alerts")
            time.sleep(step)


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


def serve(port: int) -> None:
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(('0.0.0.0', port), partial(Handler, directory=str(HERE)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('10.255.255.255', 1))
        lan = s.getsockname()[0]
        s.close()
    except OSError:
        lan = None
    print(f'desk:  http://localhost:{port}/web/')
    if lan:
        print(f'phone: http://{lan}:{port}/web/   (same wifi)')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--season', type=int, default=datetime.now().year)
    ap.add_argument('--round', type=int, help="the AFL's round number (Opening Round is 0); default the current one")
    ap.add_argument('--replay', help='SEASON:ROUND, a finished round played back')
    ap.add_argument('--every', type=int, default=60, help='seconds between polls (live) or steps (replay)')
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--book', help='a record book other than desk/data/record_book.json (replay tests)')
    a = ap.parse_args()
    global BOOK
    if a.book:
        BOOK = Path(a.book).resolve()
    if not BOOK.exists():
        raise SystemExit('no record book: run python desk/record_book.py first')
    serve(a.port)
    if a.replay:
        s, r = a.replay.split(':')
        run_replay(int(s), int(r), a.every if a.every != 60 else 20)
    else:
        run_live(a.season, a.round, a.every)


if __name__ == '__main__':
    main()
