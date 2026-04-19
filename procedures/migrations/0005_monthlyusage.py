"""
Migration pour ajouter le modèle MonthlyUsage.
À placer dans procedures/migrations/ et renommer avec le bon numéro.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        # À ajuster selon tes migrations existantes
        ('procedures', '0004_procedure_archived_at_procedure_archived_by_and_more'),
        ('organizations', '0004_plan_system'),
    ]

    operations = [
        migrations.CreateModel(
            name='MonthlyUsage',
            fields=[
                ('id', models.AutoField(
                    auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                )),
                ('year', models.PositiveSmallIntegerField(verbose_name='Année')),
                ('month', models.PositiveSmallIntegerField(verbose_name='Mois (1-12)')),
                ('analyses_count', models.PositiveIntegerField(
                    default=0,
                    verbose_name="Nombre d'analyses effectuées"
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organization', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='monthly_usages',
                    to='organizations.organization',
                )),
            ],
            options={
                'verbose_name': 'Usage mensuel',
                'verbose_name_plural': 'Usages mensuels',
                'ordering': ['-year', '-month'],
                'unique_together': {('organization', 'year', 'month')},
            },
        ),
        migrations.AddIndex(
            model_name='monthlyusage',
            index=models.Index(
                fields=['organization', '-year', '-month'],
                name='procedures__organiz_7c2d_idx',
            ),
        ),
    ]
