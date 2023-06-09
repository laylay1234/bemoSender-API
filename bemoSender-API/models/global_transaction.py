from django.db import models
from django.utils.translation import ugettext_lazy as _
from loguru import logger
from bemoSenderr.models.base import AbstractBaseModel, CollectTransactionStatus, FundingTransactionStatus, GlobalTransactionStatus, PartnerStatus, PartnerType
from bemoSenderr.models.partner.partner import Country, MobileNetwork, MobileNetworkAvailability, Partner, PartnerExchangeRate, PartnerSettlementAccount, TransactionMethod, TransactionMethodAvailability
from django.forms.models import model_to_dict
from bemoSenderr.models.partner.transactions import CollectTransaction, FundingTransaction
from django_fsm import FSMField
from bemoSenderr.models.transitions import GlobalTransactionTransitions

class GlobalTransaction(AbstractBaseModel, GlobalTransactionTransitions):
    user = models.ForeignKey('User', help_text=_('Associated user'), on_delete=models.RESTRICT, null=True, blank=True)
    status = FSMField(_('Status'), help_text=_('Global Transaction status'), max_length=64, choices=GlobalTransactionStatus.choices, default=GlobalTransactionStatus.new)
    receiver_snapshot = models.JSONField(_('Recipient Information'), default=dict, null=True, blank=True)
    user_snapshot = models.JSONField(_('User Information including the IP address'), default=dict)
    parameters = models.JSONField(_('Countries , Amounts, Reason of Transfer, Currencies, Total, and deliveryMethodFee'), default=dict)
    exchange_rate_tier_snapshot = models.JSONField(_('partnerRate, rateFee, rateFx, refRate, commissionPartner, exchangeRate, commissionYxf'), default=dict)
    invoice_number = models.BigIntegerField(_('The invoice number'), null=True, blank=True) ## set to null
    notifications = models.JSONField(_('SMS notifications status'), null=True, blank=True) ## set to null
    payment_date = models.DateTimeField(_('The payment date'), null=True, blank=True)
    funding_method = models.CharField(_('Funding method of the user'), max_length=255)#TODO validate where to put this
    collect_method = models.CharField(_('Collect method of the user'), max_length=255)#TODO validate where to put this
    collect_transactions = models.ManyToManyField('CollectTransaction', blank=True, null=True)
    funding_transaction = models.ForeignKey('FundingTransaction', on_delete=models.RESTRICT, null=True, blank=True)
    revenue = models.CharField(_('The revenue from this transaction'), max_length=255, null=True, blank=True)
    def save(self, force_insert=False, force_update=False, *args, **kwargs):
        if self.funding_transaction is None:
            self.add_funding_transaction()
        if not self.invoice_number:
            try:
                latest_global_tx = GlobalTransaction.objects.latest('created_at')
                self.invoice_number = latest_global_tx.invoice_number + 1
            except Exception as e:
                print('This is the first object')
                self.invoice_number = 1
        if self.notifications is None:
            self.notifications = {
                "tx_collect_ready_sender": False,
                "tx_collected_sender": False,
                "tx_collect_ready_receiver": False
            }
        instance = super(GlobalTransaction, self).save(force_insert, force_update, *args, **kwargs)
        if not self.collect_transactions.all().exists():
            self.add_collect_transactions()
        
        # transaction.on_commit(self.add_collect_transactions,)
        
        return instance

    # Add the right partners and transactions for the global transaction
    def add_collect_transactions(self):
        destination_country = Country.objects.get(iso_code=self.parameters['destination_country'])
        collect_partners = list()
        if "bank" in str(self.collect_method).lower():
            print('BANK TRANSFER')
            #TODO change it after the translation is stable
            # collect_method = TransactionMethod.objects.filter(code_name=self.collect_method).first()
            collect_method = TransactionMethod.objects.filter(name__icontains="bank").first()
            if collect_method:
                collect_method_availability = TransactionMethodAvailability.objects.filter(partner__country=destination_country, partner_method=collect_method, active=True).select_related("partner").first()
                if collect_method_availability:
                    collect_partners = [collect_method_availability.partner]
                else:
                    collect_partners =  None
        elif "mobile" in str(self.collect_method).lower():
            print("Mobile Network")
            #TODO change it after the translation is stable
            # collect_method = TransactionMethod.objects.filter(code_name=self.collect_method).first()
            mobile_network = TransactionMethod.objects.filter(name__icontains="mobile").first()
            if mobile_network:
                mobile_network_availability = MobileNetworkAvailability.objects.filter(country=destination_country, active=True).first()
                if mobile_network_availability:
                    collect_partners = [Partner.objects.filter(country=destination_country, status=PartnerStatus.active).first()]
                else:
                    collect_partners =  None
        elif "cash" in str(self.collect_method).lower():
            print('cash')
            #TODO change it after the translation is stable
            # collect_method = TransactionMethod.objects.filter(code_name=self.collect_method).first()
            collect_method = TransactionMethod.objects.filter(name__icontains="cash").first()
            if collect_method:
                collect_method_availabilities = TransactionMethodAvailability.objects.filter(partner__country=destination_country, partner_method=collect_method, active=True)
                if collect_method_availabilities:
                    for collect_method_availability in collect_method_availabilities:
                        if collect_method_availability.partner.status == PartnerStatus.active:
                            collect_partners.append(collect_method_availability.partner)
                else:
                    collect_partners =  None      
        if collect_partners is not None:
            for collect_partner in collect_partners:
                exchange_rate = PartnerExchangeRate.objects.get(partner=collect_partner)
                partner_settlement_currency = PartnerSettlementAccount.objects.filter(partner=collect_partner, active=True).prefetch_related("currency").first()
                partner_sett_acc_snapshot = {}
                if partner_settlement_currency:
                    partner_sett_acc_snapshot['settlement_currency'] = partner_settlement_currency.currency.iso_code
                    partner_sett_acc_snapshot['account_number'] = partner_settlement_currency.account_number
                # snapshot the currency iso_code and account number
                #TODO which fields should i include/exclude and fix the UUID not serializable
                exchange_rate_snapshot = model_to_dict(exchange_rate, exclude=['uuid', 'settlement_currency', 'country_destination', 'country_origin', 'partner'])
                collect_transaction = CollectTransaction.objects.create(partner=collect_partner, status=CollectTransactionStatus.new,
                                        exchange_rate_snapshot=exchange_rate_snapshot, partner_settlement_acc_snapshot=partner_sett_acc_snapshot
                )
                self.collect_transactions.add(collect_transaction)
                
    def add_funding_transaction(self):
        origin_country = Country.objects.get(iso_code=self.parameters['origin_country'])
        funding_partner = Partner.objects.filter(type=PartnerType.funding,
            status=PartnerStatus.active, country=origin_country).first()
        if funding_partner is not None:
            funding_transaction = FundingTransaction.objects.create(partner=funding_partner, status=FundingTransactionStatus.in_progress)
            self.funding_transaction = funding_transaction
            print(funding_transaction)

    def calculate_revenue(self, collect_tx=None):
        try:
            for instance in self.collect_transactions.all():
                logger.info(f'COLLECT TRANSACTION {instance} {instance.status} ')
            collect_transaction = collect_tx
            logger.info(f"THIS IS THE REVENUE CALCULATION {collect_transaction}")
            if collect_transaction:
                collect_partner = collect_transaction.partner
                exchange_rate = PartnerExchangeRate.objects.filter(partner=collect_partner).first()
                amount_origin = float(self.parameters['amount_origin'])
                amount_destination = float(self.parameters['amount_destination'])
                if exchange_rate:
                    A = ((float(exchange_rate.settlement_to_destination_rate) * float(exchange_rate.origin_to_settlement_rate) * amount_origin) * (1-float(exchange_rate.commission_percentage))) - amount_destination
                    logger.info(f'this is exchange_rate.settlement_to_destination_rate {float(exchange_rate.settlement_to_destination_rate)}')
                    logger.info(f'this is exchange_rate.origin_to_settlement_rate {float(exchange_rate.origin_to_settlement_rate)}')
                    logger.info(f'this is exchange_rate.commission_percentage {(1-float(exchange_rate.commission_percentage))}')
                    logger.info(f'this is amount_destination {amount_destination}')
                    logger.info(f'this is A {A}')
                    B = float(exchange_rate.settlement_to_destination_rate) * float(exchange_rate.origin_to_settlement_rate)
                    logger.info(f'this is A {B}')
                    REVENUE = A / B + float(self.parameters['fee'])
                    self.revenue = round(REVENUE, 3)
                    self.save()
                    return True
        except Exception as e:
            print(e.args)
            self.save()
            return False
                

    def __str__(self):
        return f'Global Transaction for user {self.user.email}'

    class Meta:
        verbose_name = _('Global Transaction')
        verbose_name_plural = _('Global Transactions')
        ordering = ['created_at']

    

