"""
Service d'ingestion de procédures — point d'entrée pour toutes les sources.

Flux :
    1. La vue (views.py) récupère le texte source (libre ou extrait d'un fichier)
    2. Elle appelle une des fonctions ingest_* ci-dessous
    3. On masque les données personnelles si demandé (via masker)
    4. On passe par le dispatcher qui choisit entre spaCy et Claude selon :
       - le plan de l'organisation (Free → spaCy, Pro/Business → Claude)
       - le flag is_public_endpoint (public → spaCy toujours)
       - le quota mensuel (atteint → dégradation silencieuse sur spaCy)
    5. On crée la Procedure et ses Steps en base
    6. On incrémente le compteur d'analyses mensuel de l'organisation
    7. On retourne le résultat avec des métadonnées (moteur utilisé, masquage, quota)

Rétrocompatibilité :
    Quand LLM_PARSER_ENABLED=False (défaut), le comportement est STRICTEMENT
    identique à l'ancienne version : spaCy est utilisé pour toutes les ingestions,
    comme avant.
"""

import csv
import io
import logging
import pdfplumber
import docx
from django.contrib.auth.models import User

from organizations.models import Organization
from procedures.models import Procedure, Step
from procedures.services.masker import mask_text
from procedures.services import parser_dispatch

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Extracteurs de texte (inchangés)
# ─────────────────────────────────────────────

def extract_text_from_pdf(file) -> str:
    """Extrait le texte brut d'un fichier PDF page par page."""
    text_parts = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text.strip())
    return '\n'.join(text_parts)


def extract_text_from_docx(file) -> str:
    """Extrait le texte brut d'un fichier Word (.docx) paragraphe par paragraphe."""
    document = docx.Document(file)
    paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    return '\n'.join(paragraphs)


def extract_text_from_txt(file) -> str:
    """Extrait le texte brut d'un fichier .txt."""
    if hasattr(file, 'read'):
        return file.read().decode('utf-8')
    with open(file, 'r', encoding='utf-8') as f:
        return f.read()


def extract_steps_from_csv(file) -> list:
    """
    Lit un fichier CSV structuré et retourne une liste de dictionnaires.
    Les données étant déjà structurées, on ne passe PAS par le NLP.
    """
    from procedures.services.parser import _calculate_automation_score

    steps = []
    if hasattr(file, 'read'):
        content = file.read().decode('utf-8')
    else:
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()

    reader = csv.DictReader(io.StringIO(content))

    for i, row in enumerate(reader, start=1):
        is_recur  = str(row.get('is_recurring', 'false')).lower() == 'true'
        has_cond  = str(row.get('has_condition', 'false')).lower() == 'true'
        verb      = row.get('action_verb', '').strip().lower()
        tool      = row.get('tool_used', '').strip()
        auto_score = _calculate_automation_score(verb, has_cond, is_recur, tool)

        steps.append({
            'order'             : int(row.get('order', i)),
            'title'             : row.get('title', f'Étape {i}').strip(),
            'action_verb'       : verb,
            'actor_role'        : row.get('actor_role', '').strip(),
            'tool_used'         : tool,
            'estimated_duration': int(row.get('estimated_duration', 0) or 0),
            'is_recurring'      : is_recur,
            'trigger_type'      : row.get('trigger_type', 'manual').strip(),
            'has_condition'     : has_cond,
            'output_type'       : row.get('output_type', 'none').strip(),
            'automation_score'  : auto_score,
        })

    return steps


# ─────────────────────────────────────────────
# Quota & dégradation silencieuse
# ─────────────────────────────────────────────

def _check_quota_and_adjust(organization, is_public_endpoint):
    """
    Vérifie le quota mensuel d'analyses de l'organisation.

    Retourne un tuple :
        (use_llm_allowed: bool, quota_info: dict)

    Logique :
        - Diagnostic Express public : pas de quota (toujours autorisé, toujours spaCy)
        - Organisation sans quota défini : toujours autorisé (plan Business)
        - Sous la limite : autorisé, llm_allowed=True si plan le permet
        - À la limite : llm_allowed=False (dégradation silencieuse), on laisse passer mais en spaCy

    Dans TOUS les cas, on ne bloque jamais l'analyse — seul le moteur peut changer.
    """
    quota_info = {
        'quota_reached': False,
        'analyses_this_month': 0,
        'monthly_limit': None,
    }

    # Diagnostic Express : pas de quota vérifié
    if is_public_endpoint or organization is None:
        return True, quota_info

    allowed, current, limit = organization.can_analyze_this_month()
    quota_info['analyses_this_month'] = current
    quota_info['monthly_limit'] = limit

    if not allowed:
        # Quota atteint : on force spaCy même pour un plan Pro/Business
        # C'est la dégradation silencieuse demandée
        quota_info['quota_reached'] = True
        logger.info(
            f"Quota atteint pour org {organization.id} "
            f"({current}/{limit}), dégradation sur spaCy"
        )
        return False, quota_info

    return True, quota_info


# ─────────────────────────────────────────────
# Sauvegarde en base (adapté pour les nouveaux champs)
# ─────────────────────────────────────────────

def _create_step_dependencies(procedure: Procedure) -> None:
    """Crée les dépendances séquentielles entre étapes pour le graphe NetworkX."""
    from procedures.models import StepDependency

    steps = list(
        Step.objects.filter(procedure=procedure).order_by('step_order')
    )
    StepDependency.objects.filter(from_step__procedure=procedure).delete()

    for i in range(len(steps) - 1):
        StepDependency.objects.create(
            from_step       = steps[i],
            to_step         = steps[i + 1],
            condition_label = ''
        )


def _create_procedure_and_steps(
    steps_data: list,
    title: str,
    service: str,
    organization: Organization,
    owner,
    source_type: str = 'text',
    engine_used: str = 'spacy',
    quota_info: dict = None,
    masking_applied: bool = False,
) -> dict:
    """
    Crée la Procedure et ses Steps en base.
    Incrémente le compteur mensuel si organization fournie.

    Args:
        engine_used     : 'spacy' ou 'claude', retourné dans la réponse API
        quota_info      : métadonnées de quota pour l'UX frontend
        masking_applied : True si le masquage RGPD a été appliqué en amont
    """
    if not steps_data:
        return {
            'success'    : False,
            'error'      : 'Aucune étape détectée.',
            'steps_count': 0,
            'engine_used': engine_used,
        }

    procedure = Procedure.objects.create(
        organization = organization,
        title        = title,
        service      = service,
        owner        = owner,
        status       = Procedure.STATUS_DRAFT,
        version      = '1.0',
    )

    steps_created = []
    for s in steps_data:
        step = Step.objects.create(
            procedure          = procedure,
            title              = s.get('title', ''),
            action_verb        = s.get('action_verb', ''),
            actor_role         = s.get('actor_role', ''),
            tool_used           = s.get('tool_used', ''),
            estimated_duration = s.get('estimated_duration', 0),
            is_recurring       = s.get('is_recurring', False),
            trigger_type       = s.get('trigger_type', Step.TRIGGER_MANUAL),
            has_condition      = s.get('has_condition', False),
            output_type        = s.get('output_type', Step.OUTPUT_NONE),
            automation_score   = s.get('automation_score', 0.0),
            compliance_status  = Step.COMPLIANCE_WARNING,
            step_order         = s.get('order', 0),
        )
        steps_created.append(step)

    _create_step_dependencies(procedure)

    # Incrémentation du compteur mensuel d'analyses
    # (après création réussie, pour ne pas compter les échecs)
    if organization is not None:
        try:
            organization.increment_monthly_analyses()
        except Exception as e:
            logger.warning(f"Échec de l'incrémentation du compteur mensuel : {e}")

    # Déclenchement automatique de l'analyse
    try:
        from procedures.services.analyzer import analyze_procedure
        analysis = analyze_procedure(procedure.id)
    except Exception as e:
        analysis = {
            'scores': {'optimization': 0, 'automation': 0},
            'anomalies': [],
            'report_id': None,
            'error': str(e)
        }

    return {
        'success'        : True,
        'procedure_id'   : procedure.id,
        'procedure_title': procedure.title,
        'source_type'    : source_type,
        'steps_count'    : len(steps_created),
        'engine_used'    : engine_used,
        'masking_applied': masking_applied,
        'quota'          : quota_info or {},
        'analysis'       : {
            'score_optim'    : analysis.get('scores', {}).get('optimization', 0),
            'score_auto'     : analysis.get('scores', {}).get('automation', 0),
            'anomalies_count': len(analysis.get('anomalies', [])),
            'report_id'      : analysis.get('report_id'),
        },
        'steps'          : [
            {
                'order'           : s.step_order,
                'title'           : s.title,
                'action_verb'     : s.action_verb,
                'actor_role'      : s.actor_role,
                'automation_score': s.automation_score,
            }
            for s in steps_created
        ]
    }


# ─────────────────────────────────────────────
# Core : parsing unifié via le dispatcher
# ─────────────────────────────────────────────

def _parse_and_normalize(
    text: str,
    organization: Organization,
    apply_masking: bool,
    is_public_endpoint: bool,
) -> tuple:
    """
    Fonction interne qui factorise la logique de masquage + dispatch + normalisation.

    Utilisée par ingest_text, ingest_pdf, ingest_docx, ingest_txt.
    Pas utilisée par ingest_csv (CSV = données déjà structurées, pas de NLP).

    Returns:
        (steps_data: list[dict], engine_used: str, quota_info: dict, mapping: dict)
    """
    # Vérification du quota (dégradation silencieuse si atteint)
    llm_allowed, quota_info = _check_quota_and_adjust(organization, is_public_endpoint)

    # Masquage RGPD
    masked_text = text
    mapping = {}
    if apply_masking:
        masked_text, mapping = mask_text(text)

    # Dispatch vers spaCy ou Claude
    # Si le quota est atteint, on force spaCy en passant is_public_endpoint=True
    # (c'est la règle n°1 du dispatcher qui force spaCy)
    effective_public = is_public_endpoint or not llm_allowed
    parsed, engine = parser_dispatch.parse(
        text=masked_text,
        organization=organization,
        is_public_endpoint=effective_public,
        apply_masking=apply_masking,
    )

    # Conversion ParsedStep → dict pour _create_procedure_and_steps
    steps_data = [
        {
            'order'           : p.order,
            'title'           : p.title,
            'action_verb'     : p.action_verb,
            'actor_role'      : p.actor_role,
            'tool_used'       : p.tool_used,
            'has_condition'   : p.has_condition,
            'is_recurring'    : p.is_recurring,
            'output_type'     : p.output_type,
            'automation_score': p.automation_score,
        }
        for p in parsed
    ]

    return steps_data, engine, quota_info, mapping


# ─────────────────────────────────────────────
# Fonctions d'ingestion publiques
# ─────────────────────────────────────────────

def ingest_text(
    text: str,
    title: str,
    service: str,
    organization: Organization,
    owner,
    apply_masking: bool = True,
    is_public_endpoint: bool = False,
) -> dict:
    """Ingestion depuis texte libre."""
    steps_data, engine, quota_info, mapping = _parse_and_normalize(
        text=text,
        organization=organization,
        apply_masking=apply_masking,
        is_public_endpoint=is_public_endpoint,
    )

    result = _create_procedure_and_steps(
        steps_data, title, service, organization, owner,
        source_type='text',
        engine_used=engine,
        quota_info=quota_info,
        masking_applied=apply_masking,
    )
    result['mapping'] = mapping
    return result


def ingest_pdf(
    file,
    title: str,
    service: str,
    organization: Organization,
    owner,
    apply_masking: bool = True,
    is_public_endpoint: bool = False,
) -> dict:
    """Ingestion depuis un fichier PDF."""
    try:
        text = extract_text_from_pdf(file)
    except Exception as e:
        return {'success': False, 'error': f'Erreur lecture PDF : {str(e)}'}

    if not text.strip():
        return {'success': False, 'error': 'Le PDF ne contient pas de texte extractible.'}

    steps_data, engine, quota_info, mapping = _parse_and_normalize(
        text=text,
        organization=organization,
        apply_masking=apply_masking,
        is_public_endpoint=is_public_endpoint,
    )

    result = _create_procedure_and_steps(
        steps_data, title, service, organization, owner,
        source_type='pdf',
        engine_used=engine,
        quota_info=quota_info,
        masking_applied=apply_masking,
    )
    result['mapping'] = mapping
    return result


def ingest_docx(
    file,
    title: str,
    service: str,
    organization: Organization,
    owner,
    apply_masking: bool = True,
    is_public_endpoint: bool = False,
) -> dict:
    """Ingestion depuis un fichier Word (.docx)."""
    try:
        text = extract_text_from_docx(file)
    except Exception as e:
        return {'success': False, 'error': f'Erreur lecture DOCX : {str(e)}'}

    if not text.strip():
        return {'success': False, 'error': 'Le fichier Word ne contient pas de texte.'}

    steps_data, engine, quota_info, mapping = _parse_and_normalize(
        text=text,
        organization=organization,
        apply_masking=apply_masking,
        is_public_endpoint=is_public_endpoint,
    )

    result = _create_procedure_and_steps(
        steps_data, title, service, organization, owner,
        source_type='docx',
        engine_used=engine,
        quota_info=quota_info,
        masking_applied=apply_masking,
    )
    result['mapping'] = mapping
    return result


def ingest_csv(
    file,
    title: str,
    service: str,
    organization: Organization,
    owner,
    is_public_endpoint: bool = False,
) -> dict:
    """
    Ingestion depuis le template CSV structuré.
    Pas de NLP — les données sont déjà structurées.
    Pas de masquage — le CSV ne contient pas de données sensibles par convention.
    """
    try:
        steps_data = extract_steps_from_csv(file)
    except Exception as e:
        return {'success': False, 'error': f'Erreur lecture CSV : {str(e)}'}

    # Pour le CSV, on considère que le moteur utilisé est "csv" (pas de NLP)
    _, quota_info = _check_quota_and_adjust(organization, is_public_endpoint)

    return _create_procedure_and_steps(
        steps_data, title, service, organization, owner,
        source_type='csv',
        engine_used='csv',
        quota_info=quota_info,
        masking_applied=False,
    )


def ingest_txt(
    file,
    title: str,
    service: str,
    organization: Organization,
    owner,
    apply_masking: bool = True,
    is_public_endpoint: bool = False,
) -> dict:
    """Ingestion depuis un fichier texte (.txt)."""
    try:
        text = extract_text_from_txt(file)
    except Exception as e:
        return {'success': False, 'error': f'Erreur lecture TXT : {str(e)}'}

    if not text.strip():
        return {'success': False, 'error': 'Le fichier texte est vide.'}

    steps_data, engine, quota_info, mapping = _parse_and_normalize(
        text=text,
        organization=organization,
        apply_masking=apply_masking,
        is_public_endpoint=is_public_endpoint,
    )

    result = _create_procedure_and_steps(
        steps_data, title, service, organization, owner,
        source_type='txt',
        engine_used=engine,
        quota_info=quota_info,
        masking_applied=apply_masking,
    )
    result['mapping'] = mapping
    return result
