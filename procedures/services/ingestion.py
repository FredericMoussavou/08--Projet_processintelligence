from django.contrib.auth.models import User
from procedures.models import Procedure, Step
from procedures.services.masker import mask_text
from procedures.services.parser import parse_procedure_text
from organizations.models import Organization


def ingest_text(
    text: str,
    title: str,
    service: str,
    organization: Organization,
    owner: User,
    apply_masking: bool = True
) -> dict:
    """
    Fonction principale d'ingestion.

    Orchestration :
    1. Masquage RGPD (optionnel)
    2. Parsing NLP → liste de ParsedStep
    3. Création de la Procedure en base
    4. Création des Step en base
    5. Retourne un résumé de l'opération

    Paramètres :
    - text          : le texte brut décrivant la procédure
    - title         : titre de la procédure
    - service       : département (ex: RH, Comptabilité)
    - organization  : l'Organisation propriétaire
    - owner         : l'utilisateur qui soumet
    - apply_masking : True par défaut — masque les données sensibles
    """

    masked_text = text
    mapping = {}

    # --- Étape 1 : Masquage RGPD ---
    if apply_masking:
        masked_text, mapping = mask_text(text)

    # --- Étape 2 : Parsing NLP ---
    parsed_steps = parse_procedure_text(masked_text)

    if not parsed_steps:
        return {
            'success': False,
            'error': 'Aucune étape détectée dans le texte fourni.',
            'steps_count': 0,
        }

    # --- Étape 3 : Création de la Procedure ---
    procedure = Procedure.objects.create(
        organization = organization,
        title        = title,
        service      = service,
        owner        = owner,
        status       = Procedure.STATUS_DRAFT,
        version      = '1.0',
    )

    # --- Étape 4 : Création des Steps ---
    steps_created = []
    for parsed in parsed_steps:
        step = Step.objects.create(
            procedure          = procedure,
            title              = parsed.title,
            action_verb        = parsed.action_verb,
            actor_role         = parsed.actor_role,
            tool_used          = parsed.tool_used,
            has_condition      = parsed.has_condition,
            is_recurring       = parsed.is_recurring,
            output_type        = parsed.output_type,
            automation_score   = parsed.automation_score,
            trigger_type       = Step.TRIGGER_MANUAL,
            compliance_status  = Step.COMPLIANCE_WARNING,
            step_order         = parsed.order,
        )
        steps_created.append(step)

    # --- Étape 5 : Résumé ---
    return {
        'success'       : True,
        'procedure_id'  : procedure.id,
        'procedure_title': procedure.title,
        'steps_count'   : len(steps_created),
        'masking_applied': apply_masking,
        'mapping'       : mapping,
        'steps'         : [
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