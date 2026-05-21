"""
Standalone test for fetch_espn_brownlow() from dashboard.py.
Mocks Streamlit so the module can be imported without a running server.
"""
import sys
import os
import traceback
from unittest.mock import MagicMock

# ── Mock Streamlit before any import touches it ──────────────────────────────
_st = MagicMock()

def _cache_mock(*args, **kwargs):
    # Handles both @st.cache_data and @st.cache_data(ttl=...) usage
    if args and callable(args[0]):
        return args[0]      # bare decorator: @st.cache_data
    return lambda fn: fn    # factory: @st.cache_data(ttl=3600)

_st.cache_data = _cache_mock
_st.cache_resource = _cache_mock
# Unpack-safe mock for st.columns / st.tabs etc.
_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]
_st.tabs.return_value = [MagicMock(), MagicMock()]
sys.modules["streamlit"] = _st
sys.modules["streamlit.components"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()

# ── Change to project directory ───────────────────────────────────────────────
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ── Import dashboard module ───────────────────────────────────────────────────
import importlib.util

spec = importlib.util.spec_from_file_location("dashboard", "dashboard.py")
dashboard = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(dashboard)
except Exception as e:
    print(f"WARNING: dashboard import raised (may be harmless Streamlit call): {e}")

fetch_espn = getattr(dashboard, "fetch_espn_brownlow", None)
if fetch_espn is None:
    print("ERROR: fetch_espn_brownlow not found in dashboard.py")
    sys.exit(1)

# ── Run the scraper ───────────────────────────────────────────────────────────
print("Running fetch_espn_brownlow() ...\n")
try:
    df, err = fetch_espn()
    if err:
        print(f"Scraper returned error: {err}\n")
    if df is None or df.empty:
        print("Result: empty DataFrame")
    else:
        print(f"Columns: {df.columns.tolist()}")
        print(f"Rows: {len(df)}\n")
        print("Top 20:")
        print(df.head(20).to_string(index=False))
except Exception:
    traceback.print_exc()
