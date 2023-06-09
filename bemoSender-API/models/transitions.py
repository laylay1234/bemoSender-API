from loguru import logger
from django_fsm import  transition
from bemosenderrr.models.base import CollectTransactionStatus, FundingTransactionStatus, GlobalTransactionStatus
from bemosenderrr.operations import SendMoney
from bemosenderrr.models.task import PeriodicTasksEntry

class CollectTransactionTransitions():

    @transition(field='status', source=CollectTransactionStatus.collect_ready, 
        target=CollectTransactionStatus.canceled, custom=dict(admin=True))
    def cancell(self):
        try:
            self.cancel(self.uuid)
            global_tx = self.globaltransaction_set.all().first()
            print(global_tx.user)
            print(f'checking {str(self.uuid)} collect of {global_tx.user} {global_tx.uuid}')
            collect_check_status_tasks = PeriodicTasksEntry.objects.filter(name=f'checking {str(self.uuid)} collect of {global_tx.user} {global_tx.uuid}')
            if collect_check_status_tasks:
                for collect_check_status_task in collect_check_status_tasks:
                    collect_check_status_task.delete()
        except Exception as e:
            print("UNABLE TO CANCEL THIS COLLECT TRANSACTION DUE TO ", e)



class GlobalTransactionTransitions():

    @transition(field='status', source=GlobalTransactionStatus.new, 
        target=GlobalTransactionStatus.fundtransaction_in_progress, custom=dict(admin=True))
    def fund(self):
        SendMoney().fund_transaction.apply_async((str(self.uuid),))


    @transition(field='status', source=GlobalTransactionStatus.fundtransaction_in_progress,
        target=GlobalTransactionStatus.collectransaction_in_progress, custom=dict(admin=True))
    def collect(self):
        # Start collect transaction
        self.funding_transaction.status = FundingTransactionStatus.success
        self.funding_transaction.save()

    def check_collect_çancelled(self):
        count = len(self.collect_transactions.all())
        i = 0
        refund_counter = 0
        for collect_operation in self.collect_transactions.all():
            if collect_operation.status == CollectTransactionStatus.canceled:
                i += 1
        logger.info(f'Count : {count}')
        logger.info(f'I : {i}')
        if count == i:
            return True
        else:
            return False
    @transition(field='status', source=GlobalTransactionStatus.canceled, 
        target=GlobalTransactionStatus.refundtransaction_in_progress, custom=dict(admin=True), conditions=[check_collect_çancelled])
    def start_refunding(self):
        logger.info('Refunding in progress')
    

    @transition(field='status', source=GlobalTransactionStatus.refundtransaction_in_progress, 
        target=GlobalTransactionStatus.refunded, custom=dict(admin=True))
    def refunded(self):
        logger.info('Refunding in progress')


    @transition(field='status', source=GlobalTransactionStatus.refundtransaction_in_progress, 
        target=GlobalTransactionStatus.refunded_error, custom=dict(admin=True))
    def refunding_error(self):
        logger.info('Refunding Error')


    @transition(field='status', source=GlobalTransactionStatus.collectransaction_in_progress, 
        target=GlobalTransactionStatus.blocked, custom=dict(admin=True))
    def block(self):
        logger.info('Global Transaction blocked.')


    @transition(field='status', source=GlobalTransactionStatus.collectransaction_in_progress, 
        target=GlobalTransactionStatus.canceled, custom=dict(admin=True))
    def cancel(self):
        if self.status not in [GlobalTransactionStatus.success, GlobalTransactionStatus.funding_error, GlobalTransactionStatus.blocked, GlobalTransactionStatus.refunded,
                                GlobalTransactionStatus.canceled, GlobalTransactionStatus.refundtransaction_in_progress, GlobalTransactionStatus.refunded_error, GlobalTransactionStatus.refunded]:
            logger.info('Globaltransaction status not final !')
            collect_transactions = self.collect_transactions.all()
            if collect_transactions:
                for collect_operation in collect_transactions:
                    print(collect_operation)
                    # TODO might check if some collect transactions are succesful
                    if collect_operation.status not in [CollectTransactionStatus.canceled, CollectTransactionStatus.blocked, CollectTransactionStatus.on_hold,
                            CollectTransactionStatus.rejected, CollectTransactionStatus.aml_blocked, CollectTransactionStatus.error, CollectTransactionStatus.not_found, CollectTransactionStatus.collected]:
                        tasks = PeriodicTasksEntry.objects.filter(name=f'checking {collect_operation.partner} collect of {self.user} {self.uuid}')
                        if tasks:
                            for task in tasks:
                                task.delete()
                        collect_operation.cancel.apply_async((collect_operation.uuid,))
        logger.info('Global Transaction cancelled')
        
    


    """
    @transition(field='status', source=[GlobalTransactionStatus.fundtransaction_in_progress, GlobalTransactionStatus.collectransaction_in_progress], 
        target=GlobalTransactionStatus.refunded, custom=dict(admin=True))
    def refund(self):
        # Start refund transaction
        #TODO add code to refund
        pass
    """