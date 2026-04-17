from organizations.models import Membership, ServiceMembership
from procedures.models import Procedure


def get_user_role(user, organization) -> str:
    """
    Retourne le rôle global d'un utilisateur dans une organisation.
    Retourne None si l'utilisateur n'est pas membre.
    """
    try:
        membership = Membership.objects.get(user=user, organization=organization)
        return membership.role
    except Membership.DoesNotExist:
        return None


def get_user_services(user, organization) -> list:
    """
    Retourne la liste des services auxquels l'utilisateur a accès
    avec son rôle pour chacun.
    """
    service_memberships = ServiceMembership.objects.filter(
        user=user, organization=organization
    )
    return [
        {
            'service': sm.service,
            'role'   : sm.role,
        }
        for sm in service_memberships
    ]


def can_view_procedure(user, procedure) -> bool:
    """
    Vérifie si un utilisateur peut voir une procédure.

    Règles :
    - Admin → toujours ✅
    - Director → toujours ✅
    - Manager/Viewer global → uniquement si membre du service
    - Service Manager/Viewer → uniquement son service
    """
    organization = procedure.organization
    role         = get_user_role(user, organization)

    if role is None:
        return False

    # Admin et Director voient tout
    if role in (Membership.ROLE_ADMIN, Membership.ROLE_DIRECTOR):
        return True

    # Les autres vérifient l'accès au service
    return _has_service_access(user, organization, procedure.service)


def can_edit_procedure(user, procedure) -> bool:
    """
    Vérifie si un utilisateur peut modifier une procédure.

    Règles :
    - Admin → toujours ✅
    - Director → ❌ (peut voir mais pas modifier)
    - Service Manager → uniquement son service ✅
    - Viewer → jamais ❌
    """
    organization = procedure.organization
    role         = get_user_role(user, organization)

    if role is None:
        return False

    if role == Membership.ROLE_ADMIN:
        return True

    if role == Membership.ROLE_DIRECTOR:
        return False

    # Vérifie si service_manager sur ce service
    return _is_service_manager(user, organization, procedure.service)


def can_approve_change_request(user, organization) -> bool:
    """
    Vérifie si un utilisateur peut approuver/rejeter une ChangeRequest.
    Seuls Admin et Director peuvent approuver.
    """
    role = get_user_role(user, organization)
    return role in (Membership.ROLE_ADMIN, Membership.ROLE_DIRECTOR)


def can_archive_procedure(user, procedure) -> bool:
    """
    Vérifie si un utilisateur peut archiver manuellement une procédure.
    Seuls Admin et Director peuvent archiver.
    """
    organization = procedure.organization
    role         = get_user_role(user, organization)
    return role in (Membership.ROLE_ADMIN, Membership.ROLE_DIRECTOR)


def get_accessible_procedures(user, organization):
    """
    Retourne le queryset des procédures accessibles par l'utilisateur.
    Utilisé pour filtrer les listes de procédures.
    """
    role = get_user_role(user, organization)

    if role is None:
        return Procedure.objects.none()

    # Admin et Director voient tout
    if role in (Membership.ROLE_ADMIN, Membership.ROLE_DIRECTOR):
        return Procedure.objects.filter(organization=organization)

    # Les autres ne voient que leurs services
    accessible_services = ServiceMembership.objects.filter(
        user=user, organization=organization
    ).values_list('service', flat=True)

    return Procedure.objects.filter(
        organization=organization,
        service__in=accessible_services
    )


def _has_service_access(user, organization, service) -> bool:
    """Vérifie si l'utilisateur a accès à un service (n'importe quel rôle)."""
    return ServiceMembership.objects.filter(
        user=user, organization=organization, service=service
    ).exists()


def _is_service_manager(user, organization, service) -> bool:
    """Vérifie si l'utilisateur est manager d'un service spécifique."""
    return ServiceMembership.objects.filter(
        user=user,
        organization=organization,
        service=service,
        role=ServiceMembership.ROLE_SERVICE_MANAGER
    ).exists()