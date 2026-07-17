-- ═══════════════════════════════════════════════════════════════════════════
-- 04_user_poll_picks.sql — Cha Ching / per-user Polls-a-Vote picks
--
-- ►► RUN AFTER 03_user_watchlists.sql. ◄◄
--
-- The second table anon/authenticated may touch, and like 03 it weakens nothing
-- in 02: bets, cha_ching_tips, poll_watchlist and player_props stay RLS
-- deny-all with zero policies and zero grants. This is public-user data only —
-- no betting data, no private content — and every policy below is scoped to the
-- caller's own rows via auth.uid().
--
-- Roles:
--   authenticated -> select / insert / update / delete, own rows only
--   anon          -> nothing (sign-in is required to read or write a pick)
--   service_role  -> untouched; the app's private client never reads this table
--
--
-- ── Why this table exists, and why it is not user_watchlists ───────────────
--
-- user_watchlists is set membership: one row per (user, season, player), and a
-- row's meaning cannot change — which is why 03 grants no UPDATE and says so.
-- A poll pick is a record, not a membership. It carries mutable state the user
-- owns (rounds called, odds, stake, notes, settled), and there is nowhere in
-- user_watchlists to put any of it. Bolting these columns onto that table would
-- either break its no-UPDATE invariant or force delete-and-reinsert on every
-- edit, throwing away created_at and the row's identity along the way.
--
--
-- ── Deliberate divergence from 03: UPDATE is granted ───────────────────────
--
-- 03's no-UPDATE rule is load-bearing *for a table whose rows are immutable*.
-- It is a conclusion drawn from that table's shape, not a house style to copy
-- blindly. Poll picks have three write shapes that each require UPDATE, and all
-- three already exist in the code this table replaces:
--
--   1. marking a pick settled        — an explicit update of one column
--   2. editing an existing pick      — upsert on id, i.e. ON CONFLICT DO UPDATE
--   3. a form-instance double-submit — the same id resubmitted, collapsing onto
--                                      one row via that same ON CONFLICT path
--
-- The invariant replacing "no UPDATE" here is narrower, and section 3 enforces
-- it: a row may be updated only by its owner, and can never be re-homed to
-- another user_id.
--
--
-- ── No cap trigger ─────────────────────────────────────────────────────────
--
-- 03 caps a watchlist at 30 players per season. That is a UX constraint on a
-- leaderboard-marking feature — not a rule about picks — so it is deliberately
-- not copied here. If picks ever need a cap, 03's trigger is the pattern to
-- follow, including its not-security-definer stance (so its count is itself
-- RLS-filtered) and its existence check.
--
-- Run in: Supabase dashboard → SQL Editor.
-- Safe to run repeatedly. Contains no DELETEs and destroys no data.
-- ═══════════════════════════════════════════════════════════════════════════


-- ── 1. Table ───────────────────────────────────────────────────────────────
--
-- id is normally supplied by the app rather than defaulted here: it is a
-- form-instance uuid, minted once per add-form instance, so a double-click or a
-- rerun mid-write reuses it and the keyed upsert collapses onto one row. The
-- DEFAULT is a backstop for any caller that omits it.
--
-- season is carried per row, and the CRUD layer takes it as a parameter — no
-- part of this feature assumes the current season.
--
-- team / my_rounds / odds / stake / notes are nullable: a pick is meaningful
-- with nothing but a player. my_rounds holds the app's display-convention
-- string ("0" = Opening Round, comma-joined) and is stored verbatim — the
-- database has no opinion about its contents, and the page owns that format.
--
-- on delete cascade: deleting an auth user removes their picks with them.

CREATE TABLE IF NOT EXISTS public.user_poll_picks (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    season     int  NOT NULL,
    player     text NOT NULL,
    team       text,
    my_rounds  text,
    odds       numeric,
    stake      numeric,
    notes      text,
    settled    boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Supports the season-scoped select the page runs on every render.
CREATE INDEX IF NOT EXISTS user_poll_picks_user_season
    ON public.user_poll_picks (user_id, season);


-- ── 2. Active-pick guard ───────────────────────────────────────────────────
--
-- The tenant-scoped successor to 01_idempotency.sql's poll_watchlist_active_player,
-- which is UNIQUE (player, team) WHERE settled = false — table-wide, with no
-- user_id in the key. That was correct while one person owned every row. Under
-- per-user picks it becomes a cross-tenant collision: one user's open pick on a
-- player would block every other user from picking him, and the app's "already
-- picked" message would be both false and a disclosure of a row the caller
-- cannot see. user_id is therefore part of the key here.
--
-- This is NOT the upsert's conflict target. The app upserts on id, and the
-- form-instance id is what makes a double-submit collapse (see section 1). This
-- index exists for the other case: the same player picked twice in separate
-- sittings while the first pick is still open. The app catches the resulting
-- unique violation and shows a quiet message instead of a traceback.
--
-- (user_id, player) rather than (user_id, player, team): a player has one team
-- at a time, and including a team string the user's row carries would let a
-- stale value reopen exactly the duplicate this guard exists to catch.
--
-- Settled picks are exempt (WHERE settled = false), so re-picking a player after
-- an earlier pick is settled stays legal — the same rule 01 applies.

CREATE UNIQUE INDEX IF NOT EXISTS user_poll_picks_active_player
    ON public.user_poll_picks (user_id, player)
    WHERE settled = false;


-- ── 3. RLS: own rows only ──────────────────────────────────────────────────
--
-- Every policy targets the `authenticated` role explicitly and is scoped to
-- user_id = auth.uid(). anon is named in NO policy, so anon sees nothing even
-- though the table exists.
--
-- The update policy carries BOTH USING and WITH CHECK, and they are not
-- redundant: USING decides which rows you may update, WITH CHECK decides what
-- those rows may look like afterwards. With USING alone, a user could update a
-- row they own and set user_id to someone else's — handing the row away, or
-- planting one in another account. WITH CHECK is what makes a pick
-- un-re-homeable, and it is the reason granting UPDATE here is safe.

ALTER TABLE public.user_poll_picks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS user_poll_picks_select_own ON public.user_poll_picks;
CREATE POLICY user_poll_picks_select_own
    ON public.user_poll_picks
    FOR SELECT
    TO authenticated
    USING (user_id = auth.uid());

DROP POLICY IF EXISTS user_poll_picks_insert_own ON public.user_poll_picks;
CREATE POLICY user_poll_picks_insert_own
    ON public.user_poll_picks
    FOR INSERT
    TO authenticated
    WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS user_poll_picks_update_own ON public.user_poll_picks;
CREATE POLICY user_poll_picks_update_own
    ON public.user_poll_picks
    FOR UPDATE
    TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS user_poll_picks_delete_own ON public.user_poll_picks;
CREATE POLICY user_poll_picks_delete_own
    ON public.user_poll_picks
    FOR DELETE
    TO authenticated
    USING (user_id = auth.uid());


-- ── 4. Grants ──────────────────────────────────────────────────────────────
--
-- RLS decides which rows; grants decide whether the role may reach the table at
-- all. Both are needed. UPDATE is granted where 03 withholds it — see the header
-- for why that is a reasoned divergence and not drift.

GRANT SELECT, INSERT, UPDATE, DELETE ON public.user_poll_picks TO authenticated;


-- ── 5. Revoke everything else ──────────────────────────────────────────────
--
-- Belt and braces, in 02's style. RLS already denies anon (it is named in no
-- policy) and no grant was made to it, so both of these are no-ops today. They
-- are here so that a policy added by mistake later still grants anon nothing.
--
-- PUBLIC is revoked as well: it is the role every role inherits, so a grant to
-- PUBLIC would quietly reach anon. Revoking PUBLIC does not touch the grant to
-- authenticated above — that is a grant to a named role, and survives this.

REVOKE ALL ON TABLE public.user_poll_picks FROM anon;
REVOKE ALL ON TABLE public.user_poll_picks FROM PUBLIC;


-- ── Verify ─────────────────────────────────────────────────────────────────
--
-- Four policies, all authenticated, all auth.uid()-scoped; the update one is
-- the only row with a non-null with_check:
--
--   SELECT policyname, cmd, roles, qual, with_check
--   FROM pg_policies
--   WHERE tablename = 'user_poll_picks'
--   ORDER BY policyname;
--
-- authenticated holds exactly SELECT/INSERT/UPDATE/DELETE, and anon holds
-- nothing (anon must return zero rows):
--
--   SELECT grantee, privilege_type
--   FROM information_schema.role_table_grants
--   WHERE table_name = 'user_poll_picks'
--     AND grantee IN ('anon', 'authenticated')
--   ORDER BY grantee, privilege_type;
--
-- The guard index exists and is tenant-scoped (expect user_id AND player, with
-- a settled = false predicate):
--
--   SELECT indexname, indexdef
--   FROM pg_indexes
--   WHERE tablename = 'user_poll_picks'
--   ORDER BY indexname;
--
-- RLS is on:
--
--   SELECT relname, relrowsecurity
--   FROM pg_class
--   WHERE relname = 'user_poll_picks';
