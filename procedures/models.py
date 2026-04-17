from django.db import models
from django.contrib.auth.models import User
from organizations.models import Organization


class Procedure(models.Model):
    """
    L'objet central du système. Représente un processus d'entreprise
    de bout en bout. Chaque procédure est versionnée et rattachée
    à une organisation (tenant).
    """

    STATUS_DRAFT = 'draft'
    STATUS_ACTIVE = 'active'
    STATUS_ARCHIVED = 'archived'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Brouillon'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_ARCHIVED, 'Archivée'),
    ]

    organization  = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='procedures')
    title         = models.CharField(max_length=255, verbose_name="Titre")
    description   = models.TextField(blank=True, verbose_name="Description")
    service       = models.CharField(max_length=100, blank=True, verbose_name="Service / Département")
    version       = models.CharField(max_length=20, default='1.0', verbose_name="Version")
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    owner         = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='owned_procedures')
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Procédure"
        verbose_name_plural = "Procédures"
        ordering = ['organization', 'title']

    def __str__(self):
        return f"{self.title} (v{self.version}) — {self.organization.name}"


class Step(models.Model):
    """
    Une étape unitaire d'une procédure.
    Chaque champ est conçu pour alimenter les algorithmes d'analyse :
    - action_verb → détection d'automatisabilité
    - actor_role → détection de congestion
    - output_type → détection de tâches orphelines
    - is_recurring → signal d'automatisation
    """

    # Type de déclencheur de l'étape
    TRIGGER_MANUAL = 'manual'
    TRIGGER_AUTO = 'auto'
    TRIGGER_TIMER = 'timer'
    TRIGGER_CHOICES = [
        (TRIGGER_MANUAL, 'Manuel'),
        (TRIGGER_AUTO, 'Automatique'),
        (TRIGGER_TIMER, 'Planifié'),
    ]

    # Type d'output produit par l'étape
    OUTPUT_DOCUMENT = 'document'
    OUTPUT_DATA = 'data'
    OUTPUT_DECISION = 'decision'
    OUTPUT_NONE = 'none'
    OUTPUT_CHOICES = [
        (OUTPUT_DOCUMENT, 'Document'),
        (OUTPUT_DATA, 'Données'),
        (OUTPUT_DECISION, 'Décision'),
        (OUTPUT_NONE, 'Aucun'),
    ]

    # Statut de conformité légale
    COMPLIANCE_OK = 'compliant'
    COMPLIANCE_WARNING = 'warning'
    COMPLIANCE_NOK = 'non_compliant'
    COMPLIANCE_CHOICES = [
        (COMPLIANCE_OK, 'Conforme'),
        (COMPLIANCE_WARNING, 'À vérifier'),
        (COMPLIANCE_NOK, 'Non conforme'),
    ]

    procedure          = models.ForeignKey(Procedure, on_delete=models.CASCADE, related_name='steps')
    title              = models.CharField(max_length=255, verbose_name="Titre de l'étape")
    action_verb        = models.CharField(max_length=100, verbose_name="Verbe d'action", help_text="Ex: saisir, valider, envoyer, copier")
    actor_role         = models.CharField(max_length=100, verbose_name="Rôle de l'acteur", help_text="Ex: Comptable, DG, RH")
    tool_used          = models.CharField(max_length=100, blank=True, verbose_name="Outil utilisé", help_text="Ex: Excel, SAP, Email")
    estimated_duration = models.PositiveIntegerField(default=0, verbose_name="Durée estimée (min)")
    is_recurring       = models.BooleanField(default=False, verbose_name="Tâche récurrente")
    trigger_type       = models.CharField(max_length=20, choices=TRIGGER_CHOICES, default=TRIGGER_MANUAL)
    has_condition      = models.BooleanField(default=False, verbose_name="Contient un Si/Alors")
    output_type        = models.CharField(max_length=20, choices=OUTPUT_CHOICES, default=OUTPUT_NONE)
    automation_score   = models.FloatField(default=0.0, verbose_name="Score d'automatisation")
    compliance_status  = models.CharField(max_length=20, choices=COMPLIANCE_CHOICES, default=COMPLIANCE_WARNING)
    step_order         = models.PositiveIntegerField(default=0, verbose_name="Ordre")
    parent_step        = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    created_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Étape"
        verbose_name_plural = "Étapes"
        ordering = ['procedure', 'step_order']

    def __str__(self):
        return f"{self.step_order}. {self.title} ({self.actor_role})"


class StepDependency(models.Model):
    """
    Lien orienté entre deux étapes — construit le graphe de la procédure.
    C'est cette table qui permet de détecter les boucles infinies
    et les tâches orphelines via NetworkX (Phase 3).
    """

    from_step       = models.ForeignKey(Step, on_delete=models.CASCADE, related_name='dependencies_out')
    to_step         = models.ForeignKey(Step, on_delete=models.CASCADE, related_name='dependencies_in')
    condition_label = models.CharField(max_length=255, blank=True, verbose_name="Condition", help_text="Ex: Si approuvé, Si montant > 500€")

    class Meta:
        verbose_name = "Dépendance"
        verbose_name_plural = "Dépendances"
        unique_together = ('from_step', 'to_step')

    def __str__(self):
        return f"{self.from_step} → {self.to_step}"


class Rule(models.Model):
    """
    Règle métier ou légale applicable à une procédure.
    Alimentera le moteur de conformité de la Phase 5.
    """

    SEVERITY_INFO = 'info'
    SEVERITY_WARNING = 'warning'
    SEVERITY_BLOCKING = 'blocking'
    SEVERITY_CHOICES = [
        (SEVERITY_INFO, 'Information'),
        (SEVERITY_WARNING, 'Avertissement'),
        (SEVERITY_BLOCKING, 'Bloquant'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='rules')
    procedure    = models.ForeignKey(Procedure, on_delete=models.SET_NULL, null=True, blank=True, related_name='rules')
    label        = models.CharField(max_length=255, verbose_name="Intitulé de la règle")
    condition    = models.TextField(verbose_name="Condition", help_text="Ex: Toute dépense > 500€ nécessite deux signatures")
    severity     = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default=SEVERITY_WARNING)
    legal_ref    = models.CharField(max_length=255, blank=True, verbose_name="Référence légale", help_text="Ex: Art. L1237-19 Code du Travail")
    is_active    = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Règle"
        verbose_name_plural = "Règles"

    def __str__(self):
        return f"{self.label} ({self.severity})"


class AuditReport(models.Model):
    """
    Diagnostic généré automatiquement par le moteur d'analyse.
    Stocke les scores et les anomalies détectées pour une procédure.
    """

    procedure         = models.ForeignKey(Procedure, on_delete=models.CASCADE, related_name='audit_reports')
    generated_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    score_optim       = models.FloatField(default=0.0, verbose_name="Score d'optimisation")
    score_auto        = models.FloatField(default=0.0, verbose_name="Score d'automatisation")
    anomalies         = models.JSONField(default=list, verbose_name="Anomalies détectées")
    recommendations   = models.JSONField(default=list, verbose_name="Recommandations")
    generated_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Rapport d'audit"
        verbose_name_plural = "Rapports d'audit"
        ordering = ['-generated_at']

    def __str__(self):
        return f"Audit — {self.procedure.title} — {self.generated_at.strftime('%d/%m/%Y')}"


class ChangeRequest(models.Model):
    """
    Workflow d'approbation pour modifier une procédure.
    """

    STATUS_PENDING          = 'pending'
    STATUS_AUTO_CHECKING    = 'auto_checking'
    STATUS_AUTO_REJECTED    = 'auto_rejected'
    STATUS_AWAITING_REVIEW  = 'awaiting_review'
    STATUS_APPROVED         = 'approved'
    STATUS_AUTO_APPROVED    = 'auto_approved'
    STATUS_REJECTED         = 'rejected'

    STATUS_CHOICES = [
        (STATUS_PENDING,         'Soumis'),
        (STATUS_AUTO_CHECKING,   'Analyse automatique en cours'),
        (STATUS_AUTO_REJECTED,   'Rejeté automatiquement'),
        (STATUS_AWAITING_REVIEW, 'En attente de validation'),
        (STATUS_APPROVED,        'Approuvée'),
        (STATUS_AUTO_APPROVED,   'Approuvée automatiquement'),
        (STATUS_REJECTED,        'Rejetée'),
    ]

    procedure     = models.ForeignKey(Procedure, on_delete=models.CASCADE, related_name='change_requests')
    requested_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='change_requests')
    reviewer      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviews')
    description   = models.TextField(verbose_name="Description du changement")
    CHANGE_PATCH = 'patch'
    CHANGE_MINOR = 'minor'
    CHANGE_MAJOR = 'major'
    CHANGE_TYPE_CHOICES = [
        (CHANGE_PATCH, 'Correctif (patch) — ex: reformulation, ajout d\'outil'),
        (CHANGE_MINOR, 'Mineur — ex: ajout d\'étape, modification d\'acteur'),
        (CHANGE_MAJOR, 'Majeur — ex: refonte structurelle, changement légal'),
    ]

    change_type = models.CharField(
        max_length=10,
        choices=CHANGE_TYPE_CHOICES,
        default=CHANGE_PATCH,
        verbose_name="Type de changement"
    )
    status        = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_PENDING)
    rejection_reason = models.TextField(blank=True, verbose_name="Motif de rejet")
    blocking_rules   = models.JSONField(default=list, verbose_name="Règles bloquantes détectées")
    workflow_log     = models.JSONField(default=list, verbose_name="Journal du workflow")
    created_at    = models.DateTimeField(auto_now_add=True)
    reviewed_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Demande de changement"
        verbose_name_plural = "Demandes de changement"
        ordering = ['-created_at']

    def __str__(self):
        return f"ChangeRequest — {self.procedure.title} ({self.status})"

    def add_log(self, event: str, detail: str = '', actor: str = 'système'):
        """
        Ajoute une entrée dans le journal du workflow.
        Permet de tracer chaque étape avec horodatage.
        """
        from django.utils import timezone
        self.workflow_log.append({
            'timestamp': timezone.now().strftime('%d/%m/%Y à %H:%M:%S'),
            'actor'    : actor,
            'event'    : event,
            'detail'   : detail,
        })
        self.save(update_fields=['workflow_log'])