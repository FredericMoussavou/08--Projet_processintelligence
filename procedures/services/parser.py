"""
Parser de procédures — orchestrateur principal (v2).

Corrections v2 :
    BUG 5 — Ajout du flag `is_generic_instruction`. Quand une étape provient
            d'une énumération numérotée à l'impératif ("1. Recevoir la demande...")
            et n'a pas d'acteur détecté, on marque l'étape comme "instruction
            générique". Ça permet à l'UI de proposer à l'utilisateur de préciser
            l'acteur manuellement, au lieu d'afficher un champ vide sans contexte.

Architecture en 4 couches (voir procedures/services/nlp/).

Backward compatibility : signature inchangée, nouveaux champs sur ParsedStep.
"""

from dataclasses import dataclass, field

from .nlp import get_nlp, load_lexicon
from .nlp.segmenter import segment
from .nlp.extractor import extract
from .nlp.conditions import detect_condition, detect_recurrence
from .nlp.normalizer import normalize_sequence


# ---------------------------------------------------------------------------
# Backward-compatible constants
# ---------------------------------------------------------------------------

_VERBS = load_lexicon("action_verbs")

HIGH_AUTOMATION_VERBS = set(_VERBS.get("high_automation", {}).keys())
LOW_AUTOMATION_VERBS = set(_VERBS.get("low_automation", {}).keys())

_TOOLS = load_lexicon("tools")
KNOWN_TOOLS = set()
for aliases in _TOOLS["known_tools"].values():
    KNOWN_TOOLS.update(a.lower() for a in aliases)


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------

@dataclass
class ParsedStep:
    """
    Étape extraite du texte.

    Champs historiques : order, title, action_verb, actor_role, tool_used,
    has_condition, is_recurring, output_type, automation_score, raw_sentence.

    Nouveaux champs NLP :
        trigger_condition     : clause conditionnelle, ex "si le montant dépasse 500€"
        frequency             : fréquence normalisée (daily/weekly/monthly/...)
        object                : complément d'objet du verbe
        confidence            : dict[str, float] avec un score 0.0-1.0 par champ
        is_generic_instruction: BUG 5 — True quand l'étape provient d'une liste
                                numérotée à l'impératif et n'a pas d'acteur.
                                Signal pour l'UI de proposer "Préciser l'acteur".
    """
    order: int
    title: str
    action_verb: str = ""
    actor_role: str = ""
    tool_used: str = ""
    has_condition: bool = False
    is_recurring: bool = False
    output_type: str = "none"
    automation_score: float = 0.0
    raw_sentence: str = ""

    trigger_condition: str = ""
    frequency: str = ""
    object: str = ""
    confidence: dict = field(default_factory=dict)
    is_generic_instruction: bool = False


# ---------------------------------------------------------------------------
# Scoring d'automatisation
# ---------------------------------------------------------------------------

def _calculate_automation_score(verb: str, has_condition: bool,
                                is_recurring: bool, tool: str) -> float:
    """
    Score d'automatisation entre 0.0 et 1.0.

    Utilise les scores granulaires du lexique (ex: "décider" = -0.8, "copier" = +1.0)
    plutôt qu'un +0.4/-0.3 uniforme.
    """
    score = 0.3

    for category in ("high_automation", "low_automation", "neutral"):
        if verb in _VERBS.get(category, {}):
            verb_score = _VERBS[category][verb]["score"]
            score += verb_score * 0.5
            break

    if is_recurring:
        score += 0.3
    if tool:
        score += 0.2
    if has_condition:
        score -= 0.1

    return round(max(0.0, min(1.0, score)), 2)


def _determine_output_type(text: str) -> str:
    tl = text.lower()
    decision_words = ["valide", "approuve", "décide", "refuse", "accepte",
                      "rejette", "autorise", "signe"]
    document_words = ["document", "rapport", "contrat", "fichier", "formulaire",
                      "fiche", "pdf", "courrier", "lettre", "attestation"]
    data_words = ["donnée", "information", "saisie", "enregistre", "base",
                  "tableau", "liste", "calcul", "résultat"]
    if any(w in tl for w in decision_words):
        return "decision"
    if any(w in tl for w in document_words):
        return "document"
    if any(w in tl for w in data_words):
        return "data"
    return "none"


def _build_title(unit_text: str, verb: str, obj: str, actor: str) -> str:
    """Construit un titre concis pour l'étape."""
    if verb and obj:
        title = f"{verb.capitalize()} {obj}"
        if len(title) > 80:
            title = title[:77] + "..."
        return title
    if verb:
        return verb.capitalize()
    title = unit_text.strip()
    if len(title) > 80:
        title = title[:77] + "..."
    return title


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def parse_procedure_text(text: str) -> list[ParsedStep]:
    """
    Parse un texte libre de procédure et retourne une liste d'étapes structurées.

    Pipeline :
        1. Segmenter  → unités procédurales
        2. Extractor  → verbe/acteur/outil/objet par unité
        3. Normalizer → canonicalisation globale + anaphores
        4. Conditions → has_condition / trigger_condition / is_recurring / frequency
        5. Assemblage → ParsedStep avec scoring et flags
    """
    units = segment(text)
    if not units:
        return []

    # Extraction syntaxique
    extractions = []
    for unit in units:
        ex = extract(unit.text)
        extractions.append(ex)

    # Normalisation inter-étapes (anaphores, canonicalisation)
    extractions = normalize_sequence(extractions)

    # Assemblage final
    nlp = get_nlp()
    steps: list[ParsedStep] = []

    for unit, ex in zip(units, extractions):
        doc_unit = nlp(unit.text)
        cond_info = detect_condition(unit.text, doc=doc_unit)
        recur_info = detect_recurrence(unit.text)

        verb = ex.action_verb
        actor = ex.actor_role
        tool = ex.tool_used
        obj = ex.object

        auto_score = _calculate_automation_score(
            verb=verb,
            has_condition=cond_info.has_condition,
            is_recurring=recur_info.is_recurring,
            tool=tool,
        )

        output_type = _determine_output_type(unit.text)
        title = _build_title(unit.text, verb, obj, actor)

        # BUG 5 : flag instruction générique
        # Une étape est "générique" si :
        #   - elle vient d'une énumération
        #   - ET elle n'a pas d'acteur détecté
        #   - ET elle a un verbe (sinon c'est juste une étape ratée)
        is_generic = (
            unit.origin == "enumeration"
            and not actor
            and bool(verb)
        )

        confidence = dict(ex.confidence)
        if cond_info.has_condition:
            confidence["condition"] = cond_info.confidence
        if recur_info.is_recurring:
            confidence["recurrence"] = recur_info.confidence

        steps.append(ParsedStep(
            order=unit.order,
            title=title,
            action_verb=verb,
            actor_role=actor,
            tool_used=tool,
            has_condition=cond_info.has_condition,
            is_recurring=recur_info.is_recurring,
            output_type=output_type,
            automation_score=auto_score,
            raw_sentence=unit.text,
            trigger_condition=cond_info.trigger_condition,
            frequency=recur_info.frequency,
            object=obj,
            confidence=confidence,
            is_generic_instruction=is_generic,
        ))

    return steps
