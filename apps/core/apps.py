from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    # ANTES DECÍA: name = 'core'
    # DEBE DECIR:
    name = 'apps.core'