-- 07_h2h_multi.sql: more than one tracked head-to-head per user per season.
--
-- 06 made it one pair per user per season, UNIQUE (user_id, season), so saving
-- a second pair replaced the first. The Live Tracker now stacks one H2H panel
-- per pair, so that constraint becomes one row per PAIR instead:
-- UNIQUE (user_id, season, player1, player2).
--
-- The cap is H2H_MAX in the Next.js lib/account-data.ts (3), enforced here too
-- by a trigger, for the same reason the watchlist's limit is: a client cap
-- alone is a suggestion.
--
-- Safe to run twice. Run it in the Supabase SQL editor. The site works before
-- and after: before, a second pair fails with an error message and the first
-- stays tracked; after, up to three are kept.
--
-- The retired Streamlit app's user_auth.save_h2h_pair upserts ON CONFLICT
-- (user_id, season), which no longer matches a constraint after this runs. That
-- app is retired (29 September 2026), so it is left as it is.

-- 1. Drop the one-per-season constraint, whatever Postgres named it.
DO $$
DECLARE c text;
BEGIN
    FOR c IN
        SELECT con.conname
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
        WHERE nsp.nspname = 'public' AND rel.relname = 'user_h2h_pairs' AND con.contype = 'u'
          AND (SELECT array_agg(att.attname::text ORDER BY att.attname)
               FROM unnest(con.conkey) k JOIN pg_attribute att ON att.attrelid = rel.oid AND att.attnum = k)
              = ARRAY['season', 'user_id']
    LOOP
        EXECUTE format('ALTER TABLE public.user_h2h_pairs DROP CONSTRAINT %I', c);
    END LOOP;
END $$;

-- 2. One row per pair.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'user_h2h_pairs_user_season_pair_key') THEN
        ALTER TABLE public.user_h2h_pairs
            ADD CONSTRAINT user_h2h_pairs_user_season_pair_key UNIQUE (user_id, season, player1, player2);
    END IF;
END $$;

-- 3. At most three pairs per user per season.
CREATE OR REPLACE FUNCTION public.user_h2h_pairs_cap()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path = public AS $$
BEGIN
    IF (SELECT count(*) FROM public.user_h2h_pairs
        WHERE user_id = NEW.user_id AND season = NEW.season) >= 3 THEN
        RAISE EXCEPTION 'h2h limit reached (3)';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS user_h2h_pairs_cap ON public.user_h2h_pairs;
CREATE TRIGGER user_h2h_pairs_cap
    BEFORE INSERT ON public.user_h2h_pairs
    FOR EACH ROW EXECUTE FUNCTION public.user_h2h_pairs_cap();
