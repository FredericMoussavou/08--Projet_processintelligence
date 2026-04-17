import json
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from procedures.services.ingestion import ingest_text
from organizations.models import Organization
from procedures.services.analyzer import analyze_procedure as run_analysis
from procedures.services.exporter import generate_audit_pdf, generate_csv_template
from procedures.services.bpmn_exporter import generate_bpmn
from procedures.services.manual_exporter import generate_manual_pdf


@csrf_exempt
def ingest_procedure(request):
    """
    Vue d'ingestion unifiée.
    Détecte automatiquement le type de source :
    - JSON body avec champ 'text' → texte libre
    - Fichier uploadé .pdf       → PDF
    - Fichier uploadé .docx      → Word
    - Fichier uploadé .csv       → CSV structuré
    - Fichier uploadé .txt       → Texte
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    # Récupération des métadonnées
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

        elif filename.endswith('.txt'):
            from procedures.services.ingestion import ingest_txt
            result = ingest_txt(uploaded_file, title, service, organization, owner, apply_masking)

        else:
            return JsonResponse(
                {'error': 'Format non supporté. Formats acceptés : PDF, DOCX, CSV, TXT'},
                status=400
            )

    else:
        # Texte libre
        text = data.get('text', '')
        if not text:
            return JsonResponse(
                {'error': 'Champ obligatoire manquant : text ou file'},
                status=400
            )
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

def export_audit_pdf(request, procedure_id):
    """
    Génère et retourne le rapport d'audit en PDF.
    URL : /api/procedures/<id>/export/pdf/
    """
    try:
        pdf_bytes = generate_audit_pdf(procedure_id)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=404)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="audit_procedure_{procedure_id}.pdf"'
    return response


def download_csv_template(request):
    """
    Retourne le template CSV officiel ProcessIntelligence.
    URL : /api/procedures/template/csv/
    """
    csv_bytes = generate_csv_template()
    response = HttpResponse(csv_bytes, content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="template_processintelligence.csv"'
    return response

def export_bpmn(request, procedure_id):
    """
    Génère et retourne le fichier BPMN 2.0.
    URL : /api/procedures/<id>/export/bpmn/
    """
    try:
        bpmn_bytes = generate_bpmn(procedure_id)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=404)

    response = HttpResponse(bpmn_bytes, content_type='application/xml')
    response['Content-Disposition'] = f'attachment; filename="procedure_{procedure_id}.bpmn"'
    return response

def export_manual(request, organization_id):
    """
    Génère le Manuel de Procédures complet d'une organisation.
    URL : /api/procedures/manual/<organization_id>/
    Paramètres optionnels :
    - ?service=RH        → filtre par service
    - ?role=Comptable    → filtre par poste
    """
    service_filter = request.GET.get('service')
    role_filter    = request.GET.get('role')

    try:
        pdf_bytes = generate_manual_pdf(
            organization_id, service_filter, role_filter
        )
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=404)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="manuel_procedures_{organization_id}.pdf"'
    )
    return response