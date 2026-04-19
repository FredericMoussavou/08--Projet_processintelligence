"""
Couche 2 — Extractor (v3)
==========================

Corrections v3 ajoutées :
    BUG B — Outil : refuser "par + acteur connu" même hors passif.
            "La validation par le manager" ne doit plus détecter "manager" comme outil.
    BUG C — Acteur/objet : quand le vrai verbe n'est pas le ROOT (on a corrigé via
            relative), on rattrape le sujet et l'objet en remontant au ROOT mal
            détecté et en lui empruntant ses enfants syntaxiques.
    BUG D — Objet : retire les prépositions traînantes en fin d'objet ("demande
            du client par" → "demande du client") et coupe l'objet aux prépositions
            instrumentales.
    BUG E — Verbe "faible" + nominalisation : si on trouve 'faire'/'devoir'/'être'
            comme verbe, on préfère la nominalisation si elle existe dans le doc.

Corrections v2 préservées :
    BUG 1 — Objet utilise .text (pas .lemma_) → évite "offre" → "offrir"
    BUG 2 — Racine verbale intelligente (relatives, auxiliaires)
    BUG 3 — Exclusion de l'agent passif de la détection outil
    BUG 7 — Fallback lemmatisation via lexique
    BUG 10 — Auxiliaires modaux → xcomp
"""

from dataclasses import dataclass, field
from typing import Optional

from . import get_nlp, load_lexicon


@dataclass
class Extraction:
    action_verb: str = ""
    actor_role: str = ""
    tool_used: str = ""
    object: str = ""
    confidence: dict = field(default_factory=dict)


# ----------------------------------------------------------------------------
# Lexiques
# ----------------------------------------------------------------------------

_VERBS = load_lexicon("action_verbs")
_TOOLS = load_lexicon("tools")
_ACTORS = load_lexicon("actors")

# Nominalisation → verbe
_NOMINALISATION_TO_VERB = {}
for category in ("high_automation", "low_automation", "neutral"):
    for lemma, data in _VERBS.get(category, {}).items():
        for nom in data.get("nominalisations", []):
            _NOMINALISATION_TO_VERB[nom.lower()] = lemma

# Verbes connus
_KNOWN_VERBS = set()
for category in ("high_automation", "low_automation", "neutral"):
    _KNOWN_VERBS.update(_VERBS.get(category, {}).keys())

# Surface → lemme (BUG 7)
_SURFACE_TO_LEMMA = {}
for verb in _KNOWN_VERBS:
    if verb.endswith("er"):
        stem = verb[:-2]
        for ending in ("e", "es", "ons", "ez", "ent"):
            _SURFACE_TO_LEMMA[stem + ending] = verb
    elif verb.endswith("ir"):
        stem = verb[:-2]
        for ending in ("is", "it", "issons", "issez", "issent"):
            _SURFACE_TO_LEMMA[stem + ending] = verb

# Outils
_TOOL_ALIAS_TO_CANONICAL = {}
for canonical, aliases in _TOOLS["known_tools"].items():
    for alias in aliases:
        _TOOL_ALIAS_TO_CANONICAL[alias.lower()] = canonical

_INSTR_HIGH = set(_TOOLS["instrumental_prepositions"]["high_confidence"])
_INSTR_MEDIUM = set(_TOOLS["instrumental_prepositions"]["medium_confidence"])
_INSTR_EXCLUSIONS = set(_TOOLS["instrumental_prepositions"]["exclusion_nouns"])

# BUG B : set des aliases d'acteurs connus, utilisé pour refuser "par + acteur"
# dans la détection d'outil même hors passif syntaxiquement détecté
_KNOWN_ACTOR_ALIASES = set()
for canonical, aliases in _ACTORS["canonical_roles"].items():
    _KNOWN_ACTOR_ALIASES.update(a.lower() for a in aliases)
    _KNOWN_ACTOR_ALIASES.add(canonical.lower())

_MODAL_AUXILIARIES = {"devoir", "pouvoir", "falloir", "vouloir", "savoir"}

# BUG E : verbes "faibles" qu'il vaut mieux remplacer par une nominalisation si disponible
_WEAK_VERBS = {"être", "avoir", "faire", "devoir", "pouvoir", "falloir"}

# Set des prépositions instrumentales pour filtrage d'objet (BUG D)
_ALL_INSTR = _INSTR_HIGH | _INSTR_MEDIUM


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _parse_unit(text: str):
    nlp = get_nlp()
    return nlp(text)


def _resolve_lemma(token) -> str:
    """BUG 7 — Lemmatisation robuste via fallback lexique."""
    spacy_lemma = token.lemma_.lower()
    if spacy_lemma in _KNOWN_VERBS:
        return spacy_lemma
    surface = token.text.lower()
    if surface in _SURFACE_TO_LEMMA:
        return _SURFACE_TO_LEMMA[surface]
    return spacy_lemma


def _is_in_relative_clause(token) -> bool:
    """BUG 2 — Détecte si un token est dans une proposition relative."""
    current = token
    for _ in range(5):
        if current.dep_ in ("acl", "acl:relcl", "amod"):
            return True
        if current.head == current:
            break
        current = current.head
    return False


def _find_spacy_root(doc):
    """
    Retourne le token ROOT brut de spaCy (même s'il est mauvais).
    Utilisé par BUG C pour rattraper les enfants syntaxiques.
    """
    for tok in doc:
        if tok.dep_ == "ROOT":
            return tok
    return None


def _find_root_verb(doc):
    """
    BUG 2 + BUG 10 — Verbe d'action principal.
    """
    root = _find_spacy_root(doc)
    if root is None:
        return None

    # Cas 1 : modal → xcomp
    if root.lemma_.lower() in _MODAL_AUXILIARIES:
        for child in root.children:
            if child.dep_ == "xcomp" and child.pos_ == "VERB":
                return child

    # Cas 2 : VERB normal hors relative
    if root.pos_ == "VERB" and not _is_in_relative_clause(root):
        return root

    # Cas 3 : AUX → VERB enfant
    if root.pos_ == "AUX":
        for child in root.children:
            if child.pos_ == "VERB" and not _is_in_relative_clause(child):
                return child

    # Cas 4 : premier VERB libre hors être/avoir
    for tok in doc:
        if (tok.pos_ == "VERB"
                and tok.lemma_.lower() not in ("être", "avoir")
                and not _is_in_relative_clause(tok)):
            return tok

    # Cas 5 : fallback
    if root.pos_ == "VERB":
        return root

    return None


def _try_nominalisation(doc) -> Optional[tuple]:
    """
    Cherche une nominalisation d'action + retourne aussi le token pour extraction
    de contexte autour (acteur, objet de la nominalisation).

    Returns:
        (lemme_verbal, token_noun) ou None
    """
    for tok in doc:
        if tok.pos_ == "NOUN":
            nom = tok.lemma_.lower()
            if nom in _NOMINALISATION_TO_VERB:
                return (_NOMINALISATION_TO_VERB[nom], tok)
    return None


def _extract_verb(doc) -> tuple[str, float, Optional[object]]:
    """
    Extrait le verbe d'action.

    Returns:
        (lemme, confidence, verb_token_or_None)

    BUG E : si le verbe extrait est "faible" (faire/devoir/être) et qu'une
    nominalisation d'action existe, on préfère la nominalisation.
    """
    root = _find_root_verb(doc)
    nominalisation = _try_nominalisation(doc)

    if root is not None:
        lemma = _resolve_lemma(root)

        # BUG E : verbe faible → préférer nominalisation si dispo
        if lemma in _WEAK_VERBS and nominalisation is not None:
            return nominalisation[0], 0.75, root  # on retourne quand même root comme token-réf

        if lemma in _KNOWN_VERBS:
            return lemma, 1.0, root
        return lemma, 0.6, root

    # Pas de verbe trouvé → nominalisation en dernier recours
    if nominalisation is not None:
        return nominalisation[0], 0.7, None

    return "", 0.0, None


def _clean_actor_span(token) -> str:
    """Nettoie un groupe nominal d'acteur."""
    head = token
    keep_tokens = [head]
    for child in head.children:
        if child.dep_ in ("amod",) and child.i < head.i + 3:
            keep_tokens.append(child)
        elif child.dep_ in ("flat:name", "fixed"):
            keep_tokens.append(child)

    keep_tokens.sort(key=lambda t: t.i)
    words = [t.text for t in keep_tokens if t.pos_ not in ("DET", "PUNCT")]
    return " ".join(words).strip()


def _extract_actor(doc, verb_token) -> tuple[str, float, Optional[int]]:
    """
    Extrait l'acteur.

    BUG C : si verb_token n'est pas le ROOT (cas d'un verbe rattrapé derrière
    un ROOT mal détecté), on cherche le nsubj dans le ROOT en priorité car
    c'est souvent là que spaCy a attaché le sujet sémantique.

    Returns:
        (acteur, confiance, position_agent_passif_ou_None)
    """
    if verb_token is None:
        for ent in doc.ents:
            if ent.label_ in ("PER", "ORG"):
                return ent.text, 0.3, None
        return "", 0.0, None

    is_passive = "Voice=Pass" in str(verb_token.morph)

    # BUG C : liste de candidats — on cherche d'abord dans verb_token, puis dans le ROOT
    candidate_heads = [verb_token]
    spacy_root = _find_spacy_root(doc)
    if spacy_root is not None and spacy_root is not verb_token:
        candidate_heads.append(spacy_root)

    if is_passive:
        # Agent introduit par "par" (recherche dans tous les candidats)
        for head in candidate_heads:
            for child in head.children:
                if child.dep_ in ("obl:agent", "obl"):
                    for subchild in child.children:
                        if subchild.dep_ == "case" and subchild.lemma_.lower() == "par":
                            return _clean_actor_span(child), 0.85, child.i
                    if child.dep_ == "obl:agent":
                        return _clean_actor_span(child), 0.7, child.i
        return "", 0.0, None

    # Voix active : on cherche nsubj dans chaque candidat
    for head in candidate_heads:
        for child in head.children:
            if child.dep_ in ("nsubj", "nsubj:pass"):
                if child.pos_ == "PRON":
                    return child.text.lower(), 0.2, None
                # Confiance réduite si on a dû aller chercher dans le ROOT au lieu du verbe
                conf = 0.9 if head is verb_token else 0.65
                return _clean_actor_span(child), conf, None

    for ent in doc.ents:
        if ent.label_ in ("PER", "ORG"):
            return ent.text, 0.3, None

    return "", 0.0, None


def _is_known_actor(token) -> bool:
    """BUG B — Vérifie si un token correspond à un acteur connu."""
    lower = token.lemma_.lower()
    text_lower = token.text.lower()
    if lower in _KNOWN_ACTOR_ALIASES or text_lower in _KNOWN_ACTOR_ALIASES:
        return True
    # Tester aussi en incluant un éventuel modificateur ("service rh")
    if token.i > 0:
        prev = token.doc[token.i - 1]
        bigram = f"{prev.lemma_.lower()} {lower}"
        if bigram in _KNOWN_ACTOR_ALIASES:
            return True
    return False


def _extract_tool(doc, verb_token, passive_agent_idx: Optional[int]) -> tuple[str, float]:
    """
    Extrait l'outil.

    BUG 3 (préservé) : exclusion de l'agent passif.
    BUG B (nouveau)  : refuser "par + acteur connu" comme préposition instrumentale,
                       même si aucun passif n'a été détecté syntaxiquement.
    """
    excluded_positions = set()
    if passive_agent_idx is not None:
        agent_token = doc[passive_agent_idx]
        for t in agent_token.subtree:
            excluded_positions.add(t.i)

    # --- 1. Outil connu par matching ---
    for tok in doc:
        if tok.i in excluded_positions:
            continue
        txt = tok.text.lower()
        if txt in _TOOL_ALIAS_TO_CANONICAL:
            return _TOOL_ALIAS_TO_CANONICAL[txt], 1.0
        if tok.i < len(doc) - 1:
            bigram = f"{tok.text} {doc[tok.i + 1].text}".lower()
            if bigram in _TOOL_ALIAS_TO_CANONICAL:
                return _TOOL_ALIAS_TO_CANONICAL[bigram], 1.0

    # --- 2. Préposition instrumentale + NOUN/PROPN ---
    for tok in doc:
        if tok.i in excluded_positions:
            continue
        if tok.pos_ == "ADP" and tok.text.lower() in _ALL_INSTR:
            head = tok.head
            if head.i in excluded_positions:
                continue
            if head.pos_ not in ("NOUN", "PROPN"):
                continue
            noun_lower = head.lemma_.lower()
            if noun_lower in _INSTR_EXCLUSIONS:
                continue

            # BUG 3 bis : "par" + verbe passif = agent
            if (tok.text.lower() == "par" and verb_token is not None
                    and "Voice=Pass" in str(verb_token.morph)):
                continue

            # BUG B : "par" + acteur connu = agent, pas outil (même sans passif)
            if tok.text.lower() == "par" and _is_known_actor(head):
                continue

            confidence = 0.75 if tok.text.lower() in _INSTR_HIGH else 0.5
            tool_name = head.text if head.pos_ == "PROPN" else head.text.capitalize()
            return tool_name, confidence

    return "", 0.0


def _extract_object(doc, verb_token) -> tuple[str, float]:
    """
    Extrait l'objet (COD).

    BUG 1 (préservé) : .text au lieu de .lemma_ pour ne pas transformer les noms
    homographes ("offre") en verbes ("offrir").
    BUG C (nouveau)  : fallback sur le ROOT si verb_token n'a pas d'obj propre.
    BUG D (nouveau)  : couper l'objet aux prépositions instrumentales et supprimer
    les prépositions traînantes en fin.
    """
    if verb_token is None:
        return "", 0.0

    candidate_heads = [verb_token]
    spacy_root = _find_spacy_root(doc)
    if spacy_root is not None and spacy_root is not verb_token:
        candidate_heads.append(spacy_root)

    for head in candidate_heads:
        for child in head.children:
            if child.dep_ == "obj":
                obj_tokens = list(child.subtree)

                # BUG D : on coupe dès qu'on rencontre une préposition instrumentale
                # (via, sur, dans, avec...) qui introduit autre chose que le cœur de l'objet
                cut_at = len(obj_tokens)
                for i, t in enumerate(obj_tokens):
                    if t.pos_ == "ADP" and t.text.lower() in _ALL_INSTR and i > 0:
                        cut_at = i
                        break
                obj_tokens = obj_tokens[:cut_at]

                # Filtre déterminants et ponctuation
                words = [t.text.lower() for t in obj_tokens
                         if t.pos_ not in ("DET", "PUNCT") and t.dep_ != "det"]

                # BUG D : retirer les prépositions résiduelles en fin
                while words and words[-1] in {"par", "via", "sur", "dans", "avec",
                                               "de", "du", "des", "à", "au", "aux"}:
                    words.pop()

                if len(words) > 4:
                    words = words[:4]

                if words:
                    conf = 0.8 if head is verb_token else 0.55
                    return " ".join(words), conf

    return "", 0.0


# ----------------------------------------------------------------------------
# API publique
# ----------------------------------------------------------------------------

def extract(text: str) -> Extraction:
    """
    Extrait les informations structurées d'une unité procédurale.
    """
    doc = _parse_unit(text)

    verb, verb_conf, verb_token = _extract_verb(doc)

    actor, actor_conf, agent_idx = _extract_actor(doc, verb_token)
    tool, tool_conf = _extract_tool(doc, verb_token, agent_idx)
    obj, obj_conf = _extract_object(doc, verb_token)

    return Extraction(
        action_verb=verb,
        actor_role=actor,
        tool_used=tool,
        object=obj,
        confidence={
            "action_verb": verb_conf,
            "actor_role": actor_conf,
            "tool_used": tool_conf,
            "object": obj_conf,
        },
    )
