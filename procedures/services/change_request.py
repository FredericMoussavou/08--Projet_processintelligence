from django.utils import timezone
from django.contrib.auth.models import User
from procedures.models import Procedure, ChangeRequest
from procedures.services.compliance import run_compliance_check


def _run_auto_check(cr: ChangeRequest) -> str:
    """
    Lance l'analyse automatique d'une demande de changement.
    Retourne le statut résultant.
    """
    cr.add_log('Analyse automatique démarrée', actor='système')

    # Lance la vérification de conformité
    compliance = run_compliance_check(cr.procedure.id)

    blocking_rules = []
    warning_rules  = []

    for step_result in compliance.get('steps', []):
        for violation in step_result.get('violations', []):
            if violation['severity'] == 'blocking':
                blocking_rules.append({
                    'step'     : step_result['step_title'],
                    'rule_id'  : violation['rule_id'],
                    'label'    : violation['label'],
                    'legal_ref': violation['legal_ref'],
                    'recommendation': violation['recommendation'],
                })
            elif violation['severity'] == 'warning':
                warning_rules.append({
                    'step'     : step_result['step_title'],
                    'rule_id'  : violation['rule_id'],
                    'label'    : violation['label'],
                })

    if blocking_rules:
        # Rejet automatique
        cr.blocking_rules    = blocking_rules
        cr.rejection_reason  = (
            f"Rejet automatique — {len(blocking_rules)} règle(s) bloquante(s) détectée(s) : "
            + ', '.join(r['label'] for r in blocking_rules)
        )
        cr.status = ChangeRequest.STATUS_AUTO_REJECTED
        cr.save(update_fields=['blocking_rules', 'rejection_reason', 'status'])
        cr.add_log(
            'Rejet automatique',
            detail=cr.rejection_reason,
            actor='système'
        )
        return ChangeRequest.STATUS_AUTO_REJECTED

    elif warning_rules:
        # Soumis au reviewer
        cr.status = ChangeRequest.STATUS_AWAITING_REVIEW
        cr.save(update_fields=['status'])
        reviewer_name = cr.reviewer.get_full_name() or cr.reviewer.username if cr.reviewer else 'reviewer désigné'
        cr.add_log(
            'En attente de validation humaine',
            detail=f"{len(warning_rules)} avertissement(s) détecté(s) — soumis à {reviewer_name}",
            actor='système'
        )
        return ChangeRequest.STATUS_AWAITING_REVIEW

    else:
        # Approbation automatique
        cr.status = ChangeRequest.STATUS_AUTO_APPROVED
        cr.save(update_fields=['status'])
        cr.add_log(
            'Approbation automatique',
            detail='Aucune anomalie détectée — procédure conforme',
            actor='système'
        )
        _apply_approval(cr, actor='système')
        return ChangeRequest.STATUS_AUTO_APPROVED


def _apply_approval(cr: ChangeRequest, actor: str = 'système'):
    """
    Applique l'approbation — incrémente la version et active la procédure.
    """
    procedure   = cr.procedure
    old_version = procedure.version
    new_version = _increment_version(old_version, cr.change_type)

    procedure.version = new_version
    procedure.status  = Procedure.STATUS_ACTIVE
    procedure.save()

# Snapshot automatique de l'ancienne version avant mise à jour
    from procedures.models import ProcedureVersion
    reviewer_user = cr.reviewer if cr.reviewer else None
    ProcedureVersion.snapshot(
        procedure      = procedure,
        reason         = 'auto_approval',
        user           = reviewer_user,
        change_summary = cr.description[:200],
    )

    # Archive l'ancienne version de la procédure
    from django.utils import timezone as tz
    old_procedure_status         = procedure.status
    procedure.archived_at        = None
    procedure.version            = new_version
    procedure.status             = Procedure.STATUS_ACTIVE
    procedure.save()

    cr.reviewed_at = timezone.now()
    cr.save(update_fields=['reviewed_at'])

    cr.add_log(
        'Procédure mise à jour',
        detail=f"Version {old_version} → {new_version} — statut : Active — snapshot v{old_version} créé",
        actor=actor
    )

def _increment_version(version: str, change_type: str = 'patch') -> str:
    """
    Incrémente la version selon le type de changement (SemVer adapté).

    patch : 1.0 → 1.1 → 1.2 → ... → 1.9 → 1.10
    minor : 1.2 → 1.3 (même logique que patch pour l'instant)
    major : 1.2 → 2.0 / 2.5 → 3.0
    """
    try:
        major, minor = version.split('.')
        major_int = int(major)
        minor_int = int(minor)

        if change_type == 'major':
            return f"{major_int + 1}.0"
        else:
            # patch et minor incrémentent le mineur
            return f"{major_int}.{minor_int + 1}"

    except Exception:
        return "2.0"


def submit_change_request(
    procedure_id: int,
    requested_by: User,
    description: str,
    reviewer_id: int = None,
    change_type: str = 'patch',
) -> dict:
    """
    Soumet une demande de changement et déclenche l'analyse automatique.
    """
    try:
        procedure = Procedure.objects.get(id=procedure_id)
    except Procedure.DoesNotExist:
        return {'success': False, 'error': 'Procédure introuvable'}

    # Vérifie qu'il n'y a pas déjà une demande en attente
    pending = ChangeRequest.objects.filter(
        procedure=procedure,
        status__in=[
            ChangeRequest.STATUS_PENDING,
            ChangeRequest.STATUS_AWAITING_REVIEW,
            ChangeRequest.STATUS_AUTO_CHECKING,
        ]
    )
    if pending.exists():
        return {
            'success': False,
            'error'  : 'Une demande est déjà en cours pour cette procédure'
        }

    reviewer = None
    if reviewer_id:
        try:
            reviewer = User.objects.get(id=reviewer_id)
        except User.DoesNotExist:
            return {'success': False, 'error': 'Reviewer introuvable'}

    # Création de la demande

    cr = ChangeRequest.objects.create(
        procedure    = procedure,
        requested_by = requested_by,
        reviewer     = reviewer,
        description  = description,
        change_type  = change_type,
        status       = ChangeRequest.STATUS_PENDING,
    )

    actor_name = requested_by.username if requested_by else 'anonyme'
    cr.add_log(
        'Demande soumise',
        detail=description[:100],
        actor=actor_name
    )

    # Analyse automatique immédiate
    final_status = _run_auto_check(cr)
    cr.refresh_from_db()

    return {
        'success'           : True,
        'change_request_id' : cr.id,
        'procedure_id'      : procedure.id,
        'procedure_title'   : procedure.title,
        'status'            : final_status,
        'status_display'    : dict(ChangeRequest.STATUS_CHOICES).get(final_status, ''),
        'workflow_log'      : cr.workflow_log,
        'blocking_rules'    : cr.blocking_rules,
        'rejection_reason'  : cr.rejection_reason,
        'reviewer'          : reviewer.username if reviewer else None,
        'message'           : _status_message(final_status),
    }


def approve_change_request(
    change_request_id: int,
    reviewer: User,
    comment: str = '',
) -> dict:
    """Approbation humaine d'une demande en attente."""
    try:
        cr = ChangeRequest.objects.get(id=change_request_id)
    except ChangeRequest.DoesNotExist:
        return {'success': False, 'error': 'Demande introuvable'}

    if cr.status != ChangeRequest.STATUS_AWAITING_REVIEW:
        return {
            'success': False,
            'error'  : f"Cette demande ne peut pas être approuvée (statut : {cr.status})"
        }

    reviewer_name = reviewer.username if reviewer else 'inconnu'
    cr.status   = ChangeRequest.STATUS_APPROVED
    cr.reviewer = reviewer
    cr.save(update_fields=['status', 'reviewer'])

    if comment:
        cr.add_log('Commentaire reviewer', detail=comment, actor=reviewer_name)

    cr.add_log('Approbation humaine', actor=reviewer_name)
    _apply_approval(cr, actor=reviewer_name)
    cr.refresh_from_db()

    return {
        'success'           : True,
        'change_request_id' : cr.id,
        'procedure_id'      : cr.procedure.id,
        'procedure_title'   : cr.procedure.title,
        'new_version'       : cr.procedure.version,
        'status'            : cr.status,
        'workflow_log'      : cr.workflow_log,
        'reviewed_at'       : cr.reviewed_at.strftime('%d/%m/%Y à %H:%M'),
        'message'           : 'Demande approuvée — procédure mise à jour',
    }


def reject_change_request(
    change_request_id: int,
    reviewer: User,
    reason: str,
) -> dict:
    """Rejet humain d'une demande en attente."""
    try:
        cr = ChangeRequest.objects.get(id=change_request_id)
    except ChangeRequest.DoesNotExist:
        return {'success': False, 'error': 'Demande introuvable'}

    if cr.status != ChangeRequest.STATUS_AWAITING_REVIEW:
        return {
            'success': False,
            'error'  : f"Cette demande ne peut pas être rejetée (statut : {cr.status})"
        }

    reviewer_name    = reviewer.username if reviewer else 'inconnu'
    cr.status        = ChangeRequest.STATUS_REJECTED
    cr.reviewer      = reviewer
    cr.rejection_reason = reason
    cr.reviewed_at   = timezone.now()
    cr.save(update_fields=['status', 'reviewer', 'rejection_reason', 'reviewed_at'])

    cr.add_log('Rejet humain', detail=reason, actor=reviewer_name)

    return {
        'success'           : True,
        'change_request_id' : cr.id,
        'procedure_id'      : cr.procedure.id,
        'procedure_title'   : cr.procedure.title,
        'status'            : cr.status,
        'rejection_reason'  : reason,
        'workflow_log'      : cr.workflow_log,
        'reviewed_at'       : cr.reviewed_at.strftime('%d/%m/%Y à %H:%M'),
        'message'           : 'Demande rejetée',
    }


def get_change_request_status(change_request_id: int) -> dict:
    """
    Retourne le statut détaillé d'une demande — avec le workflow complet.
    C'est ce qu'on affichera dans l'interface pour que l'utilisateur
    sache où en est sa demande.
    """
    try:
        cr = ChangeRequest.objects.get(id=change_request_id)
    except ChangeRequest.DoesNotExist:
        return {'success': False, 'error': 'Demande introuvable'}

    # Message de localisation dans le workflow
    location = _workflow_location(cr)

    return {
        'success'           : True,
        'change_request_id' : cr.id,
        'procedure_id'      : cr.procedure.id,
        'procedure_title'   : cr.procedure.title,
        'procedure_version' : cr.procedure.version,
        'status'            : cr.status,
        'status_display'    : dict(ChangeRequest.STATUS_CHOICES).get(cr.status, ''),
        'location'          : location,
        'requested_by'      : cr.requested_by.username if cr.requested_by else '—',
        'reviewer'          : cr.reviewer.username if cr.reviewer else '—',
        'description'       : cr.description,
        'rejection_reason'  : cr.rejection_reason,
        'blocking_rules'    : cr.blocking_rules,
        'workflow_log'      : cr.workflow_log,
        'created_at'        : cr.created_at.strftime('%d/%m/%Y à %H:%M'),
        'reviewed_at'       : cr.reviewed_at.strftime('%d/%m/%Y à %H:%M') if cr.reviewed_at else None,
    }


def get_change_requests(procedure_id: int = None, status: str = None) -> dict:
    """Retourne les demandes de changement filtrables."""
    qs = ChangeRequest.objects.all().order_by('-created_at')

    if procedure_id:
        qs = qs.filter(procedure_id=procedure_id)
    if status:
        qs = qs.filter(status=status)

    results = []
    for cr in qs:
        results.append({
            'id'               : cr.id,
            'procedure_id'     : cr.procedure.id,
            'procedure_title'  : cr.procedure.title,
            'procedure_version': cr.procedure.version,
            'requested_by'     : cr.requested_by.username if cr.requested_by else '—',
            'reviewer'         : cr.reviewer.username if cr.reviewer else '—',
            'status'           : cr.status,
            'status_display'   : dict(ChangeRequest.STATUS_CHOICES).get(cr.status, ''),
            'location'         : _workflow_location(cr),
            'created_at'       : cr.created_at.strftime('%d/%m/%Y à %H:%M'),
            'reviewed_at'      : cr.reviewed_at.strftime('%d/%m/%Y à %H:%M') if cr.reviewed_at else None,
        })

    return {'success': True, 'count': len(results), 'results': results}


def _workflow_location(cr: ChangeRequest) -> str:
    """
    Retourne une phrase claire indiquant où se trouve la demande
    dans le workflow — c'est ce que verra l'utilisateur dans l'interface.
    """
    reviewer_name = (
        cr.reviewer.get_full_name() or cr.reviewer.username
        if cr.reviewer else 'reviewer désigné'
    )
    locations = {
        ChangeRequest.STATUS_PENDING:
            "⏳ Demande reçue — analyse en cours",
        ChangeRequest.STATUS_AUTO_CHECKING:
            "🔍 Analyse automatique de conformité en cours",
        ChangeRequest.STATUS_AUTO_REJECTED:
            f"❌ Rejetée automatiquement — {cr.rejection_reason[:80]}",
        ChangeRequest.STATUS_AWAITING_REVIEW:
            f"👤 En attente de validation par {reviewer_name}",
        ChangeRequest.STATUS_APPROVED:
            f"✅ Approuvée par {reviewer_name} — procédure mise à jour",
        ChangeRequest.STATUS_AUTO_APPROVED:
            "✅ Approuvée automatiquement — aucune anomalie détectée",
        ChangeRequest.STATUS_REJECTED:
            f"❌ Rejetée par {reviewer_name} — motif : {cr.rejection_reason[:80]}",
    }
    return locations.get(cr.status, "Statut inconnu")


def _status_message(status: str) -> str:
    """Message court pour chaque statut."""
    messages = {
        ChangeRequest.STATUS_AUTO_REJECTED:
            "Demande rejetée automatiquement — des règles bloquantes ont été détectées",
        ChangeRequest.STATUS_AWAITING_REVIEW:
            "Des avertissements ont été détectés — la demande attend une validation humaine",
        ChangeRequest.STATUS_AUTO_APPROVED:
            "Demande approuvée automatiquement — procédure conforme et mise à jour",
    }
    return messages.get(status, '')