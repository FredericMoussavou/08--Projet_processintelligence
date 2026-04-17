import re
import spacy

nlp = spacy.load('fr_core_news_md')

ENTITY_PLACEHOLDERS = {
    'PER': 'NOM_PERSONNE',
    'ORG': 'ORGANISATION',
    'LOC': 'LIEU',
    'MISC': 'ENTITE',
}

# Mots courants qui ne sont pas des entités — filtre les faux positifs de spaCy
FALSE_POSITIVES = {
    'contacter', 'contact', 'bonjour', 'cordialement', 'objet',
    'sujet', 'date', 'heure', 'lieu', 'merci', 'madame', 'monsieur',
    'veuillez', 'concernant', 'suivant', 'suite', 'ci-dessous',
}

# Patterns regex ordonnés par priorité — traités AVANT spaCy
REGEX_PATTERNS = [
    # Email — priorité maximale car spaCy le découpe mal
    (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', 'EMAIL'),
    # Numéro de téléphone français
    (r'\b0[1-9](?:[\s.-]?\d{2}){4}\b', 'TELEPHONE'),
    # SIRET/SIREN
    (r'\b\d{9}(?:\s?\d{5})?\b', 'NUMERO_SIRET'),
    # Montant avec ou sans symbole €
    (r'\b\d{1,3}(?:[\s]\d{3})*(?:[.,]\d{1,2})?\s*€', 'MONTANT'),
    # Montant sans € mais avec espace milliers (ex: 15 000)
    (r'\b\d{1,3}(?:[\s]\d{3})+(?:[.,]\d{1,2})?\b', 'MONTANT'),
    # Date formats courants
    (r'\b\d{2}[-/]\d{2}[-/]\d{4}\b', 'DATE'),
    (r'\b\d{4}[-/]\d{2}[-/]\d{2}\b', 'DATE'),
]


def mask_text(text: str):
    """
    Anonymise un texte en deux passes :
    1. Regex — capture emails, montants, dates, téléphones (prioritaire)
    2. spaCy NER — capture personnes, organisations, lieux

    Retourne :
    - le texte masqué
    - un dictionnaire {placeholder: valeur_originale} pour démasquage
    """

    mapping = {}
    counters = {}
    masked = text

    # --- Passe 1 : Regex (avant spaCy pour éviter les conflits de tokenisation) ---
    for pattern, entity_type in REGEX_PATTERNS:

        def replace_match(m, et=entity_type):
            counters[et] = counters.get(et, 0) + 1
            ph = f"[{et}_{counters[et]}]"
            mapping[ph] = m.group(0)
            return ph

        masked = re.sub(pattern, replace_match, masked, flags=re.IGNORECASE)

    # --- Passe 2 : spaCy NER (sur le texte déjà partiellement masqué) ---
    doc = nlp(masked)
    entities = sorted(doc.ents, key=lambda e: e.start_char, reverse=True)

    for ent in entities:
        # Ignore tout texte contenant déjà un placeholder
        if '[' in ent.text or ']' in ent.text or re.match(r'^[A-Z_]+_\d+$', ent.text.strip()):
            continue

        # Filtre les faux positifs connus
        if ent.text.lower().strip() in FALSE_POSITIVES:
            continue

        # Ignore les entités trop courtes (1-2 caractères) — souvent des erreurs
        if len(ent.text.strip()) <= 2:
            continue

        entity_type = ENTITY_PLACEHOLDERS.get(ent.label_, 'ENTITE')
        counters[entity_type] = counters.get(entity_type, 0) + 1
        ph = f"[{entity_type}_{counters[entity_type]}]"

        mapping[ph] = ent.text
        masked = masked[:ent.start_char] + ph + masked[ent.end_char:]

    return masked, mapping


def unmask_text(masked_text: str, mapping: dict) -> str:
    """
    Restaure le texte original à partir du texte masqué et du mapping.
    """
    result = masked_text
    for placeholder, original in mapping.items():
        result = result.replace(placeholder, original)
    return result