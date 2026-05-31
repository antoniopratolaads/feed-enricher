# SPEC STATUS 2E — status per-prodotto a 3 livelli + fix enum availability

> Spec implementabile da `streamlit-dev`. Pseudocodice/regole precise, non codice finale.
> Verificata contro il codice reale (`utils/catalog_optimizer.py`, `utils/validation.py`, `utils/enrichment.py`, `utils/ui.py`) e contro le spec ufficiali GMC/Meta 2026.

---

## ⚠️ Correzione critica: Google e Meta NON condividono l'enum availability

Verifica 2026 su fonti ufficiali Google + Meta:
- **Google Merchant Center** → underscore: `in_stock`, `out_of_stock`, `preorder`, `backorder`.
- **Meta Catalog** → spazio + set diverso: `in stock`, `out of stock`, `available for order`, `preorder`, `discontinued`.

Il bug attuale (`_normalize_availability`, catalog_optimizer.py:221-231) è **duplice**: produce lo spazio (sbagliato per Google) ed è usato sia per Google sia per Meta. Serve **un normalizzatore per target**.

---

## 1. BUG P0 — `availability`

### 1.1 Enum ufficiali (verificati 2026-05-31)

| Target | Valori validi | Separatore |
|---|---|---|
| **Google** | `in_stock` · `out_of_stock` · `preorder` · `backorder` | underscore |
| **Meta** | `in stock` · `out of stock` · `available for order` · `preorder` · `discontinued` | spazio |

Note: Google `build_to_order`/`limited_availability` marginali → non gestire. Meta non ha `backorder` → mappa su `available for order`.

### 1.2 Due funzioni separate (pseudocodice)

```python
_GMC_AVAIL = {"in_stock", "out_of_stock", "preorder", "backorder"}

def _canon_availability(v) -> str:
    """Riduce qualsiasi input a un token canonico interno (underscore)."""
    s = str(v).lower().strip()
    if not s or s in ("nan", "none", "null"):
        return "out_of_stock"            # default conservativo
    norm = s.replace("-", "_").replace(" ", "_")
    while "__" in norm:
        norm = norm.replace("__", "_")
    if norm in _GMC_AVAIL:
        return norm
    if "in_stock" in norm or norm in ("instock", "yes", "available", "disponibile", "true", "1"):
        return "in_stock"
    if "preorder" in norm or "pre_order" in norm or "prevendita" in norm:
        return "preorder"
    if ("available_for_order" in norm or "backorder" in norm or "back_order" in norm
            or "ordinazione" in norm or "riassort" in norm):
        return "backorder"
    if "discontinued" in norm or "fuori_produzione" in norm or "cessato" in norm:
        return "out_of_stock"            # Google non ha 'discontinued'
    return "out_of_stock"

def _normalize_availability_google(v) -> str:
    return _canon_availability(v)        # già enum Google underscore

_CANON_TO_META = {
    "in_stock":     "in stock",
    "out_of_stock": "out of stock",
    "preorder":     "preorder",
    "backorder":    "available for order",   # Meta non ha backorder
}
def _normalize_availability_meta(v) -> str:
    return _CANON_TO_META[_canon_availability(v)]
```

Regole: output Google sempre ∈ enum underscore; output Meta sempre ∈ enum spazio; ambiguo/vuoto → out of stock (default sicuro).

### 1.3 Wiring nelle build

- `build_google_feed` (catalog_optimizer.py:397): `out["availability"].map(_normalize_availability_google)`
- `build_meta_feed` (catalog_optimizer.py:432): `out["availability"].map(_normalize_availability_meta)`
- Vecchio `_normalize_availability` (221): splittare. Per retrocompat nome: `_normalize_availability = _normalize_availability_google`.

### 1.4 Verifica a valle (nessuna re-introduzione formato errato)

| Punto | Esito |
|---|---|
| `to_gmc_xml` (exporter.py) | OK — solo `escape()`, passthrough. |
| `to_excel_bytes` / TSV | OK — passthrough. |
| `SYSTEM_PROMPT_BASE` (enrichment.py:81) | OK — istruisce l'AI con underscore; la build per-target converte. |
| `demo_data.py` | opzionale: la build normalizza comunque. Non bloccante. |

---

## 2. Modello status a 3 livelli (ortogonale a `_enrichment_status`)

`_enrichment_status` (reali: `empty`/`""`/`ok`/`cached`/`stale`/`error*`) = esito chiamata AI. Il livello export è un asse ORTOGONALE.

- **GREZZO**: `_enrichment_status` ∈ {empty,"",NaN} OPPURE `title==title_original` e `description==description_original`.
- **ARRICCHITO**: status ∈ {ok,cached} + title/description non vuoti + `google_product_category` valida (path con `>` o ID numerico) + ≥1 attributo AI popolato.
- **PRONTO EXPORT**: ARRICCHITO + TUTTI i required GMC validi (§3). PRONTO EXPORT ⊂ ARRICCHITO.

Precedenza: `error*` → asse errore (badge §5) · non-arricchito → grezzo · tutti required ok → pronto_export · else → arricchito.

---

## 3. Campi obbligatori GMC → regola → severità

Required (`GOOGLE_FIELDS` con `required_for_gmc=True`): `id, title, description, link, image_link, availability, condition, price, google_product_category, brand`.

| Campo | Regola validità | Severità | Messaggio `_missing_fields` |
|---|---|---|---|
| `id` | non vuoto; ≤50 char | BLOCCA | `id assente` / `id troppo lungo (>50)` |
| `title` | non vuoto; ≤150; WARN se <30 | BLOCCA vuoto/>150 · AVVISA <30 | `title assente` / `title >150 char` / `title troppo corto (<30)` |
| `description` | non vuota; ≤5000 | BLOCCA vuota | `description assente` |
| `link` | `http://`/`https://` | BLOCCA | `link assente` / `link non valido (no http/https)` |
| `image_link` | `https://` (GMC esige HTTPS) | BLOCCA | `image_link assente` / `image_link non https` |
| `availability` | ∈ enum Google underscore | BLOCCA | `availability fuori enum` |
| `condition` | ∈ {new,refurbished,used} | BLOCCA | `condition fuori enum` |
| `price` | `^\d+(\.\d{1,2})?\s[A-Z]{3}$`, >0 | BLOCCA | `price assente` / `price senza valuta` / `price = 0` / `price formato non valido` |
| `google_product_category` | non vuota; `>` o ID numerico; WARN single-token | BLOCCA vuota · AVVISA sospetta | `google_product_category assente` / `... path sospetto` |
| `brand` | non vuoto | BLOCCA | `brand assente` |

**identifier_exists** (AVVISA, mai BLOCCA — `no` è ammesso): mancano sia `gtin` sia `mpn` → `identificatori assenti (gtin/mpn) — identifier_exists=no`; `gtin` presente ma checksum invalido (`validation.is_valid_gtin`) → `gtin checksum non valido`.

> Calcolare lo status su un df passato per `build_google_feed` (availability/price/condition già canonici), oppure normalizzare on-the-fly con i `_normalize_*`.

---

## 4. `compute_export_status(row) -> (level, export_ready, missing)`

```python
import re, pandas as pd
_AVAIL = {"in_stock", "out_of_stock", "preorder", "backorder"}
_COND  = {"new", "refurbished", "used"}
_PRICE_RE = re.compile(r"^\d+(\.\d{1,2})?\s[A-Z]{3}$")
_AI_ATTRS = ["brand", "color", "size", "material", "pattern", "gender", "age_group",
             "product_highlight", "product_detail", "product_type"]

def g(row, col):
    if col not in row:
        return ""
    v = row[col]
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    s = str(v).strip()
    return "" if s.lower() in ("nan", "none", "null", "<na>") else s

def _is_url(s, schemes=("http://", "https://")):
    return s.startswith(schemes)

def _category_valid(s):                      # -> (valida, sospetta)
    if not s:
        return (False, False)
    if ">" in s or s.isdigit():
        return (True, False)
    return (True, True)

def compute_export_status(row):
    """level ∈ {grezzo, arricchito, pronto_export}; export_ready bool; missing list[str].
    L'asse errore/da-rivedere resta su _enrichment_status (badge §5)."""
    missing = []
    status = g(row, "_enrichment_status").lower()
    title, desc, cat = g(row, "title"), g(row, "description"), g(row, "google_product_category")
    title_o, desc_o = g(row, "title_original"), g(row, "description_original")
    cat_ok, cat_suspect = _category_valid(cat)
    text_rewritten = bool(title) and bool(desc) and not (title == title_o and desc == desc_o and title_o != "")
    is_arricchito = (status in ("ok", "cached") and title and desc and cat_ok and cat
                     and any(g(row, a) for a in _AI_ATTRS) and text_rewritten)
    if not is_arricchito:
        return ("grezzo", False, [])

    blocking = 0
    _id = g(row, "id")
    if not _id: missing.append("id assente"); blocking += 1
    elif len(_id) > 50: missing.append("id troppo lungo (>50)"); blocking += 1
    if not title: missing.append("title assente"); blocking += 1
    elif len(title) > 150: missing.append("title >150 char"); blocking += 1
    elif len(title) < 30: missing.append("title troppo corto (<30)")          # AVVISA
    if not desc: missing.append("description assente"); blocking += 1
    link = g(row, "link")
    if not link: missing.append("link assente"); blocking += 1
    elif not _is_url(link): missing.append("link non valido (no http/https)"); blocking += 1
    img = g(row, "image_link")
    if not img: missing.append("image_link assente"); blocking += 1
    elif not _is_url(img, ("https://",)): missing.append("image_link non https"); blocking += 1
    if g(row, "availability") not in _AVAIL: missing.append("availability fuori enum"); blocking += 1
    if g(row, "condition") not in _COND: missing.append("condition fuori enum"); blocking += 1
    price = g(row, "price")
    if not price: missing.append("price assente"); blocking += 1
    elif not _PRICE_RE.match(price): missing.append("price formato non valido"); blocking += 1
    else:
        try:
            if float(price.split()[0]) <= 0: missing.append("price = 0"); blocking += 1
        except ValueError:
            missing.append("price formato non valido"); blocking += 1
    if not cat: missing.append("google_product_category assente"); blocking += 1
    elif cat_suspect: missing.append("google_product_category path sospetto")  # AVVISA
    if not g(row, "brand"): missing.append("brand assente"); blocking += 1
    gtin, mpn = g(row, "gtin"), g(row, "mpn")
    if not gtin and not mpn:
        missing.append("identificatori assenti (gtin/mpn) — identifier_exists=no")   # AVVISA
    elif gtin and not is_valid_gtin(gtin):
        missing.append("gtin checksum non valido")                                   # AVVISA

    export_ready = (blocking == 0)
    return ("pronto_export" if export_ready else "arricchito", export_ready, missing)
```

Colonne calcolate da salvare accanto a `_enrichment_status`: **`_export_ready` (bool)** e **`_missing_fields` (list[str])** — JSON-encode su parquet/sqlite. Stesse regole di persistenza P0 già risolte per `_enrichment_status` (`merge_enriched`). NB: vettorizzare su 2767 righe (df.apply o costruzione colonnare) mantenendo identici i messaggi; cache-are su `_df_fingerprint` come per `product_keys_for_df`.

---

## 5. `status_badge` → 5° stato "Pronto export"

`utils/ui.py` ha già `_STATUS_STYLES` (4 chiavi) + `_status_kind`. Aggiungere:
```python
_STATUS_STYLES["pronto_export"] = ("Pronto export", "#2F6FED", "#EEF4FF", "✓")  # blue-500 / blue-50
```

Mapping combinato (2 assi, precedenza dall'alto):

| Condizione | Badge |
|---|---|
| `_enrichment_status` inizia con `error` | Errore |
| `_enrichment_status` ∈ {cached, stale} | Da rivedere |
| `level == "pronto_export"` (status ok) | Pronto export |
| `level == "arricchito"` (status ok) | Arricchito |
| else (grezzo/empty) | Grezzo |

Nuova funzione, non rompe l'API esistente (`status_badge(status)` resta a 4 stati):
```python
def export_status_badge(enrichment_status: str, level: str) -> str:
    # applica la tabella sopra, riusa _STATUS_STYLES e lo stesso markup <span> soft
```

---

## Dove va usato

- **Card grid / tabella** (enrichment_ai.py): badge per-prodotto via `export_status_badge`.
- **Catalog Optimizer** (scarica_catalogo.py): pannello "Pronti all'export N / Da completare M" + drill-down `_missing_fields`; bloccare/avvisare export sui BLOCCA.
- **Sidebar contesto** (ui.render_sidebar_status): conteggio "Pronti export".

## File rilevanti
- `utils/catalog_optimizer.py` (221-231 normalize; 397/432 wiring build)
- `utils/ui.py` (`_STATUS_STYLES`, `status_badge` ~1188-1225)
- `utils/validation.py` (`is_valid_gtin`)
- `utils/exporter.py` (verificato passthrough)
