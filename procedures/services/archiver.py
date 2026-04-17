from django.utils import timezone
from django.contrib.auth.models import User
from procedures.models import Procedure, ProcedureVersion
from procedures.services.permissions import can_archive_procedure


def archive_procedure_version(
    procedure_id: int,
    user: User,
    reason: str = 'manual_archive',
    change_summary: str = ''
) -> dict:
    """
    Archive manuellement une procédure.
    Crée un snapshot de la version courante et passe la procédure en ARCHIVED.
    """
    try:
        procedure = Procedure.objects.get(id=procedure_id)
    except Procedure.DoesNotExist:
        return {'success': False, 'error': 'Procédure introuvable'}

    # Vérification des permissions
    if user and not can_archive_procedure(user, procedure):
        return {
            'success': False,
            'error'  : 'Permission refusée — seuls Admin et Directeur peuvent archiver'
        }

    if procedure.status == Procedure.STATUS_ARCHIVED:
        return {
            'success': False,
            'error'  : f"La procédure est déjà archivée (v{procedure.version})"
        }

    # Snapshot avant archivage
    snapshot = ProcedureVersion.snapshot(
        procedure      = procedure,
        reason         = reason,
        user           = user,
        change_summary = change_summary or f"Archivage manuel v{procedure.version}",
    )

    # Archivage de la procédure
    procedure.status      = Procedure.STATUS_ARCHIVED
    procedure.archived_at = timezone.now()
    procedure.archived_by = user
    procedure.save()

    return {
        'success'        : True,
        'procedure_id'   : procedure.id,
        'procedure_title': procedure.title,
        'version'        : procedure.version,
        'snapshot_id'    : snapshot.id,
        'archived_at'    : procedure.archived_at.strftime('%d/%m/%Y à %H:%M'),
        'message'        : f"Procédure v{procedure.version} archivée avec succès",
    }


def get_procedure_history(procedure_id: int) -> dict:
    """
    Retourne l'historique complet des versions d'une procédure.
    """
    try:
        procedure = Procedure.objects.get(id=procedure_id)
    except Procedure.DoesNotExist:
        return {'success': False, 'error': 'Procédure introuvable'}

    versions = ProcedureVersion.objects.filter(
        procedure=procedure
    ).order_by('-created_at')

    return {
        'success'        : True,
        'procedure_id'   : procedure.id,
        'procedure_title': procedure.title,
        'current_version': procedure.version,
        'current_status' : procedure.status,
        'history'        : [
            {
                'version_number': v.version_number,
                'reason'        : v.get_reason_display(),
                'change_summary': v.change_summary,
                'steps_count'   : v.snapshot_data.get('steps_count', 0),
                'created_at'    : v.created_at.strftime('%d/%m/%Y à %H:%M'),
                'created_by'    : v.created_by.username if v.created_by else 'système',
            }
            for v in versions
        ],
        'total_versions': versions.count(),
    }


def get_procedures_by_status(
    organization_id: int,
    user,
    status: str = None,
    service: str = None,
) -> dict:
    """
    Retourne les procédures filtrées par statut et/ou service.
    Respecte les permissions de l'utilisateur.
    """
    from organizations.models import Organization
    from procedures.services.permissions import get_accessible_procedures

    try:
        organization = Organization.objects.get(id=organization_id)
    except Organization.DoesNotExist:
        return {'success': False, 'error': 'Organisation introuvable'}

    # Filtre selon les permissions
    procedures = get_accessible_procedures(user, organization)

    # Filtres optionnels
    if status:
        procedures = procedures.filter(status=status)
    if service:
        procedures = procedures.filter(service__iexact=service)

    procedures = procedures.order_by('service', 'title')

    return {
        'success': True,
        'count'  : procedures.count(),
        'filters': {'status': status, 'service': service},
        'procedures': [
            {
                'id'          : p.id,
                'title'       : p.title,
                'service'     : p.service,
                'version'     : p.version,
                'status'      : p.status,
                'status_display': p.get_status_display(),
                'owner'       : p.owner.username if p.owner else '—',
                'created_at'  : p.created_at.strftime('%d/%m/%Y'),
                'updated_at'  : p.updated_at.strftime('%d/%m/%Y'),
                'archived_at' : p.archived_at.strftime('%d/%m/%Y à %H:%M') if p.archived_at else None,
            }
            for p in procedures
        ]
    }