# Feed Enricher Pro

Dashboard Streamlit per arricchire feed e-commerce con AI (Claude/OpenAI) + dati Google Ads + Shopify, generare custom_label intelligenti e produrre cataloghi ottimizzati per **Google Merchant Center** e **Meta Catalog**.

## Quick start

```bash
cd "feed-enricher"
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Apri http://localhost:8501 → sidebar → **Carica dataset demo** per esplorare con dati realistici.

## Setup API key

Vai su **0. Settings** → incolla la Claude API key → **Test connessione** → **Salva su disco**.
La chiave viene salvata in `~/.feed_enricher/config.json` (permessi 600).

In alternativa: env var `ANTHROPIC_API_KEY` o `OPENAI_API_KEY`.

## Pipeline (solo Upload e Labels sono richiesti, il resto è opzionale)

| # | Pagina | Cosa fa | Richiesto |
|---|---|---|---|
| 0 | **Settings** | API keys + modelli + parametri | sì (per AI) |
| 1 | **Upload Feed** | URL/file XML/CSV/TSV/JSON | ✅ sì |
| 2 | **Google Ads** | Script .js da copiare in GAds + upload performance | opzionale |
| 3 | **Shopify** | Sales / Inventory / Views (3 tab indipendenti) con auto-detect ID + match preview | opzionale |
| 4 | **Enrichment AI** | Claude classifica taxonomy, estrae attributi, riscrive titoli/descrizioni · **Chat con Claude** + refinement custom | opzionale |
| 5 | **Labels Performance** | ROAS tiers, zombie, no_clicks (richiede GAds) | opzionale |
| 6 | **Labels Margine** | Bucket prezzo + margine alto/medio/basso | opzionale |
| 7 | **Labels Stagionalità & Shopify** | freshness, bestseller, clearance, sell-through, view-to-buy | opzionale |
| 8 | **Labels Stock** | in/out + low/mid/high | opzionale |
| 9 | **Feed Supplementare** | Mappa label su `custom_label_0..4` + export | ✅ sì |
| 10 | **Performance Analytics** | KPI, scatter spesa/ROAS, top/flop | opzionale |
| 11 | **History** | Cronologia sessioni + cartella file generati | automatico |
| 12 | **Catalog Optimizer** | Genera feed ottimizzati Google + Meta con best practice | opzionale |

## Dashboard principale

- **Hero KPI** con glassmorphism (Horizon UI style)
- **Alert intelligenti**: zombie che bruciano €, immagini mancanti, categorie da arricchire
- **Tab**: Overview / Performance / Qualità dati / Labels preview / Esplora con search
- **Quick export**: CSV · Excel multi-foglio · JSON · XML GMC · **PDF Report**
- **"Salva tutti gli export"** in cartella sessione con un click

## Cronologia & sessioni

Tutto salvato in `~/.feed_enricher/sessions/<timestamp>/`:
- `history.jsonl` — log eventi (demo caricata, file salvati, ecc.)
- `outputs/` — file generati

Pagina **History** mostra tutte le sessioni passate, permette di ricaricarle, eliminarle, aprirle nel Finder.

## Custom labels disponibili

| Label | Fonte | Valori |
|---|---|---|
| performance_label | GAds | high_roas / mid_roas / low_roas / zombie / no_clicks / no_conv |
| price_bucket_label | feed | price_q1..q5 (quantili) |
| margin_label | Shopify COGS | margin_high/mid/low |
| freshness_label | data_added | new_arrival / recent / evergreen |
| bestseller_label | GAds o Shopify | bestseller / seller / no_sales |
| clearance_label | sale_price | clearance / on_sale / full_price |
| sellthrough_label | Shopify | fast_mover / steady_mover / slow_mover / stale_stock |
| view_to_buy_label | Shopify | high/mid/organic_zombie/low_traffic |
| stock_label | feed | in/out + low/mid/high (con quantity) |

## Catalog Optimizer (Google + Meta)

Mappa automaticamente i 28 campi Google + 31 campi Meta usando i risultati AI quando presenti (`title_optimized`, `description_enriched`, `brand_ai`, `color_ai`, ecc.).

**Normalizzazioni applicate** (best practice ufficiali):
- `availability` → `in stock` / `out of stock` / `preorder` / `backorder`
- `condition` → `new` / `refurbished` / `used`
- `price` → formato `99.99 EUR`
- `title` troncato a 150 (Google) / 200 (Meta) char
- `description` 5000 (Google) / 9999 (Meta) char max
- `identifier_exists` calcolato automaticamente (no se mancano gtin+mpn)

**Validazione**: tabella colorata che mostra stato campo per campo (OK/WARN/ERROR) con compilazione %.

**Export per piattaforma**: TSV (preferito GMC), CSV, Excel, XML RSS 2.0.

## Chat AI in Enrichment

Sotto i risultati dell'enrichment:
- **Refinement custom**: filtri per brand/status, scrivi un'istruzione (es. *"titoli più aggressivi, brand all'inizio"*), Claude riscrive in bulk
- **Chat conversazionale**: Claude ha già il contesto del catalogo (totale, ROAS, zombie, lunghezza media titoli...) e suggerisce istruzioni concrete
- **4 prompt rapidi** per analisi comuni

## Demo data

Generatore in [utils/demo_data.py](utils/demo_data.py): 500 prodotti finti realistici (15 brand veri), performance GAds con zombie ~15%, Shopify con distribuzione Pareto delle vendite. Tutto già mergeato in 1 click dalla sidebar.

## Provider AI supportati

- **Anthropic Claude** (consigliato): Sonnet 4.6 / Haiku 4.5 / Opus 4.6 con prompt caching
- **OpenAI**: gpt-4o-mini / gpt-4o / gpt-4-turbo / gpt-3.5

Configura entrambi in Settings → scegli quello predefinito.

## Struttura

```
feed-enricher/
├── app.py                          # dashboard principale
├── pages/
│   ├── 0_Settings.py
│   ├── 1_Upload_Feed.py
│   ├── 2_Google_Ads.py             # opzionale
│   ├── 3_Shopify.py                # opzionale, 3 tab indipendenti
│   ├── 4_Enrichment_AI.py          # AI + chat + refinement
│   ├── 5-8_Labels_*.py             # 4 tipi di label
│   ├── 9_Feed_Supplementare.py
│   ├── 10_Performance_Analytics.py
│   ├── 11_History.py               # sessioni & cronologia
│   └── 12_Catalog_Optimizer.py     # Google + Meta export
├── utils/
│   ├── feed_parser.py              # XML/CSV/JSON parsing
│   ├── enrichment.py               # Claude API + chat + refine
│   ├── labels.py                   # logiche custom_label
│   ├── exporter.py                 # Excel / XML GMC
│   ├── catalog_optimizer.py        # Google + Meta builders
│   ├── pdf_report.py               # PDF reportlab
│   ├── demo_data.py                # generatore dati finti
│   ├── config.py                   # persistenza API keys
│   ├── history.py                  # sessioni & log
│   ├── state.py                    # session state
│   └── ui.py                       # tema Horizon CSS
└── requirements.txt
```
