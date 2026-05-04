from django.core.management.base import BaseCommand
from django.db.models import Count
from biometric.models import AttendanceRegistry


class Command(BaseCommand):
    help = 'Limpia marcaciones duplicadas (mismo empleado y misma fecha/hora)'

    def handle(self, *args, **options):
        # 1. Identificar los grupos que tienen marcaciones duplicadas
        # Cambiamos 'timestamp' por 'registry_date'
        duplicados = AttendanceRegistry.objects.values('employee', 'registry_date') \
            .annotate(total=Count('id')) \
            .filter(total__gt=1)

        total_borrados = 0
        self.stdout.write(f"🔍 Buscando duplicados en la columna 'registry_date'...")
        self.stdout.write(f"📊 Encontrados {duplicados.count()} grupos con registros repetidos.")

        for registro in duplicados:
            # 2. Obtener todos los IDs de este grupo específico
            # Cambiamos 'timestamp' por 'registry_date'
            ids = AttendanceRegistry.objects.filter(
                employee_id=registro['employee'],
                registry_date=registro['registry_date']
            ).order_by('id').values_list('id', flat=True)

            # 3. Mantener el primero de la lista (index 0) y preparar el resto para borrar
            ids_a_borrar = ids[1:]

            # 4. Borrar los duplicados
            AttendanceRegistry.objects.filter(id__in=ids_a_borrar).delete()
            total_borrados += len(ids_a_borrar)

        if total_borrados > 0:
            self.stdout.write(
                self.style.SUCCESS(f"✅ Limpieza completada. Se eliminaron {total_borrados} registros duplicados."))
        else:
            self.stdout.write(self.style.SUCCESS("✅ No se encontraron registros duplicados para borrar."))