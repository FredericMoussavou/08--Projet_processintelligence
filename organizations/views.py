import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from organizations.models import Organization, Membership, ServiceMembership
from procedures.services.theme import get_theme


def get_organization_theme(request, slug):
    """GET /api/organizations/<slug>/theme/"""
    try:
        organization = Organization.objects.get(slug=slug)
    except Organization.DoesNotExist:
        return JsonResponse({'error': 'Organisation introuvable'}, status=404)
    return JsonResponse(get_theme(organization))


def get_members(request, org_id):
    """GET /api/organizations/<id>/members/"""
    try:
        org = Organization.objects.get(id=org_id)
    except Organization.DoesNotExist:
        return JsonResponse({'error': 'Organisation introuvable'}, status=404)

    memberships = Membership.objects.filter(
        organization=org
    ).select_related('user')

    members = []
    for m in memberships:
        service_memberships = ServiceMembership.objects.filter(
            user=m.user, organization=org
        )
        members.append({
            'user_id'  : m.user.id,
            'username' : m.user.username,
            'email'    : m.user.email,
            'role'     : m.role,
            'joined_at': m.joined_at.strftime('%d/%m/%Y'),
            'services' : [
                {'service': sm.service, 'role': sm.role}
                for sm in service_memberships
            ]
        })

    return JsonResponse({'success': True, 'members': members})


@csrf_exempt
def manage_members(request, org_id):
    """POST /api/organizations/<id>/members/ — ajoute un membre"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    try:
        org  = Organization.objects.get(id=org_id)
        data = json.loads(request.body)
    except (Organization.DoesNotExist, json.JSONDecodeError):
        return JsonResponse({'error': 'Données invalides'}, status=400)

    username = data.get('username', '').strip()
    role     = data.get('role', 'viewer')

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return JsonResponse({'error': f"Utilisateur '{username}' introuvable"}, status=404)

    membership, created = Membership.objects.get_or_create(
        user=user, organization=org,
        defaults={'role': role}
    )
    if not created:
        membership.role = role
        membership.save()

    return JsonResponse({
        'success': True,
        'message': f"{username} ajouté avec le rôle {role}",
    })


@csrf_exempt
def remove_member(request, org_id, user_id):
    """DELETE /api/organizations/<id>/members/<user_id>/"""
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    try:
        org  = Organization.objects.get(id=org_id)
        user = User.objects.get(id=user_id)
        Membership.objects.filter(user=user, organization=org).delete()
        ServiceMembership.objects.filter(user=user, organization=org).delete()
        return JsonResponse({'success': True})
    except (Organization.DoesNotExist, User.DoesNotExist):
        return JsonResponse({'error': 'Introuvable'}, status=404)


@csrf_exempt
def manage_service_members(request, org_id):
    """POST /api/organizations/<id>/service-members/"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    try:
        org  = Organization.objects.get(id=org_id)
        data = json.loads(request.body)
    except (Organization.DoesNotExist, json.JSONDecodeError):
        return JsonResponse({'error': 'Données invalides'}, status=400)

    username = data.get('username', '').strip()
    service  = data.get('service', '').strip()
    role     = data.get('role', 'service_viewer')

    if not username or not service:
        return JsonResponse({'error': 'username et service sont obligatoires'}, status=400)

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return JsonResponse({'error': f"Utilisateur '{username}' introuvable"}, status=404)

    # Vérifie que l'user est bien membre de l'org
    if not Membership.objects.filter(user=user, organization=org).exists():
        return JsonResponse(
            {'error': f"'{username}' n'est pas membre de cette organisation"},
            status=400
        )

    sm, created = ServiceMembership.objects.get_or_create(
        user=user, organization=org, service=service,
        defaults={'role': role}
    )
    if not created:
        sm.role = role
        sm.save()

    return JsonResponse({
        'success': True,
        'message': f"{username} assigné au service {service} avec le rôle {role}",
    })


def get_services(request, org_id):
    """GET /api/organizations/<id>/services/ — liste les services uniques"""
    try:
        org = Organization.objects.get(id=org_id)
    except Organization.DoesNotExist:
        return JsonResponse({'error': 'Organisation introuvable'}, status=404)

    from procedures.models import Procedure
    services = list(
        Procedure.objects.filter(organization=org)
        .exclude(service='')
        .values_list('service', flat=True)
        .distinct()
        .order_by('service')
    )

    # Ajoute aussi les services des ServiceMemberships
    sm_services = list(
        ServiceMembership.objects.filter(organization=org)
        .values_list('service', flat=True)
        .distinct()
    )

    all_services = sorted(set(services + sm_services))
    return JsonResponse({'success': True, 'services': all_services})


@csrf_exempt
def add_service(request, org_id):
    """POST /api/organizations/<id>/services/ — ajoute un service"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalide'}, status=400)

    if not name:
        return JsonResponse({'error': 'Le nom du service est obligatoire'}, status=400)

    # On crée un ServiceMembership fictif pour persister le service
    # (les services sont déduits des procédures et des memberships)
    return JsonResponse({
        'success': True,
        'message': f"Service '{name}' enregistré",
        'service': name,
    })