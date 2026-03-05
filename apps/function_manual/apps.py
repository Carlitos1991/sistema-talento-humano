from django.apps import AppConfig


class FunctionManualConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'function_manual'
    verbose_name = 'Manual de funciones'

    def ready(self):
        import function_manual.signals