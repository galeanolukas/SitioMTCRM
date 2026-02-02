"""
Servicio de sincronización para categorías con soporte de empresa
"""

import os
from django.conf import settings
from django.db import connections
from core.erp.models import Category, Company
import logging

logger = logging.getLogger(__name__)

class CategorySyncService:
    """Servicio para sincronización de categorías con relación empresa."""
    
    @staticmethod
    def is_server_mode():
        """Verifica si estamos en modo servidor."""
        return os.getenv('ENVIRONMENT', 'development') == 'production'
    
    @staticmethod
    def sync_category_to_remote(category_id, target_company_id=None):
        """
        Sincroniza una categoría a la base de datos remota.
        
        Args:
            category_id: ID de la categoría a sincronizar
            target_company_id: ID de la empresa destino (opcional)
        """
        # En modo servidor no sincronizamos (recibimos datos)
        # En modo POS sí sincronizamos (enviamos datos al servidor)
        if CategorySyncService.is_server_mode():
            logger.info("Estamos en modo servidor, omitiendo sincronización de categoría")
            return False, "Estamos en modo servidor"
        
        try:
            # Obtener categoría de la base de datos local
            category = Category.objects.get(id=category_id)
            
            # Usar la conexión remota
            remote_conn = connections['remote']
            
            # Verificar si la categoría ya existe en remoto para esta empresa
            with remote_conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM erp_category WHERE name = %s AND company_id = %s",
                    [category.name, target_company_id or category.company_id]
                )
                existing = cursor.fetchone()
                
                if existing:
                    # Actualizar categoría existente
                    cursor.execute("""
                        UPDATE erp_category 
                        SET name = %s, "desc" = %s, company_id = %s
                        WHERE id = %s
                    """, [
                        category.name,
                        category.desc or '',
                        target_company_id or category.company_id,
                        existing[0]
                    ])
                    action = "actualizada"
                    remote_id = existing[0]
                else:
                    # Insertar nueva categoría
                    cursor.execute("""
                        INSERT INTO erp_category 
                        (name, "desc", company_id, date_creation, date_updated)
                        VALUES (%s, %s, %s, NOW(), NOW())
                    """, [
                        category.name,
                        category.desc or '',
                        target_company_id or category.company_id
                    ])
                    remote_id = cursor.lastrowid
                    action = "creada"
                
                remote_conn.commit()
            
            logger.info(f"Categoría '{category.name}' {action} en base de datos remota (ID: {remote_id})")
            return True, remote_id
            
        except Exception as e:
            logger.error(f"Error sincronizando categoría {category_id}: {e}")
            return False, str(e)
    
    @staticmethod
    def sync_categories_for_company(company_id):
        """
        Sincroniza todas las categorías de una empresa.
        
        Args:
            company_id: ID de la empresa cuyas categorías se sincronizarán
        """
        if not CategorySyncService.is_server_mode():
            return False, "No estamos en modo servidor"
        
        try:
            categories = Category.objects.filter(company_id=company_id)
            success_count = 0
            error_count = 0
            errors = []
            
            for category in categories:
                success, result = CategorySyncService.sync_category_to_remote(
                    category.id, company_id
                )
                if success:
                    success_count += 1
                else:
                    error_count += 1
                    errors.append(f"{category.name}: {result}")
            
            result_msg = f"Sincronización de categorías completada: {success_count} exitosas, {error_count} errores"
            if errors:
                result_msg += f". Errores: {'; '.join(errors[:5])}"
            
            return True, result_msg
            
        except Exception as e:
            logger.error(f"Error sincronizando categorías para empresa {company_id}: {e}")
            return False, str(e)
    
    @staticmethod
    def get_or_create_remote_category(category_name, company_id, desc=''):
        """
        Obtiene o crea una categoría en remoto para una empresa específica.
        
        Args:
            category_name: Nombre de la categoría
            company_id: ID de la empresa
            desc: Descripción opcional
            
        Returns:
            tuple: (success, category_id)
        """
        if not CategorySyncService.is_server_mode():
            return False, None
        
        try:
            remote_conn = connections['remote']
            
            with remote_conn.cursor() as cursor:
                # Buscar categoría existente
                cursor.execute(
                    "SELECT id FROM erp_category WHERE name = %s AND company_id = %s",
                    [category_name, company_id]
                )
                existing = cursor.fetchone()
                
                if existing:
                    return True, existing[0]
                
                # Crear nueva categoría
                cursor.execute("""
                    INSERT INTO erp_category 
                    (name, desc, company_id, created_at, updated_at)
                    VALUES (%s, %s, %s, NOW(), NOW())
                """, [category_name, desc, company_id])
                
                remote_conn.commit()
                return True, cursor.lastrowid
                
        except Exception as e:
            logger.error(f"Error obteniendo/creando categoría remota '{category_name}': {e}")
            return False, None
    
    @staticmethod
    def validate_category_company_relationship(category_id, company_id):
        """
        Valida que una categoría pertenezca a la empresa especificada.
        
        Args:
            category_id: ID de la categoría
            company_id: ID de la empresa
            
        Returns:
            bool: True si la relación es válida
        """
        try:
            category = Category.objects.get(id=category_id)
            return category.company_id == company_id
        except Category.DoesNotExist:
            return False
    
    @staticmethod
    def get_remote_categories_for_company(company_id):
        """
        Obtiene categorías de la base de datos remota para una empresa.
        
        Args:
            company_id: ID de la empresa
            
        Returns:
            list: Lista de categorías desde remoto
        """
        try:
            remote_conn = connections['remote']
            
            with remote_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, name, desc, company_id
                    FROM erp_category 
                    WHERE company_id = %s
                    ORDER BY name
                """, [company_id])
                
                columns = [col[0] for col in cursor.description]
                categories = []
                
                for row in cursor.fetchall():
                    category_dict = dict(zip(columns, row))
                    categories.append(category_dict)
                
                return categories
                
        except Exception as e:
            logger.error(f"Error obteniendo categorías remotas para empresa {company_id}: {e}")
            return []
