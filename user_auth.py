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
2. User-scoped data lives only in st.session_state, never st.cache_data — same
   reason: cache_data is keyed by arguments, not by viewer.

Session keys all start with "cc_user", which is what sign_out() clears.
"""

import time

import streamlit as st

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


# ── Session state ──────────────────────────────────────────────────────────

def _set_user(user, session) -> None:
    st.session_state["cc_user"] = {
        "id":            getattr(user, "id", None),
        "email":         getattr(user, "email", None),
        "access_token":  getattr(session, "access_token", None),
        "refresh_token": getattr(session, "refresh_token", None),
    }


def current_user():
    """The signed-in public user, or None. Independent of bh_authed."""
    return st.session_state.get("cc_user")


def sign_out() -> None:
    """Clear every cc_user* key and nothing else.

    This includes the multiselect's widget key, which matters: without it, one
    user's picks would still be sitting in the widget when the next person signs
    in on the same browser session.
    """
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
