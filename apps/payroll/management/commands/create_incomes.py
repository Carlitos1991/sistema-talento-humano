from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Crea los incomes DECIMO_TERCERO y DECIMO_CUARTO si no existen (dry-run por defecto)."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Crear realmente los registros en la base de datos.')
        parser.add_argument('--account-code', type=str, help='Código de la cuenta contable a asignar (opcional).')

    def handle(self, *args, **options):
        from payroll.models import Income
        try:
            from accounting.models import Account
        except Exception:
            Account = None

        do_apply = options.get('apply', False)
        acct_code = options.get('account_code')
        account = None

        if acct_code and Account is not None:
            try:
                account = Account.objects.get(code=acct_code)
            except Account.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Cuenta con código '{acct_code}' no encontrada. Se continuará sin asignar cuenta."))

        targets = [
            {'code': 'DECIMO_TERCERO', 'name': 'Décimo Tercero', 'description': 'Décimo tercero prorrateado'},
            {'code': 'DECIMO_CUARTO', 'name': 'Décimo Cuarto', 'description': 'Décimo cuarto prorrateado'},
        ]

        for t in targets:
            existing = Income.objects.filter(code=t['code']).first()
            if existing:
                # Si existe y se pasó account_code, intentar asignarla si no tiene cuenta
                if account is not None and getattr(existing, 'account_id', None) is None and do_apply:
                    existing.account = account
                    existing.save()
                    self.stdout.write(self.style.SUCCESS(f"Existente: {t['code']} (id={existing.id}) - cuenta asignada."))
                else:
                    self.stdout.write(self.style.SUCCESS(f"Existente: {t['code']} (id={existing.id}) - se omite."))
                continue

            self.stdout.write(f"Preparando creación: {t['code']} - {t['name']}")
            if not do_apply:
                self.stdout.write(self.style.WARNING("Dry-run: use --apply para crear los registros."))
                continue

            inc = Income.objects.create(
                name=t['name'],
                code=t['code'],
                description=t['description'],
                is_active=True,
                account=account if account is not None else None
            )
            self.stdout.write(self.style.SUCCESS(f"Creado: {t['code']} (id={inc.id})"))

        self.stdout.write(self.style.SUCCESS('Comando finalizado.'))
