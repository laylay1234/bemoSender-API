import copy
from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm, UsernameField
from django.contrib.auth.models import Permission
from django.utils.translation import ugettext_lazy as _
from djangoql.admin import DjangoQLSearchMixin
from guardian.models import UserObjectPermission
from reversion.admin import VersionAdmin
from bemoSenderr.models.partner.partner import APICollectToken, APIRequestMonitoring, AppSettings, Country, Currency, MobileNetwork, \
    MobileNetworkAvailability, Partner, TransactionMethodAvailability, PartnerPayer, PartnerSettlementAccount, PartnerExchangeRate, ExchangeRateTier, \
    TransactionMethod, UserTier
from bemoSenderr.models.global_transaction import GlobalTransaction
from bemoSenderr.models import User, UserTask
from bemoSenderr.models.partner import UserBankVerificationRequest, KycVerificationRequest
from bemoSenderr.models.task import PeriodicTasksEntry
from bemoSenderr.models.partner.transactions import CollectTransaction, FundingTransaction, TxLimitCumul
from bemoSenderr.models.user import AdminAlerts, UserToken
from django_json_widget.widgets import JSONEditorWidget
from django.db import models
from fsm_admin.mixins import FSMTransitionMixin
# from bemoSenderr.translation import *
from modeltranslation.admin import TranslationAdmin
from django.db.models import Q
from django.contrib.admin import SimpleListFilter

'''
admin.site.site_title = "{} | {}".format(settings.CONFIG['env'], _('bemoSenderr'))
admin.site.index_title = "{} | {}".format(settings.CONFIG['env'], _('bemoSenderr'))
admin.site.site_header = "{} | {}".format(settings.CONFIG['env'], _('bemoSenderr'))
admin.site.site_url = "https://{}".format(settings.CONFIG['DOMAIN_ROOT'])
'''


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User


class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'
        field_classes = {'username': UsernameField}


@admin.register(User)
class CustomUserAdmin(DjangoQLSearchMixin, UserAdmin, VersionAdmin):
    readonly_fields = ('created_at', 'updated_at',)

    add_form = CustomUserCreationForm
    change_form = CustomUserChangeForm

    def get_fieldsets(self, request, obj=None):
        fieldsets = copy.deepcopy(super().get_fieldsets(request, obj))
        add_fieldsets = (
            (None, {
                'classes': ('wide',),
                'fields': ('username', 'email', 'password1', 'password2', 'locale', 'description', 'credentials'),
            }),
        )
        if obj is None:
            ## It's an ADD FORM
            return add_fieldsets
        if request.user.is_superuser:
            return (
                (None, {'fields': ('username', 'phone_number', 'email',
                                   'first_name', 'last_name', 'locale', 'password', 'description', 'credentials')}),
                (
                    _('Permissions'),
                    {'fields': ('is_active', 'is_staff', 'is_superuser',
                                'groups', 'user_permissions',)}
                ),
                (_('Important dates'), {
                    'fields': ('created_at', 'updated_at',)}),
            )
        else:
            return (
                (None, {'fields': ('username', 'phone_number', 'email',
                                   'first_name', 'last_name', 'locale', 'description', 'password')}),
                (
                    _('Permissions'),
                    {'fields': ('is_active', 'is_staff', 'is_superuser',
                                'groups', 'user_permissions',)}
                ),
                (_('Important dates'), {
                    'fields': ('created_at', 'updated_at',)}),
            )

    list_display = (
        'uuid', 'is_active', 'username', 'phone_number', 'email', 'first_name', 'last_name', 'is_superuser', 'is_staff', 'last_login',
        'created_at',
        'updated_at',
    )
    list_filter = (
        'last_login', 'is_superuser', 'is_active', 'is_staff', 'created_at', 'updated_at',)
    date_hierarchy = 'updated_at'

    def save_model(self, request, obj, form, change):
        if change and not request.user.groups.filter(name='Superuser').exists() and 'is_superuser' in form.changed_data:
            return messages.error(request, 'you do not have permission to change the superuser status.')
        super(CustomUserAdmin, self).save_model(request, obj, form, change)


@admin.register(UserObjectPermission)
class UserObjectPermissionAdmin(admin.ModelAdmin):
    pass


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    pass


@admin.register(UserTask)
class UserTaskAdmin(admin.ModelAdmin):
    pass


@admin.register(UserBankVerificationRequest)
class UserVerificationByBankAdmin(DjangoQLSearchMixin, VersionAdmin):
    list_display = ('uuid', 'created_at',
                    'updated_at', 'user', '_status', 'partner')
    list_filter = ('user', 'status', 'created_at', 'updated_at')

    def _status(self, obj):
        return obj.status

    date_hierarchy = 'updated_at'
    readonly_fields = ('_version',)

    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget(width="70%", height="200px", mode='text')},
    }


@admin.register(KycVerificationRequest)
class KycVerificationAdmin(DjangoQLSearchMixin, VersionAdmin):
    list_display = ('uuid', 'created_at',
                    'updated_at', 'user', 'status', 'partner')
    list_filter = ('user', 'status', 'created_at', 'updated_at')
    date_hierarchy = 'updated_at'
    readonly_fields = ('_version',)

    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget(width="70%", height="200px", mode='text')},
    }


class CollectTransactionsChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.get_full_name()


class GlobalTransactionForm(forms.ModelForm):
    transaction_uuid = forms.CharField(max_length=255, required=False, disabled=True, widget=forms.TextInput(attrs={'size': 50}))

    class Meta:
        model = GlobalTransaction
        fields = '__all__'  # It's actually best to list the fields out as per Two Scoops of Django

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.fields:
            self.fields['collect_transactions'].label_from_instance = \
                lambda obj: str(obj.uuid)
            self.fields['funding_transaction'].label_from_instance = \
                lambda obj: str(obj.uuid)
            self.fields["transaction_uuid"].initial = self.instance.uuid


@admin.register(GlobalTransaction)
class GlobalTransactionAdmin(FSMTransitionMixin, DjangoQLSearchMixin, VersionAdmin):
    list_display = ('uuid',
                    'created_at', 'updated_at', 'user', 'status', 'origin_amount', 'destination_amount', 'delivery_method', 'payment_day',
                    'the_revenue')
    list_filter = ('user', 'status', 'created_at', 'updated_at')
    fields = (
        "transaction_uuid", "user", "status", "receiver_snapshot", "user_snapshot", "parameters", "exchange_rate_tier_snapshot", "invoice_number",
        "notifications", "payment_date",
        "funding_method", "collect_method", "collect_transactions", "funding_transaction", "revenue", "_version")

    def delivery_method(self, obj):
        return obj.collect_method

    def origin_amount(self, obj):
        parameters = obj.parameters
        return format(float(parameters.get('amount_origin', None)), ".2f")

    def destination_amount(self, obj):
        parameters = obj.parameters
        return format(float(parameters.get('amount_destination', None)), ".2f")

    def the_revenue(self, obj):
        return obj.revenue

    def payment_day(self, obj):
        return obj.payment_date

    date_hierarchy = 'updated_at'
    readonly_fields = ('_version',)
    ordering = ('-created_at',)
    fsm_field = ['status', ]
    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget(width="70%", height="200px", mode='text')},
    }

    def transaction_uuid(self, obj):
        return str(obj.uuid)

    form = GlobalTransactionForm


class MyModelForm(forms.ModelForm):
    def __init__(self, user, *args, **kwargs):
        super(MyModelForm, self).__init__(*args, **kwargs)
        api_config = self.instance.api_config
        if user.is_staff:
            if "token" in api_config.keys():
                del api_config['token']
        self.initial['api_config'] = api_config

    class Meta:
        fields = "__all__"
        model = Partner


class PartnerForm(forms.ModelForm):
    class Meta:
        model = Partner
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.fields:
            self.fields['active_payer'].label_from_instance = \
                lambda obj: str(obj.name)


@admin.register(Partner)
class PartnerAdmin(DjangoQLSearchMixin, VersionAdmin):
    list_display = ('uuid', 'name', 'display_name', 'status', 'type',
                    'created_at', 'updated_at',)
    list_filter = ('status', 'created_at', 'updated_at')

    date_hierarchy = 'updated_at'
    readonly_fields = ('_version',)
    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget(width="70%", height="200px", mode='text')},
    }

    form = PartnerForm


@admin.register(Country)
class CountryAdmin(DjangoQLSearchMixin, VersionAdmin, TranslationAdmin):
    list_display = ('uuid', 'active', '__str__', 'country_code', 'enabled_as_origin',
                    'enabled_as_destination', 'calling_code', 'currency', 'created_at', 'updated_at',)
    list_filter = ('created_at', 'updated_at')
    date_hierarchy = 'updated_at'
    readonly_fields = ('_version',)

    def country_code(self, obj):
        return obj.iso_code

    def currency(self, obj):
        return obj.default_currency


@admin.register(Currency)
class CurrencyAdmin(DjangoQLSearchMixin, VersionAdmin):
    list_display = ('uuid', 'sign', 'currency', 'created_at', 'updated_at',)
    list_filter = ('created_at', 'updated_at')

    def currency(self, obj):
        return obj.name

    date_hierarchy = 'updated_at'
    readonly_fields = ('_version',)


@admin.register(PeriodicTasksEntry)
class PeriodicTasksEntryAdmin(DjangoQLSearchMixin, VersionAdmin):
    list_display = ('__str__', 'name', 'uuid', 'created_at', 'updated_at',)
    list_filter = ('name', 'created_at', 'updated_at')
    date_hierarchy = 'updated_at'
    readonly_fields = ('_version',)


@admin.register(TransactionMethod)
class PartnerMethodAdmin(DjangoQLSearchMixin, VersionAdmin):
    list_display = ('uuid', 'name', 'type', 'created_at', 'updated_at',)
    list_filter = ('name', 'created_at', 'updated_at')
    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget(width="70%", height="200px", mode='text')},
    }

    def type(self, obj):
        return obj.type

    date_hierarchy = 'updated_at'
    readonly_fields = ('_version',)


@admin.register(CollectTransaction)
class CollectTransactionAdmin(FSMTransitionMixin, DjangoQLSearchMixin, VersionAdmin):
    list_display = ('__str__', 'uuid', 'created_at', 'updated_at', 'collect_code', 'status', 'amount_origin', 'exchange_rate', 'amount_destination',
                    'delivery_method', 'partner')
    list_filter = ('partner', 'status', 'created_at', 'updated_at')

    def collect_code(self, obj):
        return obj.collect_code

    def delivery_method(self, obj):
        global_tx = obj.globaltransaction_set.all().first()
        if global_tx:
            return global_tx.collect_method

    def amount_origin(self, obj):
        global_tx = obj.globaltransaction_set.all().first()
        if global_tx and global_tx.parameters:
            return format(float(global_tx.parameters.get('amount_origin', None)), ".2f")

    def amount_destination(self, obj):
        global_tx = obj.globaltransaction_set.all().first()
        if global_tx and global_tx.parameters:
            return format(float(global_tx.parameters.get('amount_destination', None)), ".2f")

    def exchange_rate(self, obj):
        global_tx = obj.globaltransaction_set.all().first()
        if global_tx and global_tx.parameters:
            amount_destination = global_tx.parameters.get('amount_destination', None)
            total = global_tx.parameters.get('amount_origin', None)
            if amount_destination and total:
                return format(float(amount_destination) / float(total), ".3f")

    date_hierarchy = 'updated_at'
    readonly_fields = ('_version',)
    fsm_field = ['status', ]

    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget(width="70%", height="200px", mode='text')},
    }


@admin.register(FundingTransaction)
class FundingTransactionAdmin(DjangoQLSearchMixin, VersionAdmin):
    list_display = ('__str__', 'uuid', 'created_at',
                    'updated_at', 'reference_code', 'amount', 'status', 'partner')
    list_filter = ('status', 'created_at', 'updated_at')

    def amount(self, obj):
        global_tx = obj.globaltransaction_set.all().first()
        if global_tx and global_tx.parameters:
            return format(float(global_tx.parameters.get('total', None)), ".2f")

    date_hierarchy = 'updated_at'
    readonly_fields = ('_version',)

    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget(width="70%", height="200px", mode='text')},
    }


@admin.register(PartnerPayer)
class PartnerPayerAdmin(DjangoQLSearchMixin, VersionAdmin):
    list_display = ('uuid', 'partner', 'name', 'code',
                    'created_at', 'updated_at',)
    list_filter = ('partner', 'created_at', 'updated_at')

    date_hierarchy = 'updated_at'
    readonly_fields = ('_version',)


class TransactionMethodsAvaliabiltyForm(forms.ModelForm):
    class Meta:
        model = TransactionMethodAvailability
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        condition_field = self.fields.get('condition')
        if condition_field and condition_field.widget.attrs['value']:
            self.fields['active'].widget.attrs['disabled'] = 'true'


@admin.register(TransactionMethodAvailability)
class CollectTransactionMethodAvailabilityAdmin(DjangoQLSearchMixin, VersionAdmin):
    list_display = ('uuid', 'partner', 'active', 'delivery_method', 'created_at', 'updated_at',)
    list_filter = ('partner_method', 'partner',
                   'active', 'created_at', 'updated_at')

    def delivery_method(self, obj):
        return obj.partner_method

    date_hierarchy = 'updated_at'

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.condition:
            return ('active', '_version')
        else:
            print('im here')
            return ('_version',)

    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget(width="70%", height="200px", mode='text')},
    }


@admin.register(PartnerSettlementAccount)
class PartnerSettlementAccountAdmin(DjangoQLSearchMixin, VersionAdmin):
    list_display = ('uuid', 'partner',
                    'active', 'primary_account', 'currency', 'account_number', 'created_at', 'updated_at',)
    list_filter = ('partner', 'active', 'created_at', 'updated_at')

    def primary_account(self, obj):
        return obj.is_primary_account

    date_hierarchy = 'updated_at'
    readonly_fields = ('_version',)


@admin.register(ExchangeRateTier)
class RateTierAdmin(DjangoQLSearchMixin, VersionAdmin):
    list_display = ('uuid', 'country_origin',
                    'country_destination', 'bottom_amount', '_applicable_rate', 'created_at', 'updated_at',)
    list_filter = ('country_origin', 'country_destination',
                   'created_at', 'updated_at')

    date_hierarchy = 'updated_at'
    readonly_fields = ('_version',)
    ordering = ('country_origin', 'country_destination', '-bottom_amount',)

    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget(width="70%", height="200px", mode='text')},
    }

    def _applicable_rate(self, obj):
        return format(float(obj.applicable_rate), ".3f")

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context["show_close"] = True
        return super().changeform_view(
            request,
            object_id=object_id,
            form_url=form_url,
            extra_context=extra_context
        )

    def render_change_form(self, request, context, *args, **kwargs):
        if context['adminform'].form.fields:
            context['adminform'].form.fields['country_origin'].queryset = Country.objects.filter(
                enabled_as_origin=True, active=True)
            context['adminform'].form.fields['country_destination'].queryset = Country.objects.filter(
                enabled_as_destination=True, active=True)
        return super(RateTierAdmin, self).render_change_form(request, context, *args, **kwargs)


@admin.register(PartnerExchangeRate)
class RateAdmin(DjangoQLSearchMixin, VersionAdmin):
    list_display = ('uuid', 'partner', 'country_origin',
                    'country_destination', 'sett_to_dest_rate', 'orig_to_sett_rate', 'fee', '_cost_price', 'created_at', 'updated_at',)
    list_filter = ('country_origin', 'country_destination',
                   'created_at', 'updated_at')

    def sett_to_dest_rate(self, obj):
        return format(float(obj.settlement_to_destination_rate), ".3f")

    def orig_to_sett_rate(self, obj):
        return format(float(obj.origin_to_settlement_rate), ".3f")

    def _cost_price(self, obj):
        return format(float(obj.cost_price), ".3f")

    date_hierarchy = 'updated_at'
    readonly_fields = ('_version',)
    ordering = ('-country_origin', '-country_destination', '-partner')

    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget(width="70%", height="200px", mode='text')},
    }

    def render_change_form(self, request, context, *args, **kwargs):
        if context['adminform'].form.fields:
            context['adminform'].form.fields['country_origin'].queryset = Country.objects.filter(
                enabled_as_origin=True, active=True)
            context['adminform'].form.fields['country_destination'].queryset = Country.objects.filter(
                enabled_as_destination=True, active=True)
        return super(RateAdmin, self).render_change_form(request, context, *args, **kwargs)


@admin.register(UserTier)
class UserTierAdmin(DjangoQLSearchMixin, VersionAdmin):
    list_display = ('uuid', 'level', 'created_at', 'updated_at',)
    list_filter = ('level', 'tx_max', 'created_at', 'updated_at')

    date_hierarchy = 'updated_at'
    readonly_fields = ('_version',)

    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget(width="70%", height="200px", mode='text')},
    }


@admin.register(APICollectToken)
class APICollectTokenAdmin(DjangoQLSearchMixin, VersionAdmin):
    list_display = ('uuid', 'expires_at', 'api_user', 'token', 'global_transaction_id',
                    'created_at', 'updated_at',)
    list_filter = ('token', 'api_user', 'created_at', 'updated_at')

    def global_transaction_id(self, obj):
        return str(obj.global_transaction.uuid)

    date_hierarchy = 'updated_at'
    readonly_fields = ('_version',)


class PaymentCodeFilter(SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = 'Payment Code'

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'payment_code'

    def lookups(self, request, model_admin):
        queryset = APIRequestMonitoring.objects.all()
        codes = ()
        for instance in queryset:
            request = instance.body.get('request', None)
            if request and request.get("service", None):
                service = request.get('service')
                data = service.get('data', None)
                if data:
                    payment_orders = data.get('paymentOrders', None)
                    payment_order = data.get('paymentOrder', None)
                    if payment_orders:
                        if isinstance(type(payment_orders), type(list)):
                            for payment_code in payment_orders:
                                if payment_code.get('payment', None) and payment_code.get('payment', None).get('code', None):
                                    code = payment_code.get('payment', None).get('code', None)
                                    codes += ((code, code),)
                    if payment_order:
                        if isinstance(type(payment_orders), type(dict)):
                            if payment_order.get('payment', None) and payment_order.get('payment', None).get('code', None):
                                code = payment_order.get('payment', None).get('code', None)
                                codes += ((code, code),)
        return codes

    def queryset(self, request, queryset):
        if self.value():
            obj = queryset.filter(
                Q(body__request__service__data__paymentOrders__contains=[{"payment": {"code": self.value()}}]) |
                Q(body__request__service__data__paymentOrder__contains={"payment": {"code": self.value()}})
            )
            return obj
        return queryset


@admin.register(APIRequestMonitoring)
class APIRequestMonitoringAdmin(DjangoQLSearchMixin, VersionAdmin):
    list_display = ('uuid', 'api_user', 'payment_codes', 'service_name', 'response_message', 'response_status_code', 'created_at', 'updated_at',)
    list_filter = ('method', 'api_user', 'created_at', 'updated_at', PaymentCodeFilter)

    def response_message(self, obj):
        response = obj.response.get('jsonResponse', None)
        if response:
            if response.get('response', None) and response.get('response', None).get('code', None) and response.get('response', None).get('message',
                                                                                                                                          None):
                return f"{response.get('response', None).get('code', None)} - {response.get('response', None).get('message', None)}"

    def payment_codes(self, obj):
        request = obj.body.get('request', None)
        if request and request.get("service", None):
            service = request.get('service')
            data = service.get('data', None)
            if data:
                payment_orders = data.get('paymentOrders', None)
                payment_order = data.get('paymentOrder', None)
                payment_codes = []
                if payment_orders:
                    if isinstance(type(payment_orders), type(list)):
                        for payment_code in payment_orders:
                            if payment_code.get('payment', None):
                                payment_codes.append(payment_code.get('payment').get('code', None))
                if payment_order:
                    if isinstance(type(payment_order), type(dict)):
                        if payment_order.get('payment', None):
                            payment_codes.append(payment_order.get('payment').get('code', None))

                return str(payment_codes)

    def service_name(self, obj):
        request = obj.body.get('request', None)
        if request and request.get("service", None):
            service = request.get('service')
            return service.get('name', None)

    def response_status_code(self, obj):
        return obj.response.get('httpStatus', None)

    date_hierarchy = 'updated_at'
    readonly_fields = ('_version',)

    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget(width="70%", height="200px", mode='text')},
    }


@admin.register(AppSettings)
class AppSettingsAdmin(DjangoQLSearchMixin, VersionAdmin):
    list_display = ('__str__', 'uuid', 'created_at', 'updated_at',)
    list_filter = ('created_at', 'updated_at')
    date_hierarchy = 'updated_at'
    readonly_fields = ('_version',)

    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget(width="70%", height="400px", mode='code')},
    }


@admin.register(TxLimitCumul)
class TxLimitCumulAdmin(DjangoQLSearchMixin, VersionAdmin):
    list_display = ('uuid', 'user', 'operation', '_limit_1_month', '_limit_3_month',
                    '_limit_12_month', '_total_transfered_amount', 'created_at', 'updated_at',)
    list_filter = ('created_at', 'updated_at')
    date_hierarchy = 'updated_at'
    readonly_fields = ('_version',)

    def _limit_1_month(self, obj):
        return format(float(obj.limit_1_month), ".2f")

    def _limit_3_month(self, obj):
        return format(float(obj.limit_3_month), ".2f")

    def _limit_12_month(self, obj):
        return format(float(obj.limit_12_month), ".2f")

    def _total_transfered_amount(self, obj):
        return format(float(obj.total_transfered_amount), ".2f")


@admin.register(AdminAlerts)
class AdminAlertsAdmin(DjangoQLSearchMixin, VersionAdmin):
    list_display = ('uuid', 'user', 'can_get_receiver_sms', 'can_receive_admin_alerts',
                    'can_receive_celery_exceptions', 'created_at', 'updated_at',)
    list_filter = ('created_at', 'updated_at')
    date_hierarchy = 'updated_at'
    readonly_fields = ('_version',)

    def render_change_form(self, request, context, *args, **kwargs):
        if context['adminform'].form.fields:

            context['adminform'].form.fields['user'].queryset = User.objects.filter(
                is_staff=True)
        return super(AdminAlertsAdmin, self).render_change_form(request, context, *args, **kwargs)


@admin.register(UserToken)
class UserTokenAdmin(DjangoQLSearchMixin, VersionAdmin):
    list_display = ('uuid', 'user', 'device_type',
                    'created_at', 'updated_at',)
    list_filter = ('created_at', 'updated_at')
    date_hierarchy = 'updated_at'
    readonly_fields = ('_version',)

    formfield_overrides = {
        models.JSONField: {'widget': JSONEditorWidget(width="70%", height="200px", mode='text')},
    }


@admin.register(MobileNetwork)
class MobileNetworkAdmin(DjangoQLSearchMixin, VersionAdmin):
    list_display = ('uuid', 'display_name', 'created_at', 'updated_at',)
    list_filter = ('display_name', 'created_at', 'updated_at')
    date_hierarchy = 'updated_at'
    readonly_fields = ('_version',)


@admin.register(MobileNetworkAvailability)
class MobileNetworkAvailabilityAdmin(DjangoQLSearchMixin, VersionAdmin):
    list_display = ('uuid', 'mobile_network', 'country', 'active', 'created_at', 'updated_at',)
    list_filter = ('mobile_network', 'country', 'active', 'created_at', 'updated_at')
    date_hierarchy = 'updated_at'
    readonly_fields = ('_version',)
