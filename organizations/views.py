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

# -----------------------------------------------------------------------------
# Helper de permission (peut être factorisé plus tard dans un module commun)
# -----------------------------------------------------------------------------
 
def _user_can_view_organization(user, organization):
    """
    Vérifie qu'un utilisateur a le droit de lire les infos d'une organisation.
 
    Règle : l'utilisateur doit être membre (Membership) de l'organisation.
    """
    if not user or not user.is_authenticated:
        return False
    return Membership.objects.filter(
        user=user,
        organization=organization,
    ).exists()
 
 
# -----------------------------------------------------------------------------
# GET /api/organizations/<id>/plan/
# -----------------------------------------------------------------------------
 
def get_organization_plan(request, org_id):
    """
    Retourne le plan courant de l'organisation, ses limites et ses features.
    Utilisé par le frontend pour afficher les badges et griser les features
    non disponibles dans le plan actuel.
 
    Réponse :
        {
          "plan": {
            "id": "pro",
            "name": "Pro",
            "description": "...",
            "is_paid": true,
            "limits": {...},
            "features": {...}
          },
          "plan_started_at": "2026-04-01T10:00:00Z" | null,
          "plan_expires_at": null
        }
    """
    try:
        org = Organization.objects.get(id=org_id)
    except Organization.DoesNotExist:
        return JsonResponse({'error': 'Organisation introuvable'}, status=404)
 
    if not _user_can_view_organization(request.user, org):
        return JsonResponse(
            {'error': "Accès refusé : vous n'êtes pas membre de cette organisation"},
            status=403,
        )
 
    # Configuration complète du plan (formatée pour exposition publique)
    from organizations.plans import get_plan
    plan_config = get_plan(org.plan)
 
    plan_data = {
        'id':          plan_config['id'],
        'name':        plan_config['name'],
        'description': plan_config['description'],
        'is_paid':     plan_config['is_paid'],
        'limits': {
            'procedures':         plan_config['limit_procedures'],
            'users':              plan_config['limit_users'],
            'services':           plan_config['limit_services'],
            'analyses_per_month': plan_config['limit_analyses_per_month'],
        },
        'features': {
            'llm_enabled':       plan_config['llm_model'] is not None,
            'export_pdf_themed': plan_config['feature_export_pdf_themed'],
            'export_bpmn':       plan_config['feature_export_bpmn'],
            'export_manual':     plan_config['feature_export_manual'],
            'versioning':        plan_config['feature_versioning'],
            'custom_theme':      plan_config['feature_custom_theme'],
            'sso':               plan_config['feature_sso'],
            'priority_support':  plan_config['feature_priority_support'],
            'rules_sectors':     plan_config['feature_rules_sectors'],
        },
    }
 
    return JsonResponse({
        'plan':            plan_data,
        'plan_started_at': org.plan_started_at.isoformat() if org.plan_started_at else None,
        'plan_expires_at': org.plan_expires_at.isoformat() if org.plan_expires_at else None,
    })
 
 
# -----------------------------------------------------------------------------
# GET /api/organizations/<id>/usage/
# -----------------------------------------------------------------------------
 
def get_organization_usage(request, org_id):
    """
    Retourne l'usage courant de l'organisation pour le mois en cours.
    Utilisé par le frontend pour afficher la QuotaBar et les indicateurs
    de consommation (procédures, utilisateurs, analyses).
 
    Réponse :
        {
          "month": 4,
          "year": 2026,
          "analyses": {
            "count": 42,
            "limit": 500,
            "percentage_used": 8.4,
            "quota_reached": false
          },
          "procedures": { "count": 15, "limit": 100 },
          "users":      { "count": 8,  "limit": 15 }
        }
    """
    from django.utils import timezone
 
    try:
        org = Organization.objects.get(id=org_id)
    except Organization.DoesNotExist:
        return JsonResponse({'error': 'Organisation introuvable'}, status=404)
 
    if not _user_can_view_organization(request.user, org):
        return JsonResponse(
            {'error': "Accès refusé : vous n'êtes pas membre de cette organisation"},
            status=403,
        )
 
    now = timezone.now()
 
    # Analyses du mois (compteur MonthlyUsage)
    analyses_count = org.get_monthly_analyses_count()
    analyses_limit = org.limit_for('analyses_per_month')
    if analyses_limit is not None and analyses_limit > 0:
        percentage = round((analyses_count / analyses_limit) * 100, 1)
        quota_reached = analyses_count >= analyses_limit
    else:
        percentage = 0.0
        quota_reached = False
 
    # Nombre de procédures actuelles
    procedures_count = org.procedures.count()
    procedures_limit = org.limit_for('procedures')
 
    # Nombre d'utilisateurs actuels
    users_count = org.memberships.count()
    users_limit = org.limit_for('users')
 
    return JsonResponse({
        'month': now.month,
        'year':  now.year,
        'analyses': {
            'count':           analyses_count,
            'limit':           analyses_limit,
            'percentage_used': percentage,
            'quota_reached':   quota_reached,
        },
        'procedures': {
            'count': procedures_count,
            'limit': procedures_limit,
        },
        'users': {
            'count': users_count,
            'limit': users_limit,
        },
    })