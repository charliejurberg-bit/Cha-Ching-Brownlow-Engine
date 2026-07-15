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


-- ── 2. poll_watchlist: one active row per (player, team) ───────────────────
--
-- This is a GUARD ONLY. It is never an on_conflict target — PostgREST cannot
-- target a partial index, and does not need to here: _save_polls_row upserts
-- on id, and Commit 1 makes that id stable per form instance so a double
-- submit collapses onto one row.
--
-- What this index catches is the other case: the same player added to the
-- watchlist twice in separate sittings while the first entry is still open.
-- The app catches the resulting unique violation and shows a quiet "already
-- watching this player" message instead of a traceback.
--
-- Settled rows are exempt (WHERE settled = false), so re-watching a player
-- after an earlier entry is settled stays legal.
--
-- SURFACE DUPLICATES FIRST. This must return zero rows or the CREATE below
-- will fail:
--
--   SELECT player, team, count(*) AS n, array_agg(id) AS ids
--   FROM public.poll_watchlist
--   WHERE settled = false
--   GROUP BY player, team
--   HAVING count(*) > 1
--   ORDER BY n DESC;
--
-- If it returns rows, settle or remove the extras by hand, then re-run this
-- file. No DELETEs are issued here on purpose.

CREATE UNIQUE INDEX IF NOT EXISTS poll_watchlist_active_player
    ON public.poll_watchlist (player, team)
    WHERE settled = false;


-- ── 3. player_props — nothing to do ────────────────────────────────────────
--
-- _save_prop already upserts on_conflict="game_key,player,market_type", so
-- that unique constraint necessarily already exists. Deliberately untouched.
