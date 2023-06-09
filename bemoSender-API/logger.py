from datetime import datetime
import logging
import platform
import traceback
import os
from django.core.mail import send_mail
from django.conf import settings
from django.apps import apps
from django.utils import timezone
from loguru import logger
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives


#from bemoSenderr.models.user import AdminAlerts
class SendAdminAlerts():

    def __init__(self) -> None:
        self.env = None
        if settings.CONFIG and settings.CONFIG.get('env', None) in ['Dev-V3', None]:
            self.env = "Dev-V3"
        else:
            self.env = "Prod-V3"
    def send_admin_alert_partner_failure(self, global_tx=None, operation="", partner=None, params=None):
        try:
            time_now = datetime.strftime(timezone.now(), "%c")
            body = ""
            if operation == "funding_authorize_deposits_error":
                body = f"""
                Report Date: {time_now}
                Environment: {self.env}
                Partner: {partner}
                {params['failure_type']}
                An error occurred during requests to Partner: {partner}
                Content: Error during Authorize Deposits periodic task
                Failure count: 1
                """
            if operation == "funding_authorize_get_incoming_transfer" and global_tx:
                body = f"""
                Report Date: {time_now}
                Environment: {self.env}
                Partner: {partner}
                Transfer from: {global_tx.receiver_snapshot['first_name']} {global_tx.receiver_snapshot['last_name']}
                Amount: {format(float(global_tx.parameters.get('amount_origin', 0)), ".2f")} {global_tx.parameters['currency_origin']}
                Transfer Email Date : {params['time']}
                {params['failure_type']}
                An error occurred during requests to Partner: {partner}
                Content: Error during Authorize Deposits (GetIncomingTransfer process)
                GlobalTransaction UUID : {str(global_tx.uuid)}
                FundingTransaction UUID: {str(global_tx.funding_transaction.uuid)}
                Failure count: 1
                """
            if operation == "funding_authorize_authenticate_transfer" and global_tx:
                body = f"""
                Report Date: {time_now}
                Environment: {self.env}
                Partner: {partner}
                Transfer from: {global_tx.receiver_snapshot['first_name']} {global_tx.receiver_snapshot['last_name']}
                Amount: {global_tx.parameters['amount_origin']} {global_tx.parameters['currency_origin']}
                Transfer Email Date : {params['time']}
                {params['failure_type']}
                An error occurred during requests to Partner: {partner}
                Content: Error during Authorize Deposits (AuthenticateTransfer process)
                GlobalTransaction UUID : {str(global_tx.uuid)}
                FundingTransaction UUID: {str(global_tx.funding_transaction.uuid)}
                Failure count: 1
                """
            if operation == "funding_authorize_complete_transfer" and global_tx:
                body = f"""
                Report Date: {time_now}
                Environment: {self.env}
                Partner: {partner}
                Transfer from: {global_tx.receiver_snapshot['first_name']} {global_tx.receiver_snapshot['last_name']}
                Amount: {global_tx.parameters['amount_origin']} {global_tx.parameters['currency_origin']}
                Transfer Email Date : {params['time']}
                {params['failure_type']}
                An error occurred during requests to Partner: {partner}
                Content: Error during Authorize Deposits (CompleteTransfer process)
                GlobalTransaction UUID : {str(global_tx.uuid)}
                FundingTransaction UUID: {str(global_tx.funding_transaction.uuid)}
                Failure count: 1
                """
            if operation == "funding_check_deposits_apaylo":
                body = f"""
                Report Date: {time_now}
                Environment: {self.env}
                Partner: {partner}
                Content: Error during Check Deposits periodic task
                {params['failure_type']}
                An error occurred during requests to Partner: {partner}
                Failure count: 1
                """
            if operation == "funding_check_deposits_error":
                body = f"""
                Report Date: {time_now}
                Environment: {self.env}
                Partner: {partner}
                Content: Error during Check Deposits
                {params['failure_type']}
                An error occurred during requests to Partner: {partner}
                Failure count: 1
                """
            elif operation == "collect_create_order" and global_tx:
                body = f"""
                Report Date: {time_now}
                Environment: {self.env}
                Partner: {partner}
                Transfer from: {global_tx.receiver_snapshot['first_name']} {global_tx.receiver_snapshot['last_name']}
                Amount: {global_tx.parameters['amount_origin']} {global_tx.parameters['currency_origin']} - {global_tx.parameters['amount_destination']} {global_tx.parameters['currency_destination']}
                {params['failure_type']}
                Content: An error occurred during the CreateOrder Send-Money process
                Failure count: 1
                An error occurred during requests to Partner: {partner}
                GlobalTransaction UUID : {str(global_tx.uuid)}
                CollectTransaction UUID: {params['collect_uuid']}
                """
            elif operation == "collect_cancel_order" and global_tx:
                body = f"""
                Report Date: {time_now}
                Environment: {self.env}
                Partner: {partner}
                TRX ID: {str(global_tx.uuid)}
                SENDER ID: {str(global_tx.user.uuid)}
                RECIPIENT ID: 
                SENT TO  {global_tx.receiver_snapshot['first_name']} {global_tx.receiver_snapshot['last_name']} ({global_tx.receiver_snapshot['phone_number']})
                BY {global_tx.user_snapshot['first_name']} {global_tx.user_snapshot['last_name']} ({global_tx.user_snapshot['phone_number']})
                AMOUNT: {global_tx.parameters['amount_origin']} {global_tx.parameters['currency_origin']} - {global_tx.parameters['amount_destination']} {global_tx.parameters['currency_destination']}
                Network: {partner}
                TransactionCode: {params.get('tx_code', None)}
                
                {params['failure_type']}
                Content: An error occurred during the CancelOrder Send-Money process
                Failure count: 1
                An error occurred during requests to Partner: {partner}
                GlobalTransaction UUID : {global_tx.uuid}
                CollectTransaction UUID: {params['collect_uuid']}
                """
                #TODO
                #ReferenceCode: {params.get('ref_code', None)} can't be dynamic ...
            elif operation == "update_rates" and global_tx:
                body = f"""
                Report Date: {time_now}
                Environment: {self.env}
                Partner: {partner}
                {params['failure_type']}
                Content: An error occurred during the CreateOrder Send-Money process
                Failure count: 1
                An error occurred during requests to Partner: {partner}
                """
            elif operation == "funding_check_refunds_error":
                body = f"""
                Report Date: {time_now}
                Environment: {self.env}
                Partner: {partner}
                {params['failure_type']}
                An error occurred during requests to Partner: {partner}
                Content: Error during Check Refunds periodic task
                Failure count: 1
                """
            logger.info(f"Body of send admin alert error {body}")
            if body:
                self.send_admin_email(body=body, partner=partner)
        except Exception as e:
            print(f"Exception caught on SendAdminAlerts partner {partner}")
            print(e)


    def send_admin_email(self, body=None, partner=None):
        if body and partner:
            recipients = apps.get_model('bemoSenderr.AdminAlerts').objects.filter(can_receive_celery_exceptions=True)
            recipients_emails = []
            if recipients:
                for recipient in recipients:
                    recipients_emails.append(recipient.user.email)
            else:
                recipients_emails = [settings.ADMINS[0][0][1]]
            result = send_mail(
                subject=f"<{self.env}>: AN ERROR OCCURED WITH {str(partner).upper()} PARTNER",
                message=body,
                from_email=str(settings.SERVER_EMAIL),
                recipient_list=recipients_emails,
                fail_silently=True
            )


    def send_unmatched_deposit_email(self, params=None):
        if params:
            data = {
                    "date_now":datetime.utcnow().isoformat(),
                    "env": self.env,
                    "full_name": params.get("full_name", None),
                    "amount": format(float(params.get('amount', 0)), ".2f"),
                    "deposit_type" : params.get('deposit_type', "Auto Deposit"),
                    "email": params.get('email', None)
                }
            html_message = render_to_string(os.path.join(os.getcwd(), 'bemoSenderr','templates', 'deposits', 'unmatched_deposit.html'), data)
            print(html_message)
            recipients = apps.get_model('bemoSenderr.AdminAlerts').objects.filter(can_receive_celery_exceptions=True)
            recipients_emails = []
            if recipients:
                for recipient in recipients:
                    recipients_emails.append(recipient.user.email)
            else:
                recipients_emails = [settings.ADMINS[0][0][1]]
            email = EmailMultiAlternatives(
                f"<{self.env}> UNMATCHED AUTO DEPOSIT",
                f"<{self.env}> UNMATCHED AUTO DEPOSIT",
                str(settings.SERVER_EMAIL),
                recipients_emails,
            )
            
            email.attach_alternative(html_message, 'text/html')
            email.send(fail_silently=True)



class IgnoreFilter(logging.Filter):
    def __init__(self, types):
        self.types = types

    def filter(self, record):
        # This is causing some performance issues in django!
        test = record
        try:
            excp_type = type(record.exc_info[1]).__name__
            if excp_type in self.types:
                return False
            else:
                return True
        except Exception as e:
            return True

def make_filter(name):
    def filter(record):
        return record["extra"].get("name") == name
    return filter


separator = None
if platform.system() == 'Linux':
    separator = "/"
else:
    separator = "\\"
logs_path = str(os.getcwd()) + separator + "logs"
global_transaction_path = os.path.join(logs_path, "Transactions", "Global Transactions")
collect_transaction_path = os.path.join(logs_path, "Transactions", "Collect Transactions")
funding_transaction_path = os.path.join(logs_path, "Transactions", "Funding Transactions")
authorize_deposits_path = os.path.join(logs_path, "Authorize Deposits")
check_deposits_path = os.path.join(logs_path, "Check Deposits")
update_rates_path = os.path.join(logs_path, "Update Rates")
api_requests_path = os.path.join(logs_path, "API Requests")
#logger.add(sink=f"{collect_transaction_path}{separator}log_{{time}}.log", rotation="1 MB", level="INFO", encoding="utf-8", filter=make_filter("collect-transactions"))
#logger.add(sink=f"{global_transaction_path}{separator}log_{{time}}.log", rotation="1 MB", level="INFO", encoding="utf-8", filter=make_filter("global-transactions"))
#logger.add(sink=f"{funding_transaction_path}{separator}log_{{time}}.log", rotation="1 MB", level="INFO", encoding="utf-8", filter=make_filter("funding-transactions"))
#logger.add(sink=f"{authorize_deposits_path}{separator}log_{{time}}.log", rotation="1 MB", level="INFO", encoding="utf-8", filter=make_filter("authorize-deposits"))
#logger.add(sink=f"{check_deposits_path}{separator}log_{{time}}.log", rotation="1 MB", level="INFO", encoding="utf-8", filter=make_filter("check-deposits"))
#logger.add(sink=f"{update_rates_path}{separator}log_{{time}}.log", rotation="1 MB", level="INFO", encoding="utf-8", filter=make_filter("update-rates"))
#logger.add(sink=f"{api_requests_path}{separator}log_{{time}}.log", rotation="1 MB", level="INFO", encoding="utf-8", filter=make_filter("api-requests"))

"""
To log anything with a desired handler use this : 
Example:
collect_logger = logger.bind(name="collect-transactions")
collect_logger.info("this is for the collect transactions handler")
"""

##For Json Objects or Dictionaries:
"""
pp = pprint
prettified = '\n' + pp.pformat(data)
logger.info(prettified)
"""
##For Lists :
"""
data_list = [['test', 'yes'], 'no','kjgkldfjgd','kflsjdfls','lgfgldfgfd','kljgfdlkfgjdflg']
prettified_list = '\n' + (pp.pformat(data_list))
logger.info(prettified_list)
"""

def send_email_celery_exception(exception):
    e = traceback.format_exc()
    recipients = apps.get_model('bemoSenderr.AdminAlerts').objects.filter(can_receive_celery_exceptions=True)
    recipients_emails = []
    if recipients:
        for recipient in recipients:
            recipients_emails.append(recipient.user.email)
    else:
        recipients_emails = [settings.ADMINS[0][0][1]]
    result = send_mail(
        subject=f"<{str(settings.CONFIG['env'])}>: CELERY EXCEPTION : {exception}",
        message=e,
        from_email=str(settings.SERVER_EMAIL),
        recipient_list=recipients_emails,
        fail_silently=True
    )
    print(result)
    print('HANDLING EXCEPTION', result)