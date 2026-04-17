import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from procedures.services.ingestion import ingest_text
from organizations.models import Organization
from procedures.services.analyzer import analyze_procedure as run_analysis


@csrf_exempt
def ingest_procedure(request):
    """
    Vue d'ingestion d'une procédure via texte libre.
    Méthode : POST
    Body JSON :
    {
        "text": "Le RH publie l'offre...",
        "title": "Processus de recrutement",
        "service": "RH",
        "organization_id": 1,
        "apply_masking": true
    }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalide'}, status=400)

    # Validation des champs obligatoires
    required = ['text', 'title', 'organization_id']
    for field in required:
        if not data.get(field):
            return JsonResponse(
                {'error': f'Champ obligatoire manquant : {field}'},
                status=400
            )

    # Récupération de l'organisation
    try:
        organization = Organization.objects.get(id=data['organization_id'])
    except Organization.DoesNotExist:
        return JsonResponse({'error': 'Organisation introuvable'}, status=404)

    # Appel du service d'ingestion
    result = ingest_text(
        text           = data['text'],
        title          = data['title'],
        service        = data.get('service', ''),
        organization   = organization,
        owner          = request.user if request.user.is_authenticated else None,
        apply_masking  = data.get('apply_masking', True),
    )

    status_code = 201 if result['success'] else 400
    return JsonResponse(result, status=status_code)

@csrf_exempt
def analyze(request, procedure_id):
    """
    Lance l'analyse complète d'une procédure.
    Méthode : POST
    URL : /api/procedures/<id>/analyze/
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    result = run_analysis(procedure_id)
    status_code = 200 if result.get('success') else 404
    return JsonResponse(result, status=status_code)