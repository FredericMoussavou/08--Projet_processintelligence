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
    archived_at    = models.DateTimeField(null=True, blank=True, verbose_name="Archivée le")
    archived_by    = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='archived_procedures',
        verbose_name="Archivée par"
    )
    parent_version = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='derived_versions',
        verbose_name="Version parente"
    )

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

class ProcedureVersion(models.Model):
    """
    Snapshot immutable d'une procédure à un instant T.
    Créé automatiquement à chaque approbation d'un ChangeRequest
    ou manuellement par un Admin/Directeur.

    Principe : une version ne s'écrase jamais — elle s'archive.
    L'historique complet est toujours consultable.
    """

    procedure      = models.ForeignKey(
        Procedure, on_delete=models.CASCADE,
        related_name='versions'
    )
    version_number = models.CharField(max_length=20, verbose_name="Numéro de version")
    snapshot_data  = models.JSONField(verbose_name="Données de la procédure")
    change_summary = models.TextField(blank=True, verbose_name="Résumé des changements")
    created_at     = models.DateTimeField(auto_now_add=True)
    created_by     = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='created_versions'
    )

    REASON_AUTO    = 'auto_approval'
    REASON_MANUAL  = 'manual_archive'
    REASON_CHOICES = [
        (REASON_AUTO,   'Approbation automatique'),
        (REASON_MANUAL, 'Archivage manuel'),
    ]
    reason = models.CharField(
        max_length=20, choices=REASON_CHOICES,
        default=REASON_AUTO
    )

    class Meta:
        verbose_name        = "Version de procédure"
        verbose_name_plural = "Versions de procédures"
        ordering            = ['-created_at']
        unique_together     = ('procedure', 'version_number')

    def __str__(self):
        return f"{self.procedure.title} — v{self.version_number}"

    @classmethod
    def snapshot(cls, procedure, reason='auto_approval', user=None, change_summary=''):
        """
        Crée un snapshot immutable de la procédure actuelle.
        Appelé automatiquement lors de chaque approbation.
        """
        steps = list(procedure.steps.all().order_by('step_order').values(
            'step_order', 'title', 'action_verb', 'actor_role',
            'tool_used', 'output_type', 'automation_score',
            'compliance_status', 'is_recurring', 'has_condition',
            'estimated_duration', 'trigger_type'
        ))

        snapshot_data = {
            'title'      : procedure.title,
            'description': procedure.description,
            'service'    : procedure.service,
            'version'    : procedure.version,
            'status'     : procedure.status,
            'steps'      : steps,
            'steps_count': len(steps),
        }

        return cls.objects.create(
            procedure      = procedure,
            version_number = procedure.version,
            snapshot_data  = snapshot_data,
            change_summary = change_summary,
            created_by     = user,
            reason         = reason,
        )
    
class MonthlyUsage(models.Model):
    """
    Usage mensuel d'une organisation pour l'application des quotas.

    Un record unique par (organisation, year, month). Le compteur est
    incrémenté à chaque analyse de procédure (via Organization.increment_monthly_analyses()).

    Requête typique :
        usage = MonthlyUsage.objects.get(organization=org, year=2026, month=4)
        print(usage.analyses_count)   # 42

    Pour les statistiques admin :
        # Top organisations en consommation ce mois
        from django.utils import timezone
        now = timezone.now()
        top = MonthlyUsage.objects.filter(
            year=now.year, month=now.month
        ).order_by('-analyses_count')[:10]
    """

    organization   = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='monthly_usages',
    )
    year           = models.PositiveSmallIntegerField(verbose_name="Année")
    month          = models.PositiveSmallIntegerField(verbose_name="Mois (1-12)")
    analyses_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Nombre d'analyses effectuées"
    )
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Usage mensuel"
        verbose_name_plural = "Usages mensuels"
        ordering            = ['-year', '-month']
        unique_together     = ('organization', 'year', 'month')
        indexes = [
            models.Index(fields=['organization', '-year', '-month']),
        ]

    def __str__(self):
        return f"{self.organization.name} — {self.month:02d}/{self.year} : {self.analyses_count} analyses"

class LLMCallLog(models.Model):
    """
    Log d'un appel à l'API LLM pour extraction de procédure.

    Permet de suivre :
        - Les coûts mensuels (via input_tokens + output_tokens × prix par token)
        - Le taux de cache hit (ratio d'économie)
        - Le taux de fallback vers le parser par règles (indicateur de santé API)
        - La latence moyenne par modèle

    Requête typique pour un dashboard admin :
        from django.db.models import Sum
        this_month = LLMCallLog.objects.filter(
            created_at__gte=start_of_month,
            cache_hit=False,
            fallback_used=False,
        ).aggregate(
            total_input=Sum('input_tokens'),
            total_output=Sum('output_tokens'),
        )
        # Coût estimé Claude Haiku 4.5 :
        cost_usd = (this_month['total_input'] / 1_000_000) * 1.0 + \
                   (this_month['total_output'] / 1_000_000) * 5.0
    """

    organization = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='llm_calls',
    )
    text_length   = models.PositiveIntegerField(verbose_name="Longueur du texte (chars)")
    duration_ms   = models.PositiveIntegerField(verbose_name="Durée de l'appel (ms)")
    input_tokens  = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    model         = models.CharField(max_length=50, verbose_name="Modèle utilisé")
    cache_hit     = models.BooleanField(default=False, verbose_name="Cache hit ?")
    fallback_used = models.BooleanField(
        default=False,
        verbose_name="Fallback règles utilisé ?"
    )
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Log d'appel LLM"
        verbose_name_plural = "Logs d'appels LLM"
        ordering            = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['organization', '-created_at']),
        ]

    def __str__(self):
        if self.cache_hit:
            status = "cache"
        elif self.fallback_used:
            status = "fallback"
        else:
            status = "api"
        return f"LLMCall [{status}] {self.model} — {self.created_at.strftime('%d/%m %H:%M')}"

    @property
    def estimated_cost_usd(self):
        """
        Calcule le coût estimé en USD selon le modèle.
        Tarifs Claude (à ajuster si changement) :
            haiku-4-5  : 1$ / 5$   per M tokens (input / output)
            sonnet-4-6 : 3$ / 15$  per M tokens
            opus-4-7   : 15$ / 75$ per M tokens
        """
        pricing = {
            'claude-haiku-4-5-20251001': (1.0, 5.0),
            'claude-sonnet-4-6':          (3.0, 15.0),
            'claude-opus-4-7':            (15.0, 75.0),
        }
        in_price, out_price = pricing.get(self.model, (1.0, 5.0))
        return (self.input_tokens / 1_000_000) * in_price + \
               (self.output_tokens / 1_000_000) * out_price


class MaskingConsent(models.Model):
    """
    Consentement explicite pour envoyer du texte non-masqué au LLM externe.

    Sert de preuve RGPD en cas d'audit CNIL ou de demande d'information par
    un utilisateur (droit à l'information).

    Un nouvel enregistrement est créé à CHAQUE désactivation du toggle par
    l'utilisateur — on ne s'appuie pas sur un consentement ancien.
    """

    user          = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='masking_consents',
        help_text="Utilisateur authentifié, null si endpoint public",
    )
    session_hash  = models.CharField(
        max_length=64, blank=True, default='',
        help_text="Hash SHA-256 de l'IP + user-agent (pour utilisateurs anonymes)",
    )
    endpoint      = models.CharField(
        max_length=100,
        help_text="Endpoint concerné, ex: /api/procedures/ingest/",
    )
    consent_text  = models.TextField(
        help_text="Texte exact présenté à l'utilisateur au moment du consentement",
    )
    user_agent    = models.CharField(max_length=255, blank=True, default='')
    ip_last_octet = models.CharField(
        max_length=3, blank=True, default='',
        help_text="Dernier octet de l'IP (les 3 autres sont anonymisés pour RGPD)",
    )
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Consentement désactivation masquage"
        verbose_name_plural = "Consentements désactivation masquage"
        ordering            = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        who = self.user.username if self.user else f"anon#{self.session_hash[:8]}"
        return f"Consentement de {who} — {self.created_at.strftime('%d/%m/%Y %H:%M')}"
