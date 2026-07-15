-- ═══════════════════════════════════════════════════════════════════════════
-- 03_user_watchlists.sql — Cha Ching / public user accounts
--
-- ►► RUN AFTER 02_rls_lockdown.sql. ◄◄
--
-- This is the FIRST table in this project that anon/authenticated may touch.
-- It does not weaken 02 in any way: bets, cha_ching_tips, poll_watchlist and
-- player_props stay RLS deny-all with zero policies and zero grants. This table
-- is public-user data only — no betting data, no private content — and every
-- policy below is scoped to the caller's own rows via auth.uid().
--
-- Roles:
--   authenticated -> select / insert / delete, own rows only
--   anon          -> nothing (sign-in is required to read or write a watchlist)
--   service_role  -> untouched; the app's private client never reads this table
--
-- Run in: Supabase dashboard → SQL Editor.
-- Safe to run repeatedly. Contains no DELETEs and destroys no data.
-- ═══════════════════════════════════════════════════════════════════════════


-- ── 1. Table ───────────────────────────────────────────────────────────────
--
-- One row per (user, season, player). The unique constraint is load-bearing:
-- the app upserts with on_conflict="user_id,season,player" + ignore_duplicates,
-- which needs exactly this constraint as its target.
--
-- on delete cascade: deleting an auth user removes their watchlist with them.

CREATE TABLE IF NOT EXISTS public.user_watchlists (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    season     int  NOT NULL,
    player     text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, season, player)
);

-- Supports the per-user/season count in the cap trigger and the season-scoped
-- select the app runs on every render.
CREATE INDEX IF NOT EXISTS user_watchlists_user_season
    ON public.user_watchlists (user_id, season);


-- ── 2. RLS: own rows only ──────────────────────────────────────────────────
--
-- Every policy targets the `authenticated` role explicitly and is scoped to
-- user_id = auth.uid(). anon is named in NO policy, so anon sees nothing even
-- though the table exists.
--
-- There is deliberately NO update policy: the app only ever adds or removes
-- players. A row's meaning cannot change, so update is not a capability the
-- feature needs — and one it therefore should not have.

ALTER TABLE public.user_watchlists ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS user_watchlists_select_own ON public.user_watchlists;
CREATE POLICY user_watchlists_select_own
    ON public.user_watchlists
    FOR SELECT
    TO authenticated
    USING (user_id = auth.uid());

DROP POLICY IF EXISTS user_watchlists_insert_own ON public.user_watchlists;
CREATE POLICY user_watchlists_insert_own
    ON public.user_watchlists
    FOR INSERT
    TO authenticated
    WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS user_watchlists_delete_own ON public.user_watchlists;
CREATE POLICY user_watchlists_delete_own
    ON public.user_watchlists
    FOR DELETE
    TO authenticated
    USING (user_id = auth.uid());


-- ── 3. Cap: 30 players per user per season ─────────────────────────────────
--
-- Enforced by a trigger, NOT by the RLS policy. A policy is a row-visibility
-- rule; it cannot count sibling rows without re-entering the table, and a cap
-- expressed as a policy would silently reject rather than explain.
--
-- The function is intentionally NOT security definer: it runs as the caller, so
-- its count(*) is itself RLS-filtered to that user's own rows. That is exactly
-- the number we want, and it means the trigger cannot be used to probe anyone
-- else's row count.
--
-- The existence check matters: the app upserts with ON CONFLICT DO NOTHING, and
-- a BEFORE INSERT trigger fires *before* the conflict is detected. Without this
-- guard, re-submitting a player you already track while sitting on exactly 30
-- would raise 'watchlist limit reached' for what is really a no-op.

CREATE OR REPLACE FUNCTION public.user_watchlists_cap()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- Already tracked: let ON CONFLICT DO NOTHING swallow it.
    IF EXISTS (
        SELECT 1 FROM public.user_watchlists
        WHERE user_id = NEW.user_id
          AND season  = NEW.season
          AND player  = NEW.player
    ) THEN
        RETURN NEW;
    END IF;

    IF (
        SELECT count(*) FROM public.user_watchlists
        WHERE user_id = NEW.user_id
          AND season  = NEW.season
    ) >= 30 THEN
        RAISE EXCEPTION 'watchlist limit reached';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS user_watchlists_cap_trg ON public.user_watchlists;
CREATE TRIGGER user_watchlists_cap_trg
    BEFORE INSERT ON public.user_watchlists
    FOR EACH ROW
    EXECUTE FUNCTION public.user_watchlists_cap();


-- ── 4. Grants ──────────────────────────────────────────────────────────────
--
-- RLS decides which rows; grants decide whether the role may reach the table at
-- all. Both are needed. No update grant — see section 2.

GRANT SELECT, INSERT, DELETE ON public.user_watchlists TO authenticated;
REVOKE ALL ON public.user_watchlists FROM anon;


-- ── 5. Verify ──────────────────────────────────────────────────────────────
--
-- rowsecurity must be true:
--
--   SELECT tablename, rowsecurity
--   FROM pg_tables
--   WHERE schemaname = 'public' AND tablename = 'user_watchlists';
--
-- Expect exactly three policies, all roles={authenticated}, all qualified by
-- auth.uid(); cmd should read SELECT / INSERT / DELETE and never UPDATE:
--
--   SELECT policyname, cmd, roles, qual, with_check
--   FROM pg_policies
--   WHERE schemaname = 'public' AND tablename = 'user_watchlists'
--   ORDER BY policyname;
--
-- Expect authenticated -> SELECT/INSERT/DELETE and NO anon row at all:
--
--   SELECT grantee, privilege_type
--   FROM information_schema.role_table_grants
--   WHERE table_schema = 'public' AND table_name = 'user_watchlists'
--     AND grantee IN ('anon', 'authenticated')
--   ORDER BY grantee, privilege_type;
--
-- The unique constraint the app's upsert targets must exist:
--
--   SELECT indexname, indexdef
--   FROM pg_indexes
--   WHERE schemaname = 'public' AND tablename = 'user_watchlists'
--   ORDER BY indexname;
--
-- And confirm 02's lockdown is still intact — all four must remain true with
-- zero grants to anon/authenticated:
--
--   SELECT tablename, rowsecurity
--   FROM pg_tables
--   WHERE schemaname = 'public'
--     AND tablename IN ('bets', 'cha_ching_tips', 'poll_watchlist', 'player_props');
