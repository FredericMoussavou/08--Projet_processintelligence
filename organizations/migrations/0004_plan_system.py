"""
Migration pour le système de plans sur Organization.

Ajoute :
    - choices strictes au champ plan (free/pro/business)
    - plan_started_at, plan_expires_at pour le cycle d'abonnement


"""

from django.db import migrations, models


def set_default_plan_free(apps, schema_editor):
    """
    Initialise toutes les organisations existantes en plan 'free'
    et remplit plan_started_at avec created_at.
    """
    Organization = apps.get_model('organizations', 'Organization')
    for org in Organization.objects.all():
        if not org.plan or org.plan not in ('free', 'pro', 'business'):
            org.plan = 'free'
        if org.plan_started_at is None:
            org.plan_started_at = org.created_at if hasattr(org, 'created_at') else None
        org.save(update_fields=['plan', 'plan_started_at'])


def reverse_default(apps, schema_editor):
    """Pas de rollback nécessaire — la donnée reste valide."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        # À ajuster : remplacer par le nom de ta dernière migration organizations
        ('organizations', '0003_alter_membership_role_servicemembership'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organization',
            name='plan',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('free', 'Free'),
                    ('pro', 'Pro'),
                    ('business', 'Business'),
                ],
                default='free',
                verbose_name="Plan d'abonnement",
            ),
        ),
        migrations.AddField(
            model_name='organization',
            name='plan_started_at',
            field=models.DateTimeField(
                null=True, blank=True,
                verbose_name="Plan souscrit le",
            ),
        ),
        migrations.AddField(
            model_name='organization',
            name='plan_expires_at',
            field=models.DateTimeField(
                null=True, blank=True,
                verbose_name="Plan expire le",
                help_text="Null pour les plans perpétuels ou gratuits.",
            ),
        ),
        migrations.RunPython(set_default_plan_free, reverse_code=reverse_default),
    ]
