from django.core.management.base import BaseCommand
from django.db import transaction
from apps.core.models import Catalog, CatalogItem


class Command(BaseCommand):
    help = 'Crea los catálogos base y sus items para el módulo de Personas'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Iniciando carga de catálogos...'))

        # Estructura de datos: CÓDIGO_CATALOGO: (Nombre Visible, [Lista de items (código, nombre)])
        data = {
            'DOCUMENT_TYPES': {
                'name': 'Tipos de Documento',
                'items': [
                    ('CEDULA', 'Cédula de Identidad'),
                    ('RUC', 'RUC (Personas Naturales)'),
                    ('PASAPORTE', 'Pasaporte'),
                ]
            },
            'GENDERS': {
                'name': 'Género',
                'items': [
                    ('MASCULINO', 'Masculino'),
                    ('FEMENINO', 'Femenino'),
                    ('LGBTI', 'LGBTI+'),
                    ('OTRO', 'Otro')
                ]
            },
            'MARITAL_STATUSES': {
                'name': 'Estado Civil',
                'items': [
                    ('SOLTERO', 'Soltero/a'),
                    ('CASADO', 'Casado/a'),
                    ('DIVORCIADO', 'Divorciado/a'),
                    ('VIUDO', 'Viudo/a'),
                    ('UNION_HECHO', 'Unión de Hecho')
                ]
            },
            'BLOOD_TYPES': {
                'name': 'Tipo de Sangre',
                'items': [
                    ('A_POS', 'A+'),
                    ('A_NEG', 'A-'),
                    ('B_POS', 'B+'),
                    ('B_NEG', 'B-'),
                    ('AB_POS', 'AB+'),
                    ('AB_NEG', 'AB-'),
                    ('O_POS', 'O+'),
                    ('O_NEG', 'O-'),
                ]
            },
            'DISABILITY_TYPES': {
                'name': 'Tipos de Discapacidad',
                'items': [
                    ('FISICA', 'Física'),
                    ('INTELECTUAL', 'Intelectual'),
                    ('AUDITIVA', 'Auditiva'),
                    ('VISUAL', 'Visual'),
                    ('PSICOSOCIAL', 'Psicosocial'),
                    ('MULTIPLE', 'Múltiple'),
                ]
            },
            'RELATIONSHIPS': {
                'name': 'Parentesco / Relación',
                'items': [
                    ('PADRE_MADRE', 'Padre / Madre'),
                    ('HIJO', 'Hijo / Hija'),
                    ('CONYUGE', 'Cónyuge / Pareja'),
                    ('HERMANO', 'Hermano / Hermana'),
                    ('TIO', 'Tío / Tía'),
                    ('SOBRINO', 'Sobrino / Sobrina'),
                    ('ABUELO', 'Abuelo / Abuela'),
                    ('AMIGO', 'Amigo / Conocido'),
                ]
            },
            'PERSON_STATUS': {
                'name': 'Estado de la Persona',
                'items': [
                    ('ACTIVO', 'Activo'),
                    ('INACTIVO', 'Inactivo'),
                    ('SUSPENDIDO', 'Suspendido'),
                    ('LICENCIA', 'Licencia / Permiso'),
                ]
            }
        }

        try:
            with transaction.atomic():
                for cat_code, cat_data in data.items():
                    # 1. Crear o recuperar el Catálogo Padre
                    catalog, created = Catalog.objects.get_or_create(
                        code=cat_code,
                        defaults={'name': cat_data['name']}
                    )

                    if created:
                        self.stdout.write(self.style.SUCCESS(f'Catálogo creado: {cat_data["name"]}'))
                    else:
                        self.stdout.write(f'Catálogo existente: {cat_data["name"]}')

                    # 2. Crear los Items
                    for item_code, item_name in cat_data['items']:
                        item, item_created = CatalogItem.objects.get_or_create(
                            catalog=catalog,
                            code=item_code,
                            defaults={'name': item_name}
                        )
                        if item_created:
                            # self.stdout.write(f' - Item creado: {item_name}')
                            pass

            self.stdout.write(
                self.style.SUCCESS('\n¡Proceso finalizado con éxito! Todos los catálogos han sido cargados.'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error al poblar catálogos: {str(e)}'))