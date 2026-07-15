-- ═══════════════════════════════════════════════════════════════════════════
-- 02_rls_lockdown.sql — Cha Ching / Betting Hub
--
-- ╔═══════════════════════════════════════════════════════════════════════╗
-- ║  ►►  STOP. CHECK YOUR API KEY FIRST OR THE APP LOSES ALL DATA.  ◄◄     ║
-- ║                                                                       ║
-- ║  service_role bypasses RLS. anon does NOT.                            ║
-- ║                                                                       ║
-- ║  This file enables RLS with NO policies and revokes every grant from  ║
-- ║  anon and authenticated. That is deny-all for both. The app keeps      ║
-- ║  working ONLY because service_role has the BYPASSRLS attribute.       ║
-- ║                                                                       ║
-- ║  BEFORE RUNNING THIS, confirm the key the app connects with is the    ║
-- ║  service_role key — in BOTH places:                                   ║
-- ║                                                                       ║
-- ║    1. Streamlit Cloud → app → Settings → Secrets                      ║
-- ║    2. your local .streamlit/secrets.toml                              ║
-- ║                                                                       ║
-- ║  Both hold it at [supabase] secret_key. Compare against Supabase      ║
-- ║  dashboard → Settings → API. The name "secret_key" in the code is     ║
-- ║  just our key name — it does NOT prove which key is in there.         ║
-- ║                                                                       ║
-- ║  If either holds the anon key, swap it to service_role FIRST. Run     ║
-- ║  this against an anon key and every Betting Hub read and write dies   ║
-- ║  instantly, on the deployed app as well as locally.                   ║
-- ╚═══════════════════════════════════════════════════════════════════════╝
--
-- Run in: Supabase dashboard → SQL Editor.
-- Safe to run repeatedly. Contains no DELETEs and touches no row data.
--
-- Scope: the four tables the Betting Hub owns. The public Brownlow pages read
-- CSVs only and touch none of this.
-- ═══════════════════════════════════════════════════════════════════════════


-- ── 1. Enable RLS, deliberately with no policies ───────────────────────────
--
-- RLS on + zero policies = deny-all for every role without BYPASSRLS. Do not
-- add a policy to "make it work" — service_role needs none, and any policy
-- here would be a hole for anon.

ALTER TABLE public.bets            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cha_ching_tips  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.poll_watchlist  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.player_props    ENABLE ROW LEVEL SECURITY;


-- ── 2. Revoke table grants from the public-facing roles ────────────────────
--
-- Belt and braces alongside RLS: RLS filters rows, this removes the privilege
-- outright. Either alone would do; together, a future policy added by mistake
-- still grants nothing.

REVOKE ALL ON TABLE public.bets            FROM anon, authenticated;
REVOKE ALL ON TABLE public.cha_ching_tips  FROM anon, authenticated;
REVOKE ALL ON TABLE public.poll_watchlist  FROM anon, authenticated;
REVOKE ALL ON TABLE public.player_props    FROM anon, authenticated;


-- ── 3. Revoke any sequences owned by those tables ──────────────────────────
--
-- A serial/identity column keeps its own sequence, and USAGE on a sequence
-- survives a table-level revoke. This finds only sequences owned by a column
-- of the four tables, so nothing else in the schema is touched. If the tables
-- use text/uuid keys only, this loop finds nothing and is a no-op.
--
-- To see what it will act on, run this first:
--
--   SELECT t.relname AS table_name, s.relname AS sequence_name
--   FROM pg_class s
--   JOIN pg_depend d  ON d.objid = s.oid AND d.classid = 'pg_class'::regclass
--   JOIN pg_class t   ON t.oid = d.refobjid
--   JOIN pg_namespace n ON n.oid = s.relnamespace
--   WHERE s.relkind = 'S'
--     AND n.nspname = 'public'
--     AND t.relname IN ('bets', 'cha_ching_tips', 'poll_watchlist', 'player_props');

DO $$
DECLARE
    seq_name text;
BEGIN
    FOR seq_name IN
        SELECT quote_ident(n.nspname) || '.' || quote_ident(s.relname)
        FROM pg_class s
        JOIN pg_depend d  ON d.objid = s.oid AND d.classid = 'pg_class'::regclass
        JOIN pg_class t   ON t.oid = d.refobjid
        JOIN pg_namespace n ON n.oid = s.relnamespace
        WHERE s.relkind = 'S'
          AND n.nspname = 'public'
          AND t.relname IN ('bets', 'cha_ching_tips', 'poll_watchlist', 'player_props')
    LOOP
        EXECUTE format('REVOKE ALL ON SEQUENCE %s FROM anon, authenticated', seq_name);
        RAISE NOTICE 'revoked on sequence %', seq_name;
    END LOOP;
END $$;


-- ── 4. Verify ──────────────────────────────────────────────────────────────
--
-- rowsecurity must be true for all four:
--
--   SELECT tablename, rowsecurity
--   FROM pg_tables
--   WHERE schemaname = 'public'
--     AND tablename IN ('bets', 'cha_ching_tips', 'poll_watchlist', 'player_props');
--
-- This must return ZERO rows — any row is a surviving grant to a public role:
--
--   SELECT table_name, grantee, privilege_type
--   FROM information_schema.role_table_grants
--   WHERE table_schema = 'public'
--     AND grantee IN ('anon', 'authenticated')
--     AND table_name IN ('bets', 'cha_ching_tips', 'poll_watchlist', 'player_props');
--
-- Then load the Betting Hub on the deployed app: if reads and writes still
-- work, the key is service_role and the lockdown is correct.
