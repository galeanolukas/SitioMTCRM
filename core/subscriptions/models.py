from django.db import models
from django.utils import timezone


class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name='Nombre')
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Precio')
    duration_days = models.PositiveIntegerField(default=30, verbose_name='Duración (días)')
    is_active = models.BooleanField(default=True, verbose_name='Activo')
    description = models.CharField(max_length=200, blank=True, verbose_name='Descripción corta')
    features = models.TextField(
        blank=True, verbose_name='Características',
        help_text='Una característica por línea (se muestran en la página pública de planes)'
    )
    is_featured = models.BooleanField(default=False, verbose_name='Destacado')
    sort_order = models.PositiveIntegerField(default=0, verbose_name='Orden')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Plan de suscripción'
        verbose_name_plural = 'Planes de suscripción'
        ordering = ['sort_order', 'name']

    def feature_list(self):
        return [f.strip() for f in self.features.splitlines() if f.strip()]

    def __str__(self):
        return f'{self.name} (${self.price} / {self.duration_days} días)'


class Subscription(models.Model):
    STATUS_CHOICES = (
        ('active', 'Activa'),
        ('suspended', 'Suspendida'),
        ('cancelled', 'Cancelada'),
    )

    company = models.OneToOneField(
        'erp.Company', on_delete=models.CASCADE,
        related_name='subscription', verbose_name='Empresa'
    )
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.PROTECT,
        related_name='subscriptions', verbose_name='Plan'
    )
    start_date = models.DateField(verbose_name='Inicio')
    end_date = models.DateField(verbose_name='Vencimiento')
    grace_days = models.PositiveIntegerField(default=7, verbose_name='Días de gracia')
    # 'active' = al día. 'suspended'/'cancelled' = bloqueo manual (no por fecha).
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name='Estado')
    notes = models.TextField(blank=True, verbose_name='Notas')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Suscripción'
        verbose_name_plural = 'Suscripciones'
        ordering = ['company__name']

    def __str__(self):
        return f'{self.company.name} - {self.plan.name}'

    def effective_state(self, today=None):
        """Estado real considerando fechas + gracia + bloqueo manual.

        Devuelve: 'active' | 'grace' | 'suspended' | 'cancelled'
        """
        today = today or timezone.localdate()
        if self.status == 'cancelled':
            return 'cancelled'
        if self.status == 'suspended':
            return 'suspended'
        if today <= self.end_date:
            return 'active'
        if today <= self.end_date + timezone.timedelta(days=self.grace_days):
            return 'grace'
        return 'suspended'

    def days_left(self, today=None):
        today = today or timezone.localdate()
        return (self.end_date - today).days

    def days_overdue(self, today=None):
        today = today or timezone.localdate()
        overdue = (today - self.end_date).days
        return overdue if overdue > 0 else 0

    def register_payment(self, amount, method, paid_at=None, notes='', user=None):
        """Registra un pago y extiende el vencimiento un período del plan."""
        paid_at = paid_at or timezone.localdate()
        payment = self.payments.create(
            amount=amount, method=method, paid_at=paid_at,
            notes=notes, created_by=user,
        )
        base = max(self.end_date, paid_at)
        self.end_date = base + timezone.timedelta(days=self.plan.duration_days)
        if self.status != 'cancelled':
            self.status = 'active'
        self.save(update_fields=['end_date', 'status', 'updated_at'])
        return payment


class SubscriptionPayment(models.Model):
    METHOD_CHOICES = (
        ('cash', 'Efectivo'),
        ('transfer', 'Transferencia'),
        ('mp', 'Mercado Pago'),
        ('other', 'Otro'),
    )

    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE,
        related_name='payments', verbose_name='Suscripción'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Monto')
    paid_at = models.DateField(default=timezone.localdate, verbose_name='Fecha de pago')
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='cash', verbose_name='Método')
    notes = models.TextField(blank=True, verbose_name='Notas')
    created_by = models.ForeignKey(
        'user.User', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='subscription_payments', verbose_name='Registrado por'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pago de suscripción'
        verbose_name_plural = 'Pagos de suscripción'
        ordering = ['-paid_at', '-id']

    def __str__(self):
        return f'{self.subscription.company.name} - ${self.amount} ({self.paid_at})'
