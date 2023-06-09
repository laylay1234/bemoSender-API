from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver
from bemosenderrr.models.base import CollectTransactionStatus, FundingTransactionStatus, GlobalTransactionStatus, VerificationStatus
from bemosenderrr.models.global_transaction import GlobalTransaction
from bemosenderrr.models.partner.bank_verification import UserBankVerificationRequest
from bemosenderrr.models.partner.kyc_verification import KycVerificationRequest
from bemosenderrr.models.partner.partner import AppSettings, Country, Currency, ExchangeRateTier, Partner, PartnerExchangeRate, TransactionMethodAvailability
from bemosenderrr.models.partner.transactions import CollectTransaction, FundingTransaction
from bemosenderrr.models.task import PeriodicTasksEntry
from bemosenderrr.operations import  SendMoney
from bemosenderrr.services import CountryService, CurrencyService, SyncCollectTransactions, sync_app_settings, sync_bank_verification_status, sync_kyc_verification_status
from bemosenderrr.services import push_globaltx_datastore
from redbeat import RedBeatSchedulerEntry as Entry
from bemosenderrr.tasks import update_rates

from bemosenderrr.utils.notifications import NotificationsHandler
from bemosenderrr.utils.pinpoint import PinpointWrapper
from bemosenderrr.utils.sync_flinks_signup_data import sync_flinks_signup_data
from .celery import app
from django.db import transaction
from loguru import logger
from django.utils import timezone
from bemosenderrr.operations import SendAdminAlert
from bemosenderrr.operations import TxLimitCumulOperations


"""
Signal to start funding transactions when the global transaction is created
"""
@receiver(post_save, senderr=GlobalTransaction)
def start_funding_transaction(senderr, instance, created, **kwargs):
    if created and instance.status == GlobalTransactionStatus.new:
        instance.status = GlobalTransactionStatus.fundtransaction_in_progress
        instance.save()
        print('created global transaction')
        transaction.on_commit(lambda : SendMoney().fund_transaction.apply_async((str(instance.uuid),)))
    
    
        
"""
Signal to sync global transaction status (create an update mutation) to the datastore
"""
@receiver(pre_save, senderr=GlobalTransaction)
def push_globaltx_status(senderr, instance, **kwargs):
    try:
        obj = senderr.objects.get(pk=instance.pk)
    except senderr.DoesNotExist:
        print('Global transaction is new')
        # Object is new, so field hasn't technically changed
    else:
        if not obj.status == instance.status : # TODO TEST THIS PROPERLY !!
              # Status field has changed
            logger.info('push global transaction !')
            transaction.on_commit(lambda: push_globaltx_datastore(instance=instance, status=instance.status))           


"""
Signal to handle sending push notifications and sms when global transaction status changes
"""

@receiver(pre_save, senderr=GlobalTransaction)
def handle_notifications(senderr, instance, **kwargs):
    try:
        obj = senderr.objects.get(pk=instance.pk)
    except senderr.DoesNotExist:
        print('Global transaction is new')
        # Object is new, so field hasn't technically changed
    else:
        if not obj.status == instance.status : # TODO TEST THIS PROPERLY !!
            logger.info('handle notifications !')
            try:
                if instance.status == GlobalTransactionStatus.success:
                    senderr_name = str(instance.user_snapshot.get('first_name', "UNDEFINED"))
                    receiver_name = str(instance.receiver_snapshot.get('first_name', "UNDEFINED")) + " " + str(instance.receiver_snapshot.get('last_name', "UNDEFINED"))
                    currency_origin = Currency.objects.get(iso_code=instance.parameters.get('currency_origin'))
                    currency_destination = Currency.objects.get(iso_code=instance.parameters.get('currency_destination'))
                    amount_origin_currency = str(instance.parameters.get('amount_origin', "UNDEFINED")) + " " + currency_origin.short_sign
                    amount_destination_currency = str(instance.parameters.get('amount_destination', "UNDEFINED")) + " " + currency_destination.short_sign
                    language = instance.user.locale
                    if not language:
                        language = "FR"
                    notif_service = NotificationsHandler()
                    push_notif_data = notif_service.get_tx_collected_senderr_push(lang=language, vars=[senderr_name, receiver_name, amount_origin_currency, amount_destination_currency])
                    pinpoint_service = PinpointWrapper()#SNSNotificationService()
                    user_snapshot = GlobalTransaction.objects.filter(user=instance.user).last().user_snapshot
                    status_push = pinpoint_service.send_push_notifications_and_data(status=GlobalTransactionStatus.success, user_snapshot=user_snapshot, user=instance.user, data=push_notif_data, type="transaction", global_tx_uuid=str(instance.uuid))
                    if status_push:
                        notifications_field = instance.notifications
                        notifications_field['tx_collected_senderr'] = True
                        nb_rows = GlobalTransaction.objects.filter(uuid=instance.uuid).update(notifications=notifications_field)
                        print('handle_notifications rows affected(tx_collected_senderr) ', nb_rows)
                    print("Status of handle_notifications (tx_collected_senderr)", status_push)
            except Exception as e:
                print(e.args)
            


@receiver(pre_save, senderr=GlobalTransaction)
def handle_cancel_by_user(senderr, instance, **kwargs):
    # Signal to cancel operation by user in frontend
    try:
        obj = senderr.objects.get(pk=instance.pk)
    except senderr.DoesNotExist:
        print('Global transaction is new')
        # Object is new, so field hasn't technically changed
    else:
        logger.info(f"Object : {obj.status}")
        logger.info(f"Instance : {instance.status}")
        if not obj.status == instance.status:
            """
            Cancel by user when global transaction status is not final (not in these statuses [success, funding_error, refunded])
            """
            if instance.status == GlobalTransactionStatus.canceled and obj.status not in [GlobalTransactionStatus.success, GlobalTransactionStatus.funding_error, GlobalTransactionStatus.blocked, GlobalTransactionStatus.refunded,
                        GlobalTransactionStatus.canceled, GlobalTransactionStatus.refundtransaction_in_progress, GlobalTransactionStatus.refunded_error, GlobalTransactionStatus.refunded]:
                logger.info('Globaltransaction status not final !')
                """
                This to prevent cancelling collect_transactions when they're in NEW status (Global Transaction still in FUNDING status)
                notice tha obj is the old instance
                """
                if obj.status not in [GlobalTransactionStatus.fundtransaction_in_progress, GlobalTransactionStatus.new]:
                    logger.info("IM HERE")
                    collect_transactions = instance.collect_transactions.all()
                    count = len(collect_transactions)
                    i = 1
                    for collect_operation in instance.collect_transactions.all():
                        if collect_operation.status == CollectTransactionStatus.canceled:
                            i += 1
                    logger.info(f"count {count}")
                    logger.info(f"i {i}")
                    if count != i:
                        instance.status = obj.status
                        instance.save()
                """
                Refund UserTransaction Limits
                """
                periodic_task = PeriodicTasksEntry.objects.filter(
                                            name=f"Checking funding inactivity for {str(instance.funding_transaction.uuid)}").first()
                logger.info(f'DELETING PERIODIC TASK {periodic_task}')
                if periodic_task is not None:
                    periodic_task.delete()
                    logger.info(f'DELETING PERIODIC TASK {periodic_task}')
                tx_cumul = TxLimitCumulOperations()
                if obj.status in [GlobalTransactionStatus.fundtransaction_in_progress, GlobalTransactionStatus.new]:
                    #tx_cumul.on_refund_money(global_tx=instance, operation="", refund_with_fees=False)
                    print("No need for refunding")
                elif obj.status not in [GlobalTransactionStatus.collectransaction_in_progress, GlobalTransactionStatus.fundtransaction_in_progress, GlobalTransactionStatus.funding_error]:
                    tx_cumul.on_refund_money(global_tx=instance, operation="admin_refund", refund_with_fees=True)

            # Don't allow cancelling by user when global transaction status is final (in these statuses [success, funding_error, refunded])
            elif instance.status == GlobalTransactionStatus.canceled and obj.status in [GlobalTransactionStatus.success, GlobalTransactionStatus.funding_error, GlobalTransactionStatus.blocked,
                        GlobalTransactionStatus.canceled, GlobalTransactionStatus.refundtransaction_in_progress, GlobalTransactionStatus.refunded_error, GlobalTransactionStatus.refunded]:
                nb_rows = GlobalTransaction.objects.filter(uuid=instance.uuid).update(status=obj.status)
                print("handle_cancel_by_user rows affected : ", nb_rows)
        else:
            logger.info("GLOBAL TRANSACTION STATUS DIDNT CHANGE !")


"""
Signal to trigger collect transactions if funding transaction is SUCCESSFUL, otherwise FUNDING_ERROR (FINAL STATUS)
"""
@receiver(post_save, senderr=FundingTransaction)
def start_collect_transactions(senderr, instance, created, **kwargs):

    global_transaction = instance.globaltransaction_set.all().first()
    logger.info(instance.status)
    if instance.status == FundingTransactionStatus.success:
        if global_transaction:
            global_transaction.status = GlobalTransactionStatus.collectransaction_in_progress
            global_transaction.save()
            tx_cumul = TxLimitCumulOperations()
            tx_cumul.on_send_money(global_tx=global_transaction)
            #TODO I UNCOMMENTED THIS 
            task = PeriodicTasksEntry.objects.filter(name=f"Checking funding inactivity for {str(instance.uuid)}").first()
            if task:
                task.delete()
            logger.info('Starting collect transactions')
            transaction.on_commit(lambda : SendMoney().collect_transactions.apply_async((str(global_transaction.uuid),)))
    elif instance.status in [FundingTransactionStatus.auth_error, FundingTransactionStatus.complete_error, FundingTransactionStatus.error]:
        task = PeriodicTasksEntry.objects.filter(name=f"Checking funding inactivity for {str(instance.uuid)}").first()
        if task:
            task.delete()
        global_transaction.status = GlobalTransactionStatus.canceled
        global_transaction.save()
    elif instance.status == FundingTransactionStatus.refunded:
        task = PeriodicTasksEntry.objects.filter(name=f"Checking funding inactivity for {str(instance.uuid)}").first()
        if task:
            task.delete()
        global_transaction.status = GlobalTransactionStatus.refunded
        global_transaction.save()
        

"""
Signal to update global transaction status by evaluating the collect transaction(s) status
"""
@receiver(pre_save, senderr=CollectTransaction)
def update_global_collect_status(senderr, instance, **kwargs):
    # Signal to cancel operation by user in frontend
    try:
        obj = senderr.objects.get(pk=instance.pk)
    except senderr.DoesNotExist:
        print('Collect transaction is new')
        # Object is new, so field hasn't technically changed
    else:
        logger.info(f"Object : {obj.status}")
        logger.info(f"Instance : {instance.status}")
        # Sync CollectTransaction status !
        
        if not obj.status == instance.status:   
            try:
                logger.info(f"Syncing Collect Transaction {str(instance.uuid)}")
                sync_service = SyncCollectTransactions()
                logger.info(f"GOT COLLECT TX VERSION {instance._version}")
                transaction.on_commit(lambda : sync_service.sync_updated_collect_transaction(collect_tx_uuid=instance.uuid, status=instance.status))
            except Exception as e:
                logger.info(f"Syncing Collect Transaction {instance} Failed due to {e}")
                logger.info(e)
                logger.info(f"Instance : {instance.status}")
            """
            As soon as 1 collect transaction is successful(collected) --> GlobalTransactionStatus.success  -->  Cancel all other collect transactions
                    --> Delete all periodic tasks from redbeat
            """
            if instance.status == CollectTransactionStatus.collected:
                global_transaction = instance.globaltransaction_set.all().first()
                if global_transaction:
                    print('At least 1 collect transaction completed succesfuly')
                    global_transaction.status = GlobalTransactionStatus.success
                    global_transaction.payment_date = timezone.now()
                    tasks = PeriodicTasksEntry.objects.filter(name=f'checking {str(instance.uuid)} collect of {global_transaction.user} {global_transaction.uuid}')
                    if tasks:
                        for task in tasks:
                            task.delete()
                    logger.info(f"Instance excluded {instance}")
                    for collect_operation in global_transaction.collect_transactions.all().exclude(uuid=instance.uuid):
                        if collect_operation.uuid != instance.uuid:
                            logger.info(collect_operation)
                            tasks = PeriodicTasksEntry.objects.filter(name=f'checking {str(collect_operation.uuid)} collect of {global_transaction.user} {global_transaction.uuid}')
                            if tasks:
                                for task in tasks:
                                    task.delete()
                            collect_operation.cancel(collect_operation.uuid)
                    transaction.on_commit(lambda: global_transaction.calculate_revenue(collect_tx=instance))
                    SendAdminAlert().send_admin_collect_tx_collected(instance)
            """
            All collect transactions are in a blocked status [aml_blocked, blocked]  -->  GlobalTransactionStatus.blocked (Not a final status)
            """
            if instance.status in [CollectTransactionStatus.blocked, CollectTransactionStatus.aml_blocked]:
                global_transaction = instance.globaltransaction_set.all().first()
                if global_transaction:
                    count = len(global_transaction.collect_transactions.all())
                    i = 0
                    for collect_operation in global_transaction.collect_transactions.all():
                        if collect_operation.status in [CollectTransactionStatus.blocked, CollectTransactionStatus.aml_blocked]:
                            i += 1
                    if count == i:
                        global_transaction.status = GlobalTransactionStatus.blocked
                        global_transaction.save()
            """
            2. Collect transaction cancelled  --> Check if all other collect transactions in cancelled status [canceled]
                            --> Trigger refund  (GlobalTransactionStatus.refundtransaction_in_progress)
            """
            if instance.status in [CollectTransactionStatus.canceled, CollectTransactionStatus.not_found, CollectTransactionStatus.rejected, CollectTransactionStatus.error]:
                global_transaction = instance.globaltransaction_set.all().first()
                if global_transaction:
                    count = len(global_transaction.collect_transactions.all())
                    i = 1
                    refund_counter = 0
                    for collect_operation in global_transaction.collect_transactions.all():
                        if collect_operation.status in [CollectTransactionStatus.canceled, CollectTransactionStatus.not_found, CollectTransactionStatus.rejected, CollectTransactionStatus.error]:
                            i += 1
                    logger.info(f'Count : {count}')
                    logger.info(f'I : {i}')
                    if count == i:
                        for collect_operation in global_transaction.collect_transactions.all():
                            tasks = PeriodicTasksEntry.objects.filter(name=f'checking {str(collect_operation.uuid)} collect of {global_transaction.user} {global_transaction.uuid}')
                            if tasks:
                                for task in tasks:
                                    task.delete()
                        #GlobalTransaction.objects.filter(pk=global_transaction.uuid).update(status=GlobalTransactionStatus.canceled)
                        global_transaction.status = GlobalTransactionStatus.canceled
                        transaction.on_commit(lambda: global_transaction.save())
                        # Send a refund to the user.
                        logger.info(f"Refunding Global Transaction with UUID {instance.uuid}")
                        transaction.on_commit(lambda : SendMoney().refund_transfer(instance_uuid=instance.uuid))


"""
Signal to delete funding transactions (cascade) when the linked global transaction is deleted.
"""
@receiver(post_delete, senderr=GlobalTransaction)
def delete_funding_transaction(senderr, instance, **kwargs):
    periodic_task = PeriodicTasksEntry.objects.filter(
        name=f"Checking funding inactivity for {str(instance.funding_transaction.uuid)}").first()
    logger.info(f'DELETING PERIODIC TASK {periodic_task}')
    if periodic_task is not None:
        periodic_task.delete()
        logger.info(f'DELETING PERIODIC TASK {periodic_task}')
    instance.funding_transaction.delete()


"""
Signal to delete the collect transaction(s) when the linked global transaction is deleted
"""
@receiver(pre_delete, senderr=GlobalTransaction)
def delete_collect_transactions(senderr, instance, **kwargs):
    for collect_transaction in instance.collect_transactions.all():
        
        periodic_task = PeriodicTasksEntry.objects.filter(
            name=f'checking {str(collect_transaction.uuid)} collect of {instance.user} {instance.uuid}').first()
        logger.info(f'DELETING PERIODIC TASK {periodic_task}')
        if periodic_task is not None:
            logger.info(f'DELETING PERIODIC TASK {periodic_task}')
            periodic_task.delete()
        collect_transaction.delete()


"""
Signal to start kyc verification celery task (only works when there is an active kyc verification request partner and no status(null))
"""
@receiver(post_save, senderr=KycVerificationRequest)
def start_kyc_verification(senderr, instance, created, **kwargs):
    if not instance.status and instance.partner:
        api_config = instance.partner.api_config
        api_config['credentials'] = instance.partner.api_user.credentials
        print('SAVING KYCVERIFICATION INSTANCE(RUNNING CELERY TASK)')
        transaction.on_commit(lambda : instance.verify.apply_async((api_config, str(instance.uuid))))
    else:
        """
        Sync kyc verification status to datastore
        """
        print('SYNCING  KYC VERIFICATION')
        transaction.on_commit(lambda: sync_kyc_verification_status(instance.user, instance.status))


"""
Signal to start user bank verification request ()
"""
@receiver(post_save, senderr=UserBankVerificationRequest)
def start_bank_verification(senderr, instance, created, **kwargs):
    """
    if not instance.status and instance.partner:
        api_config = instance.partner.api_config
        if instance.partner.api_user:
            api_config['credentials'] = instance.partner.api_user.credentials
        transaction.on_commit(lambda : instance.verify.apply_async((api_config, str(instance.uuid))))
    """
    if instance.status == VerificationStatus.verified and instance.user:
        """
        Sync user bank verification status to datastore
        """
        print('Sync user bank verification data to datastore')
        transaction.on_commit(lambda: sync_flinks_signup_data(user=instance.user, data=instance.partner_response.get('response_formatted', None)))
        print('Sync user bank verification status to datastore')
        transaction.on_commit(lambda: sync_bank_verification_status(instance.user, instance))
        
        
        
        


"""
Signal to sync appsettings config to datastore
"""
@receiver(post_save, senderr=AppSettings)
def sync_appsettings(senderr, instance, created, **kwargs):
    sync_app_settings(instance)

"""
Signal to handle celery-redbeat periodic tasks dynamically
"""
@receiver(post_save, senderr=PeriodicTasksEntry)
def handle_periodic_task_admin(senderr, instance, created, **kwargs):
    entry = None
    try:
        entry = Entry.from_key(instance.key, app=app)
        
    except Exception as e:
        pass
    if instance.enabled == False:
        print('disabled')
        instance.delete_periodic_task()
    elif instance.enabled == True and entry is None:
        print("enabled")
        instance.add_periodic_task()
        instance.save()
        #entry.reschedule(instance.schedule)


"""
Signal to delete celery-redbeat  periodic tasks from django admin
"""
@receiver(pre_delete, senderr=PeriodicTasksEntry)
def delete_periodic_task_entry_admin(senderr, instance, using, **kwargs):
    entry = None
    try:
        entry = instance.get_entry()
    except Exception:
        pass
    if entry is not None:
        instance.delete_periodic_task()


@receiver(pre_save, senderr=PeriodicTasksEntry)
def update_task_schedule(senderr, instance, **kwargs):
    try:
        obj = senderr.objects.get(pk=instance.pk)
    except senderr.DoesNotExist:
        print('Perioidc Task is new!')
        # Object is new, so field hasn't technically changed
    else:
        if not obj.schedule == instance.schedule : # TODO TEST THIS PROPERLY !!
              # Schedule field has changed
            logger.info('Changing periodic task schedule')
            logger.info(f"INSTANCE SCHEDULE : {instance.schedule}")
            logger.info(f"OBJECT SCHEDULE : {obj.schedule}")
            transaction.on_commit(lambda: instance.update_task()) 


@receiver(post_save, senderr=PartnerExchangeRate)
def run_update_rates(senderr, instance, created, **kwargs):
    print("PartnerExchangeRate model changed, Running update rates")
    update_rates.apply_async()



@receiver(post_save, senderr=TransactionMethodAvailability)
def update_collect_methods_availabilities(senderr, instance, created, **kwargs):
    country = instance.partner.country
    print("Updating collect methods availibilities in ExchangeRateTiers")
    if country:
        exchange_rate_tiers = ExchangeRateTier.objects.filter(country_destination=country)
        for exchange_rate_tier in exchange_rate_tiers:
            exchange_rate_tier.save()


@receiver(post_save, senderr=Country)
def sync_updated_country(senderr, instance, created, **kwargs):
    CountryService().sync_country(country=instance)


@receiver(post_save, senderr=Currency)
def sync_updated_country(senderr, instance, created, **kwargs):
    CurrencyService().sync_currency(currency=instance)


@receiver(post_save, senderr=Partner)
def update_collect_methods(senderr, instance, created, **kwargs):
    tx_methods_availabilities = TransactionMethodAvailability.objects.filter(partner=instance)
    if tx_methods_availabilities:
        for tx_method in tx_methods_availabilities:
            tx_method.full_clean()
            print(tx_method.active)
            tx_method.save()