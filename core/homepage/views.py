from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

# Create your views here.
class IndexViews(TemplateView):
    template_name = 'index.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'TechVentas'
        return context
class AboutViews(LoginRequiredMixin, TemplateView):
    template_name = 'about.html'
class ProductsViews(TemplateView):
    template_name = 'products.html'