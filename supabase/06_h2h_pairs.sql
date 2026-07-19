-- ═══════════════════════════════════════════════════════════════════════════
-- 06_h2h_pairs.sql — Cha Ching / per-user tracked head-to-head pair
--
-- ►► RUN AFTER 05_drop_poll_watchlist.sql. ◄◄
--
-- The third table anon/authenticated may touch, and like 03 and 04 it weakens
-- nothing in 02: bets, cha_ching_tips, poll_watchlist and player_props stay RLS
-- deny-all with zero policies and zero grants. This is public-user data only —
-- no betting data, no private content — and every policy below is scoped to the
-- caller's own rows via auth.uid().
--
-- Roles:
--   authenticated -> select / insert / update / delete, own rows only
--   anon          -> nothing (sign-in is required to read or write a pair)
--   service_role  -> untouched; the app's private client never reads this table
--
--
-- ── One row per user per season, and why UPDATE is granted ─────────────────
--
-- The feature is "the one pair I am tracking this season", not a collection.
-- UNIQUE (user_id, season) is what makes that true in the database rather than
-- only in the UI, and it is the app's upsert conflict target: saving a new pair
-- overwrites the old one in a single statement instead of delete-then-insert.
--
-- That upsert is an ON CONFLICT DO UPDATE, so this table needs UPDATE for the
-- same reason 04 does. 03's no-UPDATE rule is a conclusion about a table whose
-- rows are immutable set membership, not a house style — see 04's header, which
-- makes the same argument at length. Section 3's WITH CHECK is what keeps the
-- grant safe: a row may be updated only by its owner and can never be re-homed
-- to another user_id.
--
--
-- ── Why the fitzRoy IDs are here, and nullable ─────────────────────────────
--
-- player1 / player2 are the app's display names, which are what the Compare tab
-- selects on. They are not stable across seasons: _disambiguate_players() only
-- rewrites a name to 'Name (Team)' when two different fitzRoy IDs share it in
-- that season's data, so the same person can serialise differently year to year.
-- The IDs are the stable identity and are preferred when matching a saved pair.
--
-- Nullable because the game frame does not always carry an ID (a live season
-- with no ID source leaves it absent), and a pair is still worth saving without
-- one. Stored as text, not bigint: the source column arrives from the CSV as a
-- float ('13054.0') and text avoids a lossy round trip through a numeric type.
--
--
-- ── No separate (user_id, season) index ────────────────────────────────────
--
-- 03 and 04 both add one because their unique constraints are wider than the
-- lookup. Here the UNIQUE constraint IS (user_id, season), and a unique
-- constraint is backed by an index, so the season-scoped select the Compare tab
-- runs is already covered. A second index on the same columns would be dead
-- weight the planner never chooses.
--
-- Run in: Supabase dashboard → SQL Editor.
-- Safe to run repeatedly. Contains no DELETEs and destroys no data.
-- ═══════════════════════════════════════════════════════════════════════════


-- ── 1. Table ───────────────────────────────────────────────────────────────
--
-- user_id carries DEFAULT auth.uid() as a backstop for a caller that omits it,
-- but the app always sets it from the session and the insert policy's WITH CHECK
-- is what actually enforces it. The default is convenience; the policy is the
-- guard.
--
-- on delete cascade: deleting an auth user removes their tracked pair with them.

CREATE TABLE IF NOT EXISTS public.user_h2h_pairs (
    id         uuid NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL DEFAULT auth.uid()
                    REFERENCES auth.users(id) ON DELETE CASCADE,
    season     int  NOT NULL,
    player1    text NOT NULL,
    player2    text NOT NULL,
    player1_id text,
    player2_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, season)
);


-- ── 2. RLS: own rows only ──────────────────────────────────────────────────
--
-- Every policy targets the `authenticated` role explicitly and is scoped to
-- user_id = auth.uid(). anon is named in NO policy, so anon sees nothing even
-- though the table exists.
--
-- The update policy carries BOTH USING and WITH CHECK, and they are not
-- redundant: USING decides which rows you may update, WITH CHECK decides what
-- those rows may look like afterwards. With USING alone a user could update a
-- row they own and set user_id to someone else's — handing the pair away, or
-- planting one in another account.

ALTER TABLE public.user_h2h_pairs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS user_h2h_pairs_select_own ON public.user_h2h_pairs;
CREATE POLICY user_h2h_pairs_select_own
    ON public.user_h2h_pairs
    FOR SELECT
    TO authenticated
    USING (user_id = auth.uid());

DROP POLICY IF EXISTS user_h2h_pairs_insert_own ON public.user_h2h_pairs;
CREATE POLICY user_h2h_pairs_insert_own
    ON public.user_h2h_pairs
    FOR INSERT
    TO authenticated
    WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS user_h2h_pairs_update_own ON public.user_h2h_pairs;
CREATE POLICY user_h2h_pairs_update_own
    ON public.user_h2h_pairs
    FOR UPDATE
    TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS user_h2h_pairs_delete_own ON public.user_h2h_pairs;
CREATE POLICY user_h2h_pairs_delete_own
    ON public.user_h2h_pairs
    FOR DELETE
    TO authenticated
    USING (user_id = auth.uid());


-- ── 3. Grants ──────────────────────────────────────────────────────────────
--
-- RLS decides which rows; grants decide whether the role may reach the table at
-- all. Both are needed.
--
-- This follows 04's grant shape, not 03's, and the difference is deliberate.
-- Supabase ships ALTER DEFAULT PRIVILEGES granting ALL on new public-schema
-- tables to anon/authenticated/service_role, so section 1's CREATE TABLE has
-- already handed authenticated the full privilege set — TRUNCATE, REFERENCES
-- and TRIGGER included — before this section is reached. Granting the four we
-- want does not take away the three we don't; only the REVOKE does. 03 predates
-- that finding and omits the revoke; copying 03 here would ship a table where
-- authenticated silently retains TRUNCATE.
--
-- TRUNCATE is the one that matters: it is not a DELETE, and RLS does not apply
-- to it, so section 2's auth.uid() scoping does nothing against it. An
-- authenticated caller holding TRUNCATE could empty every user's tracked pair in
-- one statement. A grant list is an assertion of the whole privilege set, never
-- an addition to whatever the platform left behind.

REVOKE ALL ON TABLE public.user_h2h_pairs FROM authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.user_h2h_pairs TO authenticated;


-- ── 4. Revoke everything else ──────────────────────────────────────────────
--
-- Not belt and braces. A policy is not a grant, and the same ALTER DEFAULT
-- PRIVILEGES that gave authenticated the full set gave it to anon as well.
-- These REVOKEs are what take it back. Without them anon holds TRUNCATE on a
-- table it cannot otherwise even see, and RLS will not save you.
--
-- PUBLIC is revoked for the related reason: it is the role every role inherits,
-- so a grant to PUBLIC would quietly reach anon. Revoking PUBLIC does not touch
-- section 3's grant to authenticated — that is a grant to a named role.

REVOKE ALL ON TABLE public.user_h2h_pairs FROM anon;
REVOKE ALL ON TABLE public.user_h2h_pairs FROM PUBLIC;


-- ── 5. Verify ──────────────────────────────────────────────────────────────
--
-- RLS is on:
--
--   SELECT relname, relrowsecurity
--   FROM pg_class
--   WHERE relname = 'user_h2h_pairs';
--
-- Four policies, all authenticated, all auth.uid()-scoped; the update one is
-- the only row with a non-null with_check:
--
--   SELECT policyname, cmd, roles, qual, with_check
--   FROM pg_policies
--   WHERE schemaname = 'public' AND tablename = 'user_h2h_pairs'
--   ORDER BY policyname;
--
-- The query that catches the default-privilege trap in sections 3 and 4. Expect
-- exactly four rows, all authenticated: SELECT, INSERT, UPDATE, DELETE. A fifth
-- (TRUNCATE, REFERENCES, TRIGGER) means a REVOKE did not run. anon must return
-- zero rows:
--
--   SELECT grantee, privilege_type
--   FROM information_schema.role_table_grants
--   WHERE table_schema = 'public' AND table_name = 'user_h2h_pairs'
--     AND grantee IN ('anon', 'authenticated')
--   ORDER BY grantee, privilege_type;
--
-- The unique constraint the app's upsert targets must exist — expect an index
-- on (user_id, season):
--
--   SELECT indexname, indexdef
--   FROM pg_indexes
--   WHERE schemaname = 'public' AND tablename = 'user_h2h_pairs'
--   ORDER BY indexname;
--
-- And confirm 02's lockdown is still intact — all four must remain true with
-- zero grants to anon/authenticated:
--
--   SELECT tablename, rowsecurity
--   FROM pg_tables
--   WHERE schemaname = 'public'
--     AND tablename IN ('bets', 'cha_ching_tips', 'poll_watchlist', 'player_props');
