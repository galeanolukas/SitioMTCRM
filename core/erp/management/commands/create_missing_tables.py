from django.core.management.base import BaseCommand
from django.db import connections, DatabaseError
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.state import ProjectState
from django.apps import apps

class Command(BaseCommand):
    help = 'Crear tablas faltantes en el servidor remoto'

    def handle(self, *args, **options):
        self.stdout.write('Iniciando creación de tablas faltantes...')
        
        if 'remote' not in connections:
            self.stdout.write(self.style.ERROR('No existe configuración de base de datos remota'))
            return
        
        try:
            # Obtener todas las tablas del modelo local
            local_conn = connections['default']
            remote_conn = connections['remote']
            
            with local_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name LIKE 'erp_%'
                    ORDER BY table_name
                """)
                local_tables = [row[0] for row in cursor.fetchall()]
            
            with remote_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name LIKE 'erp_%'
                    ORDER BY table_name
                """)
                remote_tables = [row[0] for row in cursor.fetchall()]
            
            # Encontrar tablas faltantes
            missing_tables = [table for table in local_tables if table not in remote_tables]
            
            if not missing_tables:
                self.stdout.write(self.style.SUCCESS('✅ Todas las tablas existen en el servidor remoto'))
                return
            
            self.stdout.write(f'Tablas faltantes en servidor remoto: {missing_tables}')
            
            # Crear tablas faltantes usando SQL generado por Django
            from django.core.management import call_command
            import io
            import sys
            
            # Generar SQL para crear tablas
            out = io.StringIO()
            call_command('sqlmigrate', 'erp', '0001_initial', stdout=out)
            sql_content = out.getvalue()
            
            # Extraer solo los CREATE TABLE para tablas faltantes
            create_statements = []
            current_statement = ""
            
            for line in sql_content.split('\n'):
                if line.strip().startswith('CREATE TABLE'):
                    current_statement = line + '\n'
                elif current_statement and line.strip().endswith(';'):
                    current_statement += line + '\n'
                    
                    # Verificar si esta tabla está en las faltantes
                    for table in missing_tables:
                        if f'CREATE TABLE {table}' in current_statement:
                            create_statements.append(current_statement)
                            break
                    
                    current_statement = ""
                elif current_statement:
                    current_statement += line + '\n'
            
            # Ejecutar CREATE TABLE statements
            with remote_conn.cursor() as cursor:
                for statement in create_statements:
                    try:
                        self.stdout.write(f'Ejecutando: {statement.split()[2]}...')
                        cursor.execute(statement)
                        self.stdout.write(f'  ✅ Tabla creada')
                    except DatabaseError as e:
                        self.stdout.write(self.style.ERROR(f'  ❌ Error: {e}'))
            
            # Verificar creación
            with remote_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name LIKE 'erp_%'
                    ORDER BY table_name
                """)
                final_remote_tables = [row[0] for row in cursor.fetchall()]
            
            still_missing = [table for table in missing_tables if table not in final_remote_tables]
            
            if still_missing:
                self.stdout.write(self.style.ERROR(f'Tablas que no se pudieron crear: {still_missing}'))
            else:
                self.stdout.write(self.style.SUCCESS('✅ Todas las tablas faltantes han sido creadas'))
            
            # Crear método alternativo si el anterior no funciona
            if still_missing:
                self.stdout.write('\nIntentando método alternativo...')
                
                # SQL manual para tablas específicas
                table_sqls = {
                    'erp_internaltransfer': '''
                        CREATE TABLE erp_internaltransfer (
                            id SERIAL PRIMARY KEY,
                            company_id INTEGER,
                            origin_branch_id INTEGER,
                            destination_branch_id INTEGER,
                            transfer_date TIMESTAMP WITH TIME ZONE,
                            notes TEXT,
                            status VARCHAR(20) DEFAULT 'pending',
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                            created_by_id INTEGER,
                            synced_to_server BOOLEAN DEFAULT FALSE
                        );
                    ''',
                    'erp_internaltransferdetail': '''
                        CREATE TABLE erp_internaltransferdetail (
                            id SERIAL PRIMARY KEY,
                            transfer_id INTEGER REFERENCES erp_internaltransfer(id) ON DELETE CASCADE,
                            product_id INTEGER,
                            quantity DECIMAL(10,2) DEFAULT 0,
                            cost_price DECIMAL(10,2) DEFAULT 0,
                            notes TEXT,
                            synced_to_server BOOLEAN DEFAULT FALSE
                        );
                    '''
                }
                
                with remote_conn.cursor() as cursor:
                    for table, sql in table_sqls.items():
                        if table in still_missing:
                            try:
                                self.stdout.write(f'Creando tabla {table} (método manual)...')
                                cursor.execute(sql)
                                self.stdout.write(f'  ✅ Tabla {table} creada')
                            except DatabaseError as e:
                                self.stdout.write(self.style.ERROR(f'  ❌ Error creando {table}: {e}'))
            
            self.stdout.write(self.style.SUCCESS('\n✅ Proceso de creación de tablas completado'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error inesperado: {e}'))
