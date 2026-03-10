from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crea una cuenta contable ficticia con código y nombre proporcionados."

    def add_arguments(self, parser):
        parser.add_argument('--code', required=True, help='Código único de la cuenta')
        parser.add_argument('--name', required=True, help='Nombre de la cuenta')
        parser.add_argument('--parent', required=False, help='Código de cuenta padre (opcional)')
        parser.add_argument('--type', required=False, choices=['ASSET','LIABILITY','EQUITY','INCOME','EXPENSE'], help='Tipo de cuenta (por defecto EXPENSE)')

    def handle(self, *args, **options):
        from accounting.models import Account

        code = options.get('code')
        name = options.get('name')
        parent_code = options.get('parent')

        acct_type = options.get('type') or 'EXPENSE'

        existing = Account.objects.filter(code=code).first()
        if existing:
            self.stdout.write(self.style.SUCCESS(f"Cuenta existente: {code} (id={existing.id})"))
            return

        acct = Account.objects.create(code=code, name=name, type=acct_type)
        self.stdout.write(self.style.SUCCESS(f"Cuenta creada: {code} (id={acct.id})"))
