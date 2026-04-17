import csv
import io
import pdfplumber
import docx
from django.contrib.auth.models import User
from procedures.models import Procedure, Step
from procedures.services.masker import mask_text
from procedures.services.parser import parse_procedure_text
from organizations.models import Organization


# ─────────────────────────────────────────────
# Extracteurs de texte
# ─────────────────────────────────────────────

def extract_text_from_pdf(file) -> str:
    """
    Extrait le texte brut d'un fichier PDF page par page.
    `file` peut être un chemin ou un objet fichier Django (InMemoryUploadedFile).
    """
    text_parts = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text.strip())
    return '\n'.join(text_parts)


def extract_text_from_docx(file) -> str:
    """
    Extrait le texte brut d'un fichier Word (.docx) paragraphe par paragraphe.
    Ignore les paragraphes vides.
    """
    document = docx.Document(file)
    paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    return '\n'.join(paragraphs)


def extract_steps_from_csv(file) -> list:
    """
    Lit un fichier CSV structuré et retourne une liste de dictionnaires.
    Le CSV doit suivre le template ProcessIntelligence :

    order,title,action_verb,actor_role,tool_used,estimated_duration,
    is_recurring,trigger_type,has_condition,output_type

    Les données étant déjà structurées, on ne passe PAS par le NLP.
    """
    steps = []

    # Gestion des deux cas : fichier Django ou fichier texte
    if hasattr(file, 'read'):
        content = file.read().decode('utf-8')
    else:
        with open(file, 'r', encoding='utf-8') as f:
            content = f.read()

    reader = csv.DictReader(io.StringIO(content))

    for i, row in enumerate(reader, start=1):
        # Valeurs booléennes
        is_recurring  = str(row.get('is_recurring', 'false')).lower() == 'true'
        has_condition = str(row.get('has_condition', 'false')).lower() == 'true'

        steps.append({
            'order'             : int(row.get('order', i)),
            'title'             : row.get('title', f'Étape {i}').strip(),
            'action_verb'       : row.get('action_verb', '').strip(),
            'actor_role'        : row.get('actor_role', '').strip(),
            'tool_used'         : row.get('tool_used', '').strip(),
            'estimated_duration': int(row.get('estimated_duration', 0) or 0),
            'is_recurring'      : is_recurring,
            'trigger_type'      : row.get('trigger_type', 'manual').strip(),
            'has_condition'     : has_condition,
            'output_type'       : row.get('output_type', 'none').strip(),
        })

    return steps


# ─────────────────────────────────────────────
# Sauvegarde en base
# ─────────────────────────────────────────────

def _create_procedure_and_steps(
    steps_data: list,
    title: str,
    service: str,
    organization: Organization,
    owner,
    source_type: str = 'text',
) -> dict:
    """
    Fonction interne partagée — crée la Procedure et ses Steps en base.
    Utilisée par tous les modes d'ingestion (texte, PDF, DOCX, CSV).
    """
    if not steps_data:
        return {
            'success'   : False,
            'error'     : 'Aucune étape détectée.',
            'steps_count': 0,
        }

    procedure = Procedure.objects.create(
        organization = organization,
        title        = title,
        service      = service,
        owner        = owner,
        status       = Procedure.STATUS_DRAFT,
        version      = '1.0',
    )

    steps_created = []
    for s in steps_data:
        step = Step.objects.create(
            procedure          = procedure,
            title              = s.get('title', ''),
            action_verb        = s.get('action_verb', ''),
            actor_role         = s.get('actor_role', ''),
            tool_used          = s.get('tool_used', ''),
            estimated_duration = s.get('estimated_duration', 0),
            is_recurring       = s.get('is_recurring', False),
            trigger_type       = s.get('trigger_type', Step.TRIGGER_MANUAL),
            has_condition      = s.get('has_condition', False),
            output_type        = s.get('output_type', Step.OUTPUT_NONE),
            automation_score   = s.get('automation_score', 0.0),
            compliance_status  = Step.COMPLIANCE_WARNING,
            step_order         = s.get('order', 0),
        )
        steps_created.append(step)

    return {
        'success'        : True,
        'procedure_id'   : procedure.id,
        'procedure_title': procedure.title,
        'source_type'    : source_type,
        'steps_count'    : len(steps_created),
        'steps'          : [
            {
                'order'           : s.step_order,
                'title'           : s.title,
                'action_verb'     : s.action_verb,
                'actor_role'      : s.actor_role,
                'automation_score': s.automation_score,
            }
            for s in steps_created
        ]
    }


# ─────────────────────────────────────────────
# Fonctions d'ingestion publiques
# ─────────────────────────────────────────────

def ingest_text(
    text: str,
    title: str,
    service: str,
    organization: Organization,
    owner,
    apply_masking: bool = True,
) -> dict:
    """Ingestion depuis texte libre."""
    masked_text = text
    mapping = {}

    if apply_masking:
        masked_text, mapping = mask_text(text)

    parsed = parse_procedure_text(masked_text)
    steps_data = [
        {
            'order'           : p.order,
            'title'           : p.title,
            'action_verb'     : p.action_verb,
            'actor_role'      : p.actor_role,
            'tool_used'       : p.tool_used,
            'has_condition'   : p.has_condition,
            'is_recurring'    : p.is_recurring,
            'output_type'     : p.output_type,
            'automation_score': p.automation_score,
        }
        for p in parsed
    ]

    result = _create_procedure_and_steps(
        steps_data, title, service, organization, owner, source_type='text'
    )
    result['masking_applied'] = apply_masking
    result['mapping'] = mapping
    return result


def ingest_pdf(
    file,
    title: str,
    service: str,
    organization: Organization,
    owner,
    apply_masking: bool = True,
) -> dict:
    """Ingestion depuis un fichier PDF."""
    try:
        text = extract_text_from_pdf(file)
    except Exception as e:
        return {'success': False, 'error': f'Erreur lecture PDF : {str(e)}'}

    if not text.strip():
        return {'success': False, 'error': 'Le PDF ne contient pas de texte extractible.'}

    masked_text = text
    mapping = {}
    if apply_masking:
        masked_text, mapping = mask_text(text)

    parsed = parse_procedure_text(masked_text)
    steps_data = [
        {
            'order'           : p.order,
            'title'           : p.title,
            'action_verb'     : p.action_verb,
            'actor_role'      : p.actor_role,
            'tool_used'       : p.tool_used,
            'has_condition'   : p.has_condition,
            'is_recurring'    : p.is_recurring,
            'output_type'     : p.output_type,
            'automation_score': p.automation_score,
        }
        for p in parsed
    ]

    result = _create_procedure_and_steps(
        steps_data, title, service, organization, owner, source_type='pdf'
    )
    result['masking_applied'] = apply_masking
    result['mapping'] = mapping
    return result


def ingest_docx(
    file,
    title: str,
    service: str,
    organization: Organization,
    owner,
    apply_masking: bool = True,
) -> dict:
    """Ingestion depuis un fichier Word (.docx)."""
    try:
        text = extract_text_from_docx(file)
    except Exception as e:
        return {'success': False, 'error': f'Erreur lecture DOCX : {str(e)}'}

    if not text.strip():
        return {'success': False, 'error': 'Le fichier Word ne contient pas de texte.'}

    masked_text = text
    mapping = {}
    if apply_masking:
        masked_text, mapping = mask_text(text)

    parsed = parse_procedure_text(masked_text)
    steps_data = [
        {
            'order'           : p.order,
            'title'           : p.title,
            'action_verb'     : p.action_verb,
            'actor_role'      : p.actor_role,
            'tool_used'       : p.tool_used,
            'has_condition'   : p.has_condition,
            'is_recurring'    : p.is_recurring,
            'output_type'     : p.output_type,
            'automation_score': p.automation_score,
        }
        for p in parsed
    ]

    result = _create_procedure_and_steps(
        steps_data, title, service, organization, owner, source_type='docx'
    )
    result['masking_applied'] = apply_masking
    result['mapping'] = mapping
    return result


def ingest_csv(
    file,
    title: str,
    service: str,
    organization: Organization,
    owner,
) -> dict:
    """
    Ingestion depuis le template CSV structuré.
    Pas de NLP — les données sont déjà structurées.
    Pas de masquage — le CSV ne contient pas de données sensibles par convention.
    """
    try:
        steps_data = extract_steps_from_csv(file)
    except Exception as e:
        return {'success': False, 'error': f'Erreur lecture CSV : {str(e)}'}

    return _create_procedure_and_steps(
        steps_data, title, service, organization, owner, source_type='csv'
    )