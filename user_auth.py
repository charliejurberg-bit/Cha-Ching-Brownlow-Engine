"""Public user accounts + personal watchlists (Supabase Auth).

Kept deliberately separate from betting_hub.py. That module talks to Supabase
with the service_role key, which bypasses RLS; this one talks with the anon key
and a per-user JWT, and RLS is the only thing standing between one visitor's
watchlist and another's. Mixing the two clients in one module would make it far
too easy to reach for the wrong one.

Two invariants hold every line below:

1. No client is ever cached. @st.cache_resource is shared across every session
   on the server, so a cached client carrying a user's JWT would hand that
   user's identity to the next visitor who happened to load the page. Clients
   are rebuilt per call; they are cheap.
2. User-scoped data reaches st.cache_data only when the viewer is part of the
   cache key. cache_data is keyed by arguments and shared across every session
   on the server, so caching per-user rows under a key that does not name the
   user serves the first viewer's data to the next. load_poll_picks() takes
   user_id for exactly that reason and no other — it is a cache key, not a
   filter. Everything else user-scoped lives in st.session_state.

Session keys all start with "cc_user", which is what sign_out() clears.
"""

import uuid
import time
import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

_log = logging.getLogger(__name__)

WATCHLIST_MAX = 30

_SESSION_PREFIX  = "cc_user"     # sign_out() clears every key starting with this
_MAX_FAILS       = 5             # failed sign-ins before the soft lockout
_LOCK_SECONDS    = 60
_SAVE_COOLDOWN   = 2.0           # seconds between accepted saves
_MIN_PASSWORD    = 8             # mirrors the Supabase password policy

# Auth copy is deliberately identical for "no such email" and "wrong password".
# Anything that distinguishes them turns the sign-in form into an account
# oracle: an attacker learns which emails are registered here.
_GENERIC_SIGNIN  = "Sign-in failed — check your email and password."
_GENERIC_SIGNUP  = "Could not create that account — try a different email."
_SESSION_EXPIRED = "Session expired — sign in again."


# ── Clients ────────────────────────────────────────────────────────────────

def _anon_client():
    """A fresh anon-key client. Never cached — see module docstring.

    Mirrors betting_hub._get_supabase's shape (lazy import, secrets lookup,
    fail-closed to None) minus the @st.cache_resource, which is the whole point.
    """
    try:
        from supabase import create_client
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["anon_key"]
        return create_client(url, key)
    except Exception:
        return None


def _user_client():
    """An anon client carrying the signed-in user's JWT, or None.

    Every PostgREST call made through this is evaluated by RLS as that user, so
    the policies in 03_user_watchlists.sql are what scope reads and writes to
    their own rows. Fresh per call.
    """
    user = st.session_state.get("cc_user")
    if not user or not user.get("access_token"):
        return None
    sb = _anon_client()
    if sb is None:
        return None
    try:
        sb.postgrest.auth(user["access_token"])
        return sb
    except Exception:
        return None


def auth_available() -> bool:
    """False when the anon key isn't configured — callers hide the UI entirely
    rather than showing a sign-in box that cannot work."""
    return _anon_client() is not None


# ── Error shape matching ───────────────────────────────────────────────────
# supabase-py's error type has moved between versions, so match on SQLSTATE and
# message text rather than on any one attribute or class. Same approach as
# betting_hub._is_duplicate_error.

def _err_text(e: Exception) -> str:
    return f"{getattr(e, 'code', '')} {getattr(e, 'message', '')} {e}".lower()


def _is_auth_expired(e: Exception) -> bool:
    """True for an expired/rejected JWT. PGRST301 is PostgREST's code for it."""
    s = _err_text(e)
    return ("pgrst301" in s or "jwt expired" in s or "jwt is expired" in s
            or "token is expired" in s or "invalid claim" in s or "401" in s)


def _is_cap_error(e: Exception) -> bool:
    """True for the watchlist cap trigger. P0001 is plpgsql's RAISE EXCEPTION."""
    s = _err_text(e)
    return "watchlist limit reached" in s or "p0001" in s


# ── Session persistence across a browser refresh ───────────────────────────
#
# st.session_state dies with the browser session, so a refresh used to sign
# everyone out. The refresh token now rides in a cookie and bootstrap_session()
# trades it for a fresh session on the first script run.
#
# READ and WRITE come from different places, deliberately:
#
#   read  -> st.context.cookies, native, no component. It is populated from the
#            INITIAL HTTP REQUEST, so it is already there on the first script
#            run — which is exactly when recovery needs it. This sidesteps the
#            first-render round-trip that makes CookieManager.get_all() return
#            {} on run one, the classic flakiness of this whole approach.
#   write -> extra_streamlit_components.CookieManager, because Streamlit has no
#            cookie-write API at all (verified: nothing in dir(st) writes one).
#
# Three consequences of that split are load-bearing:
#
#   1. st.context.cookies does NOT update as cookies change — it is a snapshot
#      of the initial request. Recovery therefore runs ONCE per browser session
#      (_BOOTSTRAPPED), not once per run: a later attempt would re-read the same
#      stale snapshot, and after a sign-out would try to recover a session the
#      user just ended.
#   2. Writes are STAGED in session_state and issued from bootstrap rather than
#      inline. A component only reaches the browser if the script keeps running,
#      and sign-in/sign-out both st.rerun() immediately, which would race it.
#   3. The manager MOUNTS EVERY RUN, and a staged write waits for a run where it
#      was already mounted on the run before. This is the whole fix for the race
#      that shipped in 1e32d87, so it is worth being precise about:
#
#      CookieManager.__init__ renders a getAll component, which is a value
#      round-trip: on first mount the browser reports back and Streamlit reruns
#      the script. The old code mounted the manager only on the run that had a
#      write staged, and popped the token on that same run — so getAll's callback
#      rerun landed on a run with nothing staged, the manager was not
#      re-rendered, and both iframes were torn down. The set iframe (a 465 KB
#      bundle, one-way, nothing waiting on it) lost that race and the cookie was
#      never written, with the token already gone.
#
#      Mounting unconditionally turns that callback from the bug into the engine:
#      it guarantees a second run right after the first mount, and by then the
#      iframe is real and a write issued into it survives. A component only stays
#      alive while it is re-rendered every run — that is the conventional pattern
#      and there is no cheaper version of it.
#
# The staging keys deliberately do NOT start with "cc_user": sign_out() clears
# every cc_user* key, and would otherwise wipe its own staged cookie delete.

_COOKIE_NAME        = "cc_session"
_COOKIE_DAYS        = 30
_COOKIE_PENDING     = "cc_cookie_pending"       # staged write: token, or "" to delete
_COOKIE_MOUNTED     = "cc_cookie_mounted"       # manager was mounted on the PREVIOUS run
_COOKIE_UNAVAILABLE = "cc_cookie_unavailable"   # component missing; persistence is off
_BOOTSTRAPPED       = "cc_cookie_bootstrapped"  # recovery is once per browser session
_UNSET              = object()


def _stage_cookie(token) -> None:
    """Queue a cookie write for the next flush. Falsy token queues a delete."""
    st.session_state[_COOKIE_PENDING] = token or ""


def _read_cookie():
    """The stored refresh token, or None. Native read — see the note above."""
    try:
        return st.context.cookies.get(_COOKIE_NAME)
    except Exception:
        return None


def _cookie_manager():
    """Mount the CookieManager for this run. None when the component isn't usable.

    Constructing it IS the mount — __init__ renders the getAll component — so
    this must be called on every run, not only when there is something to write.

    Fails soft: without it the app loses persistence across refreshes and nothing
    else. An auth module that crashes the page because an optional convenience is
    missing would be a worse trade. It no longer fails SILENTLY, though — the old
    bare except made a missing component indistinguishable from a lost write,
    which is precisely the thing that needed telling apart when this broke.
    """
    try:
        from extra_streamlit_components import CookieManager
        return CookieManager(key="cc_cookie_mgr")
    except Exception as exc:
        # Once per session, not once per run: this is called on every run and the
        # answer cannot change mid-session.
        if not st.session_state.get(_COOKIE_UNAVAILABLE):
            _log.warning("cc_session: cookie manager unavailable — %r", exc)
        st.session_state[_COOKIE_UNAVAILABLE] = True
        return None


def _hide_cookie_iframes() -> None:
    """Collapse the manager's zero-height iframes.

    The library hides its own with this rule, but only from get/set/get_all —
    __init__ never calls it. Mounting every run therefore needs it here, or the
    getAll iframe leaves an empty element container at the top of every page.
    """
    st.markdown(
        '<style>.element-container:has(iframe[height="0"]){display:none;}</style>',
        unsafe_allow_html=True,
    )


def _flush_cookie(cm) -> None:
    """Issue the staged cookie write onto an ALREADY-MOUNTED manager.

    Takes the manager rather than building one: bootstrap mounts it every run,
    and a second construction here would be a second component with the same key.

    The token stays staged until the write has actually been issued. Popping it
    first is what made the old race unrecoverable — the write was lost and the
    only copy of the token went with it.
    """
    pending = st.session_state.get(_COOKIE_PENDING, _UNSET)
    if pending is _UNSET or cm is None:
        return

    if not st.session_state.get(_COOKIE_MOUNTED):
        # The manager mounted for the FIRST time on this run: its iframe does not
        # exist in the browser yet, and a write issued into it would be racing its
        # own mount. Leave the token staged — the getAll round-trip that this
        # mount triggers reruns the script within moments, and on that run the
        # iframe is real. Waiting a run is the entire fix.
        return

    try:
        if pending:
            # expires_at is not optional in practice: omit it and the component
            # silently defaults the cookie to ONE DAY, whatever max_age says.
            cm.set(
                _COOKIE_NAME, pending,
                key="cc_cookie_set",
                path="/",
                expires_at=datetime.now(timezone.utc) + timedelta(days=_COOKIE_DAYS),
                max_age=_COOKIE_DAYS * 24 * 60 * 60,
                secure=True,
                same_site="strict",
            )
        else:
            try:
                cm.delete(_COOKIE_NAME, key="cc_cookie_del")
            except KeyError:
                # delete() issues the component call and THEN does
                # `del self.cookies[name]`, which raises when getAll has not
                # reported that cookie back. The delete was already sent; this is
                # the library's bookkeeping, not a failed write.
                pass
    except Exception as exc:
        # Left staged deliberately: a write that never went out should be retried
        # next run, not dropped. Logged rather than swallowed.
        _log.warning("cc_session: cookie write failed — %r", exc)
        return

    st.session_state.pop(_COOKIE_PENDING, None)


def _recover() -> None:
    """Trade the cookie's refresh token for a live session. Silent on failure.

    A refresh token is single-use — Supabase rotates it and hands back a new one
    — so _set_user stages the ROTATED token straight back to the cookie. Storing
    the one we just spent would break the next recovery.

    Any failure (expired, revoked, reused, replayed from another machine) drops
    the cookie and leaves the visitor signed out with no message. There is
    nothing here a visitor did wrong, and nothing they can act on.
    """
    token = _read_cookie()
    if not token:
        return
    sb = _anon_client()
    if sb is None:
        return
    try:
        res = sb.auth.refresh_session(token)
    except Exception:
        _stage_cookie(None)
        return
    user    = getattr(res, "user", None)
    session = getattr(res, "session", None)
    if not user or not session:
        _stage_cookie(None)
        return
    _set_user(user, session)


def bootstrap_session() -> None:
    """Restore a signed-in cc_user after a page refresh. Call once per script
    run, from the top of the app, before anything reads current_user().

    Mounting the manager first, unconditionally, is deliberate — see the note at
    the top of this section. It is what keeps the iframe alive between the run
    that stages a write and the run that issues it.

    Cheap on every run but the first of a browser session: recovery is gated on
    _BOOTSTRAPPED, and the flush is a session_state lookup that usually finds
    nothing.
    """
    cm = _cookie_manager()
    if cm is not None:
        _hide_cookie_iframes()

    if not st.session_state.get(_BOOTSTRAPPED):
        st.session_state[_BOOTSTRAPPED] = True
        if not st.session_state.get("cc_user"):
            _recover()

    # Reads the PREVIOUS run's mount state, so it must run before the write below.
    _flush_cookie(cm)
    st.session_state[_COOKIE_MOUNTED] = cm is not None


# ── Session state ──────────────────────────────────────────────────────────

def _set_user(user, session) -> None:
    """The single place a session is established — and therefore the single
    place the cookie is staged. sign_in, sign_up, _refresh_once and _recover all
    land here, so every path that mints a refresh token persists it, including
    the rotated one _refresh_once gets back.
    """
    st.session_state["cc_user"] = {
        "id":            getattr(user, "id", None),
        "email":         getattr(user, "email", None),
        "access_token":  getattr(session, "access_token", None),
        "refresh_token": getattr(session, "refresh_token", None),
        # Carried so a proactive refresh becomes possible later. Nothing reads it
        # yet — _run still refreshes reactively, when PostgREST says PGRST301.
        "expires_at":    getattr(session, "expires_at", None),
    }
    _stage_cookie(getattr(session, "refresh_token", None))


def current_user():
    """The signed-in public user, or None. Independent of bh_authed."""
    return st.session_state.get("cc_user")


def sign_out() -> None:
    """Revoke the session server-side, drop the cookie, clear every cc_user* key.

    Order matters. The revoke goes first because it needs the JWT that the clear
    below is about to throw away, and it is what stops the cookie's refresh token
    from outliving the sign-out: deleting the cookie alone would leave a live
    credential on any machine that had already copied it.

    Clearing cc_user* includes the multiselect's widget key, which matters:
    without it, one user's picks would still be sitting in the widget when the
    next person signs in on the same browser session. The staged cookie delete
    survives that sweep by not carrying the prefix — see the persistence note.
    """
    sb = _user_client()
    if sb is not None:
        try:
            sb.auth.sign_out()
        except Exception:
            # Already expired or unreachable. The cookie still goes, and the
            # token dies on its own; nothing here is worth a message.
            pass

    _stage_cookie(None)
    for key in [k for k in list(st.session_state.keys())
                if str(k).startswith(_SESSION_PREFIX)]:
        st.session_state.pop(key, None)


# ── Soft lockout (UX only) ─────────────────────────────────────────────────
# Session state is trivially reset by reloading, so this stops honest fat-finger
# retries, not an attacker. Supabase's per-IP rate limits are the real backstop.

def _record_failure() -> None:
    n = int(st.session_state.get("cc_user_fail_count", 0)) + 1
    if n >= _MAX_FAILS:
        st.session_state["cc_user_lock_until"] = time.time() + _LOCK_SECONDS
        st.session_state["cc_user_fail_count"] = 0
    else:
        st.session_state["cc_user_fail_count"] = n


def _clear_failures() -> None:
    st.session_state.pop("cc_user_fail_count", None)
    st.session_state.pop("cc_user_lock_until", None)


def lock_remaining() -> int:
    """Seconds left on the soft lockout, 0 when clear."""
    until = st.session_state.get("cc_user_lock_until")
    if not until:
        return 0
    left = int(until - time.time())
    if left <= 0:
        st.session_state.pop("cc_user_lock_until", None)
        return 0
    return left


# ── Sign up / sign in ──────────────────────────────────────────────────────

def sign_up(email: str, password: str):
    """Create an account. Returns (ok, message).

    Handles both Supabase email-confirmation modes without a code change:
      confirmation OFF -> a session comes back, so sign them straight in
      confirmation ON  -> a user but no session, so tell them to check email
    """
    email = (email or "").strip()
    if not email or not password:
        return False, "Enter an email and password."
    if len(password) < _MIN_PASSWORD:
        return False, f"Password must be at least {_MIN_PASSWORD} characters."

    sb = _anon_client()
    if sb is None:
        return False, _GENERIC_SIGNUP
    try:
        res = sb.auth.sign_up({"email": email, "password": password})
    except Exception:
        # Never differentiate "already registered" from anything else.
        return False, _GENERIC_SIGNUP

    user    = getattr(res, "user", None)
    session = getattr(res, "session", None)
    if user and session:
        _set_user(user, session)
        _clear_failures()
        return True, None
    if user:
        return True, "Check your email to confirm your account."
    return False, _GENERIC_SIGNUP


def sign_in(email: str, password: str):
    """Sign in. Returns (ok, message)."""
    left = lock_remaining()
    if left:
        return False, f"Too many attempts — try again in {left}s."

    email = (email or "").strip()
    if not email or not password:
        return False, "Enter an email and password."

    sb = _anon_client()
    if sb is None:
        return False, _GENERIC_SIGNIN
    try:
        res = sb.auth.sign_in_with_password({"email": email, "password": password})
    except Exception:
        _record_failure()
        return False, _GENERIC_SIGNIN

    user    = getattr(res, "user", None)
    session = getattr(res, "session", None)
    if not user or not session:
        _record_failure()
        return False, _GENERIC_SIGNIN

    _set_user(user, session)
    _clear_failures()
    return True, None


# ── Token refresh ──────────────────────────────────────────────────────────

def _refresh_once() -> bool:
    """One attempt to swap the refresh token for a new session."""
    user = st.session_state.get("cc_user")
    if not user or not user.get("refresh_token"):
        return False
    sb = _anon_client()
    if sb is None:
        return False
    try:
        res = sb.auth.refresh_session(user["refresh_token"])
    except Exception:
        return False
    new_user    = getattr(res, "user", None)
    new_session = getattr(res, "session", None)
    if not new_user or not new_session:
        return False
    _set_user(new_user, new_session)
    return True


def _run(op):
    """Run op(client) against the user's client, refreshing ONCE on an expired
    JWT. Returns (result, error_message).

    Non-auth exceptions propagate to the caller, which knows what they mean in
    context (the cap trigger, say). Only auth failures are handled here.
    """
    sb = _user_client()
    if sb is None:
        return None, _SESSION_EXPIRED
    try:
        return op(sb), None
    except Exception as e:
        if not _is_auth_expired(e):
            raise

    if not _refresh_once():
        sign_out()
        return None, _SESSION_EXPIRED
    sb = _user_client()
    if sb is None:
        sign_out()
        return None, _SESSION_EXPIRED
    try:
        return op(sb), None
    except Exception as e:
        if _is_auth_expired(e):
            sign_out()
            return None, _SESSION_EXPIRED
        raise


# ── Watchlist ──────────────────────────────────────────────────────────────

def load_watchlist(season: int) -> set:
    """The user's tracked players for `season`, cached into session state.

    No .eq("user_id", ...) filter: the select policy already scopes this to the
    caller's rows, and restating it in the query would imply the filter is what
    protects the data. It isn't — RLS is.
    """
    if not current_user():
        st.session_state.pop("cc_user_watchlist", None)
        return set()

    def _op(sb):
        return (sb.table("user_watchlists")
                  .select("player")
                  .eq("season", int(season))
                  .execute())

    try:
        res, err = _run(_op)
    except Exception:
        # A read failure should not blank the UI; keep whatever we last knew.
        return set(st.session_state.get("cc_user_watchlist", set()))
    if err:
        return set()

    players = {r["player"] for r in (getattr(res, "data", None) or []) if r.get("player")}
    st.session_state["cc_user_watchlist"] = players
    return players


def save_watchlist(selected, season: int):
    """Persist the user's picks for `season`. Returns (ok, message).

    Diffs against the session copy so a save costs at most two statements
    regardless of list size, and costs nothing at all when nothing changed.
    """
    user = current_user()
    if not user:
        return False, _SESSION_EXPIRED

    if _save_cooldown_remaining() > 0:
        st.toast("Saving a bit fast — try again in a second.")
        return False, None

    selected = set(selected or [])
    if len(selected) > WATCHLIST_MAX:
        return False, f"watchlist limit reached ({WATCHLIST_MAX})"

    current = set(st.session_state.get("cc_user_watchlist", set()))
    added   = sorted(selected - current)
    removed = sorted(current - selected)
    if not added and not removed:
        return True, None

    def _remove(sb):
        return (sb.table("user_watchlists")
                  .delete()
                  .eq("season", int(season))
                  .in_("player", removed)
                  .execute())

    def _add(sb):
        rows = [{"user_id": user["id"], "season": int(season), "player": p}
                for p in added]
        return (sb.table("user_watchlists")
                  .upsert(rows, on_conflict="user_id,season,player",
                          ignore_duplicates=True)
                  .execute())

    try:
        # Removals first, deliberately. Swapping five players while sitting on
        # the 30 cap would trip the trigger if the adds went first; clearing the
        # space before filling it makes the same edit succeed.
        if removed:
            _, err = _run(_remove)
            if err:
                return False, err
        if added:
            _, err = _run(_add)
            if err:
                return False, err
    except Exception as e:
        # Drop the session copy so the next render re-reads the table. After a
        # partial apply (removes landed, adds didn't) the session copy is a lie,
        # and the database is the only thing that knows the truth.
        st.session_state.pop("cc_user_watchlist", None)
        if _is_cap_error(e):
            return False, f"watchlist limit reached ({WATCHLIST_MAX})"
        return False, "Couldn't save your watchlist — try again."

    st.session_state["cc_user_watchlist"]  = selected
    st.session_state["cc_user_last_save"]  = time.time()
    return True, None


def _save_cooldown_remaining() -> float:
    last = st.session_state.get("cc_user_last_save")
    if not last:
        return 0.0
    left = _SAVE_COOLDOWN - (time.time() - last)
    return left if left > 0 else 0.0


# ── Poll picks ─────────────────────────────────────────────────────────────
#
# Per-user Polls-a-Vote picks, backed by user_poll_picks (supabase/04). Every
# call below goes through _user_client(), so RLS is what scopes it to the
# caller's rows — none of these functions filter on user_id, and section 3 of 04
# is the reason they don't have to.
#
# Not yet called by anything: the page still reads betting_hub's service_role
# poll_watchlist path. This is the backend it moves onto.
#
# Each write ends in load_poll_picks.clear(), which drops every viewer's cached
# entry, not just the writer's — cache_data.clear() is per-function, not per-key.
# That is correct (nobody serves stale rows) and costs the other viewers one
# re-read within the 60s ttl, which is cheaper than a bespoke invalidation.

POLL_PICKS_TABLE = "user_poll_picks"

# The page reads row['Player'], so in-memory stays TitleCase while the table is
# snake_case. Ported from betting_hub.POLLS_SB_RENAME rather than imported:
# user_auth must not depend on the service_role module (see the docstring), and
# a seven-key dict is a cheaper duplicate than that dependency. id and
# created_at share both spellings; user_id and season are storage-side only and
# never appear in the frame the page sees.
POLL_PICK_COLS = ['id', 'Player', 'Team', 'My_Rounds', 'Odds', 'Stake',
                  'Notes', 'Settled', 'created_at']
POLL_PICK_RENAME = {
    'Player': 'player', 'Team': 'team', 'My_Rounds': 'my_rounds',
    'Odds': 'odds', 'Stake': 'stake', 'Notes': 'notes', 'Settled': 'settled',
}
POLL_PICK_RENAME_INV = {v: k for k, v in POLL_PICK_RENAME.items()}

# The wording the page has shown for this case since it lived in the Betting Hub.
# save_poll_pick fills the name in — it has the pick in hand, and "already
# watching Nick Daicos" is the whole point of the message.
_DUPLICATE_PICK = "Already watching {player} — edit the existing entry."
_PICK_SAVE_FAILED = "Couldn't save that pick — try again."
_PICK_WRITE_FAILED = "Couldn't update that pick — try again."


def _is_duplicate_error(e: Exception) -> bool:
    """True for a Postgres unique violation (SQLSTATE 23505) via PostgREST.

    Ported from betting_hub, and matching on SQLSTATE + message text for the
    same reason _is_auth_expired does: the error type has moved between
    supabase-py versions. Here it means user_poll_picks_active_player fired —
    the same player picked twice while the first pick is still open.
    """
    s = _err_text(e)
    return '23505' in s or 'duplicate key' in s


def _json_safe(record: dict) -> dict:
    """NaN/NaT → None, so a float column with no value serialises to JSON null.

    The single-record equivalent of betting_hub._sb_records.
    """
    return {
        k: (None if (isinstance(v, float) and pd.isna(v)) else v)
        for k, v in record.items()
    }


def _empty_poll_picks() -> pd.DataFrame:
    """An empty frame carrying the columns and dtypes the page expects."""
    df = pd.DataFrame(columns=POLL_PICK_COLS)
    df['Odds']      = pd.to_numeric(df['Odds'],  errors='coerce')
    df['Stake']     = pd.to_numeric(df['Stake'], errors='coerce')
    df['Settled']   = df['Settled'].fillna(False).astype(bool)
    df['My_Rounds'] = df['My_Rounds'].fillna('').astype(str)
    df['Notes']     = df['Notes'].fillna('').astype(str)
    df['id']        = df['id'].fillna('').astype(str)
    return df


def _coerce_poll_picks(df: pd.DataFrame) -> pd.DataFrame:
    """Table rows → the page's in-memory shape. Mirrors betting_hub's _coerce.

    Selecting POLL_PICK_COLS at the end is load-bearing as well as tidy: the
    select is a `*`, so user_id and season arrive too and are dropped here.
    """
    if df.empty:
        return _empty_poll_picks()
    df = df.rename(columns=POLL_PICK_RENAME_INV)      # snake_case → TitleCase
    for c in POLL_PICK_COLS:
        if c not in df.columns:
            df[c] = None
    df['Odds']      = pd.to_numeric(df['Odds'],  errors='coerce')
    df['Stake']     = pd.to_numeric(df['Stake'], errors='coerce')
    df['Settled']   = df['Settled'].fillna(False).astype(bool)
    df['My_Rounds'] = df['My_Rounds'].fillna('').astype(str)
    df['Notes']     = df['Notes'].fillna('').astype(str)
    df['id']        = df['id'].fillna('').astype(str)
    df = df[POLL_PICK_COLS]
    if df['created_at'].notna().any():
        df = df.sort_values('created_at', na_position='last')
    return df.reset_index(drop=True)


@st.cache_data(ttl=60)
def load_poll_picks(user_id: str, season: int) -> pd.DataFrame:
    """The signed-in user's picks for `season`, oldest first. Never raises.

    user_id is in the signature to key the cache, NOT to filter the query.
    st.cache_data is keyed by arguments and shared across every session on the
    server, so a cache whose key doesn't name the viewer hands the first
    viewer's picks to the next — which is exactly what would happen if
    betting_hub._load_watchlist's keyless ttl=60 cache were pointed at per-user
    data. Naming user_id gives each viewer their own entry. Callers pass
    current_user()["id"].

    No .eq("user_id", ...) filter: the select policy already scopes this to the
    caller's rows, and restating it in the query would imply the filter is what
    protects the data. It isn't — RLS is.

    An empty frame on failure rather than a raise: this feeds a render, and the
    page's own "no targets yet" empty state is a better answer than a traceback.
    """
    if not current_user():
        return _empty_poll_picks()

    def _op(sb):
        return (sb.table(POLL_PICKS_TABLE)
                  .select("*")
                  .eq("season", int(season))
                  .execute())

    try:
        res, err = _run(_op)
    except Exception:
        return _empty_poll_picks()
    if err:
        return _empty_poll_picks()
    return _coerce_poll_picks(pd.DataFrame(getattr(res, "data", None) or []))


def save_poll_pick(pick: dict, season: int):
    """Insert or update one pick. Returns (ok, message).

    id semantics mirror betting_hub._save_polls_row: the caller supplies it — a
    form-instance uuid, so a double-click or a rerun mid-write reuses the id and
    this upsert collapses onto one row instead of adding a duplicate. A missing
    id gets a fresh uuid4 for callers that don't, and created_at likewise (the
    setdefault matters: an edit passes the original through, so created_at
    survives the round trip rather than being reset on every save).

    `pick` is TitleCase, as the page holds it. my_rounds is stored exactly as
    given — its convention ("0" = Opening Round, comma-joined display rounds) is
    the page's, and this layer does not parse or rewrite it.

    A duplicate is reported, not raised, mirroring how save_watchlist() turns
    the cap trigger into a message. It means the guard index fired: this player
    already has an open pick.
    """
    user = current_user()
    if not user:
        return False, _SESSION_EXPIRED

    row = dict(pick)
    row.setdefault('id', str(uuid.uuid4()))
    row.setdefault('created_at', datetime.now(timezone.utc).isoformat())

    record = {POLL_PICK_RENAME.get(k, k): v
              for k, v in row.items() if k in POLL_PICK_COLS}
    # Storage-side columns the page's shape doesn't carry. user_id is set from
    # the session rather than trusted from the caller, and the insert policy's
    # WITH CHECK rejects it anyway if it isn't auth.uid().
    record['user_id'] = user["id"]
    record['season']  = int(season)

    def _op(sb):
        return (sb.table(POLL_PICKS_TABLE)
                  .upsert(_json_safe(record), on_conflict="id")
                  .execute())

    try:
        _, err = _run(_op)
        if err:
            return False, err
    except Exception as e:
        if _is_duplicate_error(e):
            return False, _DUPLICATE_PICK.format(
                player=row.get('Player') or 'that player')
        return False, _PICK_SAVE_FAILED

    load_poll_picks.clear()
    return True, None


def mark_poll_pick_settled(pick_id: str):
    """Mark one pick settled. Returns (ok, message).

    No .eq("user_id", ...) here either: the update policy scopes it to the
    caller's rows, so an id belonging to someone else matches nothing and
    changes nothing. RLS, not a filter, is what makes that true.
    """
    if not current_user():
        return False, _SESSION_EXPIRED

    def _op(sb):
        return (sb.table(POLL_PICKS_TABLE)
                  .update({'settled': True})
                  .eq('id', str(pick_id))
                  .execute())

    try:
        _, err = _run(_op)
        if err:
            return False, err
    except Exception:
        return False, _PICK_WRITE_FAILED

    load_poll_picks.clear()
    return True, None


def delete_poll_pick(pick_id: str):
    """Delete one pick. Returns (ok, message). Scoped by the delete policy."""
    if not current_user():
        return False, _SESSION_EXPIRED

    def _op(sb):
        return (sb.table(POLL_PICKS_TABLE)
                  .delete()
                  .eq('id', str(pick_id))
                  .execute())

    try:
        _, err = _run(_op)
        if err:
            return False, err
    except Exception:
        return False, _PICK_WRITE_FAILED

    load_poll_picks.clear()
    return True, None
