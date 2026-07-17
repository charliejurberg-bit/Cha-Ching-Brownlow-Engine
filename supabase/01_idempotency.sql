-- ═══════════════════════════════════════════════════════════════════════════
-- 01_idempotency.sql — Cha Ching / Betting Hub
--
-- ►► RUN THIS BEFORE DEPLOYING COMMIT 1's CODE. ◄◄
--
-- Commit 1 converts the Betting Hub's blind inserts into keyed upserts. An
-- upsert needs its conflict target to be a real unique constraint, so these
-- indexes must exist first or every write errors.
--
-- Run in: Supabase dashboard → SQL Editor.
--
-- This file contains no DELETEs and is safe to run repeatedly. If a CREATE
-- fails because duplicate rows already exist, it fails without changing
-- anything — resolve the duplicates by hand and re-run.
-- ═══════════════════════════════════════════════════════════════════════════


-- ── 1. bets.bet_id and cha_ching_tips.tip_id ───────────────────────────────
--
-- bets.bet_id is expected to be unique already: _save_bets has been upserting
-- on_conflict="bet_id", which only works against an existing unique constraint
-- or primary key. tips is the unknown — its writes were blind inserts, so
-- nothing has ever required tip_id to be unique.
--
-- VERIFY FIRST. Run this and read the result:
--
--   SELECT tablename, indexname, indexdef
--   FROM pg_indexes
--   WHERE schemaname = 'public'
--     AND tablename IN ('bets', 'cha_ching_tips')
--   ORDER BY tablename, indexname;
--
-- You are looking for a UNIQUE index on bets(bet_id) and on
-- cha_ching_tips(tip_id). A PRIMARY KEY on the column counts — it is backed by
-- a unique index and is a valid on_conflict target.
--
-- The two statements below are the create-if-missing fallback. Only run the
-- one for a column the SELECT showed no unique index on.
--
-- ►► IF NOT EXISTS matches on the index NAME, not its definition. Running
--    these blindly when a differently-named unique index already covers the
--    column creates a redundant second index — harmless, but pointless. Read
--    the SELECT output first.

CREATE UNIQUE INDEX IF NOT EXISTS bets_bet_id_key
    ON public.bets (bet_id);

CREATE UNIQUE INDEX IF NOT EXISTS cha_ching_tips_tip_id_key
    ON public.cha_ching_tips (tip_id);


-- ── 2. poll_watchlist — dropped ────────────────────────────────────────────
--
-- This file used to create poll_watchlist_active_player, a partial unique guard
-- on (player, team). The table is gone (see 05_drop_poll_watchlist.sql) and the
-- index went with it, so the CREATE is removed rather than left to fail: it was
-- guarded IF NOT EXISTS on the INDEX, which does nothing about a missing TABLE,
-- and this file promises to be re-runnable.
--
-- Its tenant-scoped successor is user_poll_picks_active_player in 04.


-- ── 3. player_props — nothing to do ────────────────────────────────────────
--
-- _save_prop already upserts on_conflict="game_key,player,market_type", so
-- that unique constraint necessarily already exists. Deliberately untouched.
