"""
Servicio simple para sincronización de productos en modo servidor.
Usa la configuración de .env para conectar a la base de datos remota.
"""

import os
from django.conf import settings
from django.db import connections
from core.erp.models import Product, Company, Category
import logging

logger = logging.getLogger(__name__)

class ServerSyncService:
    """Servicio para sincronización de productos en modo servidor."""
    
    @staticmethod
    def is_server_mode():
        """Verifica si estamos en modo servidor."""
        return os.getenv('ENVIRONMENT', 'development') == 'production'
    
    @staticmethod
    def sync_product_to_remote(product_id, target_company_id=None):
        """
        Sincroniza un producto a la base de datos remota.
        
        Args:
            product_id: ID del producto a sincronizar
            target_company_id: ID de la empresa destino (opcional)
        """
        if not ServerSyncService.is_server_mode():
            logger.info("No estamos en modo servidor, omitiendo sincronización")
            return False, "No estamos en modo servidor"
        
        try:
            # Obtener producto de la base de datos local
            product = Product.objects.get(id=product_id)
            company_id = target_company_id or product.company_id
            
            # Validar que la categoría pertenezca a la empresa
            if product.cat:
                if product.cat.company_id != company_id:
                    logger.error(f"Error: Categoría '{product.cat.name}' no pertenece a la empresa {company_id}")
                    return False, f"La categoría '{product.cat.name}' no pertenece a esta empresa"
            
            # Sincronizar categoría primero si existe
            remote_cat_id = None
            if product.cat:
                from core.erp.services.category_sync_service import CategorySyncService
                success, cat_result = CategorySyncService.get_or_create_remote_category(
                    product.cat.name, 
                    company_id, 
                    product.cat.desc or ''
                )
                if success:
                    remote_cat_id = cat_result
                else:
                    logger.warning(f"No se pudo sincronizar categoría '{product.cat.name}': {cat_result}")
            
            # Usar la conexión remota
            remote_conn = connections['remote']
            
            # Verificar si el producto ya existe en remoto
            with remote_conn.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM erp_product WHERE code = %s AND company_id = %s",
                    [product.code, company_id]
                )
                existing = cursor.fetchone()
                
                if existing:
                    # Actualizar producto existente
                    cursor.execute("""
                        UPDATE erp_product 
                        SET name = %s, pvp = %s, iva_rate = %s, pvp_final = %s,
                            stock = %s, unit = %s, synced_to_server = %s,
                            company_id = %s, cat_id = %s
                        WHERE id = %s
                    """, [
                        product.name,
                        float(product.pvp),
                        float(product.iva_rate) if product.iva_rate else None,
                        float(product.pvp_final) if product.pvp_final else None,
                        float(product.stock),
                        product.unit,
                        True,
                        company_id,
                        remote_cat_id,
                        existing[0]
                    ])
                    action = "actualizado"
                else:
                    # Insertar nuevo producto
                    cursor.execute("""
                        INSERT INTO erp_product 
                        (name, code, pvp, iva_rate, pvp_final, stock, unit, 
                         synced_to_server, company_id, cat_id, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    """, [
                        product.name,
                        product.code,
                        float(product.pvp),
                        float(product.iva_rate) if product.iva_rate else None,
                        float(product.pvp_final) if product.pvp_final else None,
                        float(product.stock),
                        product.unit,
                        True,
                        company_id,
                        remote_cat_id
                    ])
                    action = "creado"
                
                remote_conn.commit()
            
            # Marcar como sincronizado localmente
            product.synced_to_server = True
            product.save()
            
            logger.info(f"Producto {product.code} {action} en base de datos remota (cat_id: {remote_cat_id})")
            return True, f"Producto {action} exitosamente"
            
        except Exception as e:
            logger.error(f"Error sincronizando producto {product_id}: {e}")
            return False, str(e)
    
    @staticmethod
    def sync_categories_for_company(company_id):
        """
        Sincroniza todas las categorías de una empresa antes de los productos.
        
        Args:
            company_id: ID de la empresa cuyas categorías se sincronizarán
        """
        if not ServerSyncService.is_server_mode():
            return False, "No estamos en modo servidor"
        
        try:
            from core.erp.services.category_sync_service import CategorySyncService
            return CategorySyncService.sync_categories_for_company(company_id)
        except Exception as e:
            logger.error(f"Error sincronizando categorías para empresa {company_id}: {e}")
            return False, str(e)
    
    @staticmethod
    def sync_products_for_company(company_id):
        """
        Sincroniza todos los productos de una empresa.
        
        Args:
            company_id: ID de la empresa cuyos productos se sincronizarán
        """
        if not ServerSyncService.is_server_mode():
            return False, "No estamos en modo servidor"
        
        try:
            # Primero sincronizar categorías
            cat_success, cat_message = ServerSyncService.sync_categories_for_company(company_id)
            if not cat_success:
                logger.warning(f"No se pudieron sincronizar categorías: {cat_message}")
            
            # Luego sincronizar productos
            products = Product.objects.filter(company_id=company_id)
            success_count = 0
            error_count = 0
            errors = []
            
            for product in products:
                success, message = ServerSyncService.sync_product_to_remote(
                    product.id, company_id
                )
                if success:
                    success_count += 1
                else:
                    error_count += 1
                    errors.append(f"{product.code}: {message}")
            
            result_msg = f"Sincronización completada: {success_count} exitosos, {error_count} errores"
            if errors:
                result_msg += f". Errores: {'; '.join(errors[:5])}"  # Primeros 5 errores
            
            return True, result_msg
            
        except Exception as e:
            logger.error(f"Error sincronizando productos para empresa {company_id}: {e}")
            return False, str(e)
    
    @staticmethod
    def get_remote_products_for_company(company_id):
        """
        Obtiene productos de la base de datos remota para una empresa.
        
        Args:
            company_id: ID de la empresa
            
        Returns:
            list: Lista de productos desde remoto
        """
        try:
            remote_conn = connections['remote']
            
            with remote_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, name, code, pvp, iva_rate, pvp_final, stock, unit
                    FROM erp_product 
                    WHERE company_id = %s
                    ORDER BY name
                """, [company_id])
                
                columns = [col[0] for col in cursor.description]
                products = []
                
                for row in cursor.fetchall():
                    product_dict = dict(zip(columns, row))
                    products.append(product_dict)
                
                return products
                
        except Exception as e:
            logger.error(f"Error obteniendo productos remotos para empresa {company_id}: {e}")
            return []
    
    @staticmethod
    def get_remote_users():
        """Obtener usuarios desde la base de datos remota."""
        if not ServerSyncService.is_server_mode():
            logger.info("No estamos en modo servidor, no hay usuarios remotos")
            return []
        
        try:
            remote_conn = connections['remote']  # Usar la conexión remota
            
            with remote_conn.cursor() as cursor:
                cursor.execute("""
                    SELECT u.id, u.username, u.email, u.first_name, u.last_name, 
                           u.is_superuser, u.is_staff, u.is_active, u.company_id
                    FROM user_user u
                    ORDER BY u.username
                """)
                
                columns = [col[0] for col in cursor.description]
                users = []
                
                for row in cursor.fetchall():
                    user_dict = dict(zip(columns, row))
                    users.append(user_dict)
                
                return users
                
        except Exception as e:
            logger.error(f"Error obteniendo usuarios remotos: {e}")
            return []
