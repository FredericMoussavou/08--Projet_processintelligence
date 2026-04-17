from django.db import models
from django.contrib.auth.models import User


class Organization(models.Model):
    """
    Le tenant principal. Chaque entreprise cliente est une Organization.
    Toutes les données du système lui sont rattachées.
    """

    # Plans disponibles
    PLAN_FREE = 'free'
    PLAN_PRO = 'pro'
    PLAN_ENTERPRISE = 'enterprise'
    PLAN_CHOICES = [
        (PLAN_FREE, 'Gratuit'),
        (PLAN_PRO, 'Pro'),
        (PLAN_ENTERPRISE, 'Enterprise'),
    ]

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

    name        = models.CharField(max_length=255, verbose_name="Nom")
    slug        = models.SlugField(max_length=255, unique=True)
    plan        = models.CharField(max_length=20, choices=PLAN_CHOICES, default=PLAN_FREE)
    sector      = models.CharField(max_length=20, choices=SECTOR_CHOICES, default=SECTOR_OTHER)
    country     = models.CharField(max_length=10, default='FR', verbose_name="Pays")
    theme = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Thème personnalisé",
        help_text="Surcharge du thème par défaut (couleurs, polices, tailles)"
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    is_active   = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Organisation"
        verbose_name_plural = "Organisations"
        ordering = ['name']

    def __str__(self):
        return self.name


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