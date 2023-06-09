import json
import sys
import traceback
from django.conf import settings
from django.db import models
import datetime
from bemoSenderr.logger import SendAdminAlerts, send_email_celery_exception
from bemoSenderr.models.base import AbstractBaseModel, CollectTransactionStatus, FundingTransactionStatus, GlobalTransactionStatus
from bemoSenderr.models.partner.base import AbstractCollectPartner, AbstractFundingPartner, AbstractPartnerTransaction
from celery import shared_task
from django.apps import apps
from bemoSenderr.models.partner.partner import AppSettings
from bemoSenderr.models.partner.services.utils import start_collect_periodic_task
from bemoSenderr.models.task import PeriodicTasksEntry
from bemoSenderr.models.transitions import CollectTransactionTransitions
from bemoSenderr.services import SyncCollectTransactions
from bemoSenderr.utils.log import debug
from django.utils.translation import ugettext_lazy as _
from loguru import logger
from django.db import transaction
from django.utils import timezone
from bemoSenderr.utils.notifications import NotificationsHandler
from bemoSenderr.utils.pinpoint import PinpointWrapper
from bemoSenderr.utils.s3 import upload_to_s3
from dateutil.relativedelta import relativedelta
from redbeat import RedBeatSchedulerEntry as Entry
import copy
from django_fsm import FSMField



"""
### CollectTransaction

|               old               |             new             |
|---------------------------------|-----------------------------|
| transaction_code                | collect_code                |
| partner_settlement_acc_currency | partner_settlement_currency |

"""
"""
Both the funding and collect transactions are launched from bemoSenderr/operations.py module using django signals.

"""

class CollectTransaction(AbstractPartnerTransaction, AbstractCollectPartner, CollectTransactionTransitions):

    status = FSMField(choices=CollectTransactionStatus.choices, max_length=255, default=CollectTransactionStatus.new)
    collect_code = models.CharField( _('The transaction code'), max_length=255, blank=True, null=True)
    partner_settlement_acc_snapshot = models.JSONField(help_text=_('The currency and the account number of the partner settlement account'), null=True, blank=True)
    exchange_rate_snapshot = models.JSONField(help_text=('Exchange rate snapshot'), blank=True, null=True)

    def init(self):
        super(CollectTransaction, self).init()


    def reconciliation(self):
        super(CollectTransaction, self).reconciliation()


    def ping(self):
        super(CollectTransaction, self).ping()


    @shared_task(bind=True)
    @logger.catch(onerror=send_email_celery_exception)
    def collect(self, global_transaction_id, collect_uuid, api_config, collect_code, dirham_transaction_code):
        report = ''
        try:
            collect_transaction_model = apps.get_model(
                        'bemoSenderr', 'CollectTransaction')
            instance = collect_transaction_model.objects.filter(uuid=collect_uuid).prefetch_related("partner", "partner__api_user").first()
            report += str(instance) + "\n"
            report += "UUID : " + str(instance.uuid) + "\n"
            time_now = datetime.datetime.strftime(timezone.now(), "%c")
            report += f'Time : {time_now}' +  "\n"
            global_transaction_model = apps.get_model(
                        'bemoSenderr', 'GlobalTransaction')
            global_transaction = global_transaction_model.objects.get(
                uuid=global_transaction_id)
            # Partners with services() Check if it's an Outbound partner (Partner that we use their API)
            if api_config.get('serviceClass', None):
                try:
                    #logger.info(f"Service Name {api_config['serviceClass']}")
                    report += f"Service Name {api_config['serviceClass']}" + "\n"
                    service = api_config['serviceClass']
                    partner_service = getattr(
                        sys.modules['bemoSenderr.models.partner.services'], service)()
                    report += str(global_transaction) + "\n" + " UUID : " + str(global_transaction_id) + "\n" "Global Transaction Status " + str(global_transaction.status) + '\n'
                    user_snapshot = global_transaction.user_snapshot
                    user_snapshot['document']['expiration_date'] = str(user_snapshot['document']['expiration_date']).split(' ')[0]
                    receiver_snapshot = global_transaction.receiver_snapshot
                    parameters = global_transaction.parameters
                    parameters['amount_origin'] = format(float(parameters.get('amount_origin', 0)), ".2f")
                    parameters['amount_destination'] = format(float(parameters.get('amount_destination', 0)), ".2f")
                    credentials = instance.partner.api_user.credentials
                    api_config['credentials'] = credentials
                    response = partner_service.create_order(
                        api_config, user_snapshot, receiver_snapshot, parameters, collect_uuid, collect_code, dirham_transaction_code)
                    report += "User snapshot :" + "\n" + json.dumps(user_snapshot, indent=4) + "\n"
                    report += "Receiver snapshot :" + "\n" + json.dumps(receiver_snapshot) + "\n"
                    report += "Parameters : " + "\n" + json.dumps(parameters, indent=4) + "\n"
                    i = 0
                    # If no collect_code generated or received from partner api RETRY 5 times max.

                    while not response and not response[1].get('collect_code', False) and i <= 5:
                        response = partner_service.create_order(api_config, user_snapshot, receiver_snapshot, parameters, collect_uuid, collect_code)
                        i += 1
                    """
                        1. response[0] the collect_transaction status
                        2. response[1] the response dictionary (can contain dynamic variables based on the partner)
                    """
                    if response and not response[1].get('response', None).get("yx-message", None):
                        report += "Create Order response : " + "\n" + json.dumps(response[1], indent=4) + "\n"
                        instance.collect_code = response[1].get('collect_code', None)
                        instance.partner_response = response[1]
                        instance.partner_response_formatted = response[1]
                        instance.status = response[0]
                        instance.save()
                        """
                        When the response is reveived and transaction not blocked or is sent, Start the check status periodic task of this partner.
                        """
                        if response[0] in [CollectTransactionStatus.collect_ready, CollectTransactionStatus.on_hold]:
                            transaction.on_commit(lambda: 
                                start_collect_periodic_task(instance, global_transaction)
                            )
                        with logger.catch(onerror=send_email_celery_exception):
                            sync_collect_tx = SyncCollectTransactions()
                            transaction.on_commit(lambda: sync_collect_tx.sync_created_collect_transaction(collect_tx_uuid=str(instance.uuid)))  
                    else: #response and response[1].get("response", None).get('yx-message', None):
                        logger.info("ERROR OCCURED IN CREATEORDER")
                        admin_alerts_service = SendAdminAlerts()
                        admin_alerts_service.send_admin_alert_partner_failure(
                            global_tx=global_transaction,
                            operation="collect_create_order",
                            partner=instance.partner.name,
                            params={
                                "failure_type": response[1].get("response", None).get("partner-response", None),
                                "collect_uuid": str(instance.uuid)
                            }
                        )
                        instance.partner_response = response[1]
                        instance.partner_response_formatted = response[1]
                        instance.status = CollectTransactionStatus.error
                        instance.save()
                        report += f"ERROR OCCURED IN CREATE ORDER\n {response[1]}"
                        report += "Create Order response : " + "\n" + json.dumps(response[1], indent=4) + "\n"
                except Exception as e:
                    instance.status = CollectTransactionStatus.error
                    instance.save()
                    report += f"Exception caught : {str(e)}"
                    logger.exception(f"collect for  {str(instance)} failed due to {str(e)}")
                    send_email_celery_exception(e)
            #API User (Inbound Partners who consume bemoSenderr API )
            else:
                """
                Check if collect_code already exists (in case of retrying the transaction in the admin dashboard)
                """
                if not instance.collect_code :
                    try:
                        report += f"API Partner {str(instance)}" + "\n"
                        report += "UUID : " + str(instance.uuid) + "\n"
                        report += str(global_transaction) + "\n" + " UUID : " + str(global_transaction_id) + "\n" "Global Transaction Status " + str(global_transaction.status) + '\n'
                        country_model = apps.get_model('bemoSenderr', 'Country')
                        country = country_model.objects.filter(iso_code=global_transaction.parameters['destination_country']).first()
                        if country:
                            apiPartnerPrefix = '9' + str(country.calling_code)
                            partnerPaymentCode = collect_code
                            instance.collect_code = partnerPaymentCode
                            instance.partner_response = "1000"
                            instance.partner_response_formatted = "1000"
                            instance.status = CollectTransactionStatus.collect_ready
                            instance.save()
                            with logger.catch(onerror=send_email_celery_exception):
                                sync_collect_tx = SyncCollectTransactions()
                                transaction.on_commit(lambda: sync_collect_tx.sync_created_collect_transaction(collect_tx_uuid=str(instance.uuid)))
                            """
                            except Exception as e:
                                report += "\n" + f"Syncing collect transaction failed due to {e.args}  \n" 
                                logger.info(f"Syncing collect transaction failed due to {e.args}")
                            """   
                    except Exception as e:
                        instance.partner_response = "1741"
                        instance.partner_response_formatted = "1741"
                        instance.status = CollectTransactionStatus.error
                        instance.save()
                        report += f"Exception caught : {str(e)}"
                        send_email_celery_exception(e)
                        #logger.info(e.args)
                #logger.info(f"Inbound partner : {instance.partner}")
            report += "-------------------------------------------------------" + "\n" + "End of report."
            #logger.info(report)
        except Exception as e:
            report += f"Exception caught : {str(e)}"
            report += "-------------------------------------------------------" + "\n" + "End of report."
            instance.status = CollectTransactionStatus.error
            instance.save()
            send_email_celery_exception(e)
        gtx_creation_date = datetime.datetime.strftime(global_transaction.created_at, "%Y%m%d%H%M%S")
        logger.info(f"GLOBAL TRANSACTION TIME STAMP {gtx_creation_date}")
        env = ""
        if settings.CONFIG and settings.CONFIG.get('env', None) in ['Dev-V3', None]:
            env = "dev"
        else:
            env = "prod"
        upload_to_s3(body=report, bucket='v3-reporting', key=f"{env}/transactions/collect/{str(global_transaction_id)}-{str(gtx_creation_date)}/createOrder-{str(instance.partner.name)}.txt", content_type='text/plain')
        return report

    @shared_task(bind=True)
    @logger.catch(onerror=send_email_celery_exception)
    def check_collect_status(self, params=None):
        state = False
        global_transaction_model = apps.get_model(
                        'bemoSenderr', 'GlobalTransaction')
        global_transaction = global_transaction_model.objects.get(
            uuid=params['gtx_uuid'])
        try:
            report = ''
            collect_uuid = params['collect_uuid']
            amount = params['damane_amount_mad']
            instance = CollectTransaction.objects.filter(uuid=collect_uuid).select_related("partner", "partner", "partner__api_user").first()
            api_config = copy.deepcopy(instance.partner.api_config)
            api_config['credentials'] = instance.partner.api_user.credentials
            params["api_config"] = api_config
            if instance.status == CollectTransactionStatus.collected:
                return
            report += str(instance) + "\n"
            report += "UUID : " + str(instance.uuid) + "\n"
            time_now = datetime.datetime.strftime(timezone.now(), "%c")
            report += f'Time : {time_now}' +  "\n"
            # Check if it's an Outbound partner (Partner that we use their API)
            if api_config.get('serviceClass', None):
                try:
                    report += f"Service Name {api_config['serviceClass']}" + "\n"
                    service = api_config['serviceClass']
                    partner_service = getattr(
                        sys.modules['bemoSenderr.models.partner.services'], service)()
                    transaction_code = instance.collect_code
                    logger.info(f'STARTING CHECKSTATUS FOR {instance.partner}')
                    old_status = instance.status
                    status = partner_service.check_status(params)
                    if old_status != status:
                        report += f"Status changed from {old_status} to: {status}" + "\n"
                    else:
                        report += f"Status changed to: {status}" + "\n"
                    if status:
                        instance.status = status
                        instance.save()
                    else:
                        instance.status = CollectTransactionStatus.error
                        instance.save()
                except Exception as e:
                    report += f"Exception caught : {str(e)}"
                    instance.status = CollectTransactionStatus.error
                    instance.save()
                    logger.exception(f"check collect status for  {str(instance)} failed due to {str(e)}")
                    report += f"check collect status for  {str(instance)} failed due to {str(e)}"
                    send_email_celery_exception(e)
            else:
                #This is for API partners (Inbound Partners that consume bemoSenderr API) we don't need to check the status of the transaction (cuz it's changed by the API Partner using bemoSenderr API)
                report += f"Service missing for {str(instance)} with UUID : {str(instance.uuid)}"
            report += "-------------------------------------------------------" + "\n" + "End of report."
            #logger.info(report)
            state = True
            
        except Exception as e:
            logger.info(f'CHECK STATUS  {str(e)}')
            report += f"Exception caught : {str(e)}"
            if type(e).__name__ == CollectTransaction.DoesNotExist.__name__:
                logger.info(f"OBJECT DOES NOT EXIST !")
                global_transaction_model = apps.get_model(
                        'bemoSenderr', 'GlobalTransaction')
                global_transaction = global_transaction_model.objects.get(
                    uuid=params['gtx_uuid'])
                periodic_task = PeriodicTasksEntry.objects.get(key=f"redbeat:checking {params['collect_uuid']} collect of {global_transaction.user} {global_transaction.uuid}")
                periodic_task.delete_periodic_task()
            report += "-------------------------------------------------------" + "\n" + "End of report."
            instance.status = CollectTransactionStatus.error
            instance.save()
            report += f"check collect status for  {str(instance)} failed due to {str(e)}"
            send_email_celery_exception(e)
            
        gtx_creation_date = datetime.datetime.strftime(global_transaction.created_at, "%Y%m%d%H%M%S")
        time_now = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
        logger.info(f"GLOBAL TRANSACTION TIME STAMP {gtx_creation_date}")
        env = ""
        if settings.CONFIG and settings.CONFIG.get('env', None) in ['Dev-V3', None]:
            env = "dev"
        else:
            env = "prod"
        upload_to_s3(body=report, bucket='v3-reporting', key=f"{env}/transactions/collect/{str(global_transaction.uuid)}-{str(gtx_creation_date)}/checkStatus/{time_now}-{str(instance.partner.name)}-{str(instance.uuid)}.txt", content_type='text/plain')
        return state


    @shared_task(bind=True)
    @logger.catch(onerror=send_email_celery_exception)
    def cancel(self, instance):
        instance = CollectTransaction.objects.filter(uuid=instance).prefetch_related("globaltransaction_set", "partner", "partner__api_user").first()
        global_transaction = instance.globaltransaction_set.all().first()
        state = False
        try:
            report = ''
            report += str(instance) + "\n"
            report += "UUID : " + str(instance.uuid) + "\n"
            time_now = datetime.datetime.strftime(timezone.now(), "%c")
            report += f'Time : {time_now}' +  "\n"
            service = instance.partner.api_config.get('serviceClass', None)
            # Check if it's an Outbound partner (Partner that we use their API)
            if service:
                try:
                    partner_service = getattr(sys.modules['bemoSenderr.models.partner.services'], service)()
                    api_config = instance.partner.api_config
                    credentials = instance.partner.api_user.credentials
                    api_config['credentials'] = credentials
                    amount = global_transaction.parameters['amount_destination']
                    transaction_code = instance.collect_code
                    #logger.info(instance)
                    if not instance.partner_response:
                        dh_tx_code = dh_pay_code = dam_ord_numb = atps_transaction_code = None
                    else:
                        dh_tx_code = instance.partner_response.get(
                            'dirham_transaction_code', False) if instance.partner_response.get('dirham_transaction_code', False) else ""
                        dh_pay_code = instance.partner_response.get(
                            'dirham_payment_code', False) if instance.partner_response.get('dirham_payment_code', False) else ""
                        dam_ord_numb = instance.partner_response.get(
                            'damane_order_number', False) if instance.partner_response.get('damane_order_number', False) else ""
                        atps_transaction_code = instance.partner_response.get(
                            'atps_transaction_code', False) if instance.partner_response.get('atps_transaction_code', False) else ""
                    params = {
                        "dirham_transaction_code": dh_tx_code,
                        "dirham_payment_code": dh_pay_code,
                        "damane_order_number": dam_ord_numb,
                        "damane_amount_mad": amount,
                        "atps_transaction_code": atps_transaction_code,
                        "api_config": api_config,
                        "collect_uuid": str(instance.uuid),
                        "collect_code": transaction_code,
                    }
                    response = partner_service.cancel_order(params)
                    status = response[0]
                    report += f"Status : {status}" + "\n"
                    report += "Create Order response : " + "\n" + json.dumps(response[1], indent=4) + "\n"
                    if status != CollectTransactionStatus.error:
                        instance.status = status
                        instance.save()
                    else:
                        admin_alerts_service = SendAdminAlerts()
                        admin_alerts_service.send_admin_alert_partner_failure(
                            global_tx=global_transaction,
                            operation="collect_cancel_order",
                            partner=instance.partner.name,
                            params={
                                "failure_type": response[1].get("partner-response", None),
                                "collect_uuid": str(instance.uuid),
                                "tx_code": instance.collect_code
                            }
                        )
                        instance.status = CollectTransactionStatus.error
                        instance.save()
                except Exception as e:
                    instance.status = CollectTransactionStatus.error
                    instance.save()
                    report += f"Exception caught : {str(e)}" + "\n"
                    send_email_celery_exception(e)
            # API User (Inbound Partners who consume bemoSenderr API ) just changing the status is enough.
            else:
                try:
                    report += f'Inbound partner cancelling {str(instance)}' + "\n"
                    report += 'UUID : ' + str(instance.uuid) + "\n"
                    #logger.info(f'Inbound partner cancelling {instance}')
                    instance.status = CollectTransactionStatus.canceled
                    instance.save()
                except Exception as e:
                    report += f"Exception caught : {str(e)}"
                    instance.status = CollectTransactionStatus.error
                    instance.save()
                    send_email_celery_exception(e)
            report += "-------------------------------------------------------" + "\n" + "End of report."
            state = True
        except Exception as e:
            report += f"Exception caught : {str(e)}"
            report += "-------------------------------------------------------" + "\n" + "End of report."
            instance.status = CollectTransactionStatus.error
            instance.save()
            ex = traceback.format_exc()
            logger.info(f'THE FULL EXCEPTION {ex}')
            send_email_celery_exception(e)
        gtx_creation_date = datetime.datetime.strftime(global_transaction.created_at, "%Y-%m-%d %H:%M:%S")
        logger.info(f"GLOBAL TRANSACTION TIME STAMP {gtx_creation_date}")
        env = ""
        if settings.CONFIG and settings.CONFIG.get('env', None) in ['Dev-V3', None]:
            env = "dev"
        else:
            env = "prod"
        upload_to_s3(body=report, bucket='v3-reporting', key=f"{env}/transactions/collect/{gtx_creation_date}-{str(global_transaction.uuid)}/cancelOrder-{str(instance.partner.name)}.log", content_type='text/plain')
        return state


    def __str__(self) -> str:
        global_tx = self.globaltransaction_set.all().first()
        if global_tx:
            return f'Global Transaction {self.globaltransaction_set.all().first().uuid} for user {self.globaltransaction_set.all().first().user}'
        else:
            return str(self.uuid)



class FundingTransaction(AbstractPartnerTransaction, AbstractFundingPartner):

    status = models.CharField(choices=FundingTransactionStatus.choices, max_length=255)
    reference_code = models.CharField(_('Deposit reference number'), max_length=255, blank=True, null=True)
    refund_reference_code = models.CharField(_('Refund transaction number'), max_length=255, blank=True, null=True)
    refund_api_response = models.JSONField(_('Refund API response'), null=True, blank=True)

    def init(self):
        super(FundingTransaction, self).init()

    def ping(self):
        super(FundingTransaction, self).ping()

    """
    Periodic task to check if the user hasn't done the funding of the transaction and send push notification for reminding every 15min, or the cancelling 
    of the transaction in case of 1 hour has passed without funding.
    """
    @shared_task(bind=True)
    def check_funding_inactivity(self, funding_uuid):
        try:
            funding_transaction_model = apps.get_model('bemoSenderr', 'FundingTransaction')
            instance = funding_transaction_model.objects.filter(uuid=funding_uuid).prefetch_related("globaltransaction_set", "globaltransaction_set__user").first()
            logger.info(f'CHECKING FUNDING OF {instance}')
            if instance:
                time_now = timezone.now()
                created_at = instance.created_at
                global_tx = instance.globaltransaction_set.all().first()
                user = global_tx.user
                notif_service = NotificationsHandler()
                pinpoint_service = PinpointWrapper()
                logger.info("IM HERE")
                logger.info(time_now)
                logger.info(created_at + relativedelta(minutes=15))
                logger.info(time_now > created_at + relativedelta(minutes=15))
                funding_inactivity_period = AppSettings.objects.first().config.get('fundingExpTime',None)
                logger.info(f"THE FUNDING PERIOD{funding_inactivity_period}")
                funding_inactivity_period_minutes = funding_inactivity_period * 60
                time_lapse_in_hours, time_lapse_in_minutes = divmod(funding_inactivity_period_minutes, 60)
                time_lapse_in_hours = int(time_lapse_in_hours)
                time_lapse_in_minutes = int(time_lapse_in_minutes)

                if time_now > created_at + relativedelta(hours=time_lapse_in_hours,minutes=time_lapse_in_minutes):
                    logger.info(f'Cancelling Transaction ! {instance}')
                    receiver_name = f"{global_tx.receiver_snapshot.get('first_name', 'UNDEFINED')} {global_tx.receiver_snapshot.get('last_name', 'UNDEFINED')}"
                    receiver_phone_number = str(global_tx.receiver_snapshot.get('phone_number', 'UNDEFINED'))
                    amount_origin = f"{str(round(float(global_tx.parameters.get('amount_origin', 'UNDEFINED')), 2))} {global_tx.parameters.get('currency_origin', 'UNDEFINED')}"
                    amount_destination = f"{str(round(float(global_tx.parameters.get('amount_destination', 'UNDEFINED')), 2))} {global_tx.parameters.get('currency_destination', 'UNDEFINED')}"
                    language = global_tx.user.locale
                    if not language:
                        language = "FR"
                    notif_service = NotificationsHandler()
                    push_notif_data = notif_service.get_tx_funding_incactivity_sender_push(lang=language, vars=[amount_origin, amount_destination, receiver_name, receiver_phone_number])
                    pinpoint_service = PinpointWrapper()#SNSNotificationService()
                    last_global_tx = apps.get_model('bemoSenderr', 'GlobalTransaction').objects.filter(user=global_tx.user).last()
                    user_snapshot = last_global_tx.user_snapshot
                    status = pinpoint_service.send_push_notifications_and_data(status=GlobalTransactionStatus.funding_error, user_snapshot=user_snapshot, user=user, data=push_notif_data, type="transaction", global_tx_uuid=str(global_tx.uuid))
                    logger.info(f"STATUS OF PUSH NOTIFICATION INACTIVITY FUNDING {status}")
                    instance.status = FundingTransactionStatus.error
                    instance.save()
                elif time_now > created_at + relativedelta(minutes=15):
                    #Send push notification
                    cancelation_time = created_at + relativedelta(hours=time_lapse_in_hours, minutes=time_lapse_in_minutes)
                    time_left_seconds = (cancelation_time - time_now).total_seconds()
                    time_left_minutes = int(divmod(time_left_seconds, 60)[0])
                    if time_left_minutes < 0:
                        time_left_minutes = 0
                    time_left_hours = None
                    time_left_hours, time_left_minutes = divmod(time_left_minutes, 60)
                    time_left_hours = str(int(time_left_hours))
                    time_left_minutes = str(int(int(time_left_minutes) + 1))
                    logger.info(f"time left hours {time_left_hours}")
                    logger.info(f"time left minutes {time_left_minutes}")
                    receiver_name = f"{global_tx.receiver_snapshot.get('first_name', 'UNDEFINED')} {global_tx.receiver_snapshot.get('last_name', 'UNDEFINED')}"
                    receiver_phone_number = str(global_tx.receiver_snapshot.get('phone_number', 'UNDEFINED'))
                    total_amount = f"{str(round(float(global_tx.parameters.get('total', 'UNDEFINED')), 2))} {global_tx.parameters.get('currency_origin', 'UNDEFINED')}"
                    language = global_tx.user.locale
                    if not language:
                        language = "FR"
                    push_notif_data = notif_service.get_tx_funding_required_sender_push(lang=language, vars=[receiver_name, receiver_phone_number, total_amount, time_left_hours,time_left_minutes])
                    logger.info(f"push data{push_notif_data}")
                    last_global_tx = apps.get_model('bemoSenderr', 'GlobalTransaction').objects.filter(user=global_tx.user).last()
                    user_snapshot = last_global_tx.user_snapshot
                    status = pinpoint_service.send_push_notifications_and_data(status=GlobalTransactionStatus.fundtransaction_in_progress, user_snapshot=user_snapshot, user=user, data=push_notif_data, type="transaction", global_tx_uuid=str(global_tx.uuid))
                    logger.info(f"STATUS OF PUSH NOTIFICATION REQUIRED FUNDING {status}")
        except Exception as e:
            logger.info(f"Exception caught in check funding inactivity")
            logger.info(e.args)
            send_email_celery_exception(e)

    def __str__(self) -> str:
        global_tx = self.globaltransaction_set.all().first()
        if global_tx:
            return f'Global Transaction {self.globaltransaction_set.all().first().uuid} for user {self.globaltransaction_set.all().first().user.email}'
        else:
            return str(self.uuid)


class TxLimitCumul(AbstractBaseModel):

    user = models.ForeignKey('User', help_text=_('The user that did the operation'), on_delete=models.RESTRICT)
    cumulative_debut = models.DateTimeField(help_text=_("The date at which we started calculating cumulative limits"))
    operation = models.CharField(max_length=255, help_text=_("operation that triggered the new entry (send-money, refund or limit reset)"))
    amount = models.CharField(max_length=255, help_text=_("amount of the operation (send-money: positive; refund: negative)"))
    global_transaction = models.ForeignKey('GlobalTransaction', on_delete=models.RESTRICT, null=True, blank=True, help_text=_("Global transaction associated to the operation (optional)"))
    limit_1_month = models.CharField(max_length=255, help_text=_("The cumulative amount of all operations within the last 1 month"))
    last_1_month_refresh = models.DateTimeField(help_text=_("The date at which the last monthly reset was done"))
    limit_3_month = models.CharField(max_length=255, help_text=_("The cumulative amount of all operations within the last 3 month)"))
    last_3_month_refresh = models.DateTimeField(help_text=_("The date at which the last quarterly reset was done"))
    limit_12_month = models.CharField(max_length=255, help_text=_("The cumulative amount of all operations within the last 12 month"))
    last_12_month_refresh = models.DateTimeField(help_text=_("The date at which the last yearly reset was done"))
    total_transfered_amount = models.CharField(max_length=255, help_text=_("The total of all operations made since the beginning"))

    def __str__(self) -> str:
        return f" {self.operation} for user {self.user}"

    class Meta:
        verbose_name = _('Transaction Limit Cumulative')
        verbose_name_plural = _('Transactions Limits Cumulatives')
        ordering = ['created_at']
