"""Gestione stato Streamlit condiviso tra pagine."""
from __future__ import annotations
import streamlit as st
import pandas as pd


def init_state():
    defaults = {
        "raw_df": None,          # feed caricato originale
        "feed_df": None,         # feed normalizzato
        "enriched_df": None,     # dopo enrichment AI
        "gads_df": None,         # performance Google Ads
        "merged_df": None,       # feed + gads merged
        "labels": {},            # {label_name: pd.Series}
        "api_key": "",
        "feed_source": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def current_df() -> pd.DataFrame | None:
    """Ritorna il dataframe più avanzato disponibile."""
    for key in ("merged_df", "enriched_df", "feed_df"):
        if st.session_state.get(key) is not None:
            return st.session_state[key]
    return None


def status_badge():
    import streamlit as st
    cols = st.columns(5)
    cols[0].metric("Feed", "OK" if st.session_state.get("feed_df") is not None else "—",
                   delta=f"{len(st.session_state['feed_df'])} righe" if st.session_state.get("feed_df") is not None else None)
    cols[1].metric("Enrichment", "OK" if st.session_state.get("enriched_df") is not None else "—")
    cols[2].metric("Google Ads", "OK" if st.session_state.get("gads_df") is not None else "—")
    cols[3].metric("Merge", "OK" if st.session_state.get("merged_df") is not None else "—")
    cols[4].metric("Labels attive", len(st.session_state.get("labels", {})))
