import io
import matplotlib
matplotlib.use('Agg')
import textwrap
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether,Image
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from procedures.models import Procedure, Step
from organizations.models import Organization
from procedures.services.theme import get_theme, ThemeColors

def _generate_workflow_image(procedure, tc) -> Image:
    """
    Génère une image PNG du workflow d'une procédure
    et la retourne comme élément ReportLab Image.
    """
    steps = list(procedure.steps.all().order_by('step_order'))
    if not steps:
        return None

    # Construction du graphe
    G = nx.DiGraph()
    labels = {}

    for step in steps:
        node_id = step.id
        # Titre court pour l'affichage
        # Verbe d'action en priorité, sinon titre tronqué
        title_raw = step.action_verb if step.action_verb else step.title
        # Coupe sur 15 caractères max par ligne
        title = '\n'.join(textwrap.wrap(title_raw, width=15))
        actor = step.actor_role[:18] if step.actor_role else ''
        labels[node_id] = f"{title}\n({actor})" if actor else title
        G.add_node(node_id)

    for i in range(len(steps) - 1):
        G.add_edge(steps[i].id, steps[i + 1].id)

    # Dessin
    fig, ax = plt.subplots(figsize=(12, 3))
    ax.set_facecolor('#FFFFFF')
    fig.patch.set_facecolor('#FFFFFF')

    pos = {step.id: (i * 1.4, 0) for i, step in enumerate(steps)}

    # Couleurs des nœuds selon le score d'automatisation
    node_colors = []
    for step in steps:
        if step.automation_score >= 0.7:
            node_colors.append('#D4EDDA')
        elif step.automation_score >= 0.4:
            node_colors.append('#FFF3CD')
        else:
            node_colors.append('#F8D7DA')

    nx.draw_networkx_nodes(
        G, pos, ax=ax,
        node_color=node_colors,
        node_size=6000,
        node_shape='s',
    )
    nx.draw_networkx_labels(
        G, pos, labels, ax=ax,
        font_size=7,
        font_color='#1B3A5C',
        font_family='sans-serif',
    )
    nx.draw_networkx_edges(
        G, pos, ax=ax,
        edge_color='#2E6DA4',
        arrows=True,
        arrowsize=12,
        width=1.5,
        connectionstyle='arc3,rad=0.0',
        min_source_margin=55,
        min_target_margin=55,
    )

    # Légende
    legend_elements = [
        mpatches.Patch(facecolor='#D4EDDA', label='Score élevé (≥70%)'),
        mpatches.Patch(facecolor='#FFF3CD', label='Score moyen (40-70%)'),
        mpatches.Patch(facecolor='#F8D7DA', label='Score faible (<40%)'),
    ]
    ax.legend(handles=legend_elements, loc='lower right',
              fontsize=6, framealpha=0.8)

    ax.axis('off')
    plt.tight_layout(pad=0.5)

    # Export en bytes PNG
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='PNG', dpi=150,
                bbox_inches='tight', facecolor='white')
    plt.close(fig)
    img_buffer.seek(0)

    return Image(img_buffer, width=16*cm, height=5*cm)

def p_cell(text, tc, fs=9, bold=False, color=None):
    """Paragraph pour cellule de tableau."""
    return Paragraph(str(text), ParagraphStyle(
        'c', fontSize=fs,
        fontName='Helvetica-Bold' if bold else 'Helvetica',
        textColor=color or tc.text,
        leading=fs + 3
    ))


def generate_manual_pdf(organization_id: int, service_filter: str = None,
                        role_filter: str = None) -> bytes:
    """
    Génère le Manuel de Procédures complet d'une organisation.

    Paramètres :
    - organization_id : ID de l'organisation
    - service_filter  : filtrer par service (ex: 'RH') — None = tous
    - role_filter     : filtrer par rôle/poste (ex: 'Comptable') — None = tous

    Structure du manuel :
    1. Page de garde
    2. Sommaire par service
    3. Pour chaque service → pour chaque procédure :
       - Fiche procédure (infos + scores)
       - Tableau des étapes
       - Dernières recommandations d'audit
    """
    try:
        organization = Organization.objects.get(id=organization_id)
    except Organization.DoesNotExist:
        raise ValueError(f"Organisation introuvable : {organization_id}")

    # Chargement du thème
    theme  = get_theme(organization)
    tc     = ThemeColors(theme)
    sp     = theme.get('spacing', {})
    pad    = sp.get('cell_padding', 8)
    fnt    = theme.get('fonts', {})
    fs     = theme.get('font_sizes', {})

    # Récupération des procédures
    procedures = Procedure.objects.filter(
        organization=organization,
        status=Procedure.STATUS_ACTIVE
    ).order_by('service', 'title')

    # Fallback — si aucune procédure active, on prend aussi les brouillons
    if not procedures.exists():
        procedures = Procedure.objects.filter(
            organization=organization
        ).order_by('service', 'title')

    if service_filter:
        procedures = procedures.filter(service__iexact=service_filter)

    if role_filter:
        procedures = procedures.filter(
            steps__actor_role__icontains=role_filter
        ).distinct()

    if not procedures.exists():
        raise ValueError("Aucune procédure trouvée pour cette organisation.")

    # Groupement par service
    services = {}
    for proc in procedures:
        svc = proc.service or 'Général'
        if svc not in services:
            services[svc] = []
        services[svc].append(proc)

    # Construction du PDF
    buffer = io.BytesIO()
    W = 17 * cm

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    styles = _get_styles(tc, fs, fnt)
    story  = []

    # ── PAGE DE GARDE ──────────────────────────────
    story.append(Spacer(1, 2*cm))

    # Logo / Nom organisation
    story.append(Paragraph(
        organization.name.upper(),
        styles['OrgName']
    ))
    story.append(Spacer(1, 0.6*cm))
    story.append(Paragraph("Manuel de Procédures", styles['ManualTitle']))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        f"Généré par ProcessIntelligence — {datetime.now().strftime('%d/%m/%Y')}",
        styles['ManualSubtitle']
    ))
    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width=W, color=tc.secondary, thickness=3))
    story.append(Spacer(1, 1*cm))

    # Infos générales
    cover_data = [
        ['Secteur',          organization.get_sector_display()],
        ['Nombre de services', str(len(services))],
        ['Nombre de procédures', str(procedures.count())],
        ['Date de génération', datetime.now().strftime('%d/%m/%Y à %H:%M')],
    ]
    if service_filter:
        cover_data.append(['Filtre service', service_filter])
    if role_filter:
        cover_data.append(['Filtre poste', role_filter])

    cover_table = Table(cover_data, colWidths=[6*cm, 11*cm])
    cover_table.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (0, -1), tc.light),
        ('TEXTCOLOR',     (0, 0), (0, -1), tc.primary),
        ('FONTNAME',      (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME',      (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE',      (0, 0), (-1, -1), 10),
        ('ROWBACKGROUNDS',(1, 0), (1, -1), [tc.white, tc.background]),
        ('GRID',          (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('PADDING',       (0, 0), (-1, -1), pad),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(cover_table)
    story.append(PageBreak())

    # ── SOMMAIRE ────────────────────────────────────
    story.append(Paragraph("Sommaire", styles['SectionTitle']))
    story.append(HRFlowable(width=W, color=tc.light, thickness=1))
    story.append(Spacer(1, 0.5*cm))

    for svc, procs in services.items():
        story.append(Paragraph(
            f"▸  {svc}  ({len(procs)} procédure{'s' if len(procs) > 1 else ''})",
            styles['TocService']
        ))
        for proc in procs:
            story.append(Paragraph(
                f"      —  {proc.title}  (v{proc.version})",
                styles['TocProcedure']
            ))
    story.append(PageBreak())

    # ── CONTENU PAR SERVICE ──────────────────────────
    for svc, procs in services.items():

        # Titre du service
        story.append(Paragraph(svc.upper(), styles['SectionTitle']))
        story.append(HRFlowable(width=W, color=tc.secondary, thickness=2))
        story.append(Spacer(1, 0.5*cm))

        for proc in procs:
            steps = proc.steps.all().order_by('step_order')
            latest_report = proc.audit_reports.order_by('-generated_at').first()

            # ── Fiche procédure ──
            proc_block = []

            proc_block.append(Paragraph(proc.title, styles['ProcTitle']))
            proc_block.append(Spacer(1, 0.2*cm))

            # Métadonnées
            meta_data = [
                ['Version', proc.version,
                 'Statut', proc.get_status_display()],
                ['Service', proc.service or '—',
                 'Responsable', proc.owner.get_full_name() if proc.owner else '—'],
            ]
            if latest_report:
                meta_data.append([
                    'Score optim.',
                    f"{int(latest_report.score_optim * 100)}%",
                    'Score auto.',
                    f"{int(latest_report.score_auto * 100)}%",
                ])

            meta_table = Table(meta_data, colWidths=[3*cm, 5.5*cm, 3*cm, 5.5*cm])
            meta_table.setStyle(TableStyle([
                ('BACKGROUND',    (0, 0), (0, -1), tc.light),
                ('BACKGROUND',    (2, 0), (2, -1), tc.light),
                ('TEXTCOLOR',     (0, 0), (0, -1), tc.primary),
                ('TEXTCOLOR',     (2, 0), (2, -1), tc.primary),
                ('FONTNAME',      (0, 0), (-1, -1), 'Helvetica'),
                ('FONTNAME',      (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME',      (2, 0), (2, -1), 'Helvetica-Bold'),
                ('FONTSIZE',      (0, 0), (-1, -1), 9),
                ('GRID',          (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
                ('PADDING',       (0, 0), (-1, -1), 6),
                ('ROWBACKGROUNDS',(1, 0), (1, -1), [tc.white, tc.background]),
                ('ROWBACKGROUNDS',(3, 0), (3, -1), [tc.white, tc.background]),
            ]))
            proc_block.append(meta_table)
            proc_block.append(Spacer(1, 0.4*cm))

            # Description
            if proc.description:
                proc_block.append(Paragraph(proc.description, styles['Body']))
                proc_block.append(Spacer(1, 0.3*cm))

            # Tableau des étapes
            proc_block.append(Paragraph("Étapes", styles['SubTitle']))
            proc_block.append(Spacer(1, 0.2*cm))

            if steps.exists():
                steps_data = [[
                    p_cell('#', tc, bold=True, color=tc.white),
                    p_cell('Titre', tc, bold=True, color=tc.white),
                    p_cell('Acteur', tc, bold=True, color=tc.white),
                    p_cell('Outil', tc, bold=True, color=tc.white),
                    p_cell('Output', tc, bold=True, color=tc.white),
                    p_cell('Score', tc, bold=True, color=tc.white),
                ]]

                for step in steps:
                    # Couleur du score
                    score = step.automation_score
                    score_color = tc.success if score >= 0.7 else (
                        tc.warning if score >= 0.4 else tc.danger
                    )
                    steps_data.append([
                        p_cell(step.step_order, tc),
                        p_cell(step.title, tc),
                        p_cell(step.actor_role or '—', tc),
                        p_cell(step.tool_used or '—', tc),
                        p_cell(step.get_output_type_display(), tc),
                        p_cell(f"{int(score * 100)}%", tc,
                               bold=True, color=score_color),
                    ])

                steps_table = Table(
                    steps_data,
                    colWidths=[0.8*cm, 5.5*cm, 3*cm, 2.5*cm, 2.5*cm, 1.7*cm]
                )
                steps_table.setStyle(TableStyle([
                    ('BACKGROUND',    (0, 0), (-1, 0), tc.primary),
                    ('ROWBACKGROUNDS',(0, 1), (-1, -1), [tc.white, tc.background]),
                    ('GRID',          (0, 0), (-1, -1), 0.5,
                     colors.HexColor('#CCCCCC')),
                    ('PADDING',       (0, 0), (-1, -1), 6),
                    ('ALIGN',         (0, 0), (0, -1), 'CENTER'),
                    ('ALIGN',         (5, 0), (5, -1), 'CENTER'),
                    ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
                ]))
                proc_block.append(steps_table)
            else:
                proc_block.append(Paragraph(
                    "Aucune étape enregistrée.", styles['Body']
                ))

            # Recommandations du dernier audit
            if latest_report and latest_report.recommendations:
                proc_block.append(Spacer(1, 0.4*cm))
                proc_block.append(Paragraph(
                    "Recommandations d'audit", styles['SubTitle']
                ))
                proc_block.append(Spacer(1, 0.2*cm))
                priority_colors = {
                    'high': tc.danger, 'medium': tc.warning, 'low': tc.success
                }
                priority_labels = {
                    'high': '▲ HAUTE', 'medium': '◆ MOYENNE', 'low': '▼ FAIBLE'
                }
                for rec in latest_report.recommendations[:3]:
                    priority = rec.get('priority', 'low')
                    rec_data = [[
                        p_cell(priority_labels.get(priority, ''), tc,
                               bold=True,
                               color=priority_colors.get(priority, tc.success)),
                        p_cell(rec.get('action', ''), tc),
                    ]]
                    rec_table = Table(rec_data, colWidths=[3*cm, 14*cm])
                    rec_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, -1), tc.background),
                        ('GRID', (0, 0), (-1, -1), 0.5,
                         colors.HexColor('#DDDDDD')),
                        ('PADDING', (0, 0), (-1, -1), 6),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ]))
                    proc_block.append(rec_table)
                    proc_block.append(Spacer(1, 0.15*cm))

            # Schéma du workflow
            proc_block.append(Spacer(1, 0.4*cm))
            proc_block.append(Paragraph("Schéma du workflow", styles['SubTitle']))
            proc_block.append(Spacer(1, 0.2*cm))
            workflow_img = _generate_workflow_image(proc, tc)
            if workflow_img:
                proc_block.append(workflow_img)
            proc_block.append(Spacer(1, 0.4*cm))
            proc_block.append(Spacer(1, 0.8*cm))
            proc_block.append(HRFlowable(
                width=W, color=tc.light, thickness=0.5
            ))
            proc_block.append(Spacer(1, 0.5*cm))

            story.append(KeepTogether(proc_block))

        story.append(PageBreak())

    # ── PIED DE PAGE ────────────────────────────────
    story.append(HRFlowable(width=W, color=tc.light, thickness=1))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        f"Manuel généré par ProcessIntelligence — "
        f"{organization.name} — "
        f"{datetime.now().strftime('%d/%m/%Y à %H:%M')}",
        styles['Caption']
    ))

    doc.build(story)
    return buffer.getvalue()


def _get_styles(tc, fs, fnt):
    """Génère les styles ReportLab pour le manuel."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name='OrgName',
        fontSize=16, textColor=tc.secondary,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER, spaceAfter=4
    ))
    styles.add(ParagraphStyle(
        name='ManualTitle',
        fontSize=28, textColor=tc.primary,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER, spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        name='ManualSubtitle',
        fontSize=11, textColor=tc.secondary,
        fontName='Helvetica',
        alignment=TA_CENTER, spaceAfter=10
    ))
    styles.add(ParagraphStyle(
        name='SectionTitle',
        fontSize=14, textColor=tc.primary,
        fontName='Helvetica-Bold',
        spaceBefore=12, spaceAfter=8
    ))
    styles.add(ParagraphStyle(
        name='TocService',
        fontSize=11, textColor=tc.primary,
        fontName='Helvetica-Bold',
        spaceBefore=8, spaceAfter=2
    ))
    styles.add(ParagraphStyle(
        name='TocProcedure',
        fontSize=10, textColor=tc.text,
        fontName='Helvetica',
        spaceBefore=2, spaceAfter=2,
        leftIndent=20
    ))
    styles.add(ParagraphStyle(
        name='ProcTitle',
        fontSize=12, textColor=tc.primary,
        fontName='Helvetica-Bold',
        spaceBefore=8, spaceAfter=4
    ))
    styles.add(ParagraphStyle(
        name='SubTitle',
        fontSize=10, textColor=tc.secondary,
        fontName='Helvetica-Bold',
        spaceBefore=6, spaceAfter=4
    ))
    styles.add(ParagraphStyle(
        name='Body',
        fontSize=9, textColor=tc.text,
        fontName='Helvetica',
        spaceBefore=3, spaceAfter=3,
        leading=13
    ))
    styles.add(ParagraphStyle(
        name='Caption',
        fontSize=8, textColor=tc.text,
        fontName='Helvetica',
        alignment=TA_CENTER
    ))

    return styles