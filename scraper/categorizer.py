"""
categorizer.py – Keyword-basierte Kategorisierung von Praktika.

Erkennt automatisch specialization und track aus Titel + Beschreibung
ohne AI/API – rein regelbasiert mit Keyword-Matching.
"""

# ─── Specialization Keywords ──────────────────────────────────────────
# Reihenfolge = Priorität: spezifischere Begriffe zuerst
SPECIALIZATION_RULES: list[tuple[str, list[str]]] = [
    ("Accounting", [
        "audit", "assurance", "wirtschaftsprüfung", "jahresabschluss",
        "prüfung", "ifrs", "gaap", "buchführung", "buchhaltung",
        "rechnungswesen", "bilanz", "steuer", "tax", "abschlussprüfung",
    ]),
    ("Finance", [
        "m&a", "investment banking", "corporate finance", "financial",
        "finanz", "valuation", "transaction", "transaktion", "treasury",
        "controlling", "fp&a", "due diligence", "merger", "acquisition",
        "private equity", "venture capital", "capital market",
        "unternehmensbewertung", "finanzplanung",
    ]),
    ("Consulting", [
        "consulting", "beratung", "advisory", "strategy consulting",
        "strategieberatung", "management consulting", "transformation",
        "case", "consultant",
    ]),
    ("Strategy", [
        "strategy", "strategie", "strategisch", "corporate development",
        "business development", "competitor analysis", "marktanalyse",
        "wettbewerb", "geschäftsentwicklung",
    ]),
    ("Marketing", [
        "marketing", "brand", "marke", "digital marketing", "growth",
        "performance marketing", "content", "social media", "campaign",
        "kampagne", "seo", "sem", "crm", "user acquisition",
        "produktmanagement",
    ]),
    ("Sales", [
        "sales", "vertrieb", "key account", "business development sales",
        "go-to-market", "revenue", "inside sales", "account management",
    ]),
    ("Operations", [
        "operations", "supply chain", "logistik", "logistics", "lean",
        "prozess", "process", "produktion", "production", "einkauf",
        "procurement", "warehouse", "lager",
    ]),
    ("HR", [
        "hr", "human resources", "recruiting", "talent", "people",
        "personal", "employer branding", "compensation", "benefits",
        "learning", "development", "organisationsentwicklung",
    ]),
]

# ─── Track Keywords ───────────────────────────────────────────────────
TRACK_RULES: list[tuple[str, list[str]]] = [
    ("MBB (McKinsey, BCG, Bain)", [
        "mckinsey", "bcg", "boston consulting", "bain",
    ]),
    ("Big4", [
        "deloitte", "pwc", "pricewaterhouse", "kpmg", "ey",
        "ernst & young", "ernst and young",
    ]),
    ("Investment Banking", [
        "investment bank", "ib ", "m&a advisory", "capital markets",
        "rothschild", "lazard", "goldman", "morgan stanley",
        "j.p. morgan", "deutsche bank",
    ]),
    ("Tier 2 Consulting", [
        "oliver wyman", "roland berger", "strategy&", "a.t. kearney",
        "kearney", "simon-kucher", "berylls",
    ]),
    ("Corporate Finance", [
        "corporate finance", "konzerncontrolling", "finanzplanung",
        "treasury", "fp&a",
    ]),
    ("Tech & AI", [
        "google", "amazon", "microsoft", "apple", "meta", "sap",
        "zalando", "delivery hero", "spotify", "tech", "ai ",
        "artificial intelligence", "data science",
    ]),
    ("Defense & Aerospace", [
        "rheinmetall", "airbus", "hensoldt", "mbda", "krauss-maffei",
        "aerospace", "defense", "defence", "verteidigung", "rüstung",
    ]),
    ("FMCG & Retail", [
        "beiersdorf", "henkel", "nivea", "unilever", "procter",
        "p&g", "nestlé", "nestle", "fmcg", "consumer goods",
        "retail", "einzelhandel", "lidl", "aldi", "rewe",
    ]),
    ("Automotive", [
        "bmw", "mercedes", "daimler", "volkswagen", "vw ", "audi",
        "porsche", "continental", "bosch", "zf ", "schaeffler",
        "automotive",
    ]),
    ("Startups & Scale-ups", [
        "n26", "celonis", "personio", "flixbus", "trade republic",
        "startup", "scale-up", "scaleup",
    ]),
]


def categorize_specialization(title: str, description: str, company: str = "") -> str:
    """Bestimme die Spezialisierung anhand von Keywords in Titel + Beschreibung."""
    text = f"{title} {description} {company}".lower()
    for specialization, keywords in SPECIALIZATION_RULES:
        for kw in keywords:
            if kw in text:
                return specialization
    return "Consulting"  # Default für Business-Praktika


def categorize_track(title: str, description: str, company: str = "") -> str:
    """Bestimme den Track anhand von Company-Name und Keywords."""
    text = f"{title} {description} {company}".lower()
    for track, keywords in TRACK_RULES:
        for kw in keywords:
            if kw in text:
                return track
    return "Big4"  # Default wenn Company nicht erkannt


def categorize_job(title: str, description: str, company: str = "") -> dict:
    """Kategorisiere einen Job vollständig."""
    return {
        "specialization": categorize_specialization(title, description, company),
        "track": categorize_track(title, description, company),
    }


# ─── Praktikums-Erkennung ────────────────────────────────────────────
PRAKTIKUM_KEYWORDS = [
    "praktik", "intern", "internship", "stage", "trainee",
    "working student", "werkstudent",
]

EXCLUDE_KEYWORDS = [
    "werkstudent", "working student", "festanstellung",
    "permanent", "senior", "manager", "director", "lead",
    "principal", "partner", "experienced", "professional",
    "berufserfahrung", "vollzeit", "full-time",
]


def is_praktikum(title: str, description: str = "") -> bool:
    """Prüfe ob ein Job ein Praktikum ist (kein Werkstudent/Festanstellung)."""
    text = f"{title} {description}".lower()

    # Muss mindestens ein Praktikums-Keyword enthalten
    has_praktikum = any(kw in text for kw in ["praktik", "intern", "internship"])
    if not has_praktikum:
        return False

    # Darf keine Ausschluss-Keywords enthalten (außer im Titel steht explizit "Praktikum")
    title_lower = title.lower()
    for exclude in EXCLUDE_KEYWORDS:
        if exclude in title_lower and "praktik" not in title_lower and "intern" not in title_lower:
            return False

    # Werkstudent explizit ausschließen
    if "werkstudent" in title_lower or "working student" in title_lower:
        return False

    return True


# ─── DACH Location Erkennung ─────────────────────────────────────────
DACH_CITIES = [
    "münchen", "munich", "berlin", "frankfurt", "hamburg", "köln",
    "cologne", "stuttgart", "düsseldorf", "dortmund", "essen", "leipzig",
    "dresden", "hannover", "nürnberg", "nuremberg", "bremen", "bonn",
    "mannheim", "karlsruhe", "augsburg", "wiesbaden", "aachen",
    "wien", "vienna", "graz", "linz", "salzburg", "innsbruck",
    "zürich", "zurich", "bern", "basel", "genf", "geneva", "lausanne",
    "luzern", "lucerne",
]

DACH_COUNTRIES = ["deutschland", "germany", "österreich", "austria", "schweiz", "switzerland"]


def is_dach_location(location: str) -> bool:
    """Prüfe ob der Standort in der DACH-Region ist."""
    loc = location.lower()
    return any(city in loc for city in DACH_CITIES) or any(c in loc for c in DACH_COUNTRIES)


def normalize_location(location: str) -> str:
    """Normalisiere Stadt-Namen auf Deutsch."""
    mapping = {
        "munich": "München",
        "cologne": "Köln",
        "vienna": "Wien",
        "zurich": "Zürich",
        "nuremberg": "Nürnberg",
        "geneva": "Genf",
        "lucerne": "Luzern",
        "hanover": "Hannover",
    }
    loc_lower = location.lower().strip()
    for eng, deu in mapping.items():
        if eng in loc_lower:
            return deu
    # Capitalize first letter
    return location.strip().title()
