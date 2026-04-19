"""Come funziona: documentazione completa in-app di Feed Enricher Pro."""
import streamlit as st

from utils.state import init_state
from utils.ui import apply_theme

init_state()
apply_theme()


# ============================================================
# HERO
# ============================================================
st.markdown(
    """
    <div style='background:linear-gradient(135deg, #2F6FED 0%, #1A4BB5 100%);
                border-radius:20px; padding:40px 44px; color:#FFFFFF;
                margin-bottom:28px; box-shadow:0 20px 48px rgba(47,111,237,0.25);
                position:relative; overflow:hidden;'>
        <div style='position:absolute; top:-60px; right:-40px; width:320px; height:320px;
                    background:radial-gradient(circle, rgba(255,255,255,0.12), transparent 60%);
                    pointer-events:none;'></div>
        <div style='font-size:0.72rem; letter-spacing:0.15em; text-transform:uppercase;
                    font-weight:700; opacity:0.85; margin-bottom:10px;'>Guida completa</div>
        <div style='font-size:2.4rem; font-weight:800; letter-spacing:-0.03em; line-height:1.05;
                    margin-bottom:10px;'>Come funziona Feed Enricher Pro</div>
        <div style='font-size:1.05rem; opacity:0.92; max-width:720px; line-height:1.55;'>
            Dashboard AI per arricchire cataloghi e-commerce con best practice settoriali,
            ottimizzare feed Google Merchant Center + Meta Catalog e generare custom_label
            basate su Google Ads + Shopify.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# STEPPER CONCETTUALE
# ============================================================
st.markdown("### Il flusso in 5 step")

steps = [
    ("①", "Carica feed", "XML/CSV/TSV/JSON/Excel da URL o file. Supporta Shopify, Magento, WooCommerce."),
    ("②", "Arricchisci con AI", "Claude classifica, estrae attributi, riscrive titoli/descrizioni."),
    ("③", "Genera label", "Custom label basate su performance Google Ads, Shopify, prezzo, stock."),
    ("④", "Valida qualità", "GTIN, duplicati, immagini, spell check, taxonomy autocomplete."),
    ("⑤", "Scarica export", "TSV/CSV/XML pronti per Google Merchant e Meta Commerce Manager."),
]
cols = st.columns(5)
for (icon, title, desc), col in zip(steps, cols):
    col.markdown(
        f"""
        <div style='background:#FFFFFF; border:1px solid #E5E7EB; border-radius:14px;
                    padding:18px 16px; height:100%; min-height:190px;
                    box-shadow:0 1px 3px rgba(10,10,15,0.04);
                    transition:all 0.2s;'>
            <div style='font-size:1.6rem; color:#2F6FED; font-weight:700; margin-bottom:8px;
                        line-height:1;'>{icon}</div>
            <div style='font-size:0.95rem; font-weight:700; color:#0A0A0F; margin-bottom:6px;'>
                {title}
            </div>
            <div style='font-size:0.82rem; color:#6B7280; line-height:1.5;'>{desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)

# ============================================================
# TAB COMPLETI
# ============================================================
t1, t2, t3, t4, t5, t6 = st.tabs([
    "Setup", "Pipeline Cliente", "Pipeline Labelizer",
    "Export", "Feature avanzate", "FAQ",
])

# ───── TAB 1 · SETUP ─────
with t1:
    st.markdown("## Setup iniziale (3 minuti)")

    st.markdown("### 1. API key Claude (Anthropic)")
    st.markdown(
        """
        L'enrichment AI richiede una chiave **Claude** (o in alternativa OpenAI).
        La chiave viene salvata in locale (`~/.feed_enricher/config.json`, permessi 600)
        e non lascia mai il tuo server.

        **Dove ottenerla**: [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys)
        · formato `sk-ant-api03-...`

        **Dove inserirla**: pagina **Settings → Anthropic Claude**.
        """
    )
    st.markdown("### 2. Scelta modello")
    st.markdown(
        """
        | Modello | Qualità | Velocità | Costo ~1k prodotti |
        |---|---|---|---|
        | `claude-haiku-4-5` | 🟢🟢 | ⚡⚡⚡ | ~€0.8 |
        | `claude-sonnet-4-6` (consigliato) | 🟢🟢🟢 | ⚡⚡ | ~€2.5 |
        | `claude-opus-4-6` | 🟢🟢🟢🟢 | ⚡ | ~€14 |

        Sonnet è il miglior rapporto qualità/prezzo per la maggior parte dei cataloghi.
        """
    )
    st.markdown("### 3. Settore merceologico")
    st.markdown(
        """
        Il settore attiva **best practice** specifiche caricate da `config/sectors/*.yaml`:
        formule titolo, parole vietate, attributi obbligatori, tono di voce.

        Settori inclusi: `abbigliamento`, `cosmesi`, `condizionatori`.
        Per aggiungerne uno nuovo: crea un YAML con la stessa struttura.
        """
    )

# ───── TAB 2 · PIPELINE CLIENTE ─────
with t2:
    st.markdown("## Pipeline Cliente — flusso principale")

    steps_cli = [
        ("Upload Feed",
         "Carica il catalogo prodotto da URL (Shopify `/products.json`, Magento, WooCommerce) "
         "oppure da file. Formati supportati: XML (RSS/GMC), CSV, TSV, JSON, Excel multi-foglio. "
         "Il parser **normalizza i nomi delle colonne** (es. `prezzo` → `price`, `titolo` → `title`) "
         "e salva il feed originale."),

        ("Wizard Enrichment",
         "Flusso lineare 4-step consigliato: Progetto → Upload → Enrichment AI → Scarica Catalogo. "
         "Salvataggio automatico ad ogni step. Puoi interrompere e riprendere in qualsiasi momento "
         "dalla pagina Progetti."),

        ("Enrichment AI",
         "Claude processa ogni prodotto e restituisce JSON strutturato con campi **ufficiali** Google/Meta: "
         "`title`, `description`, `title_meta`, `description_meta_short`, `google_product_category`, "
         "`product_type`, `brand`, `color`, `size`, `material`, `gender`, `age_group`, `condition`, "
         "`product_highlight` (bullet points), `product_detail`, `keywords`. "
         "Gli originali vengono preservati in `title_original` / `description_original` per l'undo."),

        ("Scarica Catalogo",
         "Costruisce feed ottimizzati per **Google Merchant Center** (28 campi) e **Meta Catalog** (31 campi). "
         "Normalizza automaticamente `availability`, `condition`, `price`, `identifier_exists`. "
         "Tronca title/description ai limiti di piattaforma (150/200 e 5000/9999 char). "
         "Export disponibili: TSV, CSV, Excel, XML RSS 2.0, JSON, PDF report."),
    ]
    for i, (title, desc) in enumerate(steps_cli, 1):
        st.markdown(
            f"""
            <div style='background:#FFFFFF; border:1px solid #E5E7EB; border-left:4px solid #2F6FED;
                        border-radius:12px; padding:18px 22px; margin-bottom:12px;'>
                <div style='font-size:1.05rem; font-weight:700; color:#0A0A0F; margin-bottom:6px;'>
                    Step {i} · {title}
                </div>
                <div style='font-size:0.9rem; color:#4B5563; line-height:1.6;'>{desc}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### Feature dell'Enrichment")
    st.markdown(
        """
        - **Cache automatica**: prodotti già arricchiti saltano il roundtrip AI (hash su id, title,
          description, brand, prezzo, attributi). Risparmio medio dopo la 2ª run: **70-95% dei costi**.
        - **Cost estimator**: calcola €/USD **prima** di lanciare, basato su modello scelto e n. prodotti.
        - **Undo**: un click ripristina titoli/descrizioni originali.
        - **Diff preview**: confronto side-by-side prima/dopo per audit qualità.
        - **Refinement custom**: filtra un sottoinsieme (es. solo zombie) e scrivi un'istruzione libera
          (_"titoli più aggressivi, brand all'inizio"_). Claude riscrive in bulk.
        - **Chat conversazionale**: Claude ha già il contesto del catalogo (ROAS, top brand, lunghezza
          media titoli) e suggerisce istruzioni concrete.
        - **Taxonomy autocomplete**: fuzzy match su tassonomia Google ufficiale (~6000 categorie).
        - **Spell check italiano**: flagga parole sospette in titoli/descrizioni.
        """
    )

# ───── TAB 3 · PIPELINE LABELIZER ─────
with t3:
    st.markdown("## Pipeline Labelizer — custom_label avanzati")
    st.markdown(
        "Sezione opzionale per chi vuole generare **custom_label_0..4** basate su dati di performance "
        "(Google Ads, Shopify) + metriche prezzo/stock. Serve per segmentazione campagne, bidding "
        "differenziato, esclusioni smart."
    )

    st.markdown("### Label disponibili")
    st.markdown(
        """
        | Label | Fonte | Valori | Uso tipico |
        |---|---|---|---|
        | `performance_label` | Google Ads | `high_roas` / `mid_roas` / `low_roas` / `zombie` / `no_clicks` / `no_conv` | Bidding tier + esclusioni |
        | `price_bucket_label` | feed | `price_q1..q5` (quantili) | Bid per fascia prezzo |
        | `margin_label` | Shopify COGS | `margin_high` / `mid` / `low` | Bid in base a margine |
        | `freshness_label` | data_added | `new_arrival` / `recent` / `evergreen` | Promo su novità |
        | `bestseller_label` | GAds/Shopify | `bestseller` / `seller` / `no_sales` | Spinta sui top seller |
        | `clearance_label` | sale_price | `clearance` / `on_sale` / `full_price` | Campagne saldi |
        | `sellthrough_label` | Shopify | `fast_mover` / `steady` / `slow` / `stale_stock` | Rotazione magazzino |
        | `view_to_buy_label` | Shopify | `high` / `mid` / `organic_zombie` / `low_traffic` | Identifica prodotti 'guardati ma non comprati' |
        | `stock_label` | feed | `in_low` / `in_mid` / `in_high` / `out` | Bidding su disponibilità |
        """
    )

    st.markdown("### Flusso consigliato")
    st.markdown(
        """
        1. **Hub** → vedi cosa ti manca per ogni label
        2. **Google Ads** → carica lo script `.js` dal Labelizer in Google Ads Scripts, lancialo, scarica CSV
           performance e caricalo qui
        3. **Shopify** → Sales / Inventory / Views (3 tab indipendenti), auto-match per SKU con fuzzy
        4. **Label Performance / Margine / Stagionalità / Stock** → genera le label
        5. **Feed Supplementare** → mappa le label su `custom_label_0..4` + export Google/Meta
        6. **Analytics** → KPI, scatter spesa/ROAS, top/flop per label
        """
    )

# ───── TAB 4 · EXPORT ─────
with t4:
    st.markdown("## Export & deploy")

    st.markdown("### Formati")
    st.markdown(
        """
        - **TSV** (preferito da Google Merchant) — `\\t` separator, UTF-8
        - **CSV** — standard Meta Commerce Manager
        - **XML RSS 2.0** — formato legacy GMC
        - **Excel** multi-foglio (prodotti + validazione + qualità)
        - **PDF report** — summary human-readable
        - **JSON** — integrazione con pipeline custom
        """
    )

    st.markdown("### Export diff — solo delta")
    st.markdown(
        """
        Salva uno **snapshot** (hash per riga) dopo ogni export. Al prossimo export il tool calcola
        `added / modified / removed / unchanged` e offre il download **solo dei prodotti cambiati**.
        Riduce l'upload a GMC di 10-100× su update incrementali.
        """
    )

    st.markdown("### Validazione pre-export")
    st.markdown(
        """
        La pagina **Scarica Catalogo** fa:
        - validazione per-campo Google + Meta (OK / WARN / ERROR con compilazione %)
        - quality check (GTIN mod-10, duplicati title+description, immagini <800×800, title corti, description corte)
        - export ZIP finale con TUTTI i formati + validation report + README
        """
    )

# ───── TAB 5 · FEATURE AVANZATE ─────
with t5:
    st.markdown("## Feature avanzate")

    feats = [
        ("Cache hash enrichment",
         "`utils/cache.py` — hash(id + title + description + brand + attributi + model + sector). "
         "Namespace condiviso `shared_v1`. Pulibile da Enrichment AI."),
        ("Prompt templates versioning",
         "`utils/prompts.py` — ogni settore ha versioni numerate del system prompt. Editor in "
         "Settings → tab Prompt templates. Attiva/disattiva/elimina per versione."),
        ("SQLite index cross-sessione",
         "`utils/sqlite_store.py` — mirror indicizzato dei JSONL history. Ricerca per project_name / "
         "session_id. Rebuild da Progetti. Trasparente: JSONL resta source of truth."),
        ("Error boundary",
         "`guarded()` context manager — cattura exception → card rossa + traceback collapsible. "
         "Niente Streamlit stacktrace brutto in produzione."),
        ("Loading progress con ETA",
         "`LoadingProgress` — barra con counter live + elapsed + ETA calcolato. Per operazioni lunghe "
         "(enrichment, validazione immagini)."),
        ("Empty state",
         "Placeholder centered + CTA invece di `st.warning + stop`. Usato in Enrichment e Catalog Optimizer."),
        ("API key banner",
         "`api_key_banner()` — warning in alto alle pagine che richiedono AI se la chiave manca, "
         "con CTA inline a Settings."),
        ("Refinement bulk",
         "Filtra per brand/status in Enrichment → istruzione libera → Claude riscrive. Funziona "
         "in parallelo su fino a 500 prodotti."),
        ("Chat con contesto catalogo",
         "Claude vede ROAS, top brand, distribuzione performance, senza che devi incollare i dati. "
         "Prompt rapidi pre-configurati."),
    ]
    for title, desc in feats:
        st.markdown(
            f"""
            <div style='background:#F9FAFB; border:1px solid #E5E7EB; border-radius:10px;
                        padding:14px 18px; margin-bottom:10px;'>
                <div style='font-weight:700; font-size:0.95rem; color:#0A0A0F; margin-bottom:4px;'>
                    {title}
                </div>
                <div style='font-size:0.85rem; color:#4B5563; line-height:1.55;'>{desc}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ───── TAB 6 · FAQ ─────
with t6:
    st.markdown("## FAQ")

    faqs = [
        ("La chiave Claude viene inviata a Google o Anthropic?",
         "Solo ad Anthropic (o OpenAI se usi quello). È salvata localmente in "
         "`~/.feed_enricher/config.json` con permessi 600. Non passa da server Streamlit né da noi."),
        ("Quanto costa arricchire 1000 prodotti con Sonnet?",
         "Circa €2.50 al netto della cache. Dopo il primo run, re-enrich di feed 80% invariato costa ~€0.50."),
        ("Cosa succede se l'enrichment fallisce a metà?",
         "Ogni prodotto OK viene salvato comunque. Rilanci e la cache salta quelli già fatti. Gli errori "
         "appaiono in `_enrichment_status` come `error: ...`."),
        ("Posso usare il tool senza Shopify/Google Ads?",
         "Sì. Shopify e Google Ads sono opzionali (solo per il Labelizer). Upload + Enrichment + Export "
         "bastano per generare feed ottimizzati Google/Meta."),
        ("Il feed generato supporta variants (taglia/colore)?",
         "Sì. Il parser rispetta `item_group_id`. Ogni variant è una riga separata nel feed con campi "
         "specifici (`color`, `size`) e `item_group_id` comune per il raggruppamento GMC."),
        ("Come testo un prompt custom prima di applicarlo a tutti?",
         "Settings → tab Prompt templates → salva una versione. Lancia Enrichment con limite=10 prodotti. "
         "Se il risultato va, applica a tutto il catalogo."),
        ("Quanto pesa la cache?",
         "~4KB per prodotto. Per 10k prodotti ≈ 40MB. Storage: `~/.feed_enricher/cache/`."),
        ("Posso usarlo offline?",
         "No. Serve connessione a api.anthropic.com (o platform.openai.com) e a fonts.googleapis.com "
         "per font e tassonomia."),
    ]
    for q, a in faqs:
        with st.expander(q):
            st.markdown(a)

st.divider()
st.caption(
    "💡 Hai trovato un bug o vuoi suggerire una feature? Apri una issue sul repo "
    "[github.com/antoniopratolaads/feed-enricher](https://github.com/antoniopratolaads/feed-enricher)."
)
