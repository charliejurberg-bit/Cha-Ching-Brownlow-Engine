"""
One-off fix: update Dempsey bet from Loss → Win in Supabase.

Usage:
    Set SUPABASE_URL and SUPABASE_KEY as environment variables, then run:
        python fix_dempsey_bet.py

    Or paste them directly in the placeholders below.
"""
import os
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL", "YOUR_SUPABASE_URL_HERE")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "YOUR_SUPABASE_ANON_KEY_HERE")

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# Find the Dempsey bet with odds 1.69 recorded as a Loss
resp = sb.table("bets").select("*").ilike("selection", "%Dempsey%").execute()
rows = resp.data or []

matches = [r for r in rows if abs(float(r.get("odds", 0) or 0) - 1.69) < 0.01 and r.get("result") == "Loss"]

if not matches:
    print("No matching Dempsey/1.69/Loss bet found — double-check the data in Supabase.")
elif len(matches) > 1:
    print(f"Found {len(matches)} matches — narrowing manually:")
    for r in matches:
        print(f"  bet_id={r['bet_id']}  selection={r['selection']}  odds={r['odds']}  result={r['result']}")
    print("Re-run with a specific bet_id if needed.")
else:
    row = matches[0]
    stake = float(row.get("stake") or 1.5)
    odds  = float(row.get("odds")  or 1.69)
    pl    = round(stake * odds - stake, 2)

    sb.table("bets").update({
        "result":      "Win",
        "profit_loss": pl,
    }).eq("bet_id", row["bet_id"]).execute()
    print(f"Updated bet_id={row['bet_id']}  {row['selection']}  {odds}@  Loss → Win  P&L={pl:+.2f}u")

    # Also fix in cha_ching_tips if it was entered via the tips system
    tips_resp = sb.table("cha_ching_tips").select("*").ilike("player", "%Dempsey%").execute()
    tip_matches = [t for t in (tips_resp.data or []) if t.get("result") == "Loss"]
    for tip in tip_matches:
        sb.table("cha_ching_tips").update({
            "result":      "Win",
            "profit_loss": pl,
        }).eq("tip_id", tip["tip_id"]).execute()
        print(f"Also updated cha_ching_tips tip_id={tip['tip_id']}")
