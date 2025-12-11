from typing import Dict
from core.erp.models import Company
from django.conf import settings

def brand(request) -> Dict[str, dict]:
    company = None
    user = getattr(request, 'user', None)

    active_cid = request.session.get('company_id')
    if user and not getattr(user, 'is_superuser', False):
        active_cid = active_cid or getattr(user, 'company_id', None)

    if active_cid:
        company = Company.objects.filter(pk=active_cid).first()
    if not company and user and getattr(user, 'company_id', None):
        company = Company.objects.filter(pk=user.company_id).first()
    if not company:
        company = Company.objects.first()

    data = {
        'name': company.name if company else 'CRM MultilideresTech',
        'logo_url': company.get_logo_url() if company else '/static/img/logo1.jpeg',
    }
    return {'brand': data}

def superuser_perms(request) -> Dict[str, dict]:
    """
    Asegura que los superusuarios tengan acceso a todos los permisos en los templates.
    """
    user = getattr(request, 'user', None)
    if user and getattr(user, 'is_superuser', False):
        # Para superusuarios, creamos un diccionario con todos los permisos como True
        from django.contrib.auth.models import Permission
        all_perms = Permission.objects.all()
        perms_dict = {}
        for perm in all_perms:
            key = f"{perm.content_type.app_label}.{perm.codename}"
            perms_dict[key] = True
        return {'perms': perms_dict}
    return {}

def app_version(request) -> Dict[str, str]:
    """
    Proporciona la versión de la aplicación obtenida automáticamente desde Git.
    """
    return {'app_version': getattr(settings, 'VERSION', '1.0.0')}