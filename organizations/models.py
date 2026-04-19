from django.db import models
from django.contrib.auth.models import User

from organizations.plans import (
    PLAN_CHOICES, PLAN_FREE, PLAN_PRO, PLAN_BUSINESS,
    get_plan, is_plan_at_least,
)


class Organization(models.Model):
    """
    Le tenant principal. Chaque entreprise cliente est une Organization.
    Toutes les données du système lui sont rattachées.

    Système de plans :
        - Le plan est géré via organizations/plans.py (source de vérité).
        - plan_started_at / plan_expires_at servent au cycle d'abonnement.
        - Les méthodes utilitaires (has_paid_plan, can_use_llm, limit_for, etc.)
          sont utilisées par les vues et services pour appliquer les restrictions.
    """

    # Secteurs d'activité (pour la conformité légale)
    SECTOR_FINANCE = 'finance'
    SECTOR_INSURANCE = 'insurance'
    SECTOR_HEALTH = 'health'
    SECTOR_HR = 'hr'
    SECTOR_FOOD = 'food'
    SECTOR_OTHER = 'other'
    SECTOR_CHOICES = [
        (SECTOR_FINANCE, 'Finance / Banque'),
        (SECTOR_INSURANCE, 'Assurance'),
        (SECTOR_HEALTH, 'Santé / Médical'),
        (SECTOR_HR, 'RH / Travail'),
        (SECTOR_FOOD, 'Agroalimentaire'),
        (SECTOR_OTHER, 'Autre'),
    ]

    # --- Champs de base ---
    name        = models.CharField(max_length=255, verbose_name="Nom")
    slug        = models.SlugField(max_length=255, unique=True)
    sector      = models.CharField(max_length=20, choices=SECTOR_CHOICES, default=SECTOR_OTHER)
    country     = models.CharField(max_length=10, default='FR', verbose_name="Pays")
    theme       = models.JSONField(
        default=dict, blank=True,
        verbose_name="Thème personnalisé",
        help_text="Surcharge du thème par défaut (couleurs, polices, tailles)",
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    is_active   = models.BooleanField(default=True)

    # --- Système de plans ---
    plan            = models.CharField(
        max_length=20,
        choices=PLAN_CHOICES,
        default=PLAN_FREE,
        verbose_name="Plan d'abonnement",
    )
    plan_started_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Plan souscrit le",
    )
    plan_expires_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Plan expire le",
        help_text="Null pour les plans perpétuels ou gratuits. Utilisé pour "
                  "rétrograder automatiquement en Free après expiration.",
    )

    class Meta:
        verbose_name = "Organisation"
        verbose_name_plural = "Organisations"
        ordering = ['name']

    def __str__(self):
        return self.name

    # -------------------------------------------------------------------------
    # Méthodes liées au plan
    # -------------------------------------------------------------------------

    def get_plan_config(self) -> dict:
        """
        Retourne la configuration complète du plan actuel (voir plans.py).
        """
        return get_plan(self.plan)

    def has_paid_plan(self) -> bool:
        """
        True si l'organisation est sur un plan payant (Pro, Business, ...).
        """
        return self.get_plan_config()["is_paid"]

    def can_use_llm(self) -> bool:
        """
        True si l'organisation a accès à l'analyse par LLM.
        Combine : plan autorisant le LLM ET abonnement non expiré.
        """
        config = self.get_plan_config()
        if config["llm_model"] is None:
            return False
        if self.plan_expires_at is not None:
            from django.utils import timezone
            if self.plan_expires_at < timezone.now():
                return False
        return True

    def get_llm_model(self):
        """
        Retourne l'identifiant du modèle LLM à utiliser, ou None si pas d'accès.
        """
        if not self.can_use_llm():
            return None
        return self.get_plan_config()["llm_model"]

    def is_plan_at_least(self, required_plan: str) -> bool:
        """
        Helper pour vérifier un niveau de plan requis.
        Exemple : org.is_plan_at_least('pro') → True si plan = pro ou business.
        """
        return is_plan_at_least(self.plan, required_plan)

    # -------------------------------------------------------------------------
    # Features et limites
    # -------------------------------------------------------------------------

    def has_feature(self, feature_key: str) -> bool:
        """
        Vérifie qu'une feature précise est disponible dans le plan courant.

        Exemples :
            org.has_feature('export_bpmn')
            org.has_feature('versioning')
            org.has_feature('custom_theme')
        """
        feature_attr = f"feature_{feature_key}"
        return self.get_plan_config().get(feature_attr, False)

    def limit_for(self, resource: str):
        """
        Retourne la limite d'une ressource. None = illimité.

        Exemples :
            org.limit_for('procedures')          → 5 (Free), 100 (Pro), None (Business)
            org.limit_for('users')
            org.limit_for('analyses_per_month')
        """
        key = f"limit_{resource}"
        return self.get_plan_config().get(key)

    def can_create_procedure(self):
        """
        Vérifie si l'organisation peut créer une nouvelle procédure.
        Returns : (allowed: bool, reason_if_blocked: str)
        """
        limit = self.limit_for("procedures")
        if limit is None:
            return True, ""
        current = self.procedures.count()
        if current >= limit:
            return False, f"Limite atteinte : votre plan permet {limit} procédures maximum."
        return True, ""

    def can_add_user(self):
        """
        Vérifie si l'organisation peut ajouter un utilisateur.
        Returns : (allowed: bool, reason_if_blocked: str)
        """
        limit = self.limit_for("users")
        if limit is None:
            return True, ""
        current = self.memberships.count()
        if current >= limit:
            return False, f"Limite atteinte : votre plan permet {limit} utilisateurs maximum."
        return True, ""

    # -------------------------------------------------------------------------
    # Compteur mensuel d'analyses
    # -------------------------------------------------------------------------

    def can_analyze_this_month(self):
        """
        Vérifie si l'organisation peut lancer une nouvelle analyse ce mois-ci.
        Returns : (allowed: bool, analyses_already_done: int, limit_or_None: int | None)
        """
        limit = self.limit_for("analyses_per_month")
        current = self.get_monthly_analyses_count()
        if limit is None:
            return True, current, None
        return (current < limit), current, limit

    def get_monthly_analyses_count(self) -> int:
        """
        Retourne le nombre d'analyses effectuées ce mois-ci pour cette organisation.
        """
        from django.utils import timezone
        from procedures.models import MonthlyUsage
        now = timezone.now()
        usage = MonthlyUsage.objects.filter(
            organization=self,
            year=now.year,
            month=now.month,
        ).first()
        return usage.analyses_count if usage else 0

    def increment_monthly_analyses(self):
        """
        Incrémente le compteur d'analyses mensuel.
        À appeler APRÈS chaque analyse réussie (LLM ou spaCy).
        """
        from django.utils import timezone
        from procedures.models import MonthlyUsage
        now = timezone.now()
        usage, _ = MonthlyUsage.objects.get_or_create(
            organization=self,
            year=now.year,
            month=now.month,
            defaults={'analyses_count': 0},
        )
        # Utilisation de F() pour éviter les race conditions en concurrence
        usage.analyses_count = models.F('analyses_count') + 1
        usage.save(update_fields=['analyses_count'])


class Membership(models.Model):
    """
    Lien entre un utilisateur et une organisation.
    Définit son rôle au sein de cette organisation.
    Un utilisateur peut appartenir à plusieurs organisations avec des rôles différents.
    """

    ROLE_ADMIN = 'admin'
    ROLE_DIRECTOR = 'director'
    ROLE_MANAGER = 'manager'
    ROLE_VIEWER = 'viewer'
    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Administrateur'),
        (ROLE_DIRECTOR, 'Directeur'),
        (ROLE_MANAGER, 'Manager'),
        (ROLE_VIEWER, 'Lecteur'),
    ]

    user         = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memberships')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='memberships')
    role         = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_VIEWER)
    joined_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Membre"
        verbose_name_plural = "Membres"
        # Un utilisateur ne peut avoir qu'un seul rôle par organisation
        unique_together = ('user', 'organization')

    def __str__(self):
        return f"{self.user.username} — {self.organization.name} ({self.role})"


class ServiceMembership(models.Model):
    """
    Lien entre un utilisateur et un service spécifique.
    Permet une granularité fine des permissions :
    un user peut être Manager en RH et Viewer en Comptabilité.
    """

    ROLE_SERVICE_MANAGER = 'service_manager'
    ROLE_SERVICE_VIEWER  = 'service_viewer'
    ROLE_CHOICES = [
        (ROLE_SERVICE_MANAGER, 'Responsable de service'),
        (ROLE_SERVICE_VIEWER,  'Membre du service'),
    ]

    user         = models.ForeignKey(User, on_delete=models.CASCADE, related_name='service_memberships')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='service_memberships')
    service      = models.CharField(max_length=100, verbose_name="Service / Département")
    role         = models.CharField(max_length=30, choices=ROLE_CHOICES, default=ROLE_SERVICE_VIEWER)
    assigned_at  = models.DateTimeField(auto_now_add=True)
    assigned_by  = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='service_assignments'
    )

    class Meta:
        verbose_name        = "Membre de service"
        verbose_name_plural = "Membres de service"
        unique_together     = ('user', 'organization', 'service')

    def __str__(self):
        return f"{self.user.username} — {self.service} ({self.role})"