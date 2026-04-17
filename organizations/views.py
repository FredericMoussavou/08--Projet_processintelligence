from django.http import JsonResponse
from organizations.models import Organization
from procedures.services.theme import get_theme


def get_organization_theme(request, slug):
    """
    Retourne le thème complet d'une organisation.
    GET /api/organizations/<slug>/theme/
    """
    try:
        organization = Organization.objects.get(slug=slug)
    except Organization.DoesNotExist:
        return JsonResponse({'error': 'Organisation introuvable'}, status=404)

    theme = get_theme(organization)
    return JsonResponse(theme)