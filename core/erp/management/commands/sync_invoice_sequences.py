from django.core.management.base import BaseCommand
from django.db import connections
from core.erp.models import Sale, Company


class Command(BaseCommand):
    help = "Sincroniza secuencias de numeración de facturas con el servidor"

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id',
            type=int,
            help='ID de empresa específica para sincronizar (opcional)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forzar sincronización incluso si no hay conflictos',
        )

    def handle(self, *args, **options):
        self.stdout.write("🔄 Sincronizando secuencias de numeración con servidor...")
        
        companies = Company.objects.using('default').all()
        if options['company_id']:
            companies = companies.filter(id=options['company_id'])
        
        if not companies.exists():
            self.stdout.write(self.style.ERROR("❌ No se encontraron empresas"))
            return
        
        synced_count = 0
        conflict_count = 0
        
        for company in companies:
            self.stdout.write(f"\n🏢 Procesando empresa: {company.name} (ID: {company.id})")
            
            try:
                # Obtener último número del servidor
                last_server_number = None
                with connections['remote'].cursor() as cursor:
                    cursor.execute('''
                        SELECT MAX(invoice_number) 
                        FROM erp_sale 
                        WHERE company_id = %s AND invoice_number IS NOT NULL
                    ''', [company.id])
                    
                    result = cursor.fetchone()
                    last_server_number = result[0] if result and result[0] else None
                
                # Probar qué número generaría localmente
                test_sale = Sale()
                test_sale.company_id = company.id
                test_sale.invoice_pos = '0001'
                test_sale.invoice_type = 'B'
                
                generated_number = test_sale.next_sequential_for_pos_type()
                
                self.stdout.write(f"  📋 Último número servidor: {last_server_number or 'Ninguno'}")
                self.stdout.write(f"  🔢 Número generaría local: {generated_number}")
                
                # Verificar si hay conflicto
                has_conflict = False
                if last_server_number:
                    try:
                        server_seq = int(last_server_number.split('-')[-1])
                        local_seq = int(generated_number.split('-')[-1])
                        
                        if local_seq <= server_seq:
                            has_conflict = True
                            conflict_count += 1
                            
                            self.stdout.write(self.style.WARNING(
                                f"  ⚠️  CONFLICTO: Secuencia local ({local_seq}) <= servidor ({server_seq})"
                            ))
                            
                            # Crear venta temporal para forzar secuencia correcta
                            if options['force'] or has_conflict:
                                self._sync_sequence(company, last_server_number)
                                synced_count += 1
                                self.stdout.write(self.style.SUCCESS(
                                    f"  ✅ Secuencia sincronizada"
                                ))
                        else:
                            self.stdout.write(self.style.SUCCESS(
                                f"  ✅ OK: Secuencia local ({local_seq}) > servidor ({server_seq})"
                            ))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(
                            f"  ❌ Error comparando secuencias: {e}"
                        ))
                else:
                    self.stdout.write(self.style.SUCCESS(
                        "  ✅ OK: No hay ventas numeradas en servidor"
                    ))
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"  ❌ Error procesando empresa {company.id}: {e}"
                ))
        
        # Resumen
        self.stdout.write(f"\n📊 RESUMEN:")
        self.stdout.write(f"  🏢 Empresas procesadas: {companies.count()}")
        self.stdout.write(f"  ⚠️  Conflictos detectados: {conflict_count}")
        self.stdout.write(f"  ✅ Secuencias sincronizadas: {synced_count}")
        
        if conflict_count > 0:
            self.stdout.write(self.style.WARNING(
                f"\n🎯 Se detectaron {conflict_count} conflictos de numeración."
            ))
            self.stdout.write(
                "💡 Ejecute con --force para sincronizar todas las secuencias."
            )
        else:
            self.stdout.write(self.style.SUCCESS(
                "\n✅ Todas las secuencias están sincronizadas correctamente."
            ))

    def _sync_sequence(self, company, last_server_number):
        """
        Crea una venta temporal para forzar la secuencia local a continuar desde el servidor.
        """
        try:
            # Extraer secuencia del servidor y crear el siguiente número
            server_seq = int(last_server_number.split('-')[-1])
            next_seq = server_seq + 1
            next_number = f"0001-B-{next_seq:08d}"
            
            # Crear venta temporal con el siguiente número que debería usar
            temp_sale = Sale.objects.using('default').create(
                company_id=company.id,
                invoice_pos='0001',
                invoice_type='B',
                invoice_number=next_number,
                subtotal=0.0,
                iva=0.0,
                total=0.0,
                payment_method='cash',
                synced_to_server=False  # No sincronizar esta venta temporal
            )
            
            # Eliminar la venta temporal inmediatamente
            # Esto fuerza que la próxima venta use la secuencia correcta
            temp_sale.delete()
            
            self.stdout.write(f"    🔢 Secuencia forzada a: {next_number}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"    ❌ Error sincronizando secuencia: {e}"
            ))
