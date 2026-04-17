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
    Vue d'ingestion unifiée.
    Détecte automatiquement le type de source :
    - JSON body avec champ 'text' → texte libre
    - Fichier uploadé .pdf       → PDF
    - Fichier uploadé .docx      → Word
    - Fichier uploadé .csv       → CSV structuré
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    # Récupération des métadonnées
    # Selon le type de requête, elles sont dans body JSON ou dans POST form
    if request.content_type and 'application/json' in request.content_type:
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON invalide'}, status=400)
        uploaded_file = None
    else:
        data = request.POST
        uploaded_file = request.FILES.get('file')

    # Validation des champs communs
    title   = data.get('title', '')
    service = data.get('service', '')
    org_id  = data.get('organization_id')

    if not title:
        return JsonResponse({'error': 'Champ obligatoire manquant : title'}, status=400)
    if not org_id:
        return JsonResponse({'error': 'Champ obligatoire manquant : organization_id'}, status=400)

    try:
        organization = Organization.objects.get(id=org_id)
    except Organization.DoesNotExist:
        return JsonResponse({'error': 'Organisation introuvable'}, status=404)

    owner         = request.user if request.user.is_authenticated else None
    apply_masking = str(data.get('apply_masking', 'true')).lower() == 'true'

    # Routage selon le type de source
    if uploaded_file:
        filename = uploaded_file.name.lower()

        if filename.endswith('.pdf'):
            from procedures.services.ingestion import ingest_pdf
            result = ingest_pdf(uploaded_file, title, service, organization, owner, apply_masking)

        elif filename.endswith('.docx'):
            from procedures.services.ingestion import ingest_docx
            result = ingest_docx(uploaded_file, title, service, organization, owner, apply_masking)

        elif filename.endswith('.csv'):
            from procedures.services.ingestion import ingest_csv
            result = ingest_csv(uploaded_file, title, service, organization, owner)

        else:
            return JsonResponse({'error': 'Format de fichier non supporté. Formats acceptés : PDF, DOCX, CSV'}, status=400)

    else:
        # Texte libre
        text = data.get('text', '')
        if not text:
            return JsonResponse({'error': 'Champ obligatoire manquant : text ou file'}, status=400)
        result = ingest_text(text, title, service, organization, owner, apply_masking)

    status_code = 201 if result.get('success') else 400
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