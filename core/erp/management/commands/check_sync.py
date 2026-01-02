from django.core.management.base import BaseCommand
from core.erp.models import Product
from django.db import transaction
from core.erp.models import Category, Supplier, Company


class Command(BaseCommand):
    help = "Verifica y fuerza la sincronización de productos con cambios de stock"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=== Verificación de sincronización de productos ==="))
        
        # 1. Verificar productos pendientes
        local_qs = Product.objects.using('default').filter(synced_to_server=False)
        total = local_qs.count()
        
        if total == 0:
            self.stdout.write(self.style.SUCCESS("✅ No hay productos pendientes de sincronizar"))
            return
        
        self.stdout.write(self.style.WARNING(f"⚠️  Hay {total} productos pendientes de sincronizar"))
        
        # 2. Mostrar algunos productos pendientes
        self.stdout.write("\nProductos pendientes (primeros 10):")
        for i, prod in enumerate(local_qs[:10]):
            self.stdout.write(f"  {i+1}. {prod.name[:40]:<40} | Stock: {prod.stock:>8} | ID: {prod.id}")
        
        if total > 10:
            self.stdout.write(f"  ... y {total - 10} más")
        
        # 3. Intentar sincronizar
        self.stdout.write(f"\n🔄 Iniciando sincronización de {total} productos...")
        
        synced = 0
        errors = 0
        
        for prod in local_qs:
            try:
                # Resolver empresa remota
                remote_company = None
                if prod.company_id:
                    local_company = Company.objects.using('default').filter(pk=prod.company_id).first()
                    if local_company:
                        if local_company.cuit:
                            remote_company = Company.objects.using('remote').filter(cuit=local_company.cuit).first()
                        if not remote_company:
                            remote_company = Company.objects.using('remote').filter(name=local_company.name).first()

                if prod.company_id and not remote_company:
                    errors += 1
                    self.stderr.write(f"❌ Producto {prod.id}: empresa local {prod.company_id} no encontrada en remoto")
                    continue

                with transaction.atomic(using='remote'):
                    # Asegurar categoría en remoto
                    remote_cat = None
                    if prod.cat_id:
                        remote_cat, _ = Category.objects.using('remote').get_or_create(
                            name=prod.cat.name,
                            defaults={'desc': prod.cat.desc},
                        )

                    # Resolver proveedor
                    remote_supplier = None
                    if prod.supplier_id:
                        if Supplier.objects.using('remote').filter(pk=prod.supplier_id).exists():
                            remote_supplier = Supplier.objects.using('remote').get(pk=prod.supplier_id)

                    # Usar code como clave natural
                    lookup = {}
                    if prod.code:
                        lookup['code'] = prod.code
                    else:
                        lookup['name'] = prod.name

                    remote_prod, created = Product.objects.using('remote').get_or_create(
                        **lookup,
                        defaults={
                            'company_id': remote_company.id if remote_company else None,
                            'name': prod.name,
                            'cat': remote_cat,
                            'supplier': remote_supplier,
                            'cost_price': prod.cost_price,
                            'pvp': prod.pvp,
                            'iva_rate': prod.iva_rate,
                            'pvp_final': prod.pvp_final,
                            'unit': prod.unit,
                            'stock': prod.stock,
                        },
                    )
                    
                    if not created:
                        # Actualizar producto existente
                        if remote_company:
                            remote_prod.company_id = remote_company.id
                        remote_prod.name = prod.name
                        if remote_cat:
                            remote_prod.cat = remote_cat
                        remote_prod.supplier = remote_supplier
                        remote_prod.cost_price = prod.cost_price
                        remote_prod.pvp = prod.pvp
                        remote_prod.iva_rate = prod.iva_rate
                        remote_prod.pvp_final = prod.pvp_final
                        remote_prod.unit = prod.unit
                        remote_prod.stock = prod.stock
                        remote_prod.save()

                # Marcar como sincronizado
                Product.objects.using('default').filter(pk=prod.pk).update(synced_to_server=True)
                synced += 1
                
                if synced % 10 == 0:
                    self.stdout.write(f"   Progreso: {synced}/{total}")
                    
            except Exception as e:
                errors += 1
                self.stderr.write(f"❌ Error sincronizando producto {prod.id}: {e}")

        # 4. Resumen
        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Sincronización completada:\n"
            f"   • Sincronizados: {synced}\n"
            f"   • Errores: {errors}\n"
            f"   • Total: {total}"
        ))
        
        if errors > 0:
            self.stdout.write(self.style.WARNING("⚠️  Algunos productos no se sincronizaron. Revisa los errores arriba."))
        
        # 5. Verificar estado final
        remaining = Product.objects.using('default').filter(synced_to_server=False).count()
        if remaining == 0:
            self.stdout.write(self.style.SUCCESS("🎉 Todos los productos están sincronizados"))
        else:
            self.stdout.write(self.style.WARNING(f"⚠️  Quedan {remaining} productos pendientes"))
