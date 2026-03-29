from __future__ import annotations

import pandas as pd
import requests
import streamlit as st

from app.config import get_settings

settings = get_settings()
API_BASE = f"http://{settings.api_host}:{settings.api_port}/api"

st.set_page_config(page_title="Weekly Options Scanner", layout="wide")
st.title("Weekly Options Premium-Selling Scanner")
st.caption("Human-in-the-loop recommendation engine. No auto-trading.")

col1, col2 = st.columns([1, 3])
with col1:
    if st.button("Run Scan Now"):
        with st.spinner("Running scan..."):
            resp = requests.post(f"{API_BASE}/scan/run", timeout=120)
            if resp.ok:
                st.success(f"Scan finished. {resp.json().get('count', 0)} recommendation(s).")
            else:
                st.error(f"Scan failed: {resp.text}")

with col2:
    limit = st.slider("Rows", min_value=10, max_value=200, value=50, step=10)

resp = requests.get(f"{API_BASE}/recommendations", params={"limit": limit}, timeout=30)
if resp.ok:
    items = resp.json().get("items", [])
    if items:
        df = pd.DataFrame(items)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No recommendations yet.")
else:
    st.error(f"Failed to load recommendations: {resp.text}")
