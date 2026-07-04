from django.core.management.base import BaseCommand
from django.db import transaction, connections
from django.contrib import messages
from django.utils import timezone
from core.erp.models import Client, Sale, Product, Category, Supplier, Expense, CashRegister, EmployeeAccountSale, PriceList, PriceListProduct, Company
from core.user.models import User

class Command(BaseCommand):
    help = 'Sincronización inteligente que evita duplicados con backups'

    def handle(self, *args, **options):
        if 'remote' not in connections:
            self.stdout.write(self.style.ERROR('No hay conexión a base de datos remota configurada'))
            return

        self.stdout.write(self.style.NOTICE("Iniciando sincronización inteligente..."))
        
        try:
            # 1) Sincronizar clientes
            self.sync_clients()
            
            # 2) Sincronizar ventas
            self.sync_sales()
            
            # 3) Sincronizar productos
            self.sync_products()
            
            # 4) Sincronizar gastos
            self.sync_expenses()
            
            # 5) Sincronizar cierres de caja
            self.sync_cash_registers()
            
            # 6) Sincronizar cuentas corrientes de empleados
            self.sync_employee_accounts()
            
            # 7) Sincronizar listas de precios
            self.sync_price_lists()
            
            self.stdout.write(self.style.SUCCESS("Sincronización inteligente completada"))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error en sincronización: {e}"))

    def sync_clients(self):
        """Sincronizar clientes evitando duplicados"""
        self.stdout.write("Sincronizando clientes...")
        
        # Obtener todos los clientes locales (no solo los no sincronizados)
        local_clients = Client.objects.using('default').all()
        synced_count = 0
        
        for client in local_clients:
            try:
                with transaction.atomic(using='remote'):
                    # Buscar cliente remoto por DNI o nombre
                    qs = Client.objects.using('remote')
                    if client.dni:
                        remote_qs = qs.filter(dni=client.dni)
                    else:
                        remote_qs = qs.filter(names=client.names, surnames=client.surnames)

                    remote_client = remote_qs.first()
                    created = remote_client is None

                    if created:
                        remote_client = Client.objects.using('remote').create(
                            company_id=client.company_id,
                            names=client.names,
                            surnames=client.surnames,
                            dni=client.dni,
                            date_birthday=client.date_birthday,
                            address=client.address,
                            gender=client.gender,
                            is_active=client.is_active,
                        )
                    else:
                        remote_client.company_id = client.company_id
                        remote_client.names = client.names
                        remote_client.surnames = client.surnames
                        remote_client.date_birthday = client.date_birthday
                        remote_client.address = client.address
                        remote_client.gender = client.gender
                        remote_client.is_active = client.is_active
                        remote_client.save(using='remote')

                    # Marcar como sincronizado
                    client.synced_to_server = True
                    client.save(using='default')
                    synced_count += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error sincronizando cliente {client.id}: {e}"))
        
        self.stdout.write(f"Clientes sincronizados: {synced_count}")

    def sync_sales(self):
        """Sincronizar ventas evitando duplicados"""
        self.stdout.write("Sincronizando ventas...")
        
        local_sales = Sale.objects.using('default').all()
        synced_count = 0
        
        for sale in local_sales:
            try:
                with transaction.atomic(using='remote'):
                    # Verificar si ya existe venta con misma fecha, monto y cliente
                    existing = Sale.objects.using('remote').filter(
                        date_joined=sale.date_joined,
                        total=sale.total,
                        cli_id=sale.cli_id
                    ).only(
                        'id', 'company_id', 'cli_id', 'date_joined', 'subtotal', 
                        'total', 'payment_method', 'is_invoiced', 'invoice_number',
                        'invoice_pos', 'invoice_type', 'local_timezone'
                    ).first()
                    
                    if existing:
                        # Ya existe, marcar como sincronizada
                        sale.synced_to_server = True
                        sale.save(using='default')
                        synced_count += 1
                        continue
                    
                    # Crear venta remota
                    # Mantener el horario local original de la venta
                    # Preservamos el date_joined tal como está para mantener la hora local del POS
                    remote_sale = Sale.objects.using('remote').create(
                        company_id=sale.company_id,
                        cli_id=sale.cli_id,
                        date_joined=sale.date_joined,
                        local_timezone=sale.local_timezone,
                        subtotal=sale.subtotal,
                        iva=sale.iva,
                        total=sale.total,
                        payment_method=sale.payment_method,
                        invoice_number=sale.invoice_number,
                        invoice_pos=sale.invoice_pos,
                        invoice_type=sale.invoice_type,
                        is_invoiced=sale.is_invoiced,
                        synced_to_server=True
                    )
                    
                    # Marcar como sincronizada
                    sale.synced_to_server = True
                    sale.save(using='default')
                    synced_count += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error sincronizando venta {sale.id}: {e}"))
        
        self.stdout.write(f"Ventas sincronizadas: {synced_count}")

    def sync_products(self):
        """Sincronizar productos evitando duplicados"""
        self.stdout.write("Sincronizando productos...")
        
        local_products = Product.objects.using('default').all()
        synced_count = 0
        
        for product in local_products:
            try:
                # Buscar por code, nombre exacto, iexact, icontains
                remote_product = None
                if product.code:
                    remote_product = Product.objects.using('remote').filter(code=product.code).first()
                if not remote_product:
                    remote_product = Product.objects.using('remote').filter(name=product.name).first()
                if not remote_product:
                    remote_product = Product.objects.using('remote').filter(name__iexact=product.name).first()
                if not remote_product:
                    remote_product = Product.objects.using('remote').filter(name__icontains=product.name.strip()).first()

                if remote_product:
                    # Actualizar producto existente
                    remote_product.company_id = product.company_id
                    remote_product.name = product.name
                    remote_product.cat_id = product.cat_id
                    remote_product.supplier_id = product.supplier_id
                    remote_product.pvp = product.pvp
                    remote_product.iva_rate = product.iva_rate
                    remote_product.pvp_final = product.pvp_final
                    remote_product.unit = product.unit
                    remote_product.stock = product.stock
                    remote_product.synced_to_server = True
                    remote_product.save(using='remote')
                else:
                    # Crear nuevo producto (con fallback si duplicate key)
                    try:
                        Product.objects.using('remote').create(
                            company_id=product.company_id,
                            name=product.name,
                            cat_id=product.cat_id,
                            supplier_id=product.supplier_id,
                            pvp=product.pvp,
                            iva_rate=product.iva_rate,
                            pvp_final=product.pvp_final,
                            unit=product.unit,
                            stock=product.stock,
                            synced_to_server=True,
                        )
                    except Exception as create_err:
                        if 'duplicate key' in str(create_err).lower() or 'unique constraint' in str(create_err).lower():
                            remote_product = Product.objects.using('remote').filter(name__icontains=product.name.strip()).first()
                            if remote_product:
                                remote_product.company_id = product.company_id
                                remote_product.name = product.name
                                remote_product.cat_id = product.cat_id
                                remote_product.supplier_id = product.supplier_id
                                remote_product.pvp = product.pvp
                                remote_product.iva_rate = product.iva_rate
                                remote_product.pvp_final = product.pvp_final
                                remote_product.unit = product.unit
                                remote_product.stock = product.stock
                                remote_product.synced_to_server = True
                                remote_product.save(using='remote')
                            else:
                                raise
                        else:
                            raise

                # Marcar como sincronizado
                product.synced_to_server = True
                product.save(using='default')
                synced_count += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error sincronizando producto {product.id}: {e}"))
        
        self.stdout.write(f"Productos sincronizados: {synced_count}")

    def sync_expenses(self):
        """Sincronizar gastos evitando duplicados"""
        self.stdout.write("Sincronizando gastos...")
        
        local_expenses = Expense.objects.using('default').all()
        synced_count = 0
        
        for expense in local_expenses:
            try:
                with transaction.atomic(using='remote'):
                    # Verificar si ya existe por fecha, monto y descripción
                    existing = Expense.objects.using('remote').filter(
                        date=expense.date,
                        amount=expense.amount,
                        description=expense.description
                    ).first()
                    
                    if existing:
                        # Ya existe, marcar como sincronizado
                        expense.synced_to_server = True
                        expense.save(using='default')
                        synced_count += 1
                        continue
                    
                    # Crear gasto remoto
                    remote_expense = Expense.objects.using('remote').create(
                        company_id=expense.company_id,
                        date=expense.date,
                        amount=expense.amount,
                        description=expense.description,
                        category=expense.category,
                        payment_type=expense.payment_type,
                        receipt_number=expense.receipt_number,
                        notes=expense.notes,
                        synced_to_server=True
                    )
                    
                    # Marcar como sincronizado
                    expense.synced_to_server = True
                    expense.save(using='default')
                    synced_count += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error sincronizando gasto {expense.id}: {e}"))
        
        self.stdout.write(f"Gastos sincronizados: {synced_count}")

    def sync_cash_registers(self):
        """Sincronizar cierres de caja evitando duplicados"""
        self.stdout.write("Sincronizando cierres de caja...")
        
        local_registers = CashRegister.objects.using('default').all()
        synced_count = 0
        
        for register in local_registers:
            try:
                with transaction.atomic(using='remote'):
                    # Verificar si ya existe por fecha y usuario
                    existing = CashRegister.objects.using('remote').filter(
                        date=register.date,
                        user_id=register.user_id
                    ).first()
                    
                    if existing:
                        # Ya existe, marcar como sincronizado
                        register.is_synced = True
                        register.save(using='default')
                        synced_count += 1
                        continue
                    
                    # Crear cierre remoto
                    remote_register = CashRegister.objects.using('remote').create(
                        company_id=register.company_id,
                        user_id=register.user_id,
                        date=register.date,
                        opening_balance=register.opening_balance,
                        closing_balance=register.closing_balance,
                        cash_sales=register.cash_sales,
                        card_sales=register.card_sales,
                        transfer_sales=register.transfer_sales,
                        mp_sales=register.mp_sales,
                        expenses=register.expenses,
                        notes=register.notes,
                        is_closed=register.is_closed,
                        is_synced=True
                    )
                    
                    # Marcar como sincronizado
                    register.is_synced = True
                    register.save(using='default')
                    synced_count += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error sincronizando cierre {register.id}: {e}"))
        
        self.stdout.write(f"Cierres de caja sincronizados: {synced_count}")
    
    def sync_employee_accounts(self):
        """Sincronizar cuentas corrientes de empleados evitando duplicados"""
        self.stdout.write("Sincronizando cuentas corrientes de empleados...")
        
        local_accounts = EmployeeAccountSale.objects.using('default').all()
        synced_count = 0
        
        for account in local_accounts:
            try:
                with transaction.atomic(using='remote'):
                    # Verificar si ya existe cuenta corriente con misma fecha, monto y empleado
                    existing = EmployeeAccountSale.objects.using('remote').filter(
                        date_joined=account.date_joined,
                        total=account.total,
                        subtotal=account.subtotal,
                        employee_id=account.employee_id,
                        notes=account.notes
                    ).only(
                        'id', 'company_id', 'employee_id', 'date_joined', 'subtotal', 
                        'total', 'notes', 'is_paid', 'paid_date', 'local_timezone'
                    ).first()
                    
                    if existing:
                        # Ya existe, marcar como sincronizada
                        account.synced_to_server = True
                        account.save(using='default')
                        synced_count += 1
                        continue
                    
                    # Crear cuenta corriente remota
                    remote_account = EmployeeAccountSale.objects.using('remote').create(
                        company_id=account.company_id,
                        employee_id=account.employee_id,
                        date_joined=account.date_joined,
                        local_timezone=account.local_timezone,
                        subtotal=account.subtotal,
                        iva=account.iva,  # Para empleados, el IVA siempre es 0
                        total=account.total,
                        notes=account.notes,
                        is_paid=account.is_paid,
                        paid_date=account.paid_date,
                        related_sale_id=account.related_sale_id,
                        synced_to_server=True
                    )
                    
                    # Marcar como sincronizada
                    account.synced_to_server = True
                    account.save(using='default')
                    synced_count += 1
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error sincronizando cuenta corriente {account.id}: {e}"))
        
        self.stdout.write(f"Cuentas corrientes sincronizadas: {synced_count}")

    def sync_price_lists(self):
        """Sincronizar listas de precios y sus overrides evitando duplicados"""
        self.stdout.write("Sincronizando listas de precios...")

        local_lists = PriceList.objects.using('default').all().prefetch_related('products')
        synced_count = 0
        list_id_map = {}

        for pl in local_lists:
            try:
                # Resolver empresa remota
                remote_company = None
                if pl.company_id:
                    local_company = Company.objects.using('default').filter(pk=pl.company_id).first()
                    if local_company:
                        if local_company.cuit:
                            remote_company = Company.objects.using('remote').filter(cuit=local_company.cuit).first()
                        if not remote_company:
                            remote_company = Company.objects.using('remote').filter(name=local_company.name).first()

                # Buscar lista existente: por nombre + empresa, luego por nombre iexact
                remote_pl = None
                if remote_company:
                    remote_pl = PriceList.objects.using('remote').filter(
                        name=pl.name, company_id=remote_company.id
                    ).first()
                if not remote_pl:
                    remote_pl = PriceList.objects.using('remote').filter(name__iexact=pl.name).first()

                if remote_pl:
                    if remote_company:
                        remote_pl.company_id = remote_company.id
                    remote_pl.name = pl.name
                    remote_pl.discount_percentage = pl.discount_percentage
                    remote_pl.is_active = pl.is_active
                    remote_pl.save(using='remote')
                else:
                    remote_pl = PriceList.objects.using('remote').create(
                        company_id=remote_company.id if remote_company else None,
                        name=pl.name,
                        discount_percentage=pl.discount_percentage,
                        is_active=pl.is_active,
                    )

                list_id_map[pl.id] = remote_pl.id
                synced_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error sincronizando lista de precios {pl.id}: {e}"))

        self.stdout.write(f"Listas de precios sincronizadas: {synced_count}")

        # Sincronizar overrides (PriceListProduct)
        local_plps = PriceListProduct.objects.using('default').select_related('product', 'price_list')
        plp_count = 0

        for plp in local_plps:
            try:
                remote_pl_id = list_id_map.get(plp.price_list_id)
                if not remote_pl_id:
                    continue

                # Buscar producto remoto por code o nombre
                remote_product = None
                if plp.product.code:
                    remote_product = Product.objects.using('remote').filter(code=plp.product.code).first()
                if not remote_product:
                    remote_product = Product.objects.using('remote').filter(name=plp.product.name).first()
                if not remote_product:
                    remote_product = Product.objects.using('remote').filter(name__iexact=plp.product.name).first()

                if not remote_product:
                    continue

                # Buscar override existente
                remote_plp = PriceListProduct.objects.using('remote').filter(
                    price_list_id=remote_pl_id,
                    product_id=remote_product.id
                ).first()

                if remote_plp:
                    remote_plp.fixed_price = plp.fixed_price
                    remote_plp.discount_override = plp.discount_override
                    remote_plp.is_exception = plp.is_exception
                    remote_plp.save(using='remote')
                else:
                    PriceListProduct.objects.using('remote').create(
                        price_list_id=remote_pl_id,
                        product_id=remote_product.id,
                        fixed_price=plp.fixed_price,
                        discount_override=plp.discount_override,
                        is_exception=plp.is_exception,
                    )

                plp_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error sincronizando override {plp.id}: {e}"))

        self.stdout.write(f"Overrides de listas sincronizados: {plp_count}")
