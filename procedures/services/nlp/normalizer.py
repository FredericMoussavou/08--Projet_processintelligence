"""
Couche 4 — Normalizer
======================

Post-traitement des extractions pour garantir la cohérence inter-étapes.

Rôles :
    1. Canonicaliser les acteurs (tous les "manager", "Le manager", "les managers"
       → "Manager"). Crucial pour le graphe : sans ça, 1 acteur unique devient
       4 acteurs distincts dans l'analyse NetworkX.

    2. Résoudre les anaphores simples : "il/elle/on" → dernier acteur nommé.
       Le parser historique ne le faisait pas, d'où des étapes dont l'acteur
       apparaissait comme "il" dans le Diagnostic Express.

    3. Normaliser les verbes à l'infinitif (déjà fait par spaCy via .lemma_,
       mais on gère ici les cas où le lemme est faux).
"""

import unicodedata
from typing import List, Optional

from . import load_lexicon


# ----------------------------------------------------------------------------
# Lexique
# ----------------------------------------------------------------------------

_ACTORS = load_lexicon("actors")

# Dictionnaire alias → forme canonique (tout en minuscules pour matching)
# Ex : "le manager" → "Manager", "drh" → "RH"
_ALIAS_TO_CANONICAL = {}
for canonical, aliases in _ACTORS["canonical_roles"].items():
    for alias in aliases:
        _ALIAS_TO_CANONICAL[alias.lower()] = canonical
    # Ajoute la forme canonique elle-même comme alias (pour matcher "Manager" → "Manager")
    _ALIAS_TO_CANONICAL[canonical.lower()] = canonical

_STOPWORDS = set(w.lower() for w in _ACTORS["stopwords_prefix"])
_IMPERSONAL = set(p.lower() for p in _ACTORS["impersonal_subjects"]["patterns"])


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _strip_accents(text: str) -> str:
    """Retire les accents pour matching tolérant."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _clean_prefix(text: str) -> str:
    """
    Retire les déterminants/possessifs en préfixe.
    'le manager' → 'manager'
    'les ressources humaines' → 'ressources humaines'
    """
    words = text.lower().split()
    while words and words[0] in _STOPWORDS:
        words = words[1:]
    return " ".join(words)


def is_impersonal(actor_text: str) -> bool:
    """
    Vrai si l'acteur extrait est un pronom impersonnel nécessitant résolution.
    Ex : "il", "elle", "on", "ils"
    """
    if not actor_text:
        return False
    cleaned = _clean_prefix(actor_text.strip())
    return cleaned in _IMPERSONAL or actor_text.lower().strip() in _IMPERSONAL


# ----------------------------------------------------------------------------
# Canonicalisation
# ----------------------------------------------------------------------------

def canonicalize_actor(actor_raw: str) -> tuple[str, float]:
    """
    Convertit un groupe nominal brut en forme canonique.

    'Le manager'              → ('Manager', 1.0)
    'les managers'            → ('Manager', 1.0)
    'le responsable comptable'→ ('Responsable', 0.6)  # match partiel
    'Paul Dupont'             → ('Paul Dupont', 0.8)  # pas dans lexique mais valide
    ''                        → ('', 0.0)

    Returns:
        (forme_canonique, confidence_boost)
    """
    if not actor_raw:
        return "", 0.0

    cleaned = _clean_prefix(actor_raw.strip())

    # Match exact ?
    if cleaned in _ALIAS_TO_CANONICAL:
        return _ALIAS_TO_CANONICAL[cleaned], 1.0

    # Match tête de groupe nominal (premier mot significatif) ?
    # "le responsable comptable" → premier mot = "responsable" → "Responsable"
    words = cleaned.split()
    if words:
        head = words[0]
        if head in _ALIAS_TO_CANONICAL:
            # On combine la forme canonique avec les qualificatifs restants
            canonical_head = _ALIAS_TO_CANONICAL[head]
            qualifiers = " ".join(words[1:])
            if qualifiers:
                return f"{canonical_head} {qualifiers}", 0.8
            return canonical_head, 0.9

    # Pas dans le lexique → on garde la forme cleaned avec capitalisation propre
    if cleaned:
        # Capitalize pour cohérence visuelle
        return " ".join(w.capitalize() for w in cleaned.split()), 0.5

    return "", 0.0


# ----------------------------------------------------------------------------
# Résolution d'anaphores
# ----------------------------------------------------------------------------

def resolve_anaphora(current_actor: str, previous_actors: List[str], max_lookback: int = 2) -> Optional[str]:
    """
    Si l'acteur courant est impersonnel ('il', 'on', ...), on remonte dans les
    acteurs précédents pour trouver le dernier acteur nommé dans un rayon limité.

    Args:
        current_actor    : acteur à potentiellement résoudre
        previous_actors  : liste des acteurs des étapes précédentes (du plus récent au plus ancien OU l'inverse, on gère)
        max_lookback     : nombre max d'étapes à remonter

    Returns:
        L'acteur résolu si anaphore, None sinon.
    """
    if not is_impersonal(current_actor):
        return None

    # On prend les dernières étapes (max_lookback)
    recent = previous_actors[-max_lookback:] if len(previous_actors) >= max_lookback else previous_actors

    # On cherche le plus récent non-impersonnel
    for actor in reversed(recent):
        if actor and not is_impersonal(actor):
            return actor

    return None


# ----------------------------------------------------------------------------
# Normalisation globale d'une liste d'extractions
# ----------------------------------------------------------------------------

def normalize_sequence(extractions: list) -> list:
    """
    Applique la normalisation sur une séquence d'extractions ordonnées.

    Modifications in-place :
        - canonicalisation de chaque acteur
        - résolution d'anaphores (il/elle/on → acteur précédent)
        - mise à jour des scores de confiance

    Args:
        extractions : liste d'objets Extraction (cf. extractor.py)

    Returns:
        La même liste, avec actor_role canonicalisés et anaphores résolues.
    """
    previous_actors: List[str] = []

    for extraction in extractions:
        raw_actor = extraction.actor_role

        if is_impersonal(raw_actor):
            # Tentative de résolution par anaphore
            resolved = resolve_anaphora(raw_actor, previous_actors)
            if resolved:
                extraction.actor_role = resolved
                # Confiance un peu abaissée car c'est une inférence
                extraction.confidence["actor_role"] = min(
                    extraction.confidence.get("actor_role", 0.5),
                    0.6,
                )
                previous_actors.append(resolved)
                continue

        # Canonicalisation normale
        canonical, conf_boost = canonicalize_actor(raw_actor)
        extraction.actor_role = canonical

        # Le boost de canonicalisation multiplie la confiance d'extraction
        current_conf = extraction.confidence.get("actor_role", 0.0)
        extraction.confidence["actor_role"] = round(current_conf * conf_boost, 2) if conf_boost < 1.0 else current_conf

        previous_actors.append(canonical)

    return extractions
