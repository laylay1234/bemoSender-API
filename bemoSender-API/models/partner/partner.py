import copy
from datetime import timedelta
from django.db import models
from loguru import logger
from bemosenderrr.models.base import AbstractBaseModel, PartnerStatus, PartnerType, TransactionTypes
from bemosenderrr.models.partner.base import PartnerApiCallType
from django.core.exceptions import ValidationError
import json
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone
from django.template.defaultfilters import truncatechars



class Partner(AbstractBaseModel):
    display_name = models.CharField(_("Partner Display Name"), help_text=_('The name of the partner to be displayed'), max_length=64)
    name = models.CharField(_("Partner Name"), help_text=_('The PartnerTransaction name'), max_length=255)
    contact_full_name = models.CharField(_('Partner Contact Full Name'), help_text=_('First and last name of the Partner'), max_length=64)
    contact_email = models.EmailField(_('Partner Contact Email'), help_text=_('Email of the Partner'))
    country = models.ForeignKey('Country', on_delete=models.RESTRICT, help_text=_('The country of the Partner'))
    status = models.CharField(_('Status'), help_text=_('Partner status'), max_length=8, choices=PartnerStatus.choices, default=PartnerStatus.active)
    api_config = models.JSONField(_('Configuration'), default=dict, help_text=_('The configuration to consume the API of the Partner'))
    api_user = models.ForeignKey('User', help_text=_('Associated API user'), on_delete=models.RESTRICT, null=True, blank=True)
    type = models.CharField(_('Type'), help_text=_('Partner type'), max_length=30, choices=PartnerType.choices)
    currency = models.ForeignKey('Currency', on_delete=models.RESTRICT)
    api_call_type = models.CharField(_('Partner API call type'), choices=PartnerApiCallType.choices, max_length=255)
    active_payer = models.ForeignKey('PartnerPayer', on_delete=models.RESTRICT, help_text=_('The active payer'), related_name='active_payer',
                                     null=True, blank=True)

    def __str__(self) -> str:
        return self.name

    def clean(self):
        if self.api_call_type == PartnerApiCallType.inbound:
            if self.api_user is None:
                raise ValidationError('You must choose an API User for this type of partner')

        """
        Temporary check for gmail and apaylo (only one active funding partner)
        In the case of multiple funding partners(other than apaylo and gmail) we have to think how
        will this effect the flow.

        """
        print('active')
        if self.status == PartnerStatus.active and self.type == PartnerType.funding:

            funding_partners = Partner.objects.filter(type=PartnerType.funding)
            if funding_partners:
                print(funding_partners)
                for funding_partner in funding_partners:
                    funding_partner.status = PartnerStatus.inactive
                    funding_partner.save()
        if self.status != PartnerStatus.active and self.type == PartnerType.collect:
            tx_methods_availabilities = TransactionMethodAvailability.objects.filter(partner=self)
            print(tx_methods_availabilities)
            if tx_methods_availabilities:
                for tx_method in tx_methods_availabilities:
                    tx_method.active = False
                    tx_method.save()
        super(Partner, self).clean()


class TransactionMethod(AbstractBaseModel):
    name = models.CharField(max_length=255, help_text="Delivery method name")
    code_name = models.CharField(max_length=255, help_text="Delivery method code name", null=True, blank=True)
    img_urls = models.JSONField(help_text="Image urls of the delivery method", default=dict)
    type = models.CharField(max_length=255, choices=TransactionTypes.choices, help_text="Transaction method type")

    def __str__(self) -> str:
        return f'{self.name} ({self.type})'


class TransactionMethodAvailability(AbstractBaseModel):
    partner = models.ForeignKey('Partner', on_delete=models.CASCADE)
    partner_method = models.ForeignKey('TransactionMethod', on_delete=models.CASCADE)
    active = models.BooleanField(help_text='Transaction method availability')
    api_code = models.IntegerField(help_text='The api code of this transaction method')
    condition = models.JSONField(_('Condition on the active payer'), blank=True, null=True)

    def clean(self) -> None:
        # TODO solve this.
        if self.condition is not None:
            conditions = self.condition.get("conditions", None)
            if conditions:
                partner_fields = [str(field.name).lower() for field in Partner._meta.get_fields()]
                for k, v in conditions.items():
                    if k == "equals":
                        for item in v:
                            if str(item.get('property', None)).lower() in partner_fields:
                                print(str(item.get('property', None)).lower())
                                print(getattr(self.partner, str(item.get('property', None)).lower()))
                                if str(item.get('value', None)).lower() in str(
                                        getattr(self.partner, str(item.get('property', None)).lower())).lower():
                                    self.active = True
                                else:
                                    self.active = False
        if "bank" in str(self.partner_method.name).lower():
            collect_methods_availabilities = TransactionMethodAvailability.objects.filter(partner__country=self.partner.country,
                                                                                          partner_method=self.partner_method, active=True)
            if collect_methods_availabilities:
                for tx_meth_avail in collect_methods_availabilities:
                    tx_meth_avail.active = False
                    tx_meth_avail.save()
        super(TransactionMethodAvailability, self).clean()

    def __str__(self) -> str:
        return f'{self.partner_method.name} availability for {self.partner}'

    class Meta:
        verbose_name_plural = _('Transaction Methods Availabilities')
        ordering = ['created_at']


class PartnerPayer(AbstractBaseModel):
    partner = models.ForeignKey('Partner', on_delete=models.RESTRICT)
    name = models.CharField(_("Payer Name"), max_length=255)
    code = models.IntegerField(help_text="The partner's payer code")

    def __str__(self) -> str:
        return f'{self.name} for {self.partner} Partner'


# TODO  needs to be determined if needed or not
class PartnerBalance(AbstractBaseModel):
    partner = models.ForeignKey('Partner', on_delete=models.RESTRICT)
    key = models.CharField(_('Key'), help_text=_('Probably the account name'), max_length=64)
    balance = models.DecimalField(_('Balance'), help_text=_('The calculated balance for the given account.'), decimal_places=2, max_digits=30)


class Currency(AbstractBaseModel):
    sign = models.CharField(_("Currency's sign"), help_text=_('sign of the currency ex. CAD'), max_length=3)
    name = models.CharField(_('Currency Name'), help_text=_('Name of the currency'), max_length=255)
    short_sign = models.CharField(_("Currency's short sign"), help_text=_('Short sign of the currency ex. $'), max_length=255)
    iso_code = models.CharField(_('Currency ISO Code'), help_text=_('ISO Code of this currency'), max_length=4)

    def __str__(self) -> str:
        return self.sign

    class Meta:
        verbose_name_plural = _('Currencies')
        ordering = ['created_at']


class Country(AbstractBaseModel):
    iso_code = models.CharField(_('Country ISO Code'), help_text=_('ISO Code of this country'), max_length=2)
    alpha_3_code = models.CharField(_('Country ISO Code alpha 3'), help_text=_('3 letter country code'), max_length=3, null=True, blank=True)
    name = models.CharField(_('Country Name'), help_text=_('Country name'), max_length=64)
    enabled_as_origin = models.BooleanField(help_text='Enabled as origin country')
    enabled_as_destination = models.BooleanField(help_text='Enabled as destination country')
    active = models.BooleanField()
    calling_code = models.CharField(help_text='Country phone code', max_length=4)
    default_currency = models.ForeignKey('Currency', on_delete=models.RESTRICT)

    def __str__(self) -> str:
        return self.name

    class Meta:
        verbose_name_plural = _('Countries')
        ordering = ['created_at']


class PartnerSettlementAccount(AbstractBaseModel):
    currency = models.ForeignKey('Currency', on_delete=models.RESTRICT)
    partner = models.ForeignKey('Partner', on_delete=models.RESTRICT)
    active = models.BooleanField(help_text='Status of the this account')
    is_primary_account = models.BooleanField()
    account_number = models.CharField(max_length=255, help_text='The account number of this account')

    def clean(self):
        if self.active:
            sett_account_queryset = PartnerSettlementAccount.objects.filter(partner=self.partner).exclude(uuid=self.uuid)
            for sett_acc in sett_account_queryset:
                sett_acc.active = False
                sett_acc.save()
        super(PartnerSettlementAccount, self).clean()

    def __str__(self) -> str:
        return f'{self.partner} settlement account'


"""
### PartnerExchangeRate

|          old            |             new                |
|-------------------------|--------------------------------|
| ref_rate                | reference_rate                 |
| rate_partner            | settlement_to_destination_rate |
| rate_fx                 | origin_to_settlement_rate      |
| rate_fee                | fee                            |
| rate_yxf                | cost_price                     |
| partner_active_currency | settlement_currency            |
| commission_partner      | commission_percentage          |
| *add*                   | commission_fixed               |
| percent_partner         | sales_percentage               |

"""


class PartnerExchangeRate(AbstractBaseModel):
    partner = models.ForeignKey('Partner', on_delete=models.RESTRICT)
    country_origin = models.ForeignKey('Country', on_delete=models.RESTRICT, related_name='rate_country_origin')
    country_destination = models.ForeignKey('Country', on_delete=models.RESTRICT, related_name='rate_country_destination')
    settlement_currency = models.ForeignKey('Currency', on_delete=models.RESTRICT)
    reference_rate = models.CharField(max_length=255, help_text='Exchange rate from currency origin to currency destination')
    settlement_to_destination_rate = models.CharField(max_length=255,
                                                      help_text='Exchange rate from ActivePartnerSettlementCurrency to destination currency')
    fee = models.CharField(max_length=255, help_text='The rate fee')
    origin_to_settlement_rate = models.CharField(max_length=255, help_text='Exhange rate from origin currency to ActivePartnerSettlementCurrency')
    cost_price = models.CharField(max_length=255, help_text='Applicable exchange rate of the partner')  # TODO  find a better naming
    commission_percentage = models.CharField(max_length=255, help_text='Sales commission per transaction for this partner')  # TODO add description
    commission_fixed = models.CharField(_("Commission Fixed (this field is not used anywhere !)"), max_length=255,
                                        help_text='Sales commission per transaction for this partner (This is not used anywhere!)')  # can be used along with commission_percentage
    sales_percentage = models.CharField(max_length=255, help_text='The percentage of transactions on the partner network')
    query_response = models.JSONField(null=True, blank=True)

    @property
    def settlement_to_destination_rate_truncated(self):
        return truncatechars(self.settlement_to_destination_rate, 15)

    def clean(self):

        exchange_rates = PartnerExchangeRate.objects.filter(country_origin=self.country_origin, country_destination=self.country_destination).exclude(
            uuid=self.uuid)
        if float(self.commission_percentage) > 0.025 or float(self.commission_percentage) < 0:
            raise ValidationError(f"Commission percentage must be in range 0 ... 0.025")
        if exchange_rates:
            sales_percentages = [float(item.sales_percentage) for item in exchange_rates]
            sum_sales_percentages = round(sum(sales_percentages), 4) + float(self.sales_percentage)
            logger.info(sum_sales_percentages)
            if sum_sales_percentages > 1:
                raise ValidationError('Percent partner total exceeded 1')
        super(PartnerExchangeRate, self).clean()

    def __str__(self) -> str:
        return self.partner.name


"""
### ExchangeRateTier

|       old      |              new                |
|----------------|---------------------------------|
| commission_yxf | profit_margin_percentage        |
| fees           | collect_transaction_method_fees |
| rate           | applicable_rate                 |
| low            | bottom_amount                   |

"""


class ExchangeRateTier(AbstractBaseModel):
    country_origin = models.ForeignKey('Country', on_delete=models.RESTRICT, related_name='rate_tier_country_origin')
    country_destination = models.ForeignKey('Country', on_delete=models.RESTRICT, related_name='rate_tier_country_destination')
    bottom_amount = models.PositiveIntegerField(help_text='Minimum value of this rate tier')
    distribution_percentage = models.CharField(max_length=255, help_text='The percentage of transactions in this rate tier')
    profit_margin_percentage = models.CharField(max_length=255,
                                                help_text='Sales commission per transaction for bemosenderrr')  # TODO rename this properly (sales commission for bemosenderrr)
    applicable_rate = models.CharField(max_length=255, help_text='calculataed exchange rate available to the client based on ratetier level')
    collect_transaction_method_fees = models.JSONField(help_text='Fees related to the delivery method', null=True, blank=True)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super(ExchangeRateTier, self).save(*args, **kwargs)

    def clean(self):
        partners = Partner.objects.filter(country=self.country_destination)
        data = list()
        collect_methods = TransactionMethod.objects.filter(type=TransactionTypes.collect)
        for collect_method in collect_methods:
            names = copy.deepcopy([])
            names.append({
                "lang": "en",
                "name": collect_method.name_en
            })
            names.append({
                "lang": "fr",
                "name": collect_method.name_fr
            })
            image_data = {f"img_{k}": v for k, v in collect_method.img_urls.items()}
            data.append(
                {
                    **image_data,
                    "name": collect_method.name,
                    "fee": "",
                    "active": "",
                    "code_name": collect_method.code_name,
                    "names": names
                }
            )
        for item in data:
            collect_methods = TransactionMethodAvailability.objects.filter(partner__in=partners, partner_method__name=item['name'], active=True)
            if collect_methods:
                item["active"] = str(True)
            else:
                item["active"] = str(False)
        if self.collect_transaction_method_fees:
            for item in self.collect_transaction_method_fees:
                tmp = False
                if item["fee"] != "":
                    for val in data:
                        if val['name'] == item['name']:
                            tmp = True
                            val['fee'] = item['fee']
                            break
                    if not tmp:
                        for val in data:
                            if val['fee'] == "":
                                val['fee'] = item['fee']
                                break

        self.collect_transaction_method_fees = data

        if float(self.profit_margin_percentage) > 1 or float(self.profit_margin_percentage) < -0.0007:
            raise ValidationError(f"Profit Margin Percentage must be in range 1 ... -0.0007")
        super(ExchangeRateTier, self).clean()

    def __str__(self) -> str:
        return f'Exchange Rate tier for {self.country_origin} => {self.country_destination} for bottom amount => {self.bottom_amount}'


class UserTier(AbstractBaseModel):
    level = models.CharField(max_length=255, help_text='the user tier level')
    tx_max = models.JSONField(help_text='the maximum amount to send in a transaction for this level')
    monthly_max = models.JSONField(help_text='The maximum number of transactions and amount per month')
    quarterly_max = models.JSONField(help_text='The maximum number of transactions and amount per 3 months')
    yearly_max = models.JSONField(help_text='The maximum number of transactions and amount per year')

    def __str__(self) -> str:
        return f'User tier level {self.level}'


class APICollectToken(AbstractBaseModel):
    token = models.CharField(max_length=255, help_text='The Partner API user generated token')
    expires_at = models.DateTimeField(default=timezone.now, blank=True, null=True, help_text='Expiration time of the token')
    api_user = models.ForeignKey('User', on_delete=models.RESTRICT, null=False, blank=False, help_text="The associated API User")
    global_transaction = models.ForeignKey('GlobalTransaction', on_delete=models.RESTRICT, help_text='The global transaction associated')

    def save(self, force_insert=False, force_update=False, *args, **kwargs):
        self.expires_at = self.expires_at + timedelta(minutes=10)
        instance = super(APICollectToken, self).save(force_insert, force_update, *args, **kwargs)
        return instance


class APIRequestMonitoring(AbstractBaseModel):
    method = models.CharField(max_length=255, help_text='The HTTP method of the request', null=True, blank=True)
    path = models.CharField(max_length=255, help_text='The url after the base url of the domain', null=True, blank=True)
    api_user = models.ForeignKey('User', on_delete=models.RESTRICT)
    body = models.JSONField(help_text='The request body data', null=True, blank=True)
    request = models.JSONField(help_text='The request params and headers', null=True, blank=True)
    response = models.JSONField(help_text='The response, status and timestamp', null=True, blank=True)

    def __str__(self) -> str:
        return str(f"API Request Monitoring for  {self.api_user}")


class AppSettings(AbstractBaseModel):
    config = models.JSONField(help_text="Application Settings", null=True, blank=True)
    """
    ------------------------------------------------------------------------------------------------------------------------------------------------------------
    |       Field               |                                                    Desctiption                                                               |
    |---------------------------|------------------------------------------------------------------------------------------------------------------------------|
    | clientHelpDesk            | Client support information                                                                                                   |
    | policyUrlList             | Used in the frontend to display the desired link to TOS and privacy policies based on mobile app language and origin country.|
    | minTransactionValue       | Minimum transaction values for each origin country                                                                           |
    | supportedAppVersion       | Used on the frontend to force the update of the mobile app and restrict the use of older/non-supported apps.                 |
    ------------------------------------------------------------------------------------------------------------------------------------------------------------


    clientHelpDesk = models.JSONField(help_text="Client support information", null=True, blank=True)
    policyUrlList = models.JSONField(help_text="Used in the frontend to display the desired link to TOS and privacy policies based on mobile app language and origin country.", null=True, blank=True)
    minTransactionValue = models.JSONField(help_text="Minimum transaction values for each origin country", null=True, blank=True)
    #supportedAppVersion = models.JSONField(help_text="Used on the frontend to force the update of the mobile app and restrict the use of older/non-supported apps.", null=True, blank=True)
    rateLimits = models.JSONField(help_text="Used in the admin back-office to validate the values entered when creating/updating ExchangeRates and ExchangeRateTiers", null=True, blank=True)
    rateTierLevels = models.JSONField(help_text="Used by the backend as default values when creating ExchangeRateTiers", null=True, blank=True)
   
    def clean(self) -> None:
        merged = {}
        merged["clientHelpDesk"] = self.clientHelpDesk
        merged["policyUrlList"] = self.policyUrlList
        merged["minTransactionValue"] = self.minTransactionValue
        merged["rateLimits"] = self.rateLimits
        merged["rateTierLevels"] = self.rateTierLevels
        print(merged)
        return super().clean()
     """

    def clean(self) -> None:
        config = self.config
        if config:
            funding_expiry_time = config.get('fundingExpTime', None)
            print(type(funding_expiry_time))
            if funding_expiry_time:
                if not isinstance(funding_expiry_time, float) and not isinstance(funding_expiry_time, int):
                    raise ValidationError("Funding Expiration Time must be a float ")
                else:
                    remainder = funding_expiry_time % 0.5
                    if remainder != 0:
                        raise ValidationError("Funding Expiration Time must be dividable by 0.5 ")
        return super().clean()

    class Meta:
        verbose_name_plural = _('App Settings')
        ordering = ['created_at']


class MobileNetwork(AbstractBaseModel):
    display_name = models.CharField(help_text="The mobile network name", max_length=255)
    partner_api_code_mapping = models.JSONField(null=True, blank=True,
                                                help_text="the keys for this dictionary must come from the api_config['serviceClass'] in the partner model")

    def __str__(self) -> str:
        return self.display_name


class MobileNetworkAvailability(AbstractBaseModel):
    mobile_network = models.ForeignKey("MobileNetwork", help_text="The mobile network", on_delete=models.RESTRICT)
    country = models.ForeignKey("Country", help_text="Destination country", on_delete=models.RESTRICT)
    active = models.BooleanField(help_text="Mobile Network availbility")

    class Meta:
        verbose_name_plural = _('Mobile Networks Availabilities')
        ordering = ['created_at']
