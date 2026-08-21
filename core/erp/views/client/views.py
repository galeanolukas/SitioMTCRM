import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView

from core.erp.forms import ClientForm
from core.erp.models import Client
from core.erp.mixins import ValidatePermissionRequiredMixin, CompanyInitialMixin

logger = logging.getLogger(__name__)


class ClientView(LoginRequiredMixin, TemplateView):
    template_name = 'client/list.html'

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST['action']
            if action == 'searchdata':
                data = []
                if request.user.is_superuser:
                    active_cid = request.session.get('company_id')
                else:
                    active_cid = getattr(request.user, 'company_id', None)
                qs = Client.objects.all()
                if active_cid:
                    qs = qs.filter(company_id=active_cid)
                for i in qs:
                    data.append(i.toJSON())
            elif action == 'add':
                form = ClientForm(request.POST)
                if form.is_valid():
                    form.save()
                else:
                    data['error'] = form.errors
            elif action == 'edit':
                cli = Client.objects.get(pk=request.POST['id'])
                form = ClientForm(request.POST, instance=cli)
                if form.is_valid():
                    form.save()
                else:
                    data['error'] = form.errors
            elif action == 'delete':
                cli = Client.objects.get(pk=request.POST['id'])
                cli.delete()
            else:
                data['error'] = 'Ha ocurrido un error'
        except Exception as e:
            data['error'] = str(e)
        return JsonResponse(data, safe=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Listado de Clientes'
        context['list_url'] = reverse_lazy('erp:client')
        context['entity'] = 'Clientes'
        context['form'] = ClientForm()
        return context

@method_decorator(csrf_exempt, name='dispatch')
class ClientListView(LoginRequiredMixin, ValidatePermissionRequiredMixin, ListView):
    model = Client
    template_name = 'client/list.html'
    permission_required = 'erp.view_client'

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST['action']
            if action == 'searchdata':
                data = []
                if request.user.is_superuser:
                    active_cid = request.session.get('company_id')
                else:
                    active_cid = getattr(request.user, 'company_id', None)
                logger.info(f'ClientListView searchdata - user: {request.user}, company_id session: {request.session.get("company_id")}, active_cid: {active_cid}')
                qs = Client.objects.filter(is_active=True)
                if active_cid:
                    qs = qs.filter(company_id=active_cid)
                logger.info(f'ClientListView searchdata - query count: {qs.count()}')
                for i in qs:
                    try:
                        data.append(i.toJSON())
                    except Exception as e:
                        logger.exception(f'ClientListView toJSON error for client {i.id}: {e}')
                        raise
            elif action == 'add':
                form = ClientForm(request.POST)
                if form.is_valid():
                    form.save()
                else:
                    data['error'] = form.errors
            elif action == 'edit':
                cli = Client.objects.get(pk=request.POST['id'])
                form = ClientForm(request.POST, instance=cli)
                if form.is_valid():
                    form.save()
                else:
                    data['error'] = form.errors
            elif action == 'delete':
                obj = Client.objects.get(pk=request.POST['id'])
                obj.is_active = False
                obj.synced_to_server = False
                obj.save()
            elif action == 'delete_all':
                if request.user.is_superuser:
                    active_cid = request.session.get('company_id')
                else:
                    active_cid = getattr(request.user, 'company_id', None)
                qs = Client.objects.filter(is_active=True)
                if active_cid:
                    qs = qs.filter(company_id=active_cid)
                count = qs.count()
                qs.delete()
                data['deleted'] = count
            else:
                data['error'] = 'Ha ocurrido un error'
        except Exception as e:
            data['error'] = str(e)
        return JsonResponse(data, safe=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Listado de Clientes'
        context['create_url'] = reverse_lazy('erp:client_create')
        context['list_url'] = reverse_lazy('erp:client_list')
        context['entity'] = 'Clientes'
        context['form'] = ClientForm()
        return context
    
class ClientCreateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, CompanyInitialMixin, CreateView):
    model = Client
    form_class = ClientForm
    template_name = 'client/create.html'
    success_url = reverse_lazy('erp:client_list')
    permission_required = 'erp.add_client'
    url_redirect = success_url

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_superuser:
            return super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST['action']
            if action == 'add':
                with transaction.atomic():
                    form = self.get_form()
                    data = form.save()
            elif action == 'search_cuit':
                cuit = request.POST.get('cuit', '').strip()
                if not cuit:
                    data = {'error': 'Debe ingresar un CUIT'}
                else:
                    from core.erp.afip.client import AfipClient
                    if request.user.is_superuser:
                        active_cid = request.session.get('company_id')
                    else:
                        active_cid = getattr(request.user, 'company_id', None)
                    try:
                        client = AfipClient(company_id=active_cid)
                        result = client.get_taxpayer_data(cuit)
                        if 'error' in result:
                            data = {'error': result['error']}
                        else:
                            data = result
                    except Exception as e:
                        data = {'error': f'No se pudo consultar AFIP: {str(e)}'}
            else:
                data['error'] = 'No ha ingresado a ninguna opción'
        except Exception as e:
            data['error'] = str(e)
        return JsonResponse(data)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Creación un Cliente'
        context['entity'] = 'Clientes'
        context['list_url'] = self.success_url
        context['action'] = 'add'
        return context

class ClientUpdateView(LoginRequiredMixin, ValidatePermissionRequiredMixin, UpdateView):
    model = Client
    form_class = ClientForm
    template_name = 'client/create.html'
    success_url = reverse_lazy('erp:client_list')
    permission_required = 'erp.change_client'
    url_redirect = success_url

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            action = request.POST['action']
            if action == 'edit':
                with transaction.atomic():
                    form = self.get_form()
                    data = form.save()
            elif action == 'search_cuit':
                cuit = request.POST.get('cuit', '').strip()
                if not cuit:
                    data = {'error': 'Debe ingresar un CUIT'}
                else:
                    from core.erp.afip.client import AfipClient
                    if request.user.is_superuser:
                        active_cid = request.session.get('company_id')
                    else:
                        active_cid = getattr(request.user, 'company_id', None)
                    try:
                        client = AfipClient(company_id=active_cid)
                        result = client.get_taxpayer_data(cuit)
                        if 'error' in result:
                            data = {'error': result['error']}
                        else:
                            data = result
                    except Exception as e:
                        data = {'error': f'No se pudo consultar AFIP: {str(e)}'}
            else:
                data['error'] = 'No ha ingresado a ninguna opción'
        except Exception as e:
            data['error'] = str(e)
        return JsonResponse(data)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Edición un Cliente'
        context['entity'] = 'Clientes'
        context['list_url'] = self.success_url
        context['action'] = 'edit'
        return context


class ClientDeleteView(LoginRequiredMixin, ValidatePermissionRequiredMixin, DeleteView):
    model = Client
    template_name = 'client/delete.html'
    success_url = reverse_lazy('erp:client_list')
    permission_required = 'erp.delete_client'
    url_redirect = success_url

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        data = {}
        try:
            self.object.delete()
        except Exception as e:
            data['error'] = str(e)
        return JsonResponse(data)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Eliminación de un Cliente'
        context['entity'] = 'Clientes'
        context['list_url'] = self.success_url
        return context
