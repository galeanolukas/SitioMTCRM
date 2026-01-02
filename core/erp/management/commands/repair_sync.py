from django.core.management.base import BaseCommand
from core.erp.models import Product, Company, Category, Supplier, SyncLog
from django.db import transaction, connections
from django.utils import timezone
from datetime import timedelta
import traceback


class Command(BaseCommand):
    help = "Diagnostica y repara errores de sincronización"

    def add_arguments(self, parser):
        parser.add_argument(
            '--repair',
            action='store_true',
            help='Ejecuta reparaciones automát además de diagnosticar',
        )
        parser.add_argument(
            '--force-resync',
            action='store_true',
            help='Fuerza la resincronización completa de todos los productos',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=== DIAGNÓSTICO Y REPARACIÓN DE SINCRONIZACIÓN ==="))
        
        repair_mode = options.get('repair', False)
        force_resync = options.get('force_resync', False)
        
        if force_resync:
            self.stdout.write(self.style.WARNING("⚠️  Modo de resincronización forzada activado"))
        
        # 1. Verificar conexión a BD remota
        self.stdout.write("\n1. 🔍 Verificando conexión a base de datos remota...")
        remote_ok = self._check_remote_connection()
        
        if not remote_ok:
            self.stdout.write(self.style.ERROR("❌ No hay conexión a BD remota. Abortando."))
            return
        
        # 2. Analizar inconsistencias
        self.stdout.write("\n2. 🔍 Analizando inconsistencias de datos...")
        issues = self._analyze_inconsistencies()
        
        # 3. Verificar productos huérfanos
        self.stdout.write("\n3. 🔍 Verificando productos huérfanos...")
        orphaned = self._check_orphaned_products()
        
        # 4. Verificar sincronización atascada
        self.stdout.write("\n4. 🔍 Verificando productos atascados en sincronización...")
        stuck = self._check_stuck_sync()
        
        # 5. Verificar logs de errores recientes
        self.stdout.write("\n5. 🔍 Verificando errores recientes de sincronización...")
        recent_errors = self._check_recent_errors()
        
        # 6. Resumen
        total_issues = len(issues) + len(orphaned) + len(stuck) + len(recent_errors)
        
        self.stdout.write(f"\n📊 RESUMEN:")
        self.stdout.write(f"   • Inconsistencias: {len(issues)}")
        self.stdout.write(f"   • Productos huérfanos: {len(orphaned)}")
        self.stdout.write(f"   • Productos atascados: {len(stuck)}")
        self.stdout.write(f"   • Errores recientes: {len(recent_errors)}")
        self.stdout.write(f"   • Total de problemas: {total_issues}")
        
        if total_issues == 0:
            self.stdout.write(self.style.SUCCESS("\n✅ No se detectaron problemas de sincronización"))
            return
        
        if not repair_mode:
            self.stdout.write(self.style.WARNING(f"\n⚠️  Se detectaron {total_issues} problemas"))
            self.stdout.write("   Ejecuta con --repair para solucionarlos automáticamente")
            self.stdout.write("   Ejecuta con --force-resync para forzar resincronización completa")
            return
        
        # 7. Reparación
        self.stdout.write(self.style.NOTICE(f"\n🔧 Iniciando reparación de {total_issues} problemas..."))
        
        repaired = 0
        failed = 0
        
        # Reparar inconsistencias
        if issues:
            self.stdout.write("\n   🔧 Reparando inconsistencias...")
            for issue in issues:
                if self._repair_inconsistency(issue, force_resync):
                    repaired += 1
                else:
                    failed += 1
        
        # Reparar huérfanos
        if orphaned:
            self.stdout.write("\n   🔧 Reparando productos huérfanos...")
            for product in orphaned:
                if self._repair_orphaned_product(product):
                    repaired += 1
                else:
                    failed += 1
        
        # Liberar atascados
        if stuck:
            self.stdout.write("\n   🔧 Liberando productos atascados...")
            for product in stuck:
                if self._free_stuck_product(product):
                    repaired += 1
                else:
                    failed += 1
        
        # Resumen final
        self.stdout.write(self.style.SUCCESS(f"\n✅ Reparación completada:"))
        self.stdout.write(f"   • Reparados: {repaired}")
        self.stdout.write(f"   • Fallidos: {failed}")
        
        if failed > 0:
            self.stdout.write(self.style.WARNING("⚠️  Algunos problemas no pudieron ser reparados automáticamente"))

    def _check_remote_connection(self):
        try:
            conn = connections['remote']
            conn.ensure_connection()
            self.stdout.write(self.style.SUCCESS("   ✅ Conexión a BD remota: OK"))
            return True
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Error de conexión: {e}"))
            return False

    def _analyze_inconsistencies(self):
        issues = []
        
        try:
            # Productos locales sin correspondencia remota
            local_products = Product.objects.using('default').all()
            
            for prod in local_products:
                try:
                    # Buscar en remoto por code o name
                    remote_prod = None
                    if prod.code:
                        remote_prod = Product.objects.using('remote').filter(code=prod.code).first()
                    if not remote_prod:
                        remote_prod = Product.objects.using('remote').filter(name=prod.name).first()
                    
                    if not remote_prod:
                        issues.append({
                            'type': 'missing_remote',
                            'product': prod,
                            'description': f"Producto '{prod.name}' no existe en servidor remoto"
                        })
                    else:
                        # Verificar diferencias importantes
                        differences = []
                        if abs(float(prod.stock or 0) - float(remote_prod.stock or 0)) > 0.01:
                            differences.append(f"stock: local={prod.stock}, remote={remote_prod.stock}")
                        if abs(float(prod.pvp or 0) - float(remote_prod.pvp or 0)) > 0.01:
                            differences.append(f"pvp: local={prod.pvp}, remote={remote_prod.pvp}")
                        if abs(float(prod.cost_price or 0) - float(remote_prod.cost_price or 0)) > 0.01:
                            differences.append(f"cost_price: local={prod.cost_price}, remote={remote_prod.cost_price}")
                        
                        if differences:
                            issues.append({
                                'type': 'data_mismatch',
                                'product': prod,
                                'remote_product': remote_prod,
                                'description': f"Diferencias en {', '.join(differences)}"
                            })
                
                except Exception as e:
                    issues.append({
                        'type': 'remote_access_error',
                        'product': prod,
                        'description': f"Error accediendo a remoto: {e}"
                    })
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Error analizando inconsistencias: {e}"))
        
        return issues

    def _check_orphaned_products(self):
        orphaned = []
        
        try:
            # Productos con empresas que no existen localmente
            orphaned = Product.objects.using('default').filter(
                company_id__isnull=False
            ).exclude(
                company_id__in=Company.objects.using('default').values_list('id', flat=True)
            )
            
            orphaned_list = list(orphaned)
            if orphaned_list:
                self.stdout.write(self.style.WARNING(f"   ⚠️  Se encontraron {len(orphaned_list)} productos con empresas inexistentes"))
                for prod in orphaned_list[:5]:
                    self.stdout.write(f"      - {prod.name} (company_id={prod.company_id})")
                if len(orphaned_list) > 5:
                    self.stdout.write(f"      ... y {len(orphaned_list) - 5} más")
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Error verificando huérfanos: {e}"))
        
        return orphaned_list

    def _check_stuck_sync(self):
        stuck = []
        
        try:
            # Productos marcados para sincronizar hace más de 1 hora
            one_hour_ago = timezone.now() - timedelta(hours=1)
            
            # Nota: No podemos verificar cuándo se marcaron, pero podemos verificar
            # productos que están pendientes desde hace mucho tiempo
            pending_long_time = Product.objects.using('default').filter(synced_to_server=False)
            
            # Si hay muchos productos pendientes, podría haber un problema
            pending_count = pending_long_time.count()
            if pending_count > 50:
                self.stdout.write(self.style.WARNING(f"   ⚠️  Hay {pending_count} productos pendientes de sincronización"))
                self.stdout.write("      Esto podría indicar un problema con el proceso de sincronización")
                stuck = list(pending_long_time[:10])  # Mostrar primeros 10
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Error verificando atascados: {e}"))
        
        return stuck

    def _check_recent_errors(self):
        errors = []
        
        try:
            # Verificar logs de sincronización recientes con errores
            one_day_ago = timezone.now() - timedelta(days=1)
            
            recent_logs = SyncLog.objects.using('default').filter(
                created_at__gte=one_day_ago,
                success=False
            ).order_by('-created_at')[:10]
            
            for log in recent_logs:
                errors.append({
                    'log': log,
                    'description': f"{log.node_name}: {log.message}"
                })
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Error verificando logs: {e}"))
        
        return errors

    def _repair_inconsistency(self, issue, force_resync=False):
        try:
            if issue['type'] == 'missing_remote':
                # Crear producto en remoto
                prod = issue['product']
                self._create_remote_product(prod)
                self.stdout.write(self.style.SUCCESS(f"      ✅ Creado '{prod.name}' en servidor remoto"))
                return True
                
            elif issue['type'] == 'data_mismatch':
                if force_resync:
                    # Forzar sincronización del producto
                    prod = issue['product']
                    prod.synced_to_server = False
                    prod.save(using='default')
                    self.stdout.write(self.style.SUCCESS(f"      ✅ Marcado '{prod.name}' para resincronizar"))
                    return True
                else:
                    self.stdout.write(self.style.WARNING(f"      ⚠️  Diferencias en '{prod.name}'. Usa --force-resync"))
                    return False
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"      ❌ Error reparando inconsistencia: {e}"))
            return False

    def _repair_orphaned_product(self, product):
        try:
            # Asignar a la primera empresa disponible o null
            first_company = Company.objects.using('default').first()
            product.company_id = first_company.id if first_company else None
            product.synced_to_server = False
            product.save(using='default')
            self.stdout.write(self.style.SUCCESS(f"      ✅ Reasignado '{product.name}' a empresa válida"))
            return True
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"      ❌ Error reparando huérfano: {e}"))
            return False

    def _free_stuck_product(self, product):
        try:
            # Resetear estado de sincronización
            product.synced_to_server = True
            product.save(using='default')
            self.stdout.write(self.style.SUCCESS(f"      ✅ Liberado '{product.name}' de sincronización"))
            return True
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"      ❌ Error liberando producto: {e}"))
            return False

    def _create_remote_product(self, local_product):
        with transaction.atomic(using='remote'):
            # Resolver empresa
            remote_company = None
            if local_product.company_id:
                local_company = Company.objects.using('default').filter(pk=local_product.company_id).first()
                if local_company:
                    remote_company = Company.objects.using('remote').filter(
                        models.Q(cuit=local_company.cuit) | models.Q(name=local_company.name)
                    ).first()
            
            # Resolver categoría
            remote_cat = None
            if local_product.cat_id:
                remote_cat, _ = Category.objects.using('remote').get_or_create(
                    name=local_product.cat.name,
                    defaults={'desc': local_product.cat.desc}
                )
            
            # Crear producto
            lookup = {}
            if local_product.code:
                lookup['code'] = local_product.code
            else:
                lookup['name'] = local_product.name
            
            Product.objects.using('remote').get_or_create(
                **lookup,
                defaults={
                    'company_id': remote_company.id if remote_company else None,
                    'name': local_product.name,
                    'cat': remote_cat,
                    'cost_price': local_product.cost_price,
                    'pvp': local_product.pvp,
                    'iva_rate': local_product.iva_rate,
                    'pvp_final': local_product.pvp_final,
                    'unit': local_product.unit,
                    'stock': local_product.stock,
                }
            )
