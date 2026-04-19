"""
Parser Dispatcher : choisit le moteur d'extraction à utiliser selon le contexte.

Règles de sélection :
    1. Endpoint public (Diagnostic Express, sans auth)  -> spaCy toujours
    2. LLM_PARSER_ENABLED = False dans les settings     -> spaCy toujours (kill switch)
    3. Clé ANTHROPIC_API_KEY absente                    -> spaCy toujours (dégradation propre)
    4. organization.can_use_llm() == False              -> spaCy (plan Free, expiré, etc.)
    5. Sinon                                            -> Claude

Le dispatcher est le SEUL point de décision du moteur. Les services d'ingestion
(ingest_text, ingest_pdf, etc.) l'appellent sans se soucier du moteur choisi.

Retour : (steps, engine_used) où engine_used est "spacy" ou "claude".
La vue peut exposer engine_used dans la réponse API pour afficher un badge
"Analyse IA Premium" côté frontend.
"""

import logging
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


# Constantes publiques
ENGINE_SPACY = "spacy"
ENGINE_CLAUDE = "claude"


def should_use_llm(organization=None, is_public_endpoint: bool = False) -> bool:
    """
    Décide si l'analyse doit utiliser le LLM (Claude) ou le parser par règles (spaCy).

    Args:
        organization       : instance Organization, ou None si pas de contexte organisationnel
        is_public_endpoint : True pour les endpoints publics (Diagnostic Express)

    Returns:
        True si Claude doit être utilisé, False si spaCy.

    Ordre des vérifications (court-circuit dès qu'une règle s'applique) :
        1. Endpoint public       -> False (spaCy toujours, même si org Pro)
        2. Kill switch global    -> False (désactivation temporaire sans redéploiement)
        3. Clé API absente       -> False (pas de crash si oubli config prod)
        4. Organisation absente  -> False (contexte sans org = pas de plan = Free)
        5. Plan autorise le LLM  -> True ou False selon can_use_llm()
    """
    # Règle 1 : Diagnostic Express et autres endpoints publics
    if is_public_endpoint:
        return False

    # Règle 2 : kill switch global (variable d'env)
    if not getattr(settings, "LLM_PARSER_ENABLED", False):
        return False

    # Règle 3 : clé API obligatoire, sinon on ne peut pas appeler
    if not getattr(settings, "ANTHROPIC_API_KEY", ""):
        logger.warning(
            "LLM_PARSER_ENABLED=True mais ANTHROPIC_API_KEY absente. "
            "Fallback sur spaCy."
        )
        return False

    # Règle 4 : pas d'organisation = pas de plan identifiable
    if organization is None:
        return False

    # Règle 5 : décision finale selon le plan et son expiration
    return bool(organization.can_use_llm())


def parse(
    text: str,
    organization=None,
    is_public_endpoint: bool = False,
    apply_masking: bool = True,
) -> tuple:
    """
    Analyse un texte et retourne les étapes extraites + le moteur utilisé.

    C'est le SEUL point d'entrée que ingestion.py doit utiliser.
    Les services llm_parser et parser (spaCy) sont des détails d'implémentation.

    Args:
        text               : texte à analyser (déjà masqué si apply_masking=True en amont)
        organization       : instance Organization ou None
        is_public_endpoint : True pour le Diagnostic Express
        apply_masking      : passé au LLM parser pour qu'il sache si le masquage
                             a déjà été fait (pour le logging). Non utilisé par spaCy.

    Returns:
        (steps, engine) où :
            steps  = liste de ParsedStep (même structure quel que soit le moteur)
            engine = "spacy" ou "claude"
    """
    if should_use_llm(organization=organization, is_public_endpoint=is_public_endpoint):
        return _parse_with_claude(text, organization, apply_masking), ENGINE_CLAUDE
    return _parse_with_spacy(text), ENGINE_SPACY


def _parse_with_spacy(text: str) -> list:
    """
    Analyse via le parser par règles (spaCy + lexiques).
    """
    from procedures.services.parser import parse_procedure_text
    return parse_procedure_text(text)


def _parse_with_claude(text: str, organization, apply_masking: bool) -> list:
    """
    Analyse via l'API Claude. Fallback automatique sur spaCy si :
        - l'import de llm_parser échoue
        - l'appel API échoue après retry
        - le JSON retourné est invalide

    Le fallback est géré dans llm_parser lui-même : si ça pète, il retourne
    quand même une liste de ParsedStep via spaCy.
    """
    try:
        from procedures.services.llm_parser import parse_procedure_text_llm
    except ImportError as e:
        logger.error(f"llm_parser indisponible, fallback sur spaCy : {e}")
        return _parse_with_spacy(text)

    org_id = organization.id if organization is not None else None

    return parse_procedure_text_llm(
        text=text,
        apply_masking=apply_masking,
        organization_id=org_id,
    )
