from typing import Dict
from core.erp.models import Company

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