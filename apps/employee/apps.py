from django.apps import AppConfig

class EmployeeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.employee'

    def ready(self):
        import apps.employee.signals  # Importar signals aquí