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
from procedures.services.compliance import run_compliance_check, get_available_rules
from procedures.services.change_request import (
    submit_change_request, approve_change_request,
    reject_change_request, get_change_requests,
    get_change_request_status
)
from django.conf import settings
from functools import wraps


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
        if uploaded_file.size > 10 * 1024 * 1024:
            return JsonResponse(
                {'error': 'Fichier trop volumineux — maximum 10 Mo'},
                status=400
            )
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
        if len(text) > 50000:
            return JsonResponse(
                {'error': 'Texte trop long — maximum 50 000 caractères'},
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

def check_compliance(request, procedure_id):
    """
    Lance la vérification de conformité d'une procédure.
    URL : /api/procedures/<id>/compliance/
    """
    result = run_compliance_check(procedure_id)
    status_code = 200 if result.get('success') else 404
    return JsonResponse(result, status=status_code)


def list_rules(request):
    """
    Retourne le référentiel des règles disponibles.
    URL : /api/procedures/rules/?sector=finance
    """
    sector = request.GET.get('sector')
    rules  = get_available_rules(sector)
    return JsonResponse(rules)

def change_request_status(request, cr_id):
    """
    Retourne le statut détaillé d'une demande avec le workflow complet.
    GET /api/procedures/change-requests/<id>/
    """
    result = get_change_request_status(cr_id)
    status_code = 200 if result.get('success') else 404
    return JsonResponse(result, status=status_code)

@csrf_exempt
def change_requests(request):
    """
    GET  : Liste les demandes de changement
    POST : Soumet une nouvelle demande
    URL  : /api/procedures/change-requests/
    """
    if request.method == 'GET':
        procedure_id = request.GET.get('procedure_id')
        status       = request.GET.get('status')
        result = get_change_requests(procedure_id, status)
        return JsonResponse(result)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON invalide'}, status=400)

        procedure_id = data.get('procedure_id')
        description  = data.get('description', '')
        reviewer_id  = data.get('reviewer_id')
        change_type  = data.get('change_type', 'patch')

        if not procedure_id or not description:
            return JsonResponse(
                {'error': 'procedure_id et description sont obligatoires'},
                status=400
            )

        user   = request.user if request.user.is_authenticated else None
        result = submit_change_request(procedure_id, user, description, reviewer_id, change_type)
        status_code = 201 if result.get('success') else 400
        return JsonResponse(result, status=status_code)

    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@csrf_exempt
def approve_cr(request, cr_id):
    """
    Approuve une demande de changement.
    POST /api/procedures/change-requests/<id>/approve/
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    try:
        data    = json.loads(request.body) if request.body else {}
        comment = data.get('comment', '')
    except json.JSONDecodeError:
        comment = ''

    user   = request.user if request.user.is_authenticated else None
    result = approve_change_request(cr_id, user, comment)
    status_code = 200 if result.get('success') else 400
    return JsonResponse(result, status=status_code)


@csrf_exempt
def reject_cr(request, cr_id):
    """
    Rejette une demande de changement.
    POST /api/procedures/change-requests/<id>/reject/
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    try:
        data   = json.loads(request.body)
        reason = data.get('reason', 'Aucun motif fourni')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalide'}, status=400)

    user   = request.user if request.user.is_authenticated else None
    result = reject_change_request(cr_id, user, reason)
    status_code = 200 if result.get('success') else 400
    return JsonResponse(result, status=status_code)

from procedures.services.archiver import (
    archive_procedure_version, get_procedure_history, get_procedures_by_status
)

def list_procedures(request, organization_id):
    """
    Liste les procédures accessibles par l'utilisateur.
    GET /api/procedures/list/<org_id>/?status=active&service=RH
    """
    status  = request.GET.get('status')
    service = request.GET.get('service')
    user    = request.user if request.user.is_authenticated else None
    
    result = get_procedures_by_status(organization_id, user, status, service)
    return JsonResponse(result)


@csrf_exempt
def archive_procedure(request, procedure_id):
    """
    Archive manuellement une procédure.
    POST /api/procedures/<id>/archive/
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)

    try:
        data    = json.loads(request.body) if request.body else {}
        summary = data.get('change_summary', '')
    except json.JSONDecodeError:
        summary = ''

    user   = request.user if request.user.is_authenticated else None
    result = archive_procedure_version(procedure_id, user, 'manual_archive', summary)
    status_code = 200 if result.get('success') else 400
    return JsonResponse(result, status=status_code)


def procedure_history(request, procedure_id):
    """
    Retourne l'historique des versions d'une procédure.
    GET /api/procedures/<id>/history/
    """
    result = get_procedure_history(procedure_id)
    status_code = 200 if result.get('success') else 404
    return JsonResponse(result, status=status_code)