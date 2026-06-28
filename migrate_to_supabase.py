"""
One-time migration: upload local bets.csv to Supabase.
Run from brownlow_engine/:
    python migrate_to_supabase.py
"""
import os, math
import pandas as pd
import streamlit as st
from supabase import create_client

SUPABASE_URL = st.secrets["supabase"]["url"]
SUPABASE_KEY = st.secrets["supabase"]["secret_key"]  # server-side: full write access

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

def nan_to_none(val):
    if isinstance(val, float) and math.isnan(val):
        return None
    return val

def clean_row(row: dict) -> dict:
    return {k: nan_to_none(v) for k, v in row.items()}

bets_path = os.path.join(os.path.dirname(__file__), "data_betting", "bets.csv")
df = pd.read_csv(bets_path)
df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.strftime('%Y-%m-%d')
df['is_cha_ching'] = df['is_cha_ching'].fillna(False).astype(bool)

records = [clean_row(r) for r in df.to_dict('records')]
print(f"Uploading {len(records)} bets...")
resp = sb.table("bets").upsert(records, on_conflict="bet_id").execute()
print(f"Done — {len(resp.data)} rows upserted.")
