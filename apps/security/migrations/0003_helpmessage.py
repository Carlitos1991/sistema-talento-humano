from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('security', '0002_alter_usersession_options_usersession_last_activity_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='HelpMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True, verbose_name='Estado')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Última Modificación')),
                ('subject', models.CharField(max_length=255, verbose_name='Asunto')),
                ('detail', models.TextField(verbose_name='Detalle')),
                ('attachment', models.FileField(blank=True, null=True, upload_to='help_messages/attachments/', verbose_name='Anexo')),
                ('status', models.CharField(choices=[('sent', 'Enviado'), ('read', 'Leído'), ('attended', 'Atendido')], default='sent', max_length=20, verbose_name='Estado')),
                ('read_at', models.DateTimeField(blank=True, null=True, verbose_name='Fecha de lectura')),
                ('attended_at', models.DateTimeField(blank=True, null=True, verbose_name='Fecha de atención')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='security_helpmessage_created', to=settings.AUTH_USER_MODEL, verbose_name='Creado por')),
                ('original_message', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='replies', to='security.helpmessage', verbose_name='Mensaje original')),
                ('recipient_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='help_messages_received', to=settings.AUTH_USER_MODEL, verbose_name='Destinatario')),
                ('sender_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='help_messages_sent', to=settings.AUTH_USER_MODEL, verbose_name='Solicitante')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='security_helpmessage_updated', to=settings.AUTH_USER_MODEL, verbose_name='Actualizado por')),
            ],
            options={
                'verbose_name': 'Mensaje de Ayuda',
                'verbose_name_plural': 'Mensajes de Ayuda',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='helpmessage',
            index=models.Index(fields=['recipient_user', 'status', '-created_at'], name='security_he_recipient_2d3f9c_idx'),
        ),
        migrations.AddIndex(
            model_name='helpmessage',
            index=models.Index(fields=['sender_user', '-created_at'], name='security_he_sender_54b02f_idx'),
        ),
    ]
