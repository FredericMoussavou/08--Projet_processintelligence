"""
Couche 1 — Segmenter (v2)
==========================

Découpe un texte de procédure en "unités procédurales".

Correction v2 :
    BUG F — Les phrases commençant par une subordonnée conditionnelle
            ("Si X, Y fait Z." ou "Lorsque X, Y fait Z.") ne doivent PAS être
            découpées en 2 unités. Toute la phrase est 1 seule étape : l'action
            principale est "Y fait Z" avec trigger_condition = "si X".
            La couche 3 (conditions.py) extrait la condition, la couche 1 n'a
            qu'à ne pas couper sur la virgule qui suit "si ...,".

Rôle global : voir docstring v1.
"""

import re
from dataclasses import dataclass, field
from typing import List

from . import get_nlp

# Marqueurs de coordination séquentielle
SEQUENTIAL_COORDINATORS = {"puis", "ensuite", "enfin", "après", "finalement"}

# Patterns d'énumération en début de ligne
ENUMERATION_PATTERNS = [
    re.compile(r"^\s*\d+[\.\)]\s+"),
    re.compile(r"^\s*[a-z][\.\)]\s+"),
    re.compile(r"^\s*[-•\*]\s+"),
    re.compile(r"^\s*étape\s+\d+\s*:", re.IGNORECASE),
]

# BUG F : marqueurs qui introduisent une subordonnée conditionnelle en tête de phrase
# Si une phrase commence par l'un de ces marqueurs, la première virgule n'est PAS
# une coupure d'étape — c'est la jonction subordonnée/principale.
_INITIAL_SUBORDINATORS = {
    "si", "lorsque", "quand", "dès", "dès que", "en cas", "sauf si", "à condition",
    "dans le cas", "au cas", "pourvu", "à moins",
}


@dataclass
class ProceduralUnit:
    text: str
    source_span: object = None
    order: int = 0
    origin: str = "sentence"


def _preprocess_enumerations(text: str) -> str:
    """Normalise les listes pour que spaCy segmente correctement."""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        is_enum = any(p.match(line) for p in ENUMERATION_PATTERNS)
        if is_enum and line[-1] not in ".!?":
            line += "."
        cleaned.append(line)
    return "\n".join(cleaned)


def _starts_with_subordinator(sent) -> bool:
    """
    BUG F — Détecte si une phrase commence par une subordonnée conditionnelle.

    Stratégie : on regarde les 2-3 premiers tokens significatifs (hors ponctuation
    et déterminant). Si le premier ou le bigramme initial est un subordonnant
    connu, on considère que la phrase commence par une subordonnée.
    """
    # Récupère les premiers tokens non-PUNCT
    first_tokens = [t for t in sent if t.pos_ != "PUNCT"][:3]
    if not first_tokens:
        return False

    first_text = first_tokens[0].text.lower()
    if first_text in _INITIAL_SUBORDINATORS:
        return True

    if len(first_tokens) >= 2:
        bigram = f"{first_text} {first_tokens[1].text.lower()}"
        if bigram in _INITIAL_SUBORDINATORS:
            return True

    if len(first_tokens) >= 3:
        trigram = f"{first_text} {first_tokens[1].text.lower()} {first_tokens[2].text.lower()}"
        if trigram in _INITIAL_SUBORDINATORS:
            return True

    return False


def _split_on_coordination(sent) -> List[str]:
    """
    Coupe une phrase spaCy sur les coordinations séquentielles (puis, ensuite...).

    BUG F : si la phrase commence par une subordonnée conditionnelle, on ne
    découpe pas sur les coordinateurs (sinon on casserait la clause principale).
    """
    # BUG F : les phrases avec subordonnée initiale ne sont pas découpées
    if _starts_with_subordinator(sent):
        return [sent.text.strip()]

    tokens = list(sent)
    cuts = []

    for i, tok in enumerate(tokens):
        if tok.lemma_.lower() in SEQUENTIAL_COORDINATORS and i > 2 and i < len(tokens) - 3:
            has_verb_before = any(t.pos_ == "VERB" for t in tokens[:i])
            has_verb_after = any(t.pos_ == "VERB" for t in tokens[i + 1:])
            if has_verb_before and has_verb_after:
                cuts.append(i)

    if not cuts:
        return [sent.text.strip()]

    parts = []
    prev = 0
    for cut in cuts:
        segment = " ".join(t.text for t in tokens[prev:cut]).strip()
        if segment and len(segment.split()) >= 3:
            parts.append(segment)
        prev = cut + 1
    last = " ".join(t.text for t in tokens[prev:]).strip()
    if last:
        parts.append(last)

    return parts if len(parts) > 1 else [sent.text.strip()]


def segment(text: str) -> List[ProceduralUnit]:
    """
    Découpe un texte brut en unités procédurales ordonnées.
    """
    nlp = get_nlp()
    preprocessed = _preprocess_enumerations(text)
    doc = nlp(preprocessed)

    units: List[ProceduralUnit] = []
    order = 1

    for sent in doc.sents:
        if len(sent) < 4:
            continue

        stripped = sent.text.strip()
        is_enum = any(p.match(stripped) for p in ENUMERATION_PATTERNS)

        if is_enum:
            fragments = [stripped]
            origin = "enumeration"
        else:
            fragments = _split_on_coordination(sent)
            origin = "sentence" if len(fragments) == 1 else "coordination"

        for frag in fragments:
            if len(frag.split()) < 4:
                continue
            units.append(ProceduralUnit(
                text=frag,
                source_span=sent,
                order=order,
                origin=origin,
            ))
            order += 1

    return units
