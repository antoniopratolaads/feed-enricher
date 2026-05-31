# Feed Enricher Pro — Design Spec Fase 2

> Spec implementabile da `streamlit-dev`. Niente codice di produzione: wireframe + token + microcopy + note di fattibilità Streamlit.
> Stack: Streamlit puro. Responsività via `st.columns` + HTML/CSS in `st.markdown(unsafe_allow_html=True)` + media query nel tema (`utils/ui.py::apply_theme`). **Zero JS lato client.**
> Data verificata: immagine = `image_link` (fallback `additional_image_link`), cliente reale = 2767 prodotti, campi `id/title/brand/price/_enrichment_status`.

> **Aggancio al codice reale** (verificato leggendo `utils/ui.py`):
> - I token CSS esistono GIÀ come variabili nel `<style>` di `apply_theme()`: `--blue-500 #2F6FED`, `--blue-600 #2160DC`, `--blue-50 #EEF4FF`, `--blue-100 #DCE7FE`, `--text-primary #0A0A0F`, `--text-secondary #4B5563`, `--text-muted #9CA3AF`, `--border #E5E7EB`, `--border-strong #D1D5DB`, `--bg-card #FFFFFF`, `--bg-subtle #F4F5F7`, `--success #10B981`, `--success-bg #ECFDF5`, `--warning #F59E0B`, `--warning-bg #FFFBEB`, `--danger #EF4444`, `--danger-bg #FEF2F2`, più `--shadow-xs/sm/md/lg/blue`, `--radius-sm/md/lg/xl`. **NON inventare nuovi nomi.** Vedi mapping in §0bis.
> - Esiste già la classe `.preview-card`/`.step-card` con hover-lift (`translateY(-1px)` + `--shadow-md`). **La product card riusa questo pattern.**
> - `stepper(steps, current)` (riga 757) già renderizza cerchi 36px + linea di progresso assoluta (`left:12% right:12%`). **Estendere, non riscrivere** (vedi §2b).
> - `render_sidebar_status()` (riga 724) legge già `st.session_state["feed_df"]` e `st.session_state["config"]`. La sidebar "Contesto attivo" estende QUESTO stato.
> - I CTA di navigazione puntano a `client_pages/*.py` (pattern reale: `st.switch_page("client_pages/settings.py")`).
> - Esistono già `cost_estimate_card(n_rows, model)`, `cost_projection_table(n_rows)`, `empty_state(icon,title,description,cta_label,cta_page,cta_key)`, `diff_view(label,before,after)`, `LoadingProgress`, `guarded(block_name)`, `page_header(title,subtitle)`. **Riusali, non duplicare.**

---

## 0. Design Language (principi)

1. **Pulito e arioso, ma data-dense onesto.** Power user (agenzia) vogliono vedere molto. La densità si ottiene con gerarchia tipografica e spacing scale, NON comprimendo. Whitespace = `--sp-4 (16px)` tra card, `--sp-5 (24px)` tra sezioni.
2. **Feedback immediato.** Ogni azione ha riscontro percepito istantaneo: card "si accende" alla selezione, contatore selezionati live, riga di conferma dinamica sopra "Avvia".
3. **Lo stato è il protagonista.** I 5 stati enrichment hanno colore/icona coerenti ovunque (card, badge, metriche, tabella, sidebar). Un solo linguaggio cromatico.
4. **Micro-interazioni solo CSS, mai gratuite.**
   - Hover card: `transform: translateY(-2px)` + da `--shadow-xs` a `--shadow-md`, `transition: all .14s ease` (già fa così `.preview-card`).
   - Selezione: bordo → `--blue-500`, sfondo → `--blue-50`, checkmark in alto a destra.
   - **Vietato**: spinner finti, parallax, animazioni > 200ms, qualsiasi cosa che richieda JS. (Esiste già `fadeInUp 0.3s` sul main container: ok, è l'unico ammesso.)
5. **Calma cromatica.** Il colore è riservato agli STATI e alla CTA primaria. Il resto è inchiostro/grigio/bianco. Reference: Polaris (struttura), Linear/Vercel (sobrietà, ombre leggere) — coerente col tema "Horizon" già implementato.

### Spacing scale (base 4px — usala ovunque, no valori arbitrari)
`--sp-1:4 · --sp-2:8 · --sp-3:12 · --sp-4:16 · --sp-5:24 · --sp-6:32 · --sp-8:48` (px). Mappa sul ritmo già in uso nel tema (padding card 20–24px, gap metriche).

### Radius (già definiti)
`--radius-sm:8px (badge, input) · --radius-md:12px (card, banner) · --radius-lg:16px (pannelli/empty state) · --radius-xl:20px`.

### Ombre (già definite — stile Linear/Vercel)
- a riposo: `--shadow-xs` + `border:1px solid var(--border)`
- hover: `--shadow-md` (lift `translateY(-2px)`)
- selezione: `box-shadow: 0 0 0 2px var(--blue-500), var(--shadow-md)` (combinazione inline, niente nuova variabile)

### Tipografia (scala compatta, data-dense — coerente col tema)
`Display H1 2.5rem/700 · H2 1.625rem/700 · H3 1.125rem/600 · Body 14px/400 · Label 12px/600 uppercase tracking .04em · Caption 12–14px/400 muted · Mono(prezzo/id) 13px/600`. Font: Geist/Inter (già caricati).

---

## 0bis. Mapping nomi token (spec → variabile reale in `ui.py`)

streamlit-dev: dove nei wireframe scrivo `--hz-*`, usa la variabile reale a destra. **NON creare variabili nuove.**

| Nome usato nei wireframe | Variabile CSS reale già in `apply_theme()` |
|---|---|
| `--hz-primary` | `var(--blue-500)` `#2F6FED` |
| `--hz-primary-weak` (sfondo selez.) | `var(--blue-50)` `#EEF4FF` |
| `--hz-primary-border` (bordo soft) | `var(--blue-100)` `#DCE7FE` |
| `--hz-ink` | `var(--text-primary)` `#0A0A0F` |
| `--hz-muted` (label) | `var(--text-secondary)` `#4B5563` |
| `--hz-faint` (metadati deboli) | `var(--text-muted)` `#9CA3AF` |
| `--hz-border` | `var(--border)` `#E5E7EB` |
| `--hz-surface` | `var(--bg-card)` `#FFFFFF` |
| `--hz-bg` | `var(--bg-subtle)` `#F4F5F7` |
| `--hz-success` | `var(--success)` `#10B981` |
| `--hz-danger` | `var(--danger)` `#EF4444` |
| `--hz-warn` | `var(--warning)` `#F59E0B` |

> **Regola contrasto**: testo su badge pieno = bianco. Testo su badge "soft" (sfondo `*-bg` o alpha) = il colore pieno (leggibile sul soft).

---

## 2a. Sidebar "Contesto attivo"

**Job**: in ogni momento l'utente sa SU CHI lavora e con quale feed, senza tornare allo step 1.

```
┌──────────────────────────────┐
│  Feed Enricher Pro           │
│  ─────────────────────────   │
│  CONTESTO ATTIVO             │   ← Label 12/600 uppercase muted (stile h3 sidebar già esistente)
│                              │
│  ● Climando                  │   ← H3, dot = stato connessione/AI pronto
│    Cliente · settore Casa    │   ← Caption secondary
│                              │
│  ▣ feed_principale.xml       │   ← Body 600, icona feed
│    Google Merchant + Meta    │   ← Caption
│                              │
│  ┌──────────┬──────────┐    │
│  │  2.767   │   412    │    │   ← due mini-metriche affiancate
│  │ prodotti │ da arr.  │    │
│  └──────────┴──────────┘    │
│                              │
│  Stato feed                  │
│  ● Arricchiti       2.103    │   ← pallino verde
│  ● Da rivedere        180    │   ← pallino ambra
│  ● Errori              72    │   ← pallino rosso
│  ○ Grezzi             412    │   ← pallino grigio
│                              │
│  [ Cambia cliente / feed ]   │   ← link secondario → step 1
│  ─────────────────────────   │
│  ◐ Costo sessione  $1.84     │   ← footer
└──────────────────────────────┘
```

**Microcopy**
- Header sezione: `CONTESTO ATTIVO`
- Sotto cliente: `Cliente · settore {settore}`
- Sotto feed: `{target}` es. `Google Merchant + Meta`
- Mini-metriche: `prodotti` / `da arricchire` (tronca `da arr.`)
- Blocco: `Stato feed`
- Link: `Cambia cliente / feed`
- Footer: `Costo sessione`
- Empty (nessun cliente/feed): riusa `render_sidebar_status` attuale → `○  Nessun feed caricato`.

**FATTIBILITÀ STREAMLIT**: estendere `render_sidebar_status()` (riga 724). Legge già `feed_df` (conteggio) e `config` (API key). Aggiungi: cliente attivo (`st.session_state.get("active_client")`), settore, nome feed, e i 5 conteggi via `feed_df["_enrichment_status"].value_counts()` calcolati UNA volta (cache-ato). Mini-metriche + righe "Stato feed" = **un solo blocco HTML** in `st.markdown` (la sidebar è stretta: `st.columns(2)` lì produce gutter sproporzionati). Riga stato = `<div style="display:flex; justify-content:space-between">`. Dot = `<span style="color:var(--success)">●</span>`. Link "Cambia" = `st.button` secondario + `st.switch_page("client_pages/...")`. Mantieni il box `background:var(--bg-subtle); border:1px solid var(--border); border-radius:10px` già usato dalla funzione.

---

## 2b. Stepper (4 step)

`1 Cliente & Sorgente · 2 Enrichment · 3 Refine · 4 Export`

```
LARGO (≥ ~900px):
┌───────────────────────────────────────────────────────────────────┐
│   ✓ ──────────── ② ──────────── ③ ············ ④                  │
│  Cliente &      Enrichment      Refine         Export              │
│  Sorgente       In corso        In attesa      In attesa          │
└───────────────────────────────────────────────────────────────────┘
   ✓ = done (cerchio blu pieno + check)   ② = active (cerchio bianco bordo blu)   ③④ = pending grigio

STRETTO (<640px): collassa a "step corrente + progresso"
┌───────────────────────────────┐
│  Step 2 di 4 · Enrichment      │
│  ●●○○                          │   ← 4 pallini, primi 2 pieni blu
└───────────────────────────────┘
```

**Stati** (riconciliati col rendering reale di `stepper()`):
- `done` (i<current): cerchio `#2F6FED` pieno + `✓` bianco, connettore pieno blu (già fa così), label `#0A0A0F`.
- `active` (i==current): cerchio bianco bordo `#2F6FED` + numero blu + ombra `0 2px 8px rgba(47,111,237,.25)` (già implementata), label `#0A0A0F` 600, sottotitolo `In corso`.
- `pending` (i>current): cerchio bianco bordo `#E5E7EB`, numero `#9CA3AF`, label muted, sottotitolo `In attesa`.

**Microcopy** sottotitoli (NUOVO: aggiungere riga sotto la label): done → nessuno · active → `In corso` · pending → `In attesa`.

**FATTIBILITÀ STREAMLIT**: `stepper()` esiste (riga 757) e già fa cerchi/linea/colori giusti. Modifiche minime: (1) aggiungere il sottotitolo di stato sotto la label; (2) responsività <640px **CSS-only** (Streamlit non legge la viewport in Python senza JS). Soluzione: dentro l'unico `st.markdown` di `stepper()`, inietta DUE markup — `.hz-stepper-full` (quello attuale) e `.hz-stepper-mini` (riga `Step N di T · {label}` + 4 pallini) — più una media query nel tema: `@media(max-width:640px){.hz-stepper-full{display:none}.hz-stepper-mini{display:block}} @media(min-width:641px){.hz-stepper-mini{display:none}}`. Limite: la soglia px è del browser, non del container Streamlit — accettabile.

---

## ★ 2c. PRODUCT CARD GRID (il pezzo centrale)

**Job**: selezionare visivamente quali prodotti arricchire, riconoscendoli dall'immagine, su un catalogo di migliaia di item, senza far morire Streamlit.

### Anatomia card

```
┌───────────────────────────┐
│                       ✓    │  ← checkmark selezione (alto dx), visibile solo se selez.
│   ┌───────────────────┐   │
│   │                   │   │  ← IMMAGINE 1:1, object-fit:cover, radius top
│   │   [image_link]    │   │     placeholder se manca (vedi sotto)
│   │                   │   │
│   └───────────────────┘   │
│  ● Da rivedere            │  ← BADGE stato (riga propria, soft) — pallino ambra
│  Tovaglia lino grezzo …   │  ← TITLE max 2 righe, ellipsis
│  Maison Blanc             │  ← brand, caption muted (ometti se vuoto)
│  € 49,90                  │  ← prezzo, mono 600 ink ("—" se manca)
│  [ ☑ Seleziona ]          │  ← checkbox NATIVO sotto la card
└───────────────────────────┘
   selezionata: bordo blu 2px + sfondo --blue-50 + box-shadow 0 0 0 2px #2F6FED, --shadow-md
```

**Placeholder no-image** (elegante, mai "rotto"):
```
┌───────────────────┐
│        ▦          │   ← icona image-off centrata, --text-muted, 32px
│   Nessuna         │   ← Caption muted
│   immagine        │
└───────────────────┘   sfondo --bg-subtle
```

### Griglia responsive
| Viewport | Card/riga | Gutter |
|---|---|---|
| Largo ≥1200px | 4 | 16px |
| Medio 768–1199 | 3 | 16px |
| Stretto <768 | 2 | 12px |

### Selezione — pattern ibrido (IL nodo tecnico)
Card visiva in HTML (bella) + checkbox nativo Streamlit (funzionale), allineati nella stessa colonna:
- Card visiva = `st.markdown(card_html)` — NON cliccabile (un `<div>` HTML non emette eventi Python senza JS/components).
- Selezione = `st.checkbox("Seleziona", key=f"sel_{product_key}", on_change=...)` SOTTO la card.
- "Card accesa" = quando `product_key in selected_keys`, il markup HTML riceve la classe `.is-selected` (bordo blu + `--blue-50`). Lo stato si legge al render da `session_state`.

> **Perché non card-intera-cliccabile?** Senza JS non si cattura il click su un `<div>`. Il checkbox nativo è l'unico modo robusto. Lo rendiamo elegante (label `Seleziona`, full-width sotto la card).

### Selezione che PERSISTE tra pagine (requisito critico)
- **Mai per indice**. La selezione vive in `st.session_state["selected_keys"] = set()` di **product_key stabili** (`id` del prodotto, o `f"{client}:{feed}:{id}"` se gli id non sono globalmente unici).
- Ogni card: `value = product_key in selected_keys`; nel callback `on_change` fai add/discard sul set.
- Leggi SEMPRE da `selected_keys` (fonte di verità), MAI iterando le key `sel_*` (i widget di pagine non renderizzate restano in session_state ma non vanno usati per ricostruire il set).

### Paginazione (2767 prodotti = non renderizzabili tutti)
- **Cap duro: max 48 card per rerun.** Oltre, Streamlit degrada (HTML + N checkbox = inusabile).
- Default **24 card/pagina** (toggle 24/48 per power user).
- Filtra/ordina la lista completa in pandas (cache), poi `page_slice = df.iloc[start:start+page_size]`; renderizza solo lo slice.
- Navigazione in fondo: `‹ Precedente · Pagina 3 / 116 · Successiva ›`. **Preferire paginazione classica a "infinite load"**: ogni "carica altri" è un rerun che ri-renderizza TUTTE le card già caricate → con append illimitato torni al problema performance.

### Barra azioni (sopra la griglia)
```
┌───────────────────────────────────────────────────────────────────────────┐
│  [⭐ Da arricchire] [⚠ Errori] [Tutti]      🔍 Cerca…   Brand ▾  Categoria ▾│
├───────────────────────────────────────────────────────────────────────────┤
│  412 prodotti · 37 selezionati   [Seleziona pagina] [Deseleziona tutto]     │
│                                              Vista: [▦ Card] [☰ Tabella]  24▾│
└───────────────────────────────────────────────────────────────────────────┘
```

**Microcopy barra**
- Preset (segmented): `⭐ Da arricchire` (default attivo) · `⚠ Errori` · `Tutti`
- Search placeholder: `Cerca per titolo o ID…`
- Filtri: `Brand` / `Categoria` (multiselect, label sopra muted)
- Contatore: `{N} prodotti · {M} selezionati` (M in `--blue-500` 600)
- Azioni bulk: `Seleziona pagina` · `Deseleziona tutto`
- Toggle vista: `▦ Card` / `☰ Tabella` · Page size: `24` / `48`

### Toggle Card vs Tabella
- **Card** = default (riconoscimento visivo).
- **Tabella compatta** = power user: la `st.dataframe`/`data_editor` ATTUALE non si butta, si affianca. Colonne: `☑ · img · ID · Title · Brand · Prezzo · Stato`. Condivide lo STESSO `selected_keys`. Usa `st.column_config.ImageColumn` (thumbnail da `image_link`) e `st.column_config.CheckboxColumn` (selezione).

**FATTIBILITÀ STREAMLIT (card grid)**:
- Per ospitare un checkbox sotto ogni card servono widget Python → **`st.columns(4)` fisso desktop**, ogni colonna = `st.markdown(card_html)` + `st.checkbox`. Un CSS-Grid `auto-fill` puro sarebbe più responsive ma non può inframezzare widget → escluso.
- Responsività <768: media query CSS sul markup interno (immagine/font); le colonne Streamlit non si ricolonnano perfettamente sotto 768px → **limite documentato, accettato**.
- Riusa la classe `.preview-card` (hover-lift già pronto), aggiungi solo `.is-selected`.
- Performance: cap 24–48 card/rerun; `<img loading="lazy">` nel markup (non scarica tutte le 24 insieme); `@st.cache_data` sulla lista filtrata keyed su (client, feed, preset, search, brand, categoria); callback di selezione mirati (mutano solo il set, NON ri-filtrano 2767 righe).

---

## 2d. Config AI (basso carico cognitivo)

```
┌─────────────────────────────────────────────────────────────┐
│  Configurazione AI                                          │
│                                                             │
│  Livello qualità                                           │
│  ┌──────────┐ ┌──────────────┐ ┌──────────┐               │
│  │Economico │ │ Bilanciato ✓ │ │ Massima  │               │  ← 3 card-radio, Bilanciato default
│  │ veloce   │ │ consigliato  │ │ premium  │               │
│  │ $        │ │ $$           │ │ $$$      │               │
│  └──────────┘ └──────────────┘ └──────────┘               │
│                                                             │
│  Settore   [ Casa & Arredo ]  (ereditato dal cliente)      │  ← read-only/prefilled
│  Target    [ Conversione ▾ ]  Conversione · SEO · Brand    │
│                                                             │
│  ─────────────────────────────────────────────────────────│
│  ▸ Arricchirai 37 prodotti · livello Bilanciato            │  ← RIGA CONFERMA DINAMICA
│    Stima ~€0,69 · ~2 min   (riusa cost_estimate_card)       │
│                                                             │
│              [  Avvia enrichment  ]                        │  ← CTA primaria full-width
└─────────────────────────────────────────────────────────────┘
```

**Mapping livello → modello** (usa le chiavi reali di `_PRICES` in `ui.py`):
- `Economico` → `claude-haiku-4-5` (tier 3, $1/$5) o `gpt-5-nano`
- `Bilanciato` (default) → `claude-sonnet-4-6` (tier 4, $3/$15) — è anche il fallback di `estimate_cost`
- `Massima` → `claude-opus-4-6` (tier 5, $15/$75)

**Microcopy**
- Titolo: `Configurazione AI`
- Livelli: `Economico` (sub `veloce`, badge `$`) · `Bilanciato` (sub `consigliato`, `$$`) · `Massima` (sub `premium`, `$$$`)
- `Settore` caption: `ereditato dal cliente`
- `Target`: `Conversione · SEO · Brand`
- Riga conferma: `Arricchirai {M} prodotti · livello {livello}` + stima
- Se M=0: riga warn → `Seleziona almeno un prodotto per avviare.` + CTA disabilitata
- CTA: `Avvia enrichment`

**FATTIBILITÀ STREAMLIT**: 3 livelli = `st.radio(horizontal=True)` (semplice) o 3 `st.columns` con bottone per look card-radio (stato in session_state). Settore = `st.text_input(disabled=True)`. Target = `st.selectbox`. Riga conferma = **riusa `cost_estimate_card(len(selected_keys), model_del_livello)`** che già mostra €, caching, batch. CTA = `st.button(type="primary", use_container_width=True, disabled=(M==0))`. Per la proiezione "quale modello conviene": `cost_projection_table(M)` in un `st.expander`.

---

## 3. Palette stati enrichment (5 stati — fonte unica)

| Stato | Icona | Colore (var reale) | Sfondo soft (var reale) | Significato |
|---|---|---|---|---|
| Grezzo | `○` | `var(--text-muted)` `#9CA3AF` | `var(--bg-subtle)` `#F4F5F7` | mai arricchito, sorgente raw |
| Arricchito | `●` | `var(--success)` `#10B981` | `var(--success-bg)` `#ECFDF5` | AI ha generato contenuti, ok |
| Pronto export | `✓` | `var(--blue-500)` `#2F6FED` | `var(--blue-50)` `#EEF4FF` | arricchito + validato, esportabile |
| Errore | `✕` | `var(--danger)` `#EF4444` | `var(--danger-bg)` `#FEF2F2` | enrichment fallito |
| Da rivedere | `!` | `var(--warning)` `#F59E0B` | `var(--warning-bg)` `#FFFBEB` | stale/cached/output sospetto |

**Mapping `_enrichment_status` reale → stato UI** (i valori reali sono `ok/cached/error/empty/stale`):
`empty` → Grezzo · `ok` → Arricchito · `ok`+validato → Pronto export · `error` → Errore · `cached`/`stale` → Da rivedere.

**Microcopy badge**: `Grezzo · Arricchito · Pronto export · Errore · Da rivedere`.

**Uso coerente**: stesso colore+icona in (1) badge card, (2) colonna Stato tabella, (3) blocco "Stato feed" sidebar, (4) metriche overview.

**FATTIBILITÀ STREAMLIT**: centralizza un nuovo helper `status_badge(status) -> str (HTML)` in `ui.py` (accanto a `diff_view`), che restituisce `<span>` soft (sfondo `*-bg`, testo colore pieno, `border-radius:var(--radius-sm)`, padding `2px 8px`). Nella `st.dataframe` (cella non-HTML): usa pallino unicode + label testo come compromesso.

---

## Empty states (riusa `empty_state(...)` esistente — firma con cta_page → `client_pages/...`)

- **Nessun cliente/feed**: `empty_state("📭", "Nessun feed caricato", "Vai allo step 1 per collegare un cliente e importare un feed.", "Vai a Cliente & Sorgente", "client_pages/...")`.
- **Filtro senza risultati**: `empty_state("🔍", "Nessun prodotto trovato", "Nessun prodotto corrisponde ai filtri. Prova a rimuovere un filtro o cambia preset.", "Azzera filtri", ...)`.
- **Preset Errori vuoto (caso positivo)**: `empty_state("✅", "Nessun errore", "Tutti i prodotti elaborati sono andati a buon fine.")` (no CTA).
- **Nessuna selezione (config AI)**: CTA disabilitata + caption `Seleziona almeno un prodotto per avviare.`

## Edge cases

- **Immagine 404/mancante**: senza JS niente `onerror` affidabile → se `image_link` mancante o non-https usa placeholder lato Python; per i 404 residui metti `background:var(--bg-subtle)` dietro l'`<img>` così un fallimento è grigio neutro, non bianco rotto. Limite accettato.
- **Title lunghissimo**: clamp 2 righe (`-webkit-line-clamp:2; overflow:hidden`).
- **Prezzo mancante**: `—` muted, mai `€ 0,00`.
- **Brand vuoto**: ometti la riga (no label vuota).
- **"Seleziona tutti i 2767"**: NON di default. Se serve: bottone `Seleziona tutti i filtrati (412)` con `st.warning` di conferma + costo stimato PRIMA di procedere (evita enrichment accidentale costoso).
- **Catalogo enorme + filtri**: cache la lista filtrata; non ri-filtrare 2767 righe a ogni toggle (callback mirati sul set).

---

## Riepilogo limiti no-JS (accettati)
1. Responsività "vera" 4→3→2 con CSS-Grid non è compatibile coi checkbox per card → si usa `st.columns(4)` fisso + media query sul markup interno.
2. La soglia responsive è del browser, non del container Streamlit.
3. Hover/transizioni solo sul markup HTML custom, non sui widget nativi.
4. Selezione = checkbox nativo (no card-intera-cliccabile).
5. Performance: cap 24–48 card/rerun, `<img loading="lazy">`, cache dataframe filtrato, selezione per product_key (mai per indice).

> **Implementabile da streamlit-dev senza altre domande. Stima onesta: 14–20h** — card grid + persistenza selezione + toggle tabella ≈ 8–10h; sidebar contesto (estendere `render_sidebar_status`) ≈ 2h; stepper responsive + sottotitoli ≈ 1–2h; config AI + riga dinamica (riusa `cost_estimate_card`) ≈ 2h; `status_badge` + applicazione coerente ≈ 1–2h; rifiniture CSS/media query nel tema ≈ 2h.
