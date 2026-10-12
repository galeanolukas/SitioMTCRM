from django.contrib import admin

from .models import Subscription, SubscriptionPayment, SubscriptionPlan


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration_days', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('company', 'plan', 'start_date', 'end_date', 'grace_days', 'status')
    list_filter = ('status', 'plan')
    search_fields = ('company__name',)


@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = ('subscription', 'amount', 'paid_at', 'method', 'created_by')
    list_filter = ('method', 'paid_at')
    search_fields = ('subscription__company__name',)
