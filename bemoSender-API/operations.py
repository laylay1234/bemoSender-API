import datetime
from loguru import logger
from bemosenderrr.logger import send_email_celery_exception
from bemosenderrr.models.partner.base import PartnerApiCallType
from bemosenderrr.models.partner.partner import AppSettings, Country, Currency
from bemosenderrr.models.base import CollectTransactionStatus, GlobalTransactionStatus, PartnerStatus, PartnerType
from django.apps import apps
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import os
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from bemosenderrr.models.partner.services.apaylo_service import ApayloService
from bemosenderrr.models.task import PeriodicTasksEntry
from bemosenderrr.utils.notifications import NotificationsHandler
from bemosenderrr.utils.pinpoint import PinpointWrapper
from bemosenderrr.utils.s3 import upload_to_s3
from celery import shared_task, chain
from pyvirtualdisplay import Display
import pdfkit
from dateutil.relativedelta import relativedelta
from redbeat import RedBeatSchedulerEntry as Entry
from bemosenderrr.celery import app
from django.conf import settings
from bemosenderrr.models.partner.services.utils import getPaymentCode, getTransactionId


"""
This module is for the send money operations, admin alerts and transanction cumulative limits for corresponding user tiers.
"""
class SendMoney():

    @shared_task(bind=True)
    @logger.catch(onerror=send_email_celery_exception)
    def fund_transaction(self, global_transaction_id=None):
        time_now = datetime.datetime.strftime(timezone.now(), "%c")
        report = ''
        global_transaction = apps.get_model(
            'bemosenderrr.GlobalTransaction').objects.filter(uuid=global_transaction_id).select_related("funding_transaction").first()
        report += str(global_transaction) + "\n" + " UUID : " + str(global_transaction_id) + "\n" "Global Transaction Status " + str(global_transaction.status) + '\n' 
        report += "Time :"+ time_now + "\n"
        report += "----------------------------------------------------------------------" + "\n"
        # Get funding operation instance
        funding_operation = apps.get_model('bemosenderrr.FundingTransaction').objects.get(
            uuid=global_transaction.funding_transaction.uuid)
        report += "Starting Funding Transaction" + "\n"
        report += "----------------------------------------------------------------------" + "\n"
        report += str(funding_operation) + "\n" + " UUID : " + str(funding_operation.uuid) + "\n"
        """
        THIS IS VERY IMPORTANT WHEN HANDLING TASKS STORED IN REDIS DB
            GET ALL ENTRIES IN REDBEAT **VERY IMPORTANT FOR DEBUGGING**
            redis = schedulers.get_redis(app)
            conf = schedulers.RedBeatConfig(app)
            keys = redis.zrange(conf.schedule_key, 0, -1)
            entries = [schedulers.RedBeatSchedulerEntry.from_key(key, app=app) for key in keys]
            print(entries)
        """
        logger.info(report)
        try:
            e = Entry.from_key(key=f"redbeat:Checking funding inactivity for {str(funding_operation.uuid)}", app=app)
            logger.info("Funding Transaction Inactivity periodic task Exists ! ")
            # Periodic task object to manage redbeat periodic tasks(entries) dynamically)
            periodic_task, created = PeriodicTasksEntry.objects.get_or_create(key=e.key, task="bemosenderrr.models.partner.transactions.check_funding_inactivity",
                            name=e.name, schedule=900, args=[str(funding_operation.uuid)]
            )
            periodic_task.save()
        except Exception as e:
            e = Entry(schedule=900, name=f"Checking funding inactivity for {str(funding_operation.uuid)}", app=app,
                    task="bemosenderrr.models.partner.transactions.check_funding_inactivity", args=[str(funding_operation.uuid)])
            e.save()
            logger.info("Funding Transaction Inactivity periodic task is NEW ! ")
            # Periodic task object to manage redbeat periodic tasks(entries) dynamically)
            periodic_task, created = PeriodicTasksEntry.objects.get_or_create(key=e.key, task="bemosenderrr.models.partner.transactions.check_funding_inactivity",
                                                                            name=e.name, schedule=900, args=[str(funding_operation.uuid)]
                                                                            )
            periodic_task.save()


    @shared_task(bind=True)
    @logger.catch(onerror=send_email_celery_exception)
    def collect_transactions(self, global_transaction_id=None):
        report = ''
        time_now = datetime.datetime.strftime(timezone.now(), "%c")
        global_transaction = apps.get_model(
            'bemosenderrr.GlobalTransaction').objects.filter(uuid=global_transaction_id).prefetch_related("collect_transactions", "collect_transactions__partner").first()
        report += str(global_transaction) + "\n" + " UUID : " + str(global_transaction_id) + "\n" "Global Transaction Status " + str(global_transaction.status) + '\n' 
        report += "Time :"+ time_now + "\n"
        collect_operations = global_transaction.collect_transactions.all()
        collect_tasks = list()
        report += "Starting collect transactions" + "\n"
        report += "----------------------------------------------------------------------" + "\n"
        dirham_transaction_code = getTransactionId(9, 11)
        dirham_payment_code = getPaymentCode(dirham_transaction_code)
        for collect_operation in collect_operations:
            # Configuration of the collect partner API
            api_config = collect_operation.partner.api_config
            collect_uuid = collect_operation.uuid
            if collect_operation.partner.api_config.get('serviceClass', None) == "DirhamService" or collect_operation.partner.api_call_type == PartnerApiCallType.inbound:
                collect_code = dirham_payment_code
            else:
                collect_code = None
            collect_operation.status = CollectTransactionStatus.in_progress
            collect_operation.save()
            report += "Collect Transaction for partner : " + str(collect_operation.partner) + "\n"
            report += str(collect_operation) + "\n"
            report += "UUID : " + str(collect_uuid) + "\n"
            report += "-------------------------" + "\n"
            # Append Current Collect operation celery task with its signature in a list 
            task = collect_operation.collect.si(global_transaction_id, collect_uuid, api_config, collect_code, dirham_transaction_code)
            collect_tasks.append(task)
        # Create a celery group in case of a country having multiple Partners. 
        from bemosenderrr.tasks import send_invoice_task
        g = chain(collect_tasks) #Celery Group of the collect transactions.
        g.link(send_invoice_task.si((str(global_transaction_id)))) # Attach callback function to send the invoice and sync the collect_codes.
        result = g() # Start the tasks (equivalent to g.apply_async())   
        logger.info(result)

            
    @logger.catch
    def refund_transfer(self, instance_uuid=None):
        try:
            partner = apps.get_model("bemosenderrr.Partner").objects.filter(type=PartnerType.funding, status=PartnerStatus.active).select_related('api_user').first()
            api_config = None
            auto_refund = False
            if partner:
                api_config = partner.api_config
                auto_refund = api_config.get('autoRefund', False)
                if auto_refund:
                    auto_refund = True
                print("AUTO REFUND ", auto_refund)

            if partner and str(partner.name).lower() in "apaylo" and auto_refund:
                apaylo = partner
                api_config = apaylo.api_config
                api_config['credentials'] = apaylo.api_user.credentials
                collect_instance = apps.get_model("bemosenderrr.CollectTransaction").objects.get(uuid=instance_uuid)
                instance = collect_instance.globaltransaction_set.all().first()
                response = ApayloService().refund_interac_transfer(api_config=api_config, instance_uuid=str(instance.uuid))
                if response and response.get('StatusCode', None) == 200 and response.get('IsError', True) == False:
                    transaction_number = response.get("Result", None).get("TransactionNumber", None)
                    if transaction_number:
                        funding_transaction = instance.funding_transaction
                        funding_transaction.refund_reference_code = transaction_number
                        funding_transaction.refund_api_response = response
                        funding_transaction.save()
                        instance.status = GlobalTransactionStatus.refundtransaction_in_progress
                        instance.save()
                        logger.info(f'SUCCESSFULLY REFUNDED TRANSACTION WITH UUI {instance_uuid}')
                else:
                    logger.info(f"FAILED TO REFUND TRANSACTION {instance_uuid}")
            else:
                # This is where to handle new funding partners
                print("apaylo not active cannot refund.")
                return
        except Exception as e:
            print('exception caught while refunding', e)
            return 


class SendInvoice():
    @logger.catch(onerror=send_email_celery_exception)
    def send_invoice(self, global_tx):
        
        
        """
        WHEN ORDERS ARE CREATED (COLLECT_READY) NOTIFY THE ADMINS BY EMAIL
        """
        with logger.catch(onerror=send_email_celery_exception):
            SendAdminAlert().send_admin_collect_tx_sent(global_tx)
        """
        ---------------------------------------------------------------------------------------------------------------------
        Send Push notification to (senderr) and sms to (Receiver)
        ---------------------------------------------------------------------------------------------------------------------
        """
        
        with logger.catch(onerror=send_email_celery_exception):
            if global_tx.status not in (GlobalTransactionStatus.canceled, GlobalTransactionStatus.blocked, GlobalTransactionStatus.not_found):
                user = global_tx.user
                currency_origin = Currency.objects.get(iso_code=global_tx.parameters.get('currency_origin'))
                currency_destination = Currency.objects.get(iso_code=global_tx.parameters.get('currency_destination'))
                amount_origin_currency = str(global_tx.parameters.get('amount_origin', "UNDEFINED")) + " " + currency_origin.short_sign
                amount_destination_currency = str(global_tx.parameters.get('amount_destination', "UNDEFINED")) + " " + currency_destination.short_sign
                senderr_name = str(global_tx.user_snapshot.get('first_name', "UNDEFINED")) + " " + str(global_tx.user_snapshot.get('last_name', "UNDEFINED"))
                receiver_name = str(global_tx.receiver_snapshot.get('first_name', "UNDEFINED")) + " " + str(global_tx.receiver_snapshot.get('last_name', "UNDEFINED"))
                receiver_phone_number = str(global_tx.receiver_snapshot.get('phone_number', "UNDEFINED"))
                country_destination = Country.objects.get(iso_code=global_tx.parameters.get('destination_country'))
                print("THIS IS THE DESTINATION COUNTRY ", country_destination)
                lang_receiver = global_tx.receiver_snapshot.get('language', "FR")
                if lang_receiver == "french":
                    lang_receiver = "FR"
                elif lang_receiver == "english":
                    lang_receiver = "EN"
                notif_service = NotificationsHandler()
                pinpoint_service = PinpointWrapper()#SNSNotificationService()
                status_push = False
                language = user.locale
                if not language:
                    language = "FR"
                push_notif_data = notif_service.get_tx_collect_ready_senderr_push(lang=language, vars=[amount_origin_currency, amount_destination_currency, receiver_name, receiver_phone_number])
                logger.info('THIS IS THE USERSNAPSHOT OF THE LATEST GLOBALTRANSACTION')
                user_snapshot = apps.get_model('bemosenderrr.GlobalTransaction').objects.filter(user=global_tx.user).last().user_snapshot
                logger.info(user_snapshot)
                status_push = pinpoint_service.send_push_notifications_and_data(status=global_tx.status, user_snapshot=user_snapshot, user=user, data=push_notif_data, type="transaction", global_tx_uuid=str(global_tx.uuid))
                admin_phone_numbers = notif_service.get_staff_users_phone_numbers()
                if admin_phone_numbers:
                    admin_phone_numbers.append(receiver_phone_number)
                    receiver_phone_number = admin_phone_numbers
                else:
                    receiver_phone_number = [receiver_phone_number]
                logger.info(f"THIS IS THE RECEIVER PHONE NUMBER {receiver_phone_number}")
                logger.info(f'TYPE OF RECIPIENT PHONE NUMBERS {type(receiver_phone_number)}')
                status_sms = False
                collect_method = global_tx.collect_method
                if "cash" in str(collect_method).lower():
                    collect_transactions = global_tx.collect_transactions.all().filter(status=CollectTransactionStatus.collect_ready)
                    partners = ""
                    client_support = AppSettings.objects.all().first()
                    logger.info(f"CLIENT SUPPORT {client_support}")
                    if client_support:
                        client_support_help_desk = client_support.config.get('clientHelpDesk', None)
                        logger.info(f"CLIENT SUPPORT 2nd step {client_support}")
                        if client_support_help_desk:
                            client_support = str(client_support_help_desk.get("supportPhone", None).get(str(country_destination.iso_code).upper(), "")
                                ).replace(" ", "").replace("-", "").replace(",", "\n")
                            print(client_support)
                            if not client_support:
                                client_support = str(client_support_help_desk.get("supportPhone", None).get("default", "")).replace(" ", "").replace("-", "")
                                print(client_support)
                            logger.info(f"CLIENT SUPPORT {client_support} ")
                    else:
                        client_support = ""
                    for collect_tx in collect_transactions:
                        partners += f"{str(collect_tx.partner.display_name)}:\n{str(collect_tx.collect_code)}\n"
                    print(partners)
                    sms_notif_data = notif_service.get_tx_collect_cash_ready_receiver_sms(lang=lang_receiver, vars=[senderr_name, amount_destination_currency, partners, country_destination.name_fr, client_support])
                    print(sms_notif_data)
                    #TODO Check where to get origination number
                    status_sms = pinpoint_service.send_sms(destination_number=receiver_phone_number, origination_number="+123", message=sms_notif_data)
                    logger.info(f"SMS STATUS : {status_sms}")

                elif "bank" in str(collect_method).lower():
                    account_number = global_tx.receiver_snapshot.get('account_number', "UNDEFINED")
                    swift_code = global_tx.receiver_snapshot.get('swift_code', "UNDEFINED")
                    app_name = "bemosenderrr" #TODO is this gonna remain hardcoded or not ?
                    sms_notif_data = notif_service.get_tx_collect_bank_ready_receiver_sms(lang=lang_receiver, vars=[senderr_name, amount_destination_currency, account_number, swift_code])
                    #TODO Check where to get origination number
                    print(sms_notif_data)
                    status_sms = pinpoint_service.send_sms(destination_number=receiver_phone_number, origination_number="+123", message=sms_notif_data)
                    logger.info(f"SMS STATUS : {status_sms}")
                if status_push:
                    global_tx.notifications['tx_collect_ready_senderr'] = True
                if status_sms:
                    global_tx.notifications['tx_collect_ready_receiver'] = True
                global_tx.save()
        
        """
        ---------------------------------------------------------------------------------------------------
        Prepare data for the invoice
        ---------------------------------------------------------------------------------------------------
        """
        with logger.catch(onerror=send_email_celery_exception):
            subject = f'bemosenderrr Invoice {global_tx.invoice_number}'
            collect_transactions = global_tx.collect_transactions.all()
            user_snapshot = global_tx.user_snapshot
            receiver_snapshot = global_tx.receiver_snapshot
            parameters = global_tx.parameters
            origin_country = Country.objects.get(iso_code=parameters['origin_country'])
            destination_country = Country.objects.get(iso_code=parameters['destination_country'])
            origin_currency = Currency.objects.get(iso_code=parameters['currency_origin'])
            destination_currency = Currency.objects.get(iso_code=parameters['currency_destination'])
            rate_snapshot = global_tx.exchange_rate_tier_snapshot
            destination_lowest_amount = format(float(parameters['amount_destination']) / float(parameters['amount_origin']), ".2f")
            time_now = datetime.datetime.strftime(timezone.now(), "%b %d, %Y")
            data = {
                    'senderr_phone_number': user_snapshot['phone_number'],
                    'invoice_number': global_tx.invoice_number,
                    'senderr_first_name': str(user_snapshot['first_name']).upper(),
                    'senderr_last_name': str(user_snapshot['last_name']).upper(),
                    'invoice_date': time_now,
                    'senderr_address_1': user_snapshot['address_1'],
                    'senderr_state': user_snapshot['state'],
                    'senderr_zip_code': user_snapshot['zip_code'],
                    'user_city': str(user_snapshot['city']).upper(),
                    'user_country': origin_country.name,
                    'senderr_total_amount': format(float(parameters['total']), '.2f'),
                    'senderr_email': user_snapshot['email'],
                    'origin_country_name': origin_country.name,
                    'destination_country_name': destination_country.name,
                    'senderr_converted_amount': format(float(parameters['amount_destination']), ".2f"),
                    'origin_currency_sign': origin_currency.sign,
                    'senderr_origin_currency': origin_currency.iso_code,
                    'destination_lowest_amount': destination_lowest_amount,
                    'origin_currency_short_sign': origin_currency.short_sign,
                    'delivery_method_fee': parameters['fee'],
                    'delivery_method': global_tx.collect_method,
                    'origin_amount_no_fees': format(float(parameters['amount_origin']), ".2f"),
                    'destination_currency_sign': destination_currency.sign,
                    'reciever_first_name': receiver_snapshot['first_name'],
                    'receiver_last_name': receiver_snapshot['last_name'],
                    'collect_transactions': collect_transactions

            }
            html_message = render_to_string(os.path.join(os.getcwd(), 'bemosenderrr','templates', 'email', 'invoice.html'), data)
            plain_message = strip_tags(html_message)
            from_email = f'From <{settings.SERVER_EMAIL}>'
            to = 'bemosenderrr.test@gmail.com'
            admin_emails = NotificationsHandler().get_staff_users_emails()
            if admin_emails:
                if to in admin_emails:
                    pass
                else:
                    admin_emails.append(to)

            else:
                admin_emails = to
            print('THIS IS THE RECIPIENTS ', admin_emails)
            print(html_message)
            
            email = EmailMultiAlternatives(
                subject,
                f'bemosenderrr Invoice {global_tx.invoice_number}',
                str(settings.SERVER_EMAIL),
                admin_emails,
            )
            email.attach_alternative(html_message, 'text/html')
            email.content_subtype = "html"
            pdf = None
            # This is crucial in order to wkhtmltopdf work it needs an X server to work.
            with Display():
                try:
                    config = pdfkit.configuration(wkhtmltopdf='/usr/bin/wkhtmltopdf')
                    pdf = pdfkit.from_string(html_message, configuration=config, options={"encoding" : "UTF-8"})
                    print('first path worked')
                except Exception as e:
                    print("second path")
                    try:
                        config = pdfkit.configuration(wkhtmltopdf='/usr/local/bin/wkhtmltopdf')
                        print('second path worked')
                        pdf = pdfkit.from_string(html_message, configuration=config, options={"encoding" : "UTF-8"})
                    except Exception as e:
                        print('nothing worked')
                        pdf = pdfkit.from_string(html_message, options={"encoding" : "UTF-8"})
            email.attach(f"Invoice {global_tx.invoice_number}.pdf", pdf, 'application/pdf')
            email.send(fail_silently=True)
            env = ""
            if settings.CONFIG and settings.CONFIG.get('env', None) in ['Dev-V3', None]:
                env = "dev"
            else:
                env = "prod"
            upload_to_s3(body=pdf, bucket='v3-invoicing', key=f"{env}/bemosenderrr Invoice {global_tx.invoice_number} {time_now}.pdf", content_type='application/pdf')
        

class SendAdminAlert():

    """
    Send an email to admins when a NEW Global Transaction is created.
    """
    @logger.catch(onerror=send_email_celery_exception)
    def send_admin_collect_tx_sent(self, instance):
        env = str(settings.CONFIG['env'])
        transaction_method = str(instance.collect_method).lower()
        tx_method = ""
        agencies = None
        receiver_mobile_money = ""
        if "bank" in str(transaction_method).lower():
            tx_method = """
                BANK TRANSFER: <br>
                        ACCOUNT NUMBER: <receiver.accountNumber>
                        SWIFT: <receiver.swiftCode>
            """

        elif "cash" in str(transaction_method).lower():
            tx_method = "AGENCIES: <br>" 
            for collect_tx in instance.collect_transactions.all():
                tx_method += f"""{str(collect_tx.partner.name)} {str(collect_tx.collect_code)} <br>"""
            agencies = instance.collect_transactions.all()
        elif "mobile" in str(transaction_method).lower():
            receiver_mobile_money = instance.receiver_snapshot.get("mobile_network", "UNDEFINED")
        logger.info(tx_method)
        user_snapshot = instance.user_snapshot
        receiver_snapshot = instance.receiver_snapshot
        amount_origin = format(float(instance.parameters.get('amount_origin', 0)), ".2f")
        amount_destination = format(float(instance.parameters.get('amount_destination', 0)), ".2f")
        currency_origin = instance.parameters.get('currency_origin', "UNDEFINED")
        currency_destination = instance.parameters.get('currency_destination', "UNDEFINED")
        time_now = datetime.datetime.strftime(timezone.now(), "%c")
        receiver_first_name = receiver_snapshot.get("first_name", "UNDEFINED")
        receiver_last_name = receiver_snapshot.get("last_name", "UNDEFINED")
        receiver_phone_number = receiver_snapshot.get("phone_number", "UNDEFINED")
        receiver_account_number = receiver_snapshot.get("account_number", "UNDEFINED")
        receiver_swift_code = receiver_snapshot.get("swift_code", "UNDEFINED")
        user_first_name = user_snapshot.get("first_name", "UNDEFINED")
        user_last_name = user_snapshot.get("last_name", "UNDEFINED")
        user_phone_number = user_snapshot.get("phone_number", "UNDEFINED")
        user_birth_date = user_snapshot.get("birth_date", "UNDEFINED")
        user_birth_city = user_snapshot.get("birth_city", "UNDEFINED")
        user_birth_country = user_snapshot.get("birth_country", "UNDEFINED")
        data = {
            "time_now": time_now,
            "environment": env,
            "amount_origin": amount_origin,
            "amount_destination": amount_destination,
            "currency_origin": currency_origin,
            "currency_destination": currency_destination,
            "tx_method": tx_method,
            "receiver_first_name": receiver_first_name,
            "receiver_last_name": receiver_last_name,
            "receiver_phone_number": receiver_phone_number,
            "receiver_account_number": receiver_account_number,
            "receiver_swift_code": receiver_swift_code,
            "user_first_name": user_first_name,
            "user_phone_number": user_phone_number,
            "user_last_name": user_last_name,
            "user_birth_date": user_birth_date,
            "user_birth_city": user_birth_city,
            "user_birth_country": user_birth_country,
            "agencies": agencies,
            "tx_method": transaction_method,
            "receiver_mobile_money": receiver_mobile_money
        }
        html_message = render_to_string(os.path.join(os.getcwd(), 'bemosenderrr','templates', 'email', 'admin_alert_trx_sent.html'), data)
        to = 'bemosenderrr.test@gmail.com'
        admin_emails = NotificationsHandler().get_staff_users_emails()
        if admin_emails:
            if to in admin_emails:
                pass
            else:
                admin_emails.append(to)
        else:
            admin_emails = to
        print('THIS IS THE RECIPIENTS ', admin_emails)
        logger.info(html_message)
        email = EmailMultiAlternatives(
            f"<{str(settings.CONFIG['env'])}> NEW Collect Transaction Notification",
            "",
            str(settings.SERVER_EMAIL),
            admin_emails
        )
        email.attach_alternative(html_message, 'text/html')
        email.content_subtype = "html"
        email.send(fail_silently=False)
        logger.info(f"THIS IS THE EMAIL INT {email}")

    

    """
    Send an email to admins when a Global Transaction is successful (SUCCES)
    """
    @logger.catch(onerror=send_email_celery_exception)
    def send_admin_collect_tx_collected(self, instance):
        if instance.status == CollectTransactionStatus.collected:
            env = str(settings.CONFIG['env'])
            global_tx = instance.globaltransaction_set.all().first()
            amount_origin = format(float(global_tx.parameters.get('amount_origin', 0)), ".2f")
            amount_destination = format(float(global_tx.parameters.get('amount_destination', 0)), ".2f")
            currency_origin = global_tx.parameters.get('currency_origin', "UNDEFINED")
            currency_destination = global_tx.parameters.get('currency_destination', "UNDEFINED")
            user_snapshot = global_tx.user_snapshot
            receiver_snapshot = global_tx.receiver_snapshot
            time_now = datetime.datetime.strftime(timezone.now(), "%c")
            content = ""
            receiver_snapshot = global_tx.receiver_snapshot
            if receiver_snapshot.get("first_name", None) and receiver_snapshot.get("last_name", None):
                content = f"""
                            YXF OPERATION to {str(instance.partner.name).upper()}: TRX Picked up by {receiver_snapshot.get("first_name", None)} {receiver_snapshot.get("last_name", None)} {receiver_snapshot.get("phone_number", "UNDEFINED")} \n
                """
            else:
                content = f"YXF OPERATION to {str(instance.partner.name).upper()}: TRX **Picked up by** **Undefined Receiver** \n"
            user_data = ""
            if not user_snapshot:
                user_data = "Undefined User"
            else:
                user_data = f"""{user_snapshot.get("first_name", "UNDEFINED")} {user_snapshot.get("last_name", "UNDEFINED")} ({user_snapshot.get("phone_number", "UNDEFINED")})"""
            partner_name = str(instance.partner.name)
            collect_code = str(instance.collect_code)
            data = {
                "time_now": time_now,
                "environment": env,
                "content": content,
                "amount_origin": amount_origin,
                "amount_destination": amount_destination,
                "currency_origin": currency_origin,
                "currency_destination": currency_destination,
                "partner_name": partner_name,
                "collect_code": collect_code,
                "user_data": user_data
            }
            html_message = render_to_string(os.path.join(os.getcwd(), 'bemosenderrr','templates', 'email', 'admin_alert_trx_collected.html'), data)
            to = 'bemosenderrr.test@gmail.com'
            admin_emails = NotificationsHandler().get_staff_users_emails()
            if admin_emails:
                if to in admin_emails:
                    pass
                else:
                    admin_emails.append(to)
            else:
                admin_emails = to
            print('THIS IS THE RECIPIENTS ', admin_emails)
            logger.info(html_message)
            email = EmailMultiAlternatives(
                f"<{str(settings.CONFIG['env'])}> Paid Collect Transaction Notification",
                "",
                str(settings.SERVER_EMAIL),
                admin_emails
            )
            email.attach_alternative(html_message, 'text/html')
            email.content_subtype = "html"
            email.send(fail_silently=False)



class TxLimitCumulOperations():

    def on_send_money(self, global_tx=None):
        logger.info("Send money tx_limit_cumul operation")
        try:
            tx_limit_cumul_model = apps.get_model("bemosenderrr.TxLimitCumul")
            user = global_tx.user
            tx_amount = global_tx.parameters.get("amount_origin", "UNDEFINED")
            cumulative_debut = limit_1_month = last_1_month_refresh = limit_3_month = last_3_month_refresh = limit_12_month = last_12_month_refresh = total_transfered_amount = None
            last_tx_limit_cumul = tx_limit_cumul_model.objects.filter(user=user).order_by("-created_at").first()
            
            if last_tx_limit_cumul:
                logger.info(f"UUID {last_tx_limit_cumul.uuid}")
                cumulative_debut = last_tx_limit_cumul.cumulative_debut
                limit_1_month = str(round(float(last_tx_limit_cumul.limit_1_month) + float(tx_amount), 4))
                last_1_month_refresh = last_tx_limit_cumul.last_1_month_refresh
                limit_3_month = str(round(float(last_tx_limit_cumul.limit_3_month) + float(tx_amount), 4))
                last_3_month_refresh = last_tx_limit_cumul.last_3_month_refresh
                limit_12_month = str(round(float(last_tx_limit_cumul.limit_12_month) + float(tx_amount), 4))
                last_12_month_refresh = last_tx_limit_cumul.last_12_month_refresh
                total_transfered_amount = str(round(float(last_tx_limit_cumul.total_transfered_amount) + float(tx_amount), 4))
                new_tx_limit_cumul = tx_limit_cumul_model.objects.create(
                    user=user,
                    amount=tx_amount,
                    operation="Send Money",
                    global_transaction=global_tx,
                    cumulative_debut = cumulative_debut,
                    limit_1_month = limit_1_month,
                    last_1_month_refresh = last_1_month_refresh,
                    limit_3_month = limit_3_month,
                    last_3_month_refresh = last_3_month_refresh,
                    limit_12_month = limit_12_month,
                    last_12_month_refresh = last_12_month_refresh,
                    total_transfered_amount = total_transfered_amount
                )
            else:
                new_tx_limit_cumul = tx_limit_cumul_model.objects.create(
                    user=user,
                    amount=tx_amount,
                    operation="Send Money",
                    global_transaction=global_tx,
                    cumulative_debut = timezone.now(),
                    limit_1_month = tx_amount,
                    last_1_month_refresh = timezone.now(),
                    limit_3_month = tx_amount,
                    last_3_month_refresh = timezone.now(),
                    limit_12_month = tx_amount,
                    last_12_month_refresh = timezone.now(),
                    total_transfered_amount = tx_amount
                )
        except Exception as e:
            logger.info('TxLimitCumulOperations.on_send_money ERROR')
            logger.info(e.args)
            send_email_celery_exception(e)

    def on_refund_money(self, global_tx=None, operation="", refund_with_fees=False):
        logger.info("Refund tx_limit_cumul operation")
        try:
            tx_limit_cumul_model = apps.get_model("bemosenderrr.TxLimitCumul")
            user = global_tx.user
            tx_amount = global_tx.parameters.get("amount_origin", "UNDEFINED")
            cumulative_debut = limit_1_month = last_1_month_refresh = limit_3_month = last_3_month_refresh = limit_12_month = last_12_month_refresh = total_transfered_amount = None
            last_tx_limit_cumul = tx_limit_cumul_model.objects.filter(user=user).order_by("-created_at").first()
            operation_text = 'user transaction cancel with fees'
            if "admin" in operation:
                operation_text = 'admin transaction cancel'
                if refund_with_fees:
                    operation_text += ' with fees'
            if last_tx_limit_cumul:
                cumulative_debut = last_tx_limit_cumul.cumulative_debut
                limit_1_month = str(round(float(last_tx_limit_cumul.limit_1_month) + float(tx_amount) * (-1), 4))
                last_1_month_refresh = last_tx_limit_cumul.last_1_month_refresh
                limit_3_month = str(round(float(last_tx_limit_cumul.limit_3_month) + float(tx_amount) * (-1), 4))
                last_3_month_refresh = last_tx_limit_cumul.last_3_month_refresh
                limit_12_month = str(round(float(last_tx_limit_cumul.limit_12_month) + float(tx_amount) * (-1), 4))
                last_12_month_refresh = last_tx_limit_cumul.last_12_month_refresh
                total_transfered_amount = str(round(float(last_tx_limit_cumul.total_transfered_amount) + float(tx_amount) * (-1), 4))
                new_tx_limit_cumul = tx_limit_cumul_model.objects.create(
                    user=user,
                    amount=str(float(tx_amount) * (-1)),
                    operation="refund from " + operation_text,
                    global_transaction=global_tx,
                    cumulative_debut = cumulative_debut,
                    limit_1_month = limit_1_month,
                    last_1_month_refresh = last_1_month_refresh,
                    limit_3_month = limit_3_month,
                    last_3_month_refresh = last_3_month_refresh,
                    limit_12_month = limit_12_month,
                    last_12_month_refresh = last_12_month_refresh,
                    total_transfered_amount = total_transfered_amount
                )
            else:
                new_tx_limit_cumul = tx_limit_cumul_model.objects.create(
                    user=user,
                    amount= str(round((-1) * float(tx_amount), 4)),
                    operation=operation_text,
                    global_transaction=global_tx,
                    cumulative_debut = timezone.now(),
                    limit_1_month = str(round((-1) * float(tx_amount), 4)),
                    last_1_month_refresh = timezone.now(),
                    limit_3_month = str(round((-1) * float(tx_amount), 4)),
                    last_3_month_refresh = timezone.now(),
                    limit_12_month = str(round((-1) * float(tx_amount), 4)),
                    last_12_month_refresh = timezone.now(),
                    total_transfered_amount = str(round((-1) * float(tx_amount), 4))
                )
        except Exception as e:
            logger.info('TxLimitCumulOperations.on_refund_money ERROR')
            logger.info(e.args)
            send_email_celery_exception(e)
            

    def on_reset_limit(self, user=None):
        
        try:
            tx_limit_cumul_model = apps.get_model("bemosenderrr.TxLimitCumul")
            limit_1_month = last_1_month_refresh = limit_3_month = last_3_month_refresh = limit_12_month = last_12_month_refresh = None
            last_tx_limit_cumul = tx_limit_cumul_model.objects.filter(user=user).order_by("-created_at").first()
            if not last_tx_limit_cumul:
                return False
            else:
                today = timezone.now()
                operation_text = ""
                if today > last_tx_limit_cumul.last_1_month_refresh + relativedelta(months=1):
                    last_1_month_refresh = today
                    limit_1_month = 0
                    operation_text += " - " if len(operation_text) > 0 else "" + "monthly"
                else:
                    limit_1_month = last_tx_limit_cumul.limit_1_month
                    last_1_month_refresh = last_tx_limit_cumul.last_1_month_refresh
                if today > last_tx_limit_cumul.last_3_month_refresh + relativedelta(months=3):
                    last_3_month_refresh = today
                    limit_3_month = 0
                    operation_text += " - " if len(operation_text) > 0 else "" + "quarterly"
                else:
                    limit_3_month = last_tx_limit_cumul.limit_3_month
                    last_3_month_refresh = last_tx_limit_cumul.last_3_month_refresh
                if today > last_tx_limit_cumul.last_12_month_refresh + relativedelta(months=12):
                    last_12_month_refresh = today
                    limit_12_month = 0
                    operation_text += " - " if len(operation_text) > 0 else "" + "yearly"
                else:
                    limit_12_month = last_tx_limit_cumul.limit_12_month
                    last_12_month_refresh = last_tx_limit_cumul.last_12_month_refresh
                new_tx_limit_cumul = tx_limit_cumul_model.objects.create(
                    user=user,
                    amount= "0",
                    operation= 'reset limit: ' + operation_text,
                    global_transaction=None,
                    cumulative_debut = last_tx_limit_cumul.cumulative_debut,
                    limit_1_month = limit_1_month,
                    last_1_month_refresh = last_1_month_refresh,
                    limit_3_month = limit_3_month,
                    last_3_month_refresh = last_3_month_refresh,
                    limit_12_month = limit_12_month,
                    last_12_month_refresh = last_12_month_refresh,
                    total_transfered_amount = last_tx_limit_cumul.total_transfered_amount
                )
        except Exception as e:
            logger.info('TxLimitCumulOperations.on_reset_limit ERROR')
            logger.info(e.args)
            send_email_celery_exception(e)
