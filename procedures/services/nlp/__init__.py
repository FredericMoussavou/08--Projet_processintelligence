"""
Package NLP de ProcessIntelligence.

Architecture en 4 couches :
    1. segmenter    — découpe le texte en unités procédurales
    2. extractor    — extrait verbe/acteur/outil/objet via DependencyMatcher
    3. conditions   — détecte conditions (si/lorsque) et récurrences (chaque jour, mensuel...)
    4. normalizer   — canonicalise acteurs, lemmatise verbes, résout anaphores

Le modèle spaCy et les lexiques sont chargés une seule fois au niveau du package
(singleton) pour éviter les rechargements coûteux à chaque appel du parser.
"""

import json
import functools
from pathlib import Path
import spacy

LEXICONS_DIR = Path(__file__).parent / "lexicons"


@functools.lru_cache(maxsize=1)
def get_nlp():
    """
    Charge le modèle spaCy français.
    Mis en cache pour éviter le rechargement (modèle ~40 Mo).
    """
    return spacy.load("fr_core_news_md")


@functools.lru_cache(maxsize=None)
def load_lexicon(name: str) -> dict:
    """
    Charge un lexique JSON depuis procedures/services/nlp/lexicons/.

    Usage:
        verbs = load_lexicon("action_verbs")
        freqs = load_lexicon("frequencies")
    """
    path = LEXICONS_DIR / f"{name}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)
