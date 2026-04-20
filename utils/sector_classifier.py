"""Per-product sector auto-classification for mixed catalogs.

Two tiers:
  1. RULE-BASED (fast, free) — keyword matching on title/description/category
     + Google taxonomy path matching when present.
  2. AI FALLBACK (optional) — when rule score is low, ask Claude Haiku
     to classify in one call. Batched for efficiency.

Used when the user picks `sector="auto"` in Enrichment AI so each row
gets the most appropriate sector-specific prompt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

import pandas as pd

# ============================================================
# KEYWORD + TAXONOMY MARKERS PER SECTOR
# ============================================================
# Each entry:
#   keywords_strong — score 3 each when present anywhere in title/desc
#   keywords_weak   — score 1 each
#   taxonomy_hints  — score 4 each when found in google_product_category or product_type
#   exclude         — if any match, subtract 4 (guards against false positives)
# ------------------------------------------------------------

SECTOR_RULES: dict[str, dict] = {
    "abbigliamento": {
        "keywords_strong": [
            "maglia", "t-shirt", "tshirt", "camicia", "felpa", "pantaloni", "jeans",
            "giacca", "giubbotto", "cappotto", "gonna", "vestito", "abito",
            "tuta", "canotta", "maglione", "cardigan", "polo", "bermuda", "shorts",
            "intimo", "biancheria", "calza", "calzini", "leggings", "pigiama",
            "costume", "bikini", "taglia s", "taglia m", "taglia l", "taglia xl",
        ],
        "keywords_weak": ["uomo", "donna", "unisex", "cotone", "lana", "lino", "elastan"],
        "taxonomy_hints": ["apparel & accessories > clothing", "shirts", "pants", "dresses", "outerwear"],
        "exclude": ["scarpe", "stivali", "sneakers", "mocassini", "sandalo"],
    },
    "scarpe": {
        "keywords_strong": [
            "scarpe", "sneakers", "sneaker", "stivali", "stivaletti", "mocassini",
            "sandali", "sandalo", "ciabatte", "ciabatta", "infradito", "ballerine",
            "décolleté", "decollete", "pumps", "running shoes", "trail shoes",
            "trekking boot", "scarponcino", "zoccoli", "scarpe calcio",
        ],
        "keywords_weak": ["taglia 40", "taglia 41", "taglia 42", "taglia 43", "taglia 44", "eu 38", "eu 40"],
        "taxonomy_hints": ["shoes", "footwear", "athletic shoes", "running shoes"],
        "exclude": [],
    },
    "elettronica": {
        "keywords_strong": [
            "smartphone", "iphone", "android", "tablet", "laptop", "notebook",
            "desktop", "monitor", "cuffie", "auricolari", "earphones", "soundbar",
            "smart tv", " tv ", "televisore", "televisori", "console", "playstation",
            "xbox", "nintendo", "fotocamera", "reflex", "mirrorless", "obiettivo",
            "drone", "smartwatch", "sportwatch", "fitness tracker",
            "router", "modem", "access point", "switch", "ups", "ssd", "hard disk",
            "memoria ram", "processore", "schede video", "gpu",
        ],
        "keywords_weak": [
            "gb", "tb", "4k", "8k", "hdmi", "usb-c", "wifi", "bluetooth",
            "ghz", "oled", "qled", "amoled", "retina",
        ],
        "taxonomy_hints": ["electronics", "mobile phones", "laptops", "televisions", "cameras"],
        "exclude": ["elettrodomestici", "frigorifero", "lavatrice", "forno", "microonde"],
    },
    "elettrodomestici": {
        "keywords_strong": [
            "lavatrice", "asciugatrice", "lavasciuga", "frigorifero", "congelatore",
            "freezer", "forno", "microonde", "piano cottura", "cappa aspirante",
            "lavastoviglie", "robot aspirapolvere", "aspirapolvere", "scopa elettrica",
            "friggitrice ad aria", "macchina caffè", "ferro da stiro", "bollitore",
            "tostapane", "frullatore", "robot cucina", "planetaria", "estrattore di succo",
            "centrifuga", "impastatrice",
        ],
        "keywords_weak": ["kg", "litri", "classe a", "classe b", "classe c", "kwh", "db"],
        "taxonomy_hints": ["household appliances", "kitchen appliances", "laundry appliances", "floor care"],
        "exclude": [],
    },
    "arredamento": {
        "keywords_strong": [
            "divano", "divani", "poltrona", "poltrone", "sedia", "sedie", "sgabello",
            "tavolo", "tavolino", "tavoli", "scrivania", "letto", "letti", "materasso",
            "comodino", "cassettiera", "armadio", "guardaroba", "libreria",
            "credenza", "madia", "specchio", "applique", "lampadario", "lampada",
            "mensola", "scaffale", "tappeto", "tenda", "cuscino", "copripiumino",
            "lenzuola", "coperta", "plaid", "tovaglia", "tovaglietta",
        ],
        "keywords_weak": ["massello", "rovere", "noce", "faggio", "MDF", "velluto", "cotone", "tessuto"],
        "taxonomy_hints": ["furniture", "home & garden > decor", "linens & bedding"],
        "exclude": ["elettrodomestici", "termoarredo", "scaldasalviette"],
    },
    "food": {
        "keywords_strong": [
            "pasta", "riso", "pane", "biscotti", "cioccolato", "caramelle",
            "olio extravergine", "olio di oliva", "aceto balsamico", "vino", "birra",
            "liquore", "amaro", "grappa", "whisky", "gin", "rum", "champagne",
            "acqua minerale", "succo di frutta", "caffè", "the ", "tisana", "infuso",
            "yogurt", "formaggio", "salumi", "prosciutto", "mortadella", "salame",
            "tonno", "salmone", "conserva", "marmellata", "miele", "zucchero",
            "farina", "sale", "spezie", "condimento", "salsa",
        ],
        "keywords_weak": ["bio", "dop", "igp", "senza glutine", "vegano"],
        "taxonomy_hints": ["food, beverages & tobacco", "food items", "beverages"],
        "exclude": ["pet", "integratore", "farmaco"],
    },
    "sport": {
        "keywords_strong": [
            "racchetta", "pallone", "pallina", "manubri", "manubrio",
            "tapis roulant", "cyclette", "ellittica", "bilanciere", "dischi pesi",
            "materassino", "yoga mat", "tappetino yoga", "kit fitness", "borsa sport",
            "zaino trekking", "scarpe running",
            "tuta tecnica", "canotta tecnica", "short running",
            "cardiofrequenzimetro", "smartwatch sport",
            "bicicletta", "mountain bike", "bici corsa", "casco bici", "scarpe calcio",
            "parastinchi", "guantoni boxe",
        ],
        "keywords_weak": ["running", "trail", "tennis", "calcio", "palestra", "fitness", "gym"],
        "taxonomy_hints": ["sporting goods", "athletics", "exercise & fitness", "activewear"],
        "exclude": ["gioco tavolo"],
    },
    "giocattoli": {
        "keywords_strong": [
            "gioco", "giocattolo", "giochi per bambini", "lego", "playmobil",
            "action figure", "peluche", "bambola", "bambolotto", "macchinina",
            "trenino", "puzzle", "tombola", "monopoli", "monopoly", "carte da gioco",
            "gioco tavolo", "gioco di società", "cubo magico", "costruzione",
            "set costruzioni", "camion giocattolo", "pista", "pupazzo",
        ],
        "keywords_weak": ["anni", "bambino", "bambina", "età", "3+", "6+", "8+", "12+"],
        "taxonomy_hints": ["toys & games", "toys", "games > board games"],
        "exclude": [],
    },
    "pet": {
        "keywords_strong": [
            "cane", "gatto", "cucciolo", "gattino", "crocchette", "croccantini",
            "cibo umido", "pate gatto", "snack cane", "snack gatto",
            "lettiera", "tiragraffi", "trasportino", "guinzaglio", "collare",
            "pettorina", "cuccia", "gabbia", "acquario", "accessori acquario",
            "cibo cani", "cibo gatti", "pelota cane", "gioco cane",
            "antiparassitario", "antipulci", "antizecche",
        ],
        "keywords_weak": ["royal canin", "purina", "trixie", "vetpharm", "petshop"],
        "taxonomy_hints": ["animals & pet supplies", "pet supplies"],
        "exclude": [],
    },
    "gioielli": {
        "keywords_strong": [
            "anello", "fedi nuziali", "orecchino", "orecchini", "collana",
            "bracciale", "bracciali", "ciondolo", "pendente", "charm",
            "orologio", "orologi", "cronografo", "cronografi",
            "diamante", "zaffiro", "rubino", "smeraldo", "perla",
            "oro 18kt", "oro 14kt", "oro 9kt", "argento 925",
            "placcato oro", "placcato rodio",
        ],
        "keywords_weak": ["carati", "gemma", "brillante", "swarovski"],
        "taxonomy_hints": ["apparel & accessories > jewelry", "watches", "rings", "necklaces"],
        "exclude": [],
    },
    "cosmesi": {
        "keywords_strong": [
            "crema viso", "crema corpo", "crema mani", "crema antirughe",
            "siero", "contorno occhi", "fondotinta", "mascara", "rossetto",
            "eyeliner", "ombretto", "blush", "primer viso", "correttore",
            "maschera viso", "scrub viso", "struccante", "tonico",
            "shampoo", "balsamo capelli", "maschera capelli", "olio capelli",
            "profumo", "eau de toilette", "eau de parfum", "bagnoschiuma",
            "docciaschiuma", "deodorante", "dentifricio", "collutorio",
            "protezione solare", "crema solare", "spf",
        ],
        "keywords_weak": ["ml", "skincare", "beauty", "makeup", "viso", "corpo"],
        "taxonomy_hints": ["health & beauty > personal care", "cosmetics", "hair care", "skin care"],
        "exclude": ["farmaco"],
    },
    "farmacia": {
        "keywords_strong": [
            "paracetamolo", "ibuprofene", "tachipirina", "moment", "oki",
            "aspirina", "voltaren", "gel antinfiammatorio",
            "sciroppo", "compresse", "capsule", "fiale", "supposte",
            "integratore", "multivitaminico", "probiotici", "fermenti lattici",
            "omega 3", "vitamina c", "vitamina d", "magnesio", "ferro",
            "cerotti", "garze", "disinfettante", "termometro",
            "misuratore pressione", "saturimetro", "aerosol",
            "anti raffreddore", "decongestionante", "tosse", "mal di gola",
            "nicotina", "gomme smettere di fumare",
        ],
        "keywords_weak": ["mg", "ml", "cp", "compresse", "bustine"],
        "taxonomy_hints": ["health & beauty > health care", "medicine & drugs", "vitamins & supplements"],
        "exclude": ["cosmesi"],
    },
    "occhiali": {
        "keywords_strong": [
            "occhiali da sole", "occhiali da vista", "montatura", "aviator",
            "wayfarer", "cat eye", "clubmaster",
            "ray-ban", "ray ban", "persol", "oakley", "maui jim", "prada occhiali",
            "lenti a contatto", "lenti giornaliere", "lenti mensili",
            "soluzione lenti a contatto",
        ],
        "keywords_weak": ["uv400", "polarizzato", "polarizzati", "calibro", "ponte", "asta"],
        "taxonomy_hints": ["sunglasses", "eyeglasses", "contact lenses"],
        "exclude": [],
    },
    "auto_moto": {
        "keywords_strong": [
            "pastiglie freno", "disco freno", "dischi freno",
            "filtro olio", "filtro aria", "filtro carburante", "filtro abitacolo",
            "olio motore", "liquido refrigerante", "antigelo",
            "batteria auto", "batteria moto", "pneumatico", "pneumatici",
            "gomme auto", "gomme estive", "gomme invernali", "gomme 4 stagioni",
            "candele accensione", "cinghia distribuzione", "ammortizzatori",
            "tergicristallo", "spazzole tergicristallo", "lampadina h7", "lampadina h4",
            "ricambi auto", "ricambi moto",
        ],
        "keywords_weak": ["oem", "bosch", "brembo", "valeo", "denso", "ngk"],
        "taxonomy_hints": ["vehicles & parts", "motor vehicle parts"],
        "exclude": [],
    },
    "condizionatori": {
        "keywords_strong": [
            "condizionatore", "climatizzatore", "aria condizionata",
            "inverter", "split", "monosplit", "dualsplit", "multisplit",
            "pompa di calore", "deumidificatore", "condotta aria",
            "unità esterna", "unità interna", "btu", "9000 btu", "12000 btu", "18000 btu",
            "daikin", "mitsubishi electric", "olimpia splendid", "samsung climatizzatore",
        ],
        "keywords_weak": ["r32", "r410a", "classe a", "classe a+", "seer", "scop"],
        "taxonomy_hints": ["climate control appliances", "air conditioners", "heat pumps"],
        "exclude": [],
    },
    "termoarredo": {
        "keywords_strong": [
            "scaldasalviette", "termoarredo", "radiatore", "radiatori",
            "termoarredo bagno", "termoventilatore", "termoconvettore",
            "convettore elettrico", "piastra radiante",
            "scaldabagno", "boiler elettrico",
            "stufa", "stufa a pellet", "stufa a legna",
            "irsap", "zehnder", "tubes radiatori", "cordivari", "caleffi",
        ],
        "keywords_weak": ["en 442", "interasse 50", "interasse 500", "w termici", "watt termici"],
        "taxonomy_hints": ["radiators", "heated towel rails", "space heaters", "electric heaters"],
        "exclude": [],
    },
    "horeca": {
        "keywords_strong": [
            # Attrezzature cucina professionale
            "forno combinato", "forno convezione", "forno pizza", "forno rotante",
            "friggitrice professionale", "friggitrice a gas", "abbattitore",
            "abbattitore di temperatura", "cella frigorifera", "armadio frigorifero",
            "tavolo refrigerato", "vetrina refrigerata", "vetrina gastronomia",
            "bagnomaria professionale", "fry-top", "fry top", "bistecchiera",
            "piastra cottura professionale", "salamandra", "cuocipasta",
            "brasiera", "marmitta", "griglia a pietra lavica",
            # Preparazione
            "planetaria professionale", "impastatrice pizza", "tritacarne",
            "affettatrice professionale", "segaossa", "pelatrice",
            "spremiagrumi professionale", "frullatore bar", "mixer bar",
            "gelatiera professionale", "mantecatore", "pastorizzatore",
            # Lavaggio
            "lavastoviglie a capote", "lavastoviglie professionale",
            "lavabicchieri", "sottolavello professionale",
            # Bar / caffetteria
            "macchina caffè professionale", "macchina espresso",
            "macinadosatore", "pressino caffè", "macinacaffè professionale",
            "spillatore birra", "impianto spina birra", "dispenser bevande",
            "granitore", "distributore granite",
            # Mise en place / stoviglie ristorazione
            "gastronorm", "teglia gn", "contenitore gn", "vaschetta gastronorm",
            "carrello porta teglie", "carrello di servizio", "carrello self service",
            "pass through", "banco pass",
            # Brand HO.RE.CA.
            "electrolux professional", "rational", "unox", "fimar",
            "angelo po", "hobart", "friulinox", "everlasting",
            "la marzocco", "la cimbali", "nuova simonelli", "rancilio",
            "wega", "expobar", "faema", "san remo espresso",
        ],
        "keywords_weak": [
            "inox aisi 304", "inox aisi 316", "haccp", "trifase",
            "400v", "kw", "coperti/ora", "teglie/ora",
            "gn 1/1", "gn 1/2", "gn 2/1", "classe climatica",
            "ristorazione", "pizzeria", "bar",
        ],
        "taxonomy_hints": [
            "business & industrial > food service",
            "commercial food preparation",
            "commercial refrigeration",
            "commercial kitchen",
            "commercial beverage equipment",
            "commercial dishwashing",
        ],
        "exclude": ["elettrodomestici casalingo", "uso domestico"],
    },
}


@dataclass
class ClassificationResult:
    sector: str | None
    score: int
    confidence: str  # 'high', 'medium', 'low'
    top_candidates: list[tuple[str, int]] = field(default_factory=list)


def _text_of(row: dict | pd.Series) -> str:
    """Concatenate searchable fields into a single lowercase blob."""
    parts: list[str] = []
    for key in ("title", "description", "product_type", "google_product_category",
                "category", "tags", "brand"):
        v = row.get(key) if isinstance(row, dict) else row.get(key)
        if v is None:
            continue
        sv = str(v).strip()
        if sv and sv.lower() not in ("nan", "none"):
            parts.append(sv.lower())
    return " ".join(parts)


def _taxonomy_of(row: dict | pd.Series) -> str:
    """Return the product taxonomy text (lowercase) if any."""
    for key in ("google_product_category", "product_type", "category"):
        v = row.get(key) if isinstance(row, dict) else row.get(key)
        if v and str(v).strip().lower() not in ("nan", "none"):
            return str(v).strip().lower()
    return ""


def classify_row(row: dict | pd.Series) -> ClassificationResult:
    """Classify a single product row.

    Returns ClassificationResult with:
      - sector: highest-scoring sector name, or None if everything scored <=0
      - confidence: 'high' (>=10), 'medium' (>=5), 'low' (<5)
      - top_candidates: top 3 (sector, score) tuples
    """
    text = _text_of(row)
    taxonomy = _taxonomy_of(row)
    if not text and not taxonomy:
        return ClassificationResult(sector=None, score=0, confidence="low")

    scores: dict[str, int] = {}
    for name, rules in SECTOR_RULES.items():
        score = 0

        # Taxonomy hits are the strongest signal
        for hint in rules.get("taxonomy_hints", []):
            if hint in taxonomy:
                score += 4

        # Strong keywords
        for kw in rules.get("keywords_strong", []):
            if kw in text:
                score += 3

        # Weak keywords (multiple matches add up but capped)
        weak_hits = sum(1 for kw in rules.get("keywords_weak", []) if kw in text)
        score += min(weak_hits, 3)

        # Exclusions (penalty when a disqualifying term is present)
        for ex in rules.get("exclude", []):
            if ex in text:
                score -= 4

        if score > 0:
            scores[name] = score

    if not scores:
        return ClassificationResult(sector=None, score=0, confidence="low")

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_sector, top_score = ranked[0]
    conf = "high" if top_score >= 10 else ("medium" if top_score >= 5 else "low")
    return ClassificationResult(
        sector=top_sector,
        score=top_score,
        confidence=conf,
        top_candidates=ranked[:3],
    )


def classify_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Add `_sector_detected` + `_sector_confidence` columns (in-place copy)."""
    out = df.copy()
    sectors: list[str | None] = []
    confs: list[str] = []
    for _, row in out.iterrows():
        r = classify_row(row.to_dict())
        sectors.append(r.sector)
        confs.append(r.confidence)
    out["_sector_detected"] = sectors
    out["_sector_confidence"] = confs
    return out


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate detection counts for UI display."""
    if "_sector_detected" not in df.columns:
        df = classify_dataframe(df)
    agg = (
        df.groupby(["_sector_detected", "_sector_confidence"], dropna=False)
          .size()
          .reset_index(name="count")
          .sort_values("count", ascending=False)
    )
    agg["_sector_detected"] = agg["_sector_detected"].fillna("(nessun match)")
    return agg


def apply_to_enrichment(df: pd.DataFrame) -> pd.Series:
    """Return a Series of sector-name-per-row (empty string if None).

    Used by the enrichment pipeline when sector='auto' to pass the per-row
    sector into the system-prompt builder.
    """
    sectors: list[str] = []
    for _, row in df.iterrows():
        r = classify_row(row.to_dict())
        sectors.append(r.sector or "")
    return pd.Series(sectors, index=df.index, name="_sector_detected")
