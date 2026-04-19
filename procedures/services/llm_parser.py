"""
Service d'extraction d'étapes de procédure via l'API Anthropic Claude.

Pipeline :
    1. Réception du texte (déjà masqué ou non selon apply_masking)
    2. Recherche en cache (clé = hash SHA-256 du texte + flag masking)
    3. Si cache miss : appel API Claude avec prompt structuré
    4. Parsing et validation du JSON retourné
    5. Mise en cache du résultat (TTL 7 jours)
    6. Logging de l'appel dans LLMCallLog (tokens, durée, coût estimable)
    7. Retour d'une liste de ParsedStep compatible avec parser.py

Fallback : en cas d'échec (timeout, JSON invalide, clé absente), on retombe
automatiquement sur le parser par règles (spaCy). L'appelant ne voit pas
la différence — il reçoit toujours une liste de ParsedStep valide.

Compatibilité : la sortie a exactement la même structure que
`parser.parse_procedure_text()`, avec la classe `ParsedStep` importée depuis
`parser.py`. C'est le dispatcher qui décide quel moteur utiliser, pas ce module.
"""

import hashlib
import json
import logging
import time
from typing import Optional

from django.conf import settings
from django.core.cache import cache

# On réutilise le même dataclass que le parser par règles pour que ingest_*
# puisse traiter les deux sorties de manière indifférenciée.
from procedures.services.parser import ParsedStep

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

CACHE_PREFIX = "llm_parser:"
CACHE_TTL_SECONDS = 60 * 60 * 24 * 7   # 7 jours

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TIMEOUT_SECONDS = 30
RETRY_COUNT = 1                         # 1 tentative initiale + 1 retry = 2 essais max
RETRY_BACKOFF_SECONDS = 0.5


# ---------------------------------------------------------------------------
# Prompt système (factorisé pour maintenance facile)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Tu es un analyste de procédures d'entreprise. Tu extrais les étapes structurées d'un texte libre décrivant une procédure.

Tu retournes STRICTEMENT un JSON conforme au schéma suivant, sans aucun texte autour, sans markdown, sans préambule :

{
  "steps": [
    {
      "order": 1,
      "title": "Titre court à l'impératif (ex: 'Valider le dossier')",
      "action_verb": "verbe à l'infinitif en minuscules (ex: 'valider')",
      "actor_role": "rôle canonique de l'acteur (ex: 'Manager', 'RH', 'Comptable') — vide si absent",
      "tool_used": "nom de l'outil utilisé (ex: 'SAP', 'Excel', 'Email') — vide si absent",
      "object": "complément d'objet du verbe (ex: 'facture', 'dossier client') — vide si absent",
      "has_condition": true/false,
      "trigger_condition": "clause conditionnelle complète (ex: 'si le montant dépasse 500 euros') — vide si has_condition=false",
      "is_recurring": true/false,
      "frequency": "daily|weekly|monthly|quarterly|yearly|continuous|on_event — vide si is_recurring=false",
      "output_type": "decision|document|data|none",
      "automation_score": 0.0 à 1.0 (potentiel d'automatisation : 1.0 = complètement automatisable, 0.0 = décision humaine pure),
      "raw_sentence": "phrase source dans le texte original"
    }
  ]
}

RÈGLES D'EXTRACTION :

1. SEGMENTATION. Une phrase peut contenir plusieurs étapes si elle coordonne des actions successives ("saisit puis transmet" = 2 étapes). Une énumération numérotée = une étape par ligne.

2. ACTEURS CANONIQUES. Normalise les acteurs à leur forme canonique : "le manager"/"les managers"/"Manager" → "Manager". Pour un acteur genré, utilise le masculin neutre : "assistante" → "Assistant". Si le texte utilise un pronom ("il", "elle", "on"), remonte au dernier acteur nommé de la procédure.

3. CONDITIONS. Une condition ("si X, Y fait Z") doit enrichir l'étape principale ("Y fait Z") avec trigger_condition="si X", et non créer 2 étapes séparées.

4. RÉCURRENCES. Détecte les fréquences : "chaque mois" → monthly. "chaque année" ou "annuel" → yearly. "à chaque demande" → on_event. "régulièrement" → continuous.

5. OUTIL VS ACTEUR. Une préposition "par" suivie d'un acteur ("par le manager") n'est PAS un outil — c'est l'agent d'un passif. Un outil est introduit par "via", "sur", "dans", "avec" + nom de logiciel ou support.

6. NOMINALISATIONS. Si le texte utilise une forme nominalisée ("la validation du dossier par le manager"), reconstitue : verbe="valider", acteur="Manager", objet="dossier".

7. OUTPUT_TYPE.
   - "decision" si l'étape implique une validation, approbation, refus
   - "document" si elle produit un document (rapport, contrat, fiche)
   - "data" si elle manipule des données (saisie, calcul, extraction)
   - "none" dans les autres cas

8. AUTOMATION_SCORE.
   - 0.8-1.0 : tâche mécanique répétitive avec outil (saisie, copie, export, notification automatique)
   - 0.4-0.7 : tâche partiellement automatisable (création de document, relance)
   - 0.1-0.3 : tâche de jugement humain (validation, négociation, arbitrage, analyse)

Retourne UNIQUEMENT le JSON, rien d'autre."""


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _cache_key(text: str, masked: bool) -> str:
    """
    Génère une clé de cache stable pour un texte donné.
    On préfixe 'm' (masked) ou 'r' (raw) pour ne pas mélanger les résultats
    selon que le masquage a été appliqué en amont ou non.
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]
    return f"{CACHE_PREFIX}{'m' if masked else 'r'}:{digest}"


# ---------------------------------------------------------------------------
# Appel API Anthropic
# ---------------------------------------------------------------------------

def _call_claude_api(text: str, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict:
    """
    Appelle l'API Anthropic Claude et retourne le JSON brut parsé.

    Raises :
        RuntimeError : clé API absente
        anthropic.APIError : erreur réseau ou côté Anthropic
        ValueError : JSON invalide dans la réponse
    """
    import anthropic

    api_key = getattr(settings, "ANTHROPIC_API_KEY", None)
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY non configurée dans les settings")

    model = getattr(settings, "LLM_PARSER_MODEL", DEFAULT_MODEL)
    client = anthropic.Anthropic(api_key=api_key, timeout=timeout)

    message = client.messages.create(
        model=model,
        max_tokens=DEFAULT_MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": text},
        ],
    )

    # L'API retourne une liste de content blocks. On concatène les blocs texte.
    raw_output = ""
    for block in message.content:
        if hasattr(block, "text"):
            raw_output += block.text

    # Nettoyage défensif : parfois Claude wrappe en ```json ... ``` malgré l'instruction
    stripped = raw_output.strip()
    if stripped.startswith("```"):
        lines = stripped.split("\n")
        # Retire la première et la dernière ligne (les fences)
        stripped = "\n".join(lines[1:-1]) if len(lines) > 2 else stripped
        stripped = stripped.strip()

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON invalide retourné par le LLM : {e}. "
                         f"Début : {stripped[:200]!r}")

    # Métadonnées pour logging (tokens facturés)
    parsed["_meta"] = {
        "model": model,
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
    }

    return parsed


# ---------------------------------------------------------------------------
# Validation du JSON retourné
# ---------------------------------------------------------------------------

_REQUIRED_STEP_FIELDS = {"order", "title", "action_verb"}
_VALID_FREQUENCIES = {"", "daily", "weekly", "monthly", "quarterly",
                      "yearly", "continuous", "on_event"}
_VALID_OUTPUT_TYPES = {"decision", "document", "data", "none"}


def _validate_and_build_steps(llm_json: dict) -> list:
    """
    Valide la structure du JSON retourné par Claude et construit des ParsedStep.

    Tolérant aux champs manquants (valeurs par défaut) mais strict sur la
    structure racine : on exige {"steps": [...]}.

    Les champs inconnus sont ignorés silencieusement.

    Returns:
        Liste de ParsedStep (peut être vide si toutes les étapes sont invalides).

    Raises:
        ValueError : structure racine invalide (pas de clé "steps" ou pas une liste)
    """
    if "steps" not in llm_json or not isinstance(llm_json["steps"], list):
        raise ValueError("JSON LLM invalide : clé 'steps' absente ou non-liste")

    steps = []
    for idx, raw in enumerate(llm_json["steps"]):
        if not isinstance(raw, dict):
            continue

        # On tolère l'absence de certains champs obligatoires mais on skip
        # si le strict minimum n'est pas là
        if not _REQUIRED_STEP_FIELDS.issubset(raw.keys()):
            continue

        # Normalisation défensive des valeurs
        frequency = str(raw.get("frequency", "") or "")
        if frequency not in _VALID_FREQUENCIES:
            frequency = ""

        output_type = str(raw.get("output_type", "none") or "none")
        if output_type not in _VALID_OUTPUT_TYPES:
            output_type = "none"

        try:
            auto_score = float(raw.get("automation_score", 0.0))
            auto_score = max(0.0, min(1.0, auto_score))
        except (TypeError, ValueError):
            auto_score = 0.0

        steps.append(ParsedStep(
            order=int(raw.get("order", idx + 1)),
            title=str(raw.get("title", ""))[:255],
            action_verb=str(raw.get("action_verb", "")).lower()[:100],
            actor_role=str(raw.get("actor_role", ""))[:100],
            tool_used=str(raw.get("tool_used", ""))[:100],
            object=str(raw.get("object", "")),
            has_condition=bool(raw.get("has_condition", False)),
            trigger_condition=str(raw.get("trigger_condition", "")),
            is_recurring=bool(raw.get("is_recurring", False)),
            frequency=frequency,
            output_type=output_type,
            automation_score=round(auto_score, 2),
            raw_sentence=str(raw.get("raw_sentence", "")),
            # Le LLM ne retourne pas de score de confiance. On met 0.95 par défaut
            # pour refléter la haute qualité de son extraction, avec exceptions
            # sur les champs vides.
            confidence={
                "action_verb": 0.95 if raw.get("action_verb") else 0.0,
                "actor_role": 0.95 if raw.get("actor_role") else 0.0,
                "tool_used": 0.95 if raw.get("tool_used") else 0.0,
                "object": 0.95 if raw.get("object") else 0.0,
            },
            is_generic_instruction=False,
        ))

    return steps


# ---------------------------------------------------------------------------
# Logging des appels (pour suivi de coûts)
# ---------------------------------------------------------------------------

def _log_call(text_length: int, duration_ms: int, input_tokens: int,
              output_tokens: int, model: str, cache_hit: bool,
              fallback_used: bool, organization_id: Optional[int] = None):
    """
    Enregistre un appel dans LLMCallLog.
    Silencieux en cas d'échec — le logging ne doit jamais casser une requête.
    """
    try:
        from procedures.models import LLMCallLog
        LLMCallLog.objects.create(
            organization_id=organization_id,
            text_length=text_length,
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            cache_hit=cache_hit,
            fallback_used=fallback_used,
        )
    except Exception as e:
        logger.warning(f"Échec du logging LLMCallLog : {e}")


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------

def _fallback_to_rules(text: str) -> list:
    """
    Fallback : utilise le parser par règles quand l'appel LLM échoue.

    Retourne une liste de ParsedStep compatible. L'appelant ne voit pas
    la différence avec un résultat Claude normal (même type de sortie).
    """
    from procedures.services.parser import parse_procedure_text
    return parse_procedure_text(text)


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def parse_procedure_text_llm(text: str,
                              apply_masking: bool = False,
                              organization_id: Optional[int] = None,
                              force_refresh: bool = False) -> list:
    """
    Parse un texte de procédure via l'API Claude.

    Args:
        text              : texte brut de la procédure (déjà masqué en amont si besoin)
        apply_masking     : simple flag pour le cache (True si le texte passé est masqué)
                            NE fait PAS le masquage lui-même — c'est la responsabilité
                            de l'appelant (ingestion.py).
        organization_id   : id de l'organisation pour le logging
        force_refresh     : ignore le cache et force un nouvel appel (utile pour debug)

    Returns:
        Liste de ParsedStep (même type que parser.parse_procedure_text).

    En cas d'échec, fallback automatique sur spaCy.
    """
    if not text or not text.strip():
        return []

    # -------- Cache lookup --------
    cache_key = _cache_key(text, masked=apply_masking)
    if not force_refresh:
        cached = cache.get(cache_key)
        if cached is not None:
            _log_call(
                text_length=len(text),
                duration_ms=0,
                input_tokens=0,
                output_tokens=0,
                model=cached.get("_meta", {}).get("model", "cached"),
                cache_hit=True,
                fallback_used=False,
                organization_id=organization_id,
            )
            try:
                return _validate_and_build_steps(cached)
            except ValueError as e:
                # Cache corrompu : on l'invalide et on continue vers l'API
                logger.warning(f"Cache invalide pour {cache_key} : {e}. Réappel API.")
                cache.delete(cache_key)

    # -------- Appel API avec retry --------
    t0 = time.time()
    llm_json = None
    last_error = None

    for attempt in range(RETRY_COUNT + 1):
        try:
            llm_json = _call_claude_api(text)
            break
        except Exception as e:
            last_error = e
            logger.warning(
                f"Appel LLM attempt {attempt + 1}/{RETRY_COUNT + 1} échoué : {e}"
            )
            if attempt < RETRY_COUNT:
                time.sleep(RETRY_BACKOFF_SECONDS)

    duration_ms = int((time.time() - t0) * 1000)

    # -------- Fallback si tout a échoué --------
    if llm_json is None:
        logger.error(f"Appel LLM échoué après {RETRY_COUNT + 1} tentatives : {last_error}")
        _log_call(
            text_length=len(text),
            duration_ms=duration_ms,
            input_tokens=0,
            output_tokens=0,
            model="fallback",
            cache_hit=False,
            fallback_used=True,
            organization_id=organization_id,
        )
        return _fallback_to_rules(text)

    # -------- Mise en cache --------
    try:
        cache.set(cache_key, llm_json, timeout=CACHE_TTL_SECONDS)
    except Exception as e:
        # Cache foireux ≠ requête foireuse. On log mais on continue.
        logger.warning(f"Échec de mise en cache : {e}")

    # -------- Logging --------
    meta = llm_json.get("_meta", {})
    _log_call(
        text_length=len(text),
        duration_ms=duration_ms,
        input_tokens=meta.get("input_tokens", 0),
        output_tokens=meta.get("output_tokens", 0),
        model=meta.get("model", "unknown"),
        cache_hit=False,
        fallback_used=False,
        organization_id=organization_id,
    )

    # -------- Validation et conversion --------
    try:
        return _validate_and_build_steps(llm_json)
    except ValueError as e:
        logger.error(f"Validation du JSON LLM échouée : {e}. Fallback sur spaCy.")
        return _fallback_to_rules(text)
