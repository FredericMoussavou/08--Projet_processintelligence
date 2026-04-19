"""
Migration Lot 1 — Création des tables LLMCallLog et MaskingConsent.

À renommer avec le bon numéro (ex: 0006_lot1_llm_models.py).

Cette migration dépend de 0005_monthlyusage (la précédente de procedures).
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('procedures', '0005_monthlyusage'),
        ('organizations', '0004_plan_system'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # -------------------------------------------------------------------
        # LLMCallLog — trace les appels à l'API Claude
        # -------------------------------------------------------------------
        migrations.CreateModel(
            name='LLMCallLog',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                )),
                ('text_length', models.PositiveIntegerField(verbose_name='Longueur du texte (chars)')),
                ('duration_ms', models.PositiveIntegerField(verbose_name="Durée de l'appel (ms)")),
                ('input_tokens', models.PositiveIntegerField(default=0)),
                ('output_tokens', models.PositiveIntegerField(default=0)),
                ('model', models.CharField(max_length=50, verbose_name='Modèle utilisé')),
                ('cache_hit', models.BooleanField(default=False, verbose_name='Cache hit ?')),
                ('fallback_used', models.BooleanField(
                    default=False, verbose_name='Fallback règles utilisé ?'
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('organization', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='llm_calls',
                    to='organizations.organization',
                )),
            ],
            options={
                'verbose_name': "Log d'appel LLM",
                'verbose_name_plural': "Logs d'appels LLM",
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='llmcalllog',
            index=models.Index(fields=['-created_at'], name='procedures__created_llm_idx'),
        ),
        migrations.AddIndex(
            model_name='llmcalllog',
            index=models.Index(
                fields=['organization', '-created_at'],
                name='procedures__org_llm_idx',
            ),
        ),

        # -------------------------------------------------------------------
        # MaskingConsent — trace des consentements RGPD
        # -------------------------------------------------------------------
        migrations.CreateModel(
            name='MaskingConsent',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                )),
                ('session_hash', models.CharField(
                    blank=True, default='', max_length=64,
                    help_text="Hash SHA-256 de l'IP + user-agent (pour utilisateurs anonymes)"
                )),
                ('endpoint', models.CharField(
                    max_length=100,
                    help_text='Endpoint concerné, ex: /api/procedures/ingest/'
                )),
                ('consent_text', models.TextField(
                    help_text='Texte exact présenté à l\'utilisateur au moment du consentement'
                )),
                ('user_agent', models.CharField(blank=True, default='', max_length=255)),
                ('ip_last_octet', models.CharField(
                    blank=True, default='', max_length=3,
                    help_text="Dernier octet de l'IP (les 3 autres sont anonymisés pour RGPD)"
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='masking_consents',
                    to=settings.AUTH_USER_MODEL,
                    help_text='Utilisateur authentifié, null si endpoint public',
                )),
            ],
            options={
                'verbose_name': 'Consentement désactivation masquage',
                'verbose_name_plural': 'Consentements désactivation masquage',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='maskingconsent',
            index=models.Index(fields=['-created_at'], name='procedures__created_msk_idx'),
        ),
        migrations.AddIndex(
            model_name='maskingconsent',
            index=models.Index(
                fields=['user', '-created_at'],
                name='procedures__user_msk_idx',
            ),
        ),
    ]
