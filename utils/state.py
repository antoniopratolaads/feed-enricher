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
        "active_client_slug": None,  # contesto attivo: slug cliente corrente
        "active_feed_slug": None,    # contesto attivo: slug feed corrente
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ============================================================
# CONTESTO ATTIVO (cliente + feed) — unica fonte di verità del
# flusso a step. Le pagine NON devono più usare key di sessione
# locali divergenti per il cliente/feed selezionato.
# ============================================================
def reset_downstream() -> None:
    """Azzera i dataframe a valle del contesto (feed/enriched/merged).

    Chiamata quando cambia il (cliente, feed) attivo: i df caricati in
    sessione si riferiscono al contesto precedente e vanno scartati per
    evitare di mostrare dati di un altro cliente/feed.
    """
    st.session_state["feed_df"] = None
    st.session_state["enriched_df"] = None
    st.session_state["merged_df"] = None
    # Selezione prodotti forzata della pagina enrichment: non più valida.
    st.session_state.pop("_force_sel", None)


def set_active(client_slug: str | None, feed_slug: str | None) -> None:
    """Imposta il contesto attivo (cliente, feed) con SLUG puri.

    Se il contesto cambia rispetto a quello corrente, fa prima
    reset_downstream() (scarta i df del contesto precedente) e poi setta i
    nuovi slug. Se è invariato è un no-op: NON resetta nulla, così navigare
    avanti/indietro senza cambiare selezione non perde i dati caricati.
    """
    cur_client = st.session_state.get("active_client_slug")
    cur_feed = st.session_state.get("active_feed_slug")
    if (client_slug, feed_slug) == (cur_client, cur_feed):
        return  # invariato → no-op
    reset_downstream()
    st.session_state["active_client_slug"] = client_slug
    st.session_state["active_feed_slug"] = feed_slug


def get_active() -> tuple[str | None, str | None]:
    """Ritorna il contesto attivo come (client_slug, feed_slug)."""
    return (
        st.session_state.get("active_client_slug"),
        st.session_state.get("active_feed_slug"),
    )


def clear_active() -> None:
    """Azzera il contesto attivo e i df a valle."""
    st.session_state["active_client_slug"] = None
    st.session_state["active_feed_slug"] = None
    reset_downstream()


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
