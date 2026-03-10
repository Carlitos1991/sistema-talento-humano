import csv
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from budget.models import BudgetLine
from institution.models import AdministrativeUnit
from payroll.models import RubroBudgetMapping


def normalize_rubro_type(value):
    if not value:
        return None
    v = value.strip().upper()
    if v in ('INCOME', 'INGRESO', 'INGRESOS'):
        return 'INCOME'
    if v in ('DEDUCTION', 'DESCUENTO', 'DEDUCCION', 'DEDUCCIONES'):
        return 'DEDUCTION'
    return v


class Command(BaseCommand):
    help = 'Importa mapeos rubro->partida desde CSV. Columnas: rubro_type,rubro_code,budget_line_code,administrative_unit_code'

    def add_arguments(self, parser):
        parser.add_argument('-f', '--file', required=True, help='Ruta al archivo CSV')
        parser.add_argument('--encoding', default='utf-8', help='Encoding del archivo')
        parser.add_argument('--delimiter', default=',', help='Delimitador CSV')
        parser.add_argument('--apply', action='store_true', help='Aplicar cambios (por defecto dry-run)')

    def handle(self, *args, **options):
        path = options['file']
        encoding = options['encoding']
        delim = options['delimiter']
        do_apply = options['apply']

        created = 0
        updated = 0
        skipped = 0
        errors = 0
        rows = []

        try:
            with open(path, encoding=encoding, newline='') as fh:
                reader = csv.DictReader(fh, delimiter=delim)
                for i, row in enumerate(reader, start=1):
                    rows.append((i, row))
        except Exception as e:
            raise CommandError(f"No se pudo leer el archivo: {e}")

        self.stdout.write(self.style.NOTICE(f"Procesando {len(rows)} filas (apply={do_apply})"))

        for lineno, row in rows:
            try:
                rt = normalize_rubro_type(row.get('rubro_type') or row.get('type') or '')
                rc = (row.get('rubro_code') or row.get('rubro') or row.get('code') or '').strip()
                bl_code = (row.get('budget_line_code') or row.get('partida') or '').strip()
                au_code = (row.get('administrative_unit_code') or row.get('unit_code') or '').strip()

                if not rt or not rc or not bl_code:
                    self.stdout.write(self.style.WARNING(f"Fila {lineno}: valores insuficientes, saltando: {row}"))
                    skipped += 1
                    continue

                admin_unit = None
                if au_code:
                    admin_unit = AdministrativeUnit.objects.filter(code__iexact=au_code).first()
                    if not admin_unit:
                        self.stdout.write(self.style.WARNING(f"Fila {lineno}: unidad '{au_code}' no encontrada, se ignorará la unidad."))

                # Buscar BudgetLine: intento exacto por code
                candidates = BudgetLine.objects.filter(code__iexact=bl_code)
                if not candidates.exists():
                    # intento contains como fallback
                    candidates = BudgetLine.objects.filter(code__icontains=bl_code)

                if candidates.count() > 1 and admin_unit:
                    # priorizar por unidad administrativa
                    candidates = candidates.filter(administrative_unit=admin_unit)

                if not candidates.exists():
                    self.stdout.write(self.style.ERROR(f"Fila {lineno}: No se encontró BudgetLine para código '{bl_code}'"))
                    errors += 1
                    continue

                if candidates.count() > 1:
                    # hay duplicados; elegir la primera pero avisar
                    chosen = candidates.first()
                    self.stdout.write(self.style.WARNING(f"Fila {lineno}: múltiples BudgetLine para '{bl_code}', usando id={chosen.id}"))
                else:
                    chosen = candidates.first()

                # Chequear si mapeo ya existe
                existing = RubroBudgetMapping.objects.filter(rubro_type=rt, rubro_code__iexact=rc, administrative_unit=admin_unit).first()
                if existing:
                    if existing.budget_line_id == chosen.id:
                        self.stdout.write(self.style.NOTICE(f"Fila {lineno}: mapeo ya existe (sin cambios): {rc}->{chosen.code}"))
                        skipped += 1
                    else:
                        self.stdout.write(self.style.WARNING(f"Fila {lineno}: mapeo existente diferente. Actualizar {existing.budget_line.code} -> {chosen.code}"))
                        if do_apply:
                            existing.budget_line = chosen
                            existing.save()
                            updated += 1
                        else:
                            skipped += 1
                    continue

                # Crear mapeo (o dry-run)
                self.stdout.write(self.style.SUCCESS(f"Fila {lineno}: mapear {rt} {rc} -> {chosen.code} (admin_unit={admin_unit.code if admin_unit else 'N/A'})"))
                if do_apply:
                    with transaction.atomic():
                        RubroBudgetMapping.objects.create(
                            rubro_type=rt,
                            rubro_code=rc,
                            budget_line=chosen,
                            administrative_unit=admin_unit,
                            is_active=True
                        )
                        created += 1
                else:
                    # dry-run
                    skipped += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Fila {lineno}: error procesando fila: {e}"))
                errors += 1

        # resumen
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Resumen: creadas={created} actualizadas={updated} saltadas={skipped} errores={errors}"))
        if not do_apply:
            self.stdout.write(self.style.NOTICE("Modo dry-run — ninguna modificación fue persistida. Use --apply para aplicar cambios."))
