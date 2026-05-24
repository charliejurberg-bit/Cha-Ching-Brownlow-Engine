-- Run this in the Supabase SQL editor (Dashboard → SQL Editor → New query)

CREATE TABLE IF NOT EXISTS bets (
    bet_id            TEXT PRIMARY KEY,
    date              DATE,
    match             TEXT,
    market_type       TEXT,
    selection         TEXT,
    bookmaker         TEXT,
    odds              FLOAT,
    stake             FLOAT,
    result            TEXT DEFAULT 'Pending',
    profit_loss       FLOAT DEFAULT 0,
    is_cha_ching      BOOLEAN DEFAULT FALSE,
    cha_ching_criteria TEXT DEFAULT '',
    notes             TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS cha_ching_tips (
    tip_id        TEXT PRIMARY KEY,
    game_key      TEXT,
    player        TEXT,
    market_type   TEXT,
    line          FLOAT,
    bookmaker     TEXT,
    odds          FLOAT,
    stake         FLOAT DEFAULT 0,
    criteria_json TEXT DEFAULT '[]',
    is_flagged    BOOLEAN DEFAULT FALSE,
    notes         TEXT DEFAULT '',
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    result        TEXT DEFAULT '',
    profit_loss   FLOAT
);

CREATE TABLE IF NOT EXISTS player_props (
    game_key     TEXT,
    player       TEXT,
    market_type  TEXT,
    line         FLOAT,
    bookmaker    TEXT,
    odds         FLOAT,
    updated_at   TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (game_key, player, market_type)
);

-- Disable RLS (personal app — no multi-user auth needed)
ALTER TABLE bets             DISABLE ROW LEVEL SECURITY;
ALTER TABLE cha_ching_tips   DISABLE ROW LEVEL SECURITY;
ALTER TABLE player_props     DISABLE ROW LEVEL SECURITY;
