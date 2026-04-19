"""
Couche 3 — Conditions & Récurrences
====================================

Détecte dans une unité procédurale :
    - la présence d'une condition (si / lorsque / en cas de / ...)
    - la clause conditionnelle elle-même (pas juste un booléen)
    - la présence d'une récurrence + sa fréquence normalisée

Pourquoi une couche dédiée ?
-----------------------------
Le parser historique se contentait d'un `any(mot in texte)`. Résultat :
    - "lorsque midi sonne" déclenchait à tort une condition
    - "mail" matchait dans "réclamation"
    - aucune extraction de LA condition (on savait seulement qu'elle existait)

Ici on combine matching lexical + validation syntaxique :
    - Un marqueur "strict" (si, sauf si) est toujours conditionnel
    - Un marqueur "contextuel" (lorsque, quand) n'est conditionnel que s'il
      introduit une clause avec verbe conjugué (SCONJ + verbe)
"""

import re
from dataclasses import dataclass
from typing import Optional

from . import get_nlp, load_lexicon


@dataclass
class ConditionInfo:
    has_condition: bool = False
    trigger_condition: str = ""   # Ex: "si le montant dépasse 500€"
    confidence: float = 0.0


@dataclass
class RecurrenceInfo:
    is_recurring: bool = False
    frequency: str = ""           # "daily" | "weekly" | "monthly" | "quarterly" | "yearly" | "continuous" | "on_event"
    matched_pattern: str = ""     # ex: "chaque mois"
    confidence: float = 0.0


# ----------------------------------------------------------------------------
# Lexiques
# ----------------------------------------------------------------------------

_CONDITIONALS = load_lexicon("conditionals")
_FREQUENCIES = load_lexicon("frequencies")

_STRICT_COND = [c.lower() for c in _CONDITIONALS["strict_conditionals"]]
_CONTEXTUAL_COND = [c.lower() for c in _CONDITIONALS["contextual_conditionals"]["patterns"]]

# Pré-compilation des patterns de fréquence (triés par longueur décroissante
# pour que "chaque semaine" soit testé avant "chaque")
_FREQ_PATTERNS = []
for bucket_name, bucket_data in _FREQUENCIES.items():
    if bucket_name.startswith("_"):
        continue
    for pattern in bucket_data["patterns"]:
        _FREQ_PATTERNS.append({
            "pattern": pattern.lower(),
            "frequency": bucket_data["frequency"],
            "type": bucket_data["type"],
        })
_FREQ_PATTERNS.sort(key=lambda x: len(x["pattern"]), reverse=True)


# ----------------------------------------------------------------------------
# Détection de conditions
# ----------------------------------------------------------------------------

def _find_strict_conditional(text_lower: str) -> Optional[str]:
    """
    Cherche un marqueur conditionnel strict dans le texte.
    Retourne le marqueur trouvé (pour extraction de la clause), ou None.

    On matche sur bordures de mot pour éviter "si" dans "basique".
    """
    for marker in _STRICT_COND:
        # Pattern : le marqueur entouré de bordures de mot ou début/fin
        pattern = r"(?:^|[\s,;])" + re.escape(marker) + r"(?=\s|,|;|$)"
        if re.search(pattern, text_lower):
            return marker
    return None


def _validate_contextual_conditional(doc, marker: str) -> bool:
    """
    Valide qu'un marqueur contextuel (lorsque/quand) est bien utilisé comme
    conjonction de subordination introduisant une action, pas un simple temporel.

    "Lorsque le manager valide le dossier, il l'archive."   → conditionnel OK
    "Cela se produit lorsque le délai expire."              → temporel, pas d'action
    "Quand ?"                                                → question, pas conditionnel

    Heuristique : le marqueur doit être tagué SCONJ ET être suivi d'un sujet + verbe
    dans un rayon proche.
    """
    for tok in doc:
        if tok.text.lower() == marker and tok.pos_ == "SCONJ":
            # Vérifier qu'il y a un sujet + verbe dans les 8 tokens suivants
            window = doc[tok.i + 1 : min(tok.i + 9, len(doc))]
            has_subj = any(t.dep_ in ("nsubj", "nsubj:pass") for t in window)
            has_verb = any(t.pos_ == "VERB" for t in window)
            if has_subj and has_verb:
                return True
    return False


def _extract_condition_clause(text: str, marker: str) -> str:
    """
    Extrait la clause conditionnelle : du marqueur jusqu'à la virgule suivante
    (ou fin de phrase si pas de virgule).

    "Si le montant dépasse 500€, le directeur valide."
    → "si le montant dépasse 500€"
    """
    text_lower = text.lower()
    idx = text_lower.find(marker)
    if idx == -1:
        return ""

    # Trouver la prochaine virgule après le marqueur
    rest = text[idx:]
    comma_idx = rest.find(",")
    if comma_idx > 0:
        clause = rest[:comma_idx]
    else:
        # Pas de virgule : on prend jusqu'à 80 chars ou fin
        clause = rest[:80]

    return clause.strip().rstrip(".")


def detect_condition(text: str, doc=None) -> ConditionInfo:
    """
    Détecte la présence d'une condition et extrait la clause.

    Args:
        text : texte de l'unité procédurale
        doc  : doc spaCy pré-parsé (optionnel, pour éviter re-parsing)

    Returns:
        ConditionInfo
    """
    text_lower = text.lower()

    # --- 1. Marqueurs stricts (si, sauf si, en cas de, ...) ---
    strict = _find_strict_conditional(text_lower)
    if strict:
        clause = _extract_condition_clause(text, strict)
        return ConditionInfo(
            has_condition=True,
            trigger_condition=clause,
            confidence=0.95,
        )

    # --- 2. Marqueurs contextuels (lorsque, quand) — validation syntaxique ---
    if doc is None:
        doc = get_nlp()(text)

    for marker in _CONTEXTUAL_COND:
        if marker in text_lower:
            if _validate_contextual_conditional(doc, marker):
                clause = _extract_condition_clause(text, marker)
                return ConditionInfo(
                    has_condition=True,
                    trigger_condition=clause,
                    confidence=0.75,
                )

    return ConditionInfo()


# ----------------------------------------------------------------------------
# Détection de récurrences
# ----------------------------------------------------------------------------

def detect_recurrence(text: str) -> RecurrenceInfo:
    """
    Détecte la présence d'une récurrence et sa fréquence normalisée.

    Retourne la fréquence la plus spécifique trouvée
    (grâce au tri par longueur décroissante des patterns).
    """
    text_lower = text.lower()

    for entry in _FREQ_PATTERNS:
        pattern = entry["pattern"]
        # Matching sur bordures de mot
        regex = r"(?:^|[\s,;])" + re.escape(pattern) + r"(?=\s|,|;|$|[a-zà-ÿ]*\b)"
        if re.search(regex, text_lower):
            # Confiance variable selon le type
            # - periodic (chaque mois, annuel...) = très fiable
            # - event-driven (à chaque réception) = fiable
            # - continuous (régulièrement) = un peu plus ambigu
            conf_map = {"periodic": 0.95, "event-driven": 0.85, "continuous": 0.7}
            return RecurrenceInfo(
                is_recurring=True,
                frequency=entry["frequency"],
                matched_pattern=pattern,
                confidence=conf_map.get(entry["type"], 0.7),
            )

    return RecurrenceInfo()
