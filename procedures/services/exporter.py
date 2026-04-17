import io
import csv as csv_module
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable
)
from reportlab.lib.enums import TA_CENTER
from procedures.models import Procedure, AuditReport
from procedures.services.theme import get_theme, ThemeColors


def get_styles(theme: dict, tc: ThemeColors):
    """Génère les styles ReportLab à partir du thème."""
    fs  = theme.get('font_sizes', {})
    fnt = theme.get('fonts', {})
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name='PITitle',
        fontSize=fs.get('title', 24),
        textColor=tc.primary,
        fontName=fnt.get('title', 'Helvetica-Bold'),
        alignment=TA_CENTER, spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        name='PISubtitle',
        fontSize=fs.get('subtitle', 13),
        textColor=tc.secondary,
        fontName=fnt.get('body', 'Helvetica'),
        alignment=TA_CENTER, spaceAfter=20
    ))
    styles.add(ParagraphStyle(
        name='PIHeading1',
        fontSize=fs.get('heading1', 14),
        textColor=tc.primary,
        fontName=fnt.get('heading', 'Helvetica-Bold'),
        spaceBefore=16, spaceAfter=8
    ))
    styles.add(ParagraphStyle(
        name='PIBody',
        fontSize=fs.get('body', 10),
        textColor=tc.text,
        fontName=fnt.get('body', 'Helvetica'),
        spaceBefore=4, spaceAfter=4, leading=14
    ))
    styles.add(ParagraphStyle(
        name='PICaption',
        fontSize=fs.get('caption', 8),
        textColor=tc.text,
        fontName=fnt.get('caption', 'Helvetica'),
        alignment=TA_CENTER
    ))
    return styles


def score_bar(score: float) -> str:
    filled = int(score * 10)
    empty  = 10 - filled
    return f"{'█' * filled}{'░' * empty}  {int(score * 100)}%"


def p_cell(text, tc, fs=9, bold=False, color=None):
    """Crée un Paragraph pour cellule de tableau."""
    return Paragraph(str(text), ParagraphStyle(
        'c',
        fontSize=fs,
        fontName='Helvetica-Bold' if bold else 'Helvetica',
        textColor=color or tc.text,
        leading=fs + 3
    ))


def generate_audit_pdf(procedure_id: int) -> bytes:
    """
    Génère un rapport d'audit PDF en utilisant le thème de l'organisation.
    """
    try:
        procedure = Procedure.objects.get(id=procedure_id)
        report    = procedure.audit_reports.latest('generated_at')
    except (Procedure.DoesNotExist, AuditReport.DoesNotExist):
        raise ValueError(f"Procédure ou rapport introuvable pour l'ID {procedure_id}")

    # Chargement du thème
    theme  = get_theme(procedure.organization)
    tc     = ThemeColors(theme)
    styles = get_styles(theme, tc)
    sp     = theme.get('spacing', {})
    cfg    = theme.get('report', {})
    pad    = sp.get('cell_padding', 8)

    steps  = procedure.steps.all().order_by('step_order')
    buffer = io.BytesIO()
    W      = 17 * cm

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )
    story = []

    # ── ENTÊTE ──────────────────────────────────────
    if cfg.get('show_cover', True):
        story.append(Spacer(1, 1.5*cm))
        story.append(Paragraph("ProcessIntelligence", styles['PITitle']))
        story.append(Spacer(1, sp.get('title_gap', 0.4) * cm))
        story.append(Paragraph("Rapport d'Audit de Procédure", styles['PISubtitle']))
        story.append(Spacer(1, 0.3*cm))
        story.append(HRFlowable(width=W, color=tc.secondary, thickness=2))
        story.append(Spacer(1, 0.5*cm))

        info_data = [
            ['Procédure',    procedure.title],
            ['Service',      procedure.service or '—'],
            ['Organisation', procedure.organization.name],
            ['Version',      procedure.version],
            ['Statut',       procedure.get_status_display()],
            ['Date analyse', report.generated_at.strftime('%d/%m/%Y à %H:%M')],
        ]
        info_table = Table(info_data, colWidths=[4*cm, 13*cm])
        info_table.setStyle(TableStyle([
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
        story.append(info_table)
        story.append(Spacer(1, sp.get('section_gap', 1.0) * cm))

    # ── SCORES ──────────────────────────────────────
    if cfg.get('show_scores', True):
        story.append(Paragraph("1. Scores", styles['PIHeading1']))
        story.append(HRFlowable(width=W, color=tc.light, thickness=1))
        story.append(Spacer(1, 0.3*cm))

        def score_color(s):
            if s >= 0.7: return tc.success
            if s >= 0.4: return tc.warning
            return tc.danger

        scores_data = [
            [p_cell('Indicateur', tc, bold=True, color=tc.white),
             p_cell('Score', tc, bold=True, color=tc.white),
             p_cell('Visualisation', tc, bold=True, color=tc.white)],
            [p_cell("Score d'optimisation", tc),
             p_cell(f"{int(report.score_optim * 100)}%", tc, bold=True, color=score_color(report.score_optim)),
             p_cell(score_bar(report.score_optim), tc)],
            [p_cell("Score d'automatisation", tc),
             p_cell(f"{int(report.score_auto * 100)}%", tc, bold=True, color=score_color(report.score_auto)),
             p_cell(score_bar(report.score_auto), tc)],
        ]
        scores_table = Table(scores_data, colWidths=[6*cm, 3*cm, 8*cm])
        scores_table.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0), tc.primary),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [tc.white, tc.background]),
            ('GRID',          (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('PADDING',       (0, 0), (-1, -1), pad),
            ('ALIGN',         (1, 0), (1, -1), 'CENTER'),
        ]))
        story.append(scores_table)
        story.append(Spacer(1, sp.get('section_gap', 1.0) * cm))

    # ── ANOMALIES ───────────────────────────────────
    if cfg.get('show_anomalies', True):
        story.append(Paragraph("2. Anomalies détectées", styles['PIHeading1']))
        story.append(HRFlowable(width=W, color=tc.light, thickness=1))
        story.append(Spacer(1, 0.3*cm))

        anomalies = report.anomalies or []
        if anomalies:
            severity_bg = {
                'high'  : colors.HexColor('#FFEBEB'),
                'medium': colors.HexColor('#FFF4E5'),
                'low'   : colors.HexColor('#FFFDE5'),
            }
            severity_labels = {'high': 'ÉLEVÉ', 'medium': 'MOYEN', 'low': 'FAIBLE'}
            type_labels = {
                'infinite_loop'   : 'Boucle infinie',
                'congestion_point': 'Congestion',
                'orphan_task'     : 'Tâche orpheline',
            }
            anom_data = [[
                p_cell('Sévérité', tc, bold=True, color=tc.white),
                p_cell('Type', tc, bold=True, color=tc.white),
                p_cell('Description', tc, bold=True, color=tc.white),
            ]]
            row_colors = []
            for a in anomalies:
                anom_data.append([
                    p_cell(severity_labels.get(a.get('severity', ''), ''), tc),
                    p_cell(type_labels.get(a.get('type', ''), ''), tc),
                    p_cell(a.get('description', ''), tc),
                ])
                row_colors.append(severity_bg.get(a.get('severity', 'low'), tc.white))

            style_cmds = [
                ('BACKGROUND', (0, 0), (-1, 0), tc.primary),
                ('GRID',       (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
                ('PADDING',    (0, 0), (-1, -1), pad),
                ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
            ]
            for idx, bg in enumerate(row_colors, start=1):
                style_cmds.append(('BACKGROUND', (0, idx), (-1, idx), bg))

            anom_table = Table(anom_data, colWidths=[2.5*cm, 3.5*cm, 11*cm])
            anom_table.setStyle(TableStyle(style_cmds))
            story.append(anom_table)
        else:
            story.append(Paragraph("✓ Aucune anomalie détectée.", styles['PIBody']))
        story.append(Spacer(1, sp.get('section_gap', 1.0) * cm))

    # ── RECOMMANDATIONS ─────────────────────────────
    if cfg.get('show_recommendations', True):
        story.append(Paragraph("3. Recommandations", styles['PIHeading1']))
        story.append(HRFlowable(width=W, color=tc.light, thickness=1))
        story.append(Spacer(1, 0.3*cm))

        recommendations = report.recommendations or []
        priority_labels = {'high': 'PRIORITÉ HAUTE', 'medium': 'PRIORITÉ MOYENNE', 'low': 'PRIORITÉ FAIBLE'}
        priority_colors = {'high': tc.danger, 'medium': tc.warning, 'low': tc.success}

        if recommendations:
            for i, rec in enumerate(recommendations, start=1):
                priority = rec.get('priority', 'low')
                rec_data = [[
                    p_cell(f"{i}. {priority_labels.get(priority, '')}", tc,
                           bold=True, color=priority_colors.get(priority, tc.success)),
                    p_cell(rec.get('action', ''), tc),
                ]]
                rec_table = Table(rec_data, colWidths=[4*cm, 13*cm])
                rec_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), tc.background),
                    ('GRID',       (0, 0), (-1, -1), 0.5, colors.HexColor('#DDDDDD')),
                    ('PADDING',    (0, 0), (-1, -1), pad),
                    ('VALIGN',     (0, 0), (-1, -1), 'TOP'),
                ]))
                story.append(rec_table)
                story.append(Spacer(1, 0.2*cm))
        else:
            story.append(Paragraph("Aucune recommandation générée.", styles['PIBody']))
        story.append(Spacer(1, sp.get('section_gap', 1.0) * cm))

    # ── ÉTAPES ──────────────────────────────────────
    if cfg.get('show_steps', True):
        story.append(Paragraph("4. Détail des étapes", styles['PIHeading1']))
        story.append(HRFlowable(width=W, color=tc.light, thickness=1))
        story.append(Spacer(1, 0.3*cm))

        steps_data = [[
            p_cell('#', tc, bold=True, color=tc.white),
            p_cell('Titre', tc, bold=True, color=tc.white),
            p_cell('Acteur', tc, bold=True, color=tc.white),
            p_cell('Verbe', tc, bold=True, color=tc.white),
            p_cell('Outil', tc, bold=True, color=tc.white),
            p_cell('Score', tc, bold=True, color=tc.white),
        ]]
        for step in steps:
            steps_data.append([
                p_cell(step.step_order, tc),
                p_cell(step.title, tc),
                p_cell(step.actor_role, tc),
                p_cell(step.action_verb or '—', tc),
                p_cell(step.tool_used or '—', tc),
                p_cell(f"{int(step.automation_score * 100)}%", tc),
            ])

        steps_table = Table(
            steps_data,
            colWidths=[1*cm, 6.5*cm, 3*cm, 2.5*cm, 2.5*cm, 1.5*cm]
        )
        steps_table.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1, 0), tc.primary),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [tc.white, tc.background]),
            ('GRID',          (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('PADDING',       (0, 0), (-1, -1), pad),
            ('ALIGN',         (0, 0), (0, -1), 'CENTER'),
            ('ALIGN',         (5, 0), (5, -1), 'CENTER'),
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(steps_table)
        story.append(Spacer(1, sp.get('section_gap', 1.0) * cm))

    # ── PIED DE PAGE ────────────────────────────────
    if cfg.get('show_footer', True):
        story.append(HRFlowable(width=W, color=tc.light, thickness=1))
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph(
            f"Rapport généré par ProcessIntelligence — {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
            styles['PICaption']
        ))

    doc.build(story)
    return buffer.getvalue()


def generate_csv_template() -> bytes:
    """Génère le template CSV officiel ProcessIntelligence."""
    output = io.StringIO()
    writer = csv_module.writer(output)
    writer.writerow([
        'order', 'title', 'action_verb', 'actor_role', 'tool_used',
        'estimated_duration', 'is_recurring', 'trigger_type',
        'has_condition', 'output_type'
    ])
    writer.writerow([1, 'Réception de la demande', 'recevoir', 'Secrétaire', 'Email', 5, 'false', 'manual', 'false', 'document'])
    writer.writerow([2, 'Vérification des pièces', 'vérifier', 'Responsable', 'Excel', 15, 'false', 'manual', 'false', 'data'])
    writer.writerow([3, 'Validation finale', 'valider', 'Directeur', '', 10, 'false', 'manual', 'false', 'decision'])
    return output.getvalue().encode('utf-8')