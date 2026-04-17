import json
from pathlib import Path
from procedures.models import Procedure, Step, Rule, AuditReport
from organizations.models import Organization

# Chemin vers les règles
RULES_BASE_PATH = Path(__file__).resolve().parent.parent / 'rules'


def load_rules(sector: str) -> list:
    """
    Charge les règles applicables à un secteur.
    Combine les règles génériques + les règles sectorielles.
    Seules les règles actives sont chargées.
    """
    all_rules = []

    # Règles génériques
    generic_path = RULES_BASE_PATH / 'base' / 'generic.json'
    if generic_path.exists():
        with open(generic_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            all_rules += [r for r in data.get('rules', []) if r.get('active', True)]

    # Règles sectorielles
    sector_path = RULES_BASE_PATH / 'sectors' / f'{sector}.json'
    if sector_path.exists():
        with open(sector_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            all_rules += [r for r in data.get('rules', []) if r.get('active', True)]

    return all_rules


def _rule_applies_to_step(rule: dict, step: Step) -> bool:
    """
    Détermine si une règle s'applique à une étape donnée.
    Vérifie les mots-clés sur l'action, l'output et l'acteur.
    """
    applies_to = rule.get('applies_to', {})

    action_keywords = applies_to.get('action_keywords', [])
    output_types    = applies_to.get('output_types', [])
    actor_keywords  = applies_to.get('actor_keywords', [])

    step_action = (step.action_verb or '').lower()
    step_title  = step.title.lower()
    step_actor  = (step.actor_role or '').lower()
    step_output = step.output_type

    # Vérifie les mots-clés d'action
    action_match = any(
        kw.lower() in step_action or kw.lower() in step_title
        for kw in action_keywords
    ) if action_keywords else False

    # Vérifie le type d'output
    output_match = step_output in output_types if output_types else False

    # Vérifie les mots-clés d'acteur
    actor_match = any(
        kw.lower() in step_actor
        for kw in actor_keywords
    ) if actor_keywords else False

    # La règle s'applique si au moins un critère correspond
    return action_match or output_match or actor_match


def check_step_compliance(step: Step, rules: list) -> dict:
    """
    Vérifie la conformité d'une étape face à toutes les règles.
    Retourne le statut et les violations détectées.
    """
    violations   = []
    has_blocking = False
    has_warning  = False

    for rule in rules:
        if _rule_applies_to_step(rule, step):
            violations.append({
                'rule_id'       : rule['id'],
                'label'         : rule['label'],
                'severity'      : rule['severity'],
                'legal_ref'     : rule.get('legal_ref', ''),
                'description'   : rule['description'],
                'recommendation': rule.get('recommendation', ''),
            })
            if rule['severity'] == 'blocking':
                has_blocking = True
            elif rule['severity'] == 'warning':
                has_warning = True

    # Détermination du statut global
    if has_blocking:
        status = Step.COMPLIANCE_NOK
    elif has_warning:
        status = Step.COMPLIANCE_WARNING
    else:
        status = Step.COMPLIANCE_OK

    return {
        'step_id'   : step.id,
        'step_order': step.step_order,
        'step_title': step.title,
        'status'    : status,
        'violations': violations,
    }


def run_compliance_check(procedure_id: int) -> dict:
    """
    Lance la vérification de conformité complète d'une procédure.

    1. Charge les règles du secteur de l'organisation
    2. Vérifie chaque étape
    3. Met à jour le compliance_status de chaque Step en base
    4. Retourne un rapport complet

    Principe fondateur : la loi prime toujours sur l'optimisation.
    Une étape marquée BLOCKING ne peut jamais être supprimée
    ou automatisée sans validation explicite.
    """
    try:
        procedure = Procedure.objects.get(id=procedure_id)
    except Procedure.DoesNotExist:
        return {'success': False, 'error': 'Procédure introuvable'}

    organization = procedure.organization
    sector       = organization.sector

    # Chargement des règles
    rules = load_rules(sector)

    if not rules:
        return {
            'success'        : True,
            'procedure_id'   : procedure_id,
            'sector'         : sector,
            'rules_loaded'   : 0,
            'message'        : f"Aucune règle définie pour le secteur '{sector}'",
            'steps_checked'  : 0,
            'violations'     : [],
        }

    steps   = procedure.steps.all().order_by('step_order')
    results = []

    blocking_count = 0
    warning_count  = 0
    ok_count       = 0

    for step in steps:
        result = check_step_compliance(step, rules)
        results.append(result)

        # Mise à jour du statut en base
        step.compliance_status = result['status']
        step.save(update_fields=['compliance_status'])

        if result['status'] == Step.COMPLIANCE_NOK:
            blocking_count += 1
        elif result['status'] == Step.COMPLIANCE_WARNING:
            warning_count += 1
        else:
            ok_count += 1

    # Statut global de la procédure
    if blocking_count > 0:
        global_status = 'non_compliant'
    elif warning_count > 0:
        global_status = 'warning'
    else:
        global_status = 'compliant'

    return {
        'success'        : True,
        'procedure_id'   : procedure_id,
        'procedure_title': procedure.title,
        'sector'         : sector,
        'rules_loaded'   : len(rules),
        'steps_checked'  : steps.count(),
        'global_status'  : global_status,
        'summary'        : {
            'blocking': blocking_count,
            'warning' : warning_count,
            'ok'      : ok_count,
        },
        'steps'          : results,
    }


def get_available_rules(sector: str = None) -> dict:
    """
    Retourne toutes les règles disponibles.
    Utile pour afficher le référentiel réglementaire dans l'interface.
    Si sector est None, retourne toutes les règles de tous les secteurs.
    """
    result = {}

    # Règles génériques
    generic_path = RULES_BASE_PATH / 'base' / 'generic.json'
    if generic_path.exists():
        with open(generic_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            result['generic'] = data.get('rules', [])

    if sector:
        sector_path = RULES_BASE_PATH / 'sectors' / f'{sector}.json'
        if sector_path.exists():
            with open(sector_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                result[sector] = data.get('rules', [])
    else:
        # Tous les secteurs
        sectors_path = RULES_BASE_PATH / 'sectors'
        for json_file in sectors_path.glob('*.json'):
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                result[json_file.stem] = data.get('rules', [])

    return result