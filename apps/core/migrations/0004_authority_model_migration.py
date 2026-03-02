# Generated manually on 2026-03-02

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def copy_authorities_data(apps, schema_editor):
    """Copia datos de Authorities a Authority"""
    Authorities = apps.get_model('core', 'Authorities')
    Authority = apps.get_model('core', 'Authority')
    
    for old_auth in Authorities.objects.all():
        Authority.objects.create(
            id=old_auth.id,
            name=old_auth.name,
            position=old_auth.charge,
            is_active=old_auth.status if hasattr(old_auth, 'status') else True,
            created_at=old_auth.created_at if hasattr(old_auth, 'created_at') else None,
            updated_at=old_auth.updated_at if hasattr(old_auth, 'updated_at') else None,
            created_by=old_auth.created_by if hasattr(old_auth, 'created_by') else None,
            updated_by=old_auth.updated_by if hasattr(old_auth, 'updated_by') else None,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_fix_timezone_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Crear el nuevo modelo Authority
        migrations.CreateModel(
            name='Authority',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True, verbose_name='Estado')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Última Modificación')),
                ('name', models.CharField(max_length=255, verbose_name='Nombre Completo')),
                ('position', models.CharField(max_length=255, verbose_name='Cargo')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='Creado por')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='%(app_label)s_%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='Actualizado por')),
            ],
            options={
                'verbose_name': 'Autoridad',
                'verbose_name_plural': 'Autoridades',
                'ordering': ['name'],
            },
        ),
        # 2. Copiar datos de Authorities a Authority
        migrations.RunPython(copy_authorities_data, reverse_code=migrations.RunPython.noop),
        # 3. Eliminar el modelo antiguo Authorities
        migrations.DeleteModel(
            name='Authorities',
        ),
    ]
