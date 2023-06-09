# Create your tasks here
import asyncio
import datetime
import json
import os
from django.conf import settings
from django.utils import timezone as django_tz
from celery import shared_task
import reversion
from bemosenderrr.logger import SendAdminAlerts, send_email_celery_exception
from bemosenderrr.models import UserTask
from bemosenderrr.models.base import FundingTransactionStatus, GlobalTransactionStatus, PartnerStatus, PartnerType, VerificationStatus
from bemosenderrr.models.partner.bank_verification import UserBankVerificationRequest
from bemosenderrr.models.partner.currconv import CurrConvOperation
from bemosenderrr.models.partner.partner import AppSettings, Country, ExchangeRateTier, PartnerExchangeRate, Partner, PartnerSettlementAccount
from bemosenderrr.models.partner.services.apaylo_service import ApayloService
from bemosenderrr.models.partner.services.dirham_service import DirhamService
from bemosenderrr.models.partner.services.flinks_service import FlinksService
from bemosenderrr.models.user import User
from bemosenderrr.operations import  SendInvoice
from bemosenderrr.utils.email_service import EmailService
import pprint
from django.apps import apps
from loguru import  logger
from bemosenderrr.utils.mutation_queries import GET_GLOBAL_TRANSACTION_QUERY, GET_PARAMETERS_QUERY, UPDATE_GLOBAL_TX_PARAMETERS_MUTATION
from bemosenderrr.utils.s3 import upload_to_s3
from django.conf import settings
from django.core.mail import send_mail
from bemosenderrr.utils.appsync import make_client
from gql import gql
import copy
from difflib import SequenceMatcher
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from bemosenderrr.utils.notifications import NotificationsHandler
from bemosenderrr.utils.sync_flinks_signup_data import sync_flinks_signup_data



@shared_task(bind=True)
def add(self, task_id=None, a=None, b=None):
    _task = UserTask.objects.get(task_id=task_id)
    _task.results = a + b
    _task.status = 'COMPLETED'
    _task.save()
    return a + b


@shared_task(bind=True)
def user_bank_verify(self, url=None, parameters=None):
    service = FlinksService(url=url)
    logger.info(parameters)
    return asyncio.run(service.get_user_details(parameters=parameters))


@shared_task
@reversion.create_revision()
def update_rates():
    try:
        active_partners = Partner.objects.filter(status=PartnerStatus.active, type=PartnerType.collect)
        exchange_rates = list()
        country_pairs = list()
        curr_conv_partner = Partner.objects.filter(type=PartnerType.conversion, status=PartnerStatus.active).first()
        credentials = curr_conv_partner.api_user.credentials
        curr_conv_api_config = curr_conv_partner.api_config
        curr_conv_api_config['credentials'] = credentials
        logger.info(credentials)
        for partner in active_partners:
            exchange_rate = PartnerExchangeRate.objects.get(partner=partner)
            country_pairs.append(f"{exchange_rate.country_origin.iso_code}_{exchange_rate.country_destination.iso_code}")
        logger.info(country_pairs)
        country_pairs = list(set(country_pairs))
        logger.info('Deleted duplicates')
        logger.info(country_pairs)
        for country_pair in country_pairs:
            logger.info(f'CURRENT COUNTRY PAIR {country_pair}')
            logger.info('-----------------------------------------------')
            country_origin = Country.objects.get(iso_code=country_pair.split('_')[0])
            country_destination = Country.objects.get(iso_code=country_pair.split('_')[1])
            currency_origin = Country.objects.get(iso_code=country_pair.split('_')[0]).default_currency.iso_code
            currency_destination = Country.objects.get(iso_code=country_pair.split('_')[1]).default_currency.iso_code
            rate_calcualtion = 0
            commission_calcualtion = 0
            ref_rate = None
            try:
                ref_rate = CurrConvOperation.get_rates.run(curr_conv_api_config, currency_origin, currency_destination)
            except Exception as e:
                logger.info("CURRCONV IS UNREACHABLE")
                send_email_celery_exception(exception=Exception(f"CURRCONV IS UNREACHABLE {e}"))
            print('this is the reference rate', ref_rate)
            exchange_rates = PartnerExchangeRate.objects.filter(country_origin=country_origin, country_destination=country_destination, 
                partner__status=PartnerStatus.active, partner__type=PartnerType.collect)
            for exchange_rate in exchange_rates:
                if not ref_rate:
                    logger.info('CURRCONV IS DOWN OR UNREACHABLE!')
                    ref_rate = exchange_rate.reference_rate
                exchange_rate.reference_rate = ref_rate
                logger.info('im here 1 ')
                settlement_currency = PartnerSettlementAccount.objects.filter(partner=exchange_rate.partner, active=True).first().currency
                PartnerExchangeRate.objects.filter(uuid=exchange_rate.uuid).update(settlement_currency=settlement_currency, reference_rate=ref_rate)
                logger.info('im here 1 ')
                settlement_to_destination_rate = exchange_rate.settlement_to_destination_rate
                if exchange_rate.partner.name == "Dirham":
                    print('dirham')
                    dirham_service = DirhamService()
                    api_config = exchange_rate.partner.api_config
                    api_config['credentials'] = exchange_rate.partner.api_user.credentials
                    exchange_rate.query_response = dirham_service.get_fx_rate(api_config=api_config)
                    logger.info(exchange_rate.query_response)
                    data = exchange_rate.query_response['response']['data']['response']['data']
                    for rate  in data :
                        if rate['account']['from'] == settlement_currency.iso_code:
                            PartnerExchangeRate.objects.filter(uuid=exchange_rate.uuid).update(settlement_to_destination_rate=rate['account']['rate'])
                            settlement_to_destination_rate = rate['account']['rate']
                            break
                sales_percentage = exchange_rate.sales_percentage
                commission_percentage = exchange_rate.commission_percentage
                rate_partner_calc = float(settlement_to_destination_rate) * float(exchange_rate.origin_to_settlement_rate)
                print(f'rate_partner_calc for {exchange_rate}', rate_partner_calc)
                if len(exchange_rates) == 1:
                    print('length == 1')
                    sales_percentage = 1
                rate_calcualtion += float(sales_percentage) * float(rate_partner_calc)
                print(f'rate_calculation for :{exchange_rate} ', rate_calcualtion)
                commission_calcualtion += float(sales_percentage) * float(commission_percentage)
                print(f'commission_calcualtion for {exchange_rate}', commission_calcualtion)
                
            cost_price = rate_calcualtion * (1 - commission_calcualtion)
            
            for exchange_rate in exchange_rates:
                print(f'this is the cost price for {exchange_rate}', cost_price)
                PartnerExchangeRate.objects.filter(uuid=exchange_rate.uuid).update(cost_price=cost_price)
                exchange_rate.cost_price = cost_price
                reversion.add_to_revision(exchange_rate)
                logger.info(f"SAVING ----------------------------------------------- {exchange_rate.partner}")
            exchange_rate_tiers = ExchangeRateTier.objects.filter(country_origin=country_origin, country_destination=country_destination)
            for exchange_rate_tier in exchange_rate_tiers:
                exchange_rate_tier.applicable_rate = float(cost_price) * (1 - float(exchange_rate_tier.profit_margin_percentage))
                print(f'applicable rate for {exchange_rate_tier}: ', exchange_rate_tier)
                exchange_rate_tier.save()
                logger.info(f'APPLICABLE RATE {exchange_rate_tier.applicable_rate}')
    except Exception as e:
        logger.info(f"Exception caught in update rates periodic task {e}")
        send_email_celery_exception(e)
        



@shared_task(bind=True)
@reversion.create_revision()
def get_interac_emails(self, email_type=None):
    email_service = EmailService()
    service = email_service.get_service()
    mail = service.users().messages().list(userId='me', labelIds=['INBOX']).execute()
    messages = mail['messages']
    email_data = list()
    for msg in messages:
        message = service.users().messages().get(userId='me', id=msg['id'], format="full").execute()
        pp = pprint
        data = email_service.filterDepositEmailData(message, email_type)
        if isinstance(data[0], dict):
            print(type(data[0]))
            email_data.append(data[0])
            prettified =  pp.pformat(data[0], indent=4)
            #logger.info(prettified)
    return email_data


def update_global_tx_parameters(global_tx_id=None, origin_amount=None, destination_amount=None, total=None, rate=None, collect_method_fee=None):
    try:
        params_global_tx = {
            "id": str(global_tx_id)
        }
        query_global_tx = GET_GLOBAL_TRANSACTION_QUERY
        client = make_client()
        response_gtx = client.execute(gql(query_global_tx), variable_values=json.dumps({'input': params_global_tx['id']}))
        parameters_id = response_gtx.get("getGlobalTransaction", None).get("parametersID", None)
        if parameters_id:
            params = {
                "id": str(parameters_id),
                "amount_origin": str(origin_amount),
                "amount_destination": str(destination_amount),
                "total": str(total),
                "applicable_rate": str(rate),
                "collect_method_fee": str(collect_method_fee),
            }
            query = UPDATE_GLOBAL_TX_PARAMETERS_MUTATION
            response = client.execute(gql(query), variable_values=json.dumps({'input': params}))
            logger.info(f"Response after updating global_tx parameters {response}")
            return True
        else:
            print("failed to get parametersID")
    except Exception as e:
        print("update global transaction parameters failed due to ", e)
        return False


def get_latest_rate_and_fee(origin_amount=None, country_origin=None, country_destination=None, collect_method=None):
    try:
        exchange_rate_tiers = ExchangeRateTier.objects.filter(
            country_origin__iso_code__iexact=country_origin,
            country_destination__iso_code__iexact=country_destination
        )
        if exchange_rate_tiers:
            bottom_amounts = list()
            for exch_rate in exchange_rate_tiers:
                bottom_amounts.append(float(exch_rate.bottom_amount))
            sorted_bottom_amounts = sorted(bottom_amounts)
            rate = None
            fee = None
            for item in sorted_bottom_amounts:
                if float(origin_amount) >= float(item):
                    exchange_rate = exchange_rate_tiers.filter(bottom_amount=int(item)).first()
                    rate = exch_rate.applicable_rate
                    for collect_method_fee in exchange_rate.collect_transaction_method_fees:
                        if str(collect_method).lower() == str(collect_method_fee.get('name', None)).lower():
                            fee = collect_method_fee.get("fee", None)
                            break
                    print("new fee", fee)
                    print("origin amount", origin_amount)
                    print("assumed new destination amount ", ( float(origin_amount)- float(fee)) *float(rate) )
                    break
            return [float(rate), float(fee)]
        else:
            return None
    except Exception as e:
        print("Get latest rate and fee failed due to ", e)
        return None
        


def find_similarity_match(client_name=None, client_email=None, user_query_set=None, match_threshold=0.76, amount=None, deposit_type=None):
    user_list = user_query_set
    found_client = client_name
    client_name = str(client_name).lower()
    matched_user = None
    users_full_names = list()
    for user in user_list:
        users_full_names.append({str(user.uuid): str(user.first_name).lower() + " " + str(user.last_name).lower()})
    matched_list = list()
    closest_match = None
    tmp_max_close_match = 0
    for user_full in users_full_names:
        tmp_ratio = SequenceMatcher(None, list(user_full.values())[0], client_name).ratio()
        if tmp_ratio >= match_threshold:
            matched_list.append({list(user_full.keys())[0]: tmp_ratio})
        if tmp_ratio < match_threshold and tmp_ratio >= tmp_max_close_match:
            closest_match = {list(user_full.keys())[0]: tmp_ratio}
    if matched_list:
        if len(matched_list) == 1:
            matched_user = user_list.filter(uuid=list(matched_list[0].keys())[0]).first()
            print('FOUND A MATCH UNIQUE')
            return {
                "match": matched_user,
                "ratio": list(matched_list[0].values())[0]
            }
        if len(matched_list) > 1:
            matched_user_email = None
            matched_user_ratio = None
            for item in  matched_list:
                current_user = user_list.filter(uuid=list(item.keys())[0]).first()
                if current_user.email == client_email:
                    matched_user_email = current_user
                    matched_user_ratio = list(item.values())[0]
                    break
            if not matched_user_email:
                deposit_type = "Auto-Deposit" if deposit_type == "auto" else "Manual-Deposit"
                duplicates = list()
                best_match = None
                highest_ratio = 0
                for possible_match in matched_list:
                    current_duplicate = user_list.filter(uuid=list(possible_match.keys())[0]).first()
                    if list(possible_match.values())[0] >= highest_ratio:
                        highest_ratio = list(possible_match.values())[0]
                        best_match = possible_match
                    duplicates.append(
                        {
                            "uuid": list(possible_match.keys())[0],
                            "fullname" : str(current_duplicate.first_name) + " " + str(current_duplicate.last_name),
                            "phone_number": str(current_duplicate.phone_number),
                            "status": "Active" if current_duplicate.is_active else "Blocked",
                            "ratio": list(possible_match.values())[0],
                            "email": current_duplicate.email
                        }
                    )
                best_match = user_query_set.filter(uuid=list(best_match.keys())[0]).first()
                data = {
                    "date_now":datetime.datetime.utcnow().isoformat(),
                    "env": settings.CONFIG.get('ENV', "Dev-V3"),
                    "senderr_fullname": found_client,
                    "amount": format(float(amount), ".2f"),
                    "deposit_type" : deposit_type,
                    "user_id": str(best_match.uuid),
                    "user_fullname": str(best_match.first_name) + " " + str(best_match.last_name),
                    "user_phone_number": best_match.phone_number,
                    "best_match_email": best_match.email,
                    "best_match_username": best_match.username,
                    "user_email": client_email,
                    "length_duplicates": len(duplicates),
                    "duplicates": duplicates
                }
                html_message = render_to_string(os.path.join(os.getcwd(), 'bemosenderrr','templates', 'deposits', 'failed_deposits.html'), data)
                print(html_message)
                to = 'bemosenderrr.test@gmail.com'
                admin_emails = NotificationsHandler().get_staff_users_emails()
                if admin_emails:
                    if to in admin_emails:
                        pass
                    else:
                        admin_emails.append(to)
                else:
                    admin_emails = to
                email = EmailMultiAlternatives(
                    "Process Error",
                    "Process Error",
                    str(settings.SERVER_EMAIL),
                    admin_emails,
                )
                
                email.attach_alternative(html_message, 'text/html')
                email.send(fail_silently=True)
                duplicate_matches = {}
                duplicate_matches['duplicates'] = duplicates
                duplicate_matches['data'] = data
                duplicate_matches['highest_ratio'] = highest_ratio
                return duplicate_matches
            else:
                return {
                    "match": matched_user_email,
                    "ratio": matched_user_ratio
                }
    else:
        closest_user_match = user_list.filter(uuid=list(closest_match.keys())[0]).first()
        return {
            "closest_match": closest_user_match,
            "ratio": list(closest_match.values())[0]
        }


@shared_task(bind=True)
@reversion.create_revision()
def check_deposits(self, start_date=None, end_date=None):
    import datetime
    report = ''
    partner = None
    logger.info("starting check deposits")
    try:
        if start_date or end_date:
            logger.info("MANUALLY TRIGGERED CHECK DEPOSITS")
        apaylo = Partner.objects.filter(name='Apaylo').first()
        gmail = Partner.objects.filter(name='Gmail').first()
        check_deposits_end_time = datetime.datetime.strftime(datetime.datetime.utcnow(), "%Y-%m-%d %H:%M:%S.%f")
        iso_tmp_start_date = None
        iso_tmp_end_date = None
        if start_date:
            iso_tmp_start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).isoformat()
        if end_date:
            iso_tmp_end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).isoformat()
        if apaylo.status == PartnerStatus.active:
            partner = apaylo
        if gmail.status == PartnerStatus.active:
            partner = gmail
        if start_date and apaylo.status == PartnerStatus.active:
            iso_tmp_start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).isoformat()
            start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc) - datetime.timedelta(days=1)
            start_date = start_date.strftime("%Y-%m-%d")
        if apaylo.status == PartnerStatus.active and not start_date:
            partner = apaylo
            start_date = apaylo.api_config.get("depositLastUpdate", None)
            iso_tmp_start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=datetime.timezone.utc).isoformat()
            start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=datetime.timezone.utc) - datetime.timedelta(days=1)
            start_date = start_date.strftime("%Y-%m-%d %H:%M:%S.%f")
        elif gmail.status == PartnerStatus.active and not start_date:
            partner = gmail
            start_date = gmail.api_config.get("depositLastUpdate", None)
            iso_tmp_start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=datetime.timezone.utc).isoformat()
            if start_date:
                start_date = str(datetime.datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=datetime.timezone.utc).timestamp()).split(".")[0]
        if not start_date and apaylo.status == PartnerStatus.active:
            start_date = datetime.datetime.strftime(datetime.datetime.utcnow() - datetime.timedelta(minutes=16), "%Y-%m-%d %H:%M:%S.%f")
        if not end_date and apaylo.status == PartnerStatus.active:
            end_date = datetime.datetime.strftime(datetime.datetime.utcnow(), "%Y-%m-%d %H:%M:%S.%f")
            iso_tmp_end_date = datetime.datetime.utcnow().isoformat()
        if not start_date and gmail.status == PartnerStatus.active:
            start_date = str(round(datetime.datetime.utcnow().timestamp() - 1000)).split(".")[0]
        if not end_date and gmail.status == PartnerStatus.active:
            end_date = str(round(datetime.datetime.utcnow().timestamp())).split(".")[0]
            iso_tmp_end_date = datetime.datetime.utcnow().isoformat()
        iso_start_date = None
        iso_end_date = None
        logger.info(iso_tmp_start_date)
        logger.info(start_date)
        if start_date:
            iso_start_date = iso_tmp_start_date
        else:
            tmp_start_date = partner.api_config.get("depositLastUpdate", None)
            iso_start_date = datetime.datetime.strptime(tmp_start_date, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=datetime.timezone.utc).isoformat()
        if end_date:
            iso_end_date = iso_tmp_end_date
        else:
            iso_end_date = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).isoformat()
        logger.info(f"ISO START DATE {iso_start_date}")
        logger.info(f"ISO END DATE {iso_end_date}")
        logger.info(f"START DATE {start_date}")
        logger.info(f"END DATE {end_date}")
        report = report + '\n' + 'Check Deposits Periodic Task Report' + '\n' + '---------------------------------'
        report = report + '\n' + 'Start Date :' + str(iso_start_date)
        report = report + '\n' + 'End Date : ' + str(iso_end_date)
        if partner and partner.name == 'Apaylo' and partner.status == PartnerStatus.active:
            report = report + '\n' + 'Processor : Apaylo' + '\n'
            api_config = copy.deepcopy(partner.api_config)
            credentials = partner.api_user.credentials
            api_config['credentials'] = credentials
            search_transfer = ApayloService().search_incoming_transfers(api_config, start_date, end_date)
            response = list()
            report = report + 'APAYLO : SEARCH INCOMING TRANSFER :' + '\n'
            report = report + 'REQUEST' + "\n" + json.dumps(search_transfer[1], indent=4) + '\n'
            report = report + 'RESPONSE' + "\n" + json.dumps(search_transfer[0], indent=4) + '\n'
            if search_transfer and search_transfer[0] and search_transfer[0].get('StatusCode', None) == 200 and search_transfer[0].get('IsError', True) == False:
                
                report = report + f"FOUND {len(search_transfer[0].get('Result', None))} TRANSFERS " + '\n'
                i = 0
                items = search_transfer[0].get('Result', None)
                for item in items:
                    i = i + 1
                    report = report + f"TRANSFER #{i}" + '\n'
                    logger.info(item)
                    global_transaction = apps.get_model('bemosenderrr.GlobalTransaction').objects.filter(status=GlobalTransactionStatus.fundtransaction_in_progress, funding_transaction__reference_code=item['ReferenceNumber']).first()
                    logger.info(f"{global_transaction}")
                    if global_transaction:
                        funding_instance = global_transaction.funding_transaction
                        search_transfer_result = copy.deepcopy({})
                        search_transfer_result = funding_instance.partner_response
                        if not search_transfer_result:
                            search_transfer_result = copy.deepcopy({})
                        search_transfer_result['searchTransfer'] = "Available in the check deposits S3 report"
                        funding_instance.partner_response = search_transfer_result
                        client_name = global_transaction.user_snapshot['first_name'] + " " + global_transaction.user_snapshot['last_name']
                        report = report + "FOUND 1 MATCH : " + client_name + '\n'
                        print('this is the item ', item['senderrName'])
                        report = report + "Name matches " + client_name + "\n"
                        # Client matches and amount matches !
                        if global_transaction and client_name and item and float(item['Amount']) == float(
                                global_transaction.parameters['total']):
                            logger.info("THE AMOUNT MATCHES THE ORIGIN AMOUNT")
                            report = report + "Amount matches " + str(item['Amount']) + "\n"
                            funding_instance.status = FundingTransactionStatus.success
                            funding_instance.save()
                        # Client matches and amount doesn't match !

                        ## Amount received > Amount in global transaction
                        elif global_transaction and client_name and item and float(item['Amount']) > float(global_transaction.parameters['total']):
                            logger.info("THE AMOUNT IS BIGGER THAN THE ORIGIN AMOUNT")
                            old_total_amount = global_transaction.parameters['total']
                            new_total_amount = str(item['Amount'])
                            global_transaction.parameters['total'] = new_total_amount
                            rate_fee = get_latest_rate_and_fee(
                                origin_amount=item['Amount'],
                                country_origin=global_transaction.parameters['origin_country'],
                                country_destination=global_transaction.parameters['destination_country'],
                                collect_method=global_transaction.collect_method
                                )
                            fee = global_transaction.parameters['fee']
                            if rate_fee and rate_fee[0] and rate_fee[1]:
                                rate = rate_fee[0]
                                fee = rate_fee[1]
                                global_transaction.parameters['fee'] = str(fee)
                            else:
                                rate = float(global_transaction.parameters['amount_destination']) / float(global_transaction.parameters['amount_origin'])
                                global_transaction.parameters['fee'] = str(fee)
                            new_origin_amount = float(item['Amount']) - float(global_transaction.parameters['fee'])
                            global_transaction.parameters['amount_origin'] = str(new_origin_amount)
                            new_amount_destination = str(round(float(new_origin_amount) * rate, 4))
                            global_transaction.parameters['amount_destination'] = new_amount_destination
                            global_transaction.save()
                            update_global_tx_parameters(
                                global_tx_id=str(global_transaction.uuid),
                                origin_amount=new_origin_amount,
                                destination_amount=new_amount_destination,
                                total=new_total_amount,
                                rate=rate,
                                collect_method_fee=fee
                            )
                            funding_instance.status = FundingTransactionStatus.success
                            funding_instance.save()
                            report = report + "AMMOUNT DOESNT MATCH INDICTATED AMMOUNT " + "\n" + f"INDICATED AMMOUNT : {str(float(old_total_amount))}"
                            report = report + "\n" + f"FOUND AMMOUNT : {float(item['Amount'])} " + "\n"
                            report = report + "------------" + "\n"
                        ## Amount received < Amount in global transaction
                        elif global_transaction and client_name and item and float(item['Amount']) < float(global_transaction.parameters['total']):
                            logger.info("THE AMOUNT IS SMALLER THAN THE ORIGIN AMOUNT")
                            app_settings = AppSettings.objects.first()
                            min_transaction_amount = None
                            if app_settings:
                                min_transaction_amount = float(app_settings.config.get('minTransactionValue', None).get(global_transaction.parameters["origin_country"]))
                            if min_transaction_amount > float(item['Amount']):
                                logger.info("THE AMOUNT IS SMALLER THAN THE ORIGIN AMOUNT AND SMALLER THAN THE MINIMUM AMOUNT")
                                report = report + "AMMOUNT DOESNT MATCH INDICTATED AMMOUNT AND SMALLER THAN THE MINIMUM TRANSACTION VALUE" + str(item['Amount']) + "\n"
                                from pytz import timezone
                                fmt = '%Y-%m-%d %H:%M:%S %Z%z'
                                # define eastern timezone
                                cet = timezone('CET')
                                cet_datetime = datetime.datetime.strftime(datetime.datetime.now(cet), fmt)
                                env = str(settings.CONFIG['env'])
                                email_data = f"""
                                Report Date: {cet_datetime}
                                Environment: {env}
                                Partner: {partner.display_name}

                                SEND TO: {global_transaction.receiver_snapshot['first_name']} {global_transaction.receiver_snapshot['last_name']} {global_transaction.receiver_snapshot['phone_number']}
                                BY: {global_transaction.user_snapshot['first_name']} {global_transaction.user_snapshot['last_name']} {global_transaction.user_snapshot['phone_number']}
                                Amount: {format(float(global_transaction.parameters.get('amount_origin', 0)), ".2f")} {global_transaction.parameters['currency_origin']} - {format(float(global_transaction.parameters.get('amount_destination', 0)), ".2f")} {global_transaction.parameters['currency_destination']}

                                Auto-deposit interrupted
                                senderr tried to send an Interac transfer smaller than the minimum transaction amount ({min_transaction_amount} {global_transaction.parameters['currency_origin']}).
                                """
                                print(email_data)
                                recipients = apps.get_model('bemosenderrr.AdminAlerts').objects.filter(can_receive_celery_exceptions=True)
                                recipients_emails = []
                                if recipients:
                                    for recipient in recipients:
                                        recipients_emails.append(recipient.user.email)
                                else:
                                    recipients_emails = [settings.ADMINS[0][0][1]]
                                result = send_mail(
                                    subject=f"<{env}>: Interac transfer invalid received amount ",
                                    message=email_data,
                                    from_email=str(settings.SERVER_EMAIL),
                                    recipient_list=recipients_emails,
                                    fail_silently=True
                                )
                                print(result)
                            else:
                                logger.info("THE AMOUNT IS SMALLER THAN THE ORIGIN AMOUNT AND BIGGER THAN THE MINIMUM AMOUNT")
                                old_total_amount = global_transaction.parameters['total']
                                new_total_amount = str(item['Amount'])
                                global_transaction.parameters['total'] = new_total_amount
                                rate_fee = get_latest_rate_and_fee(
                                    origin_amount=item['Amount'],
                                    country_origin=global_transaction.parameters['origin_country'],
                                    country_destination=global_transaction.parameters['destination_country'],
                                    collect_method=global_transaction.collect_method
                                    )
                                fee = global_transaction.parameters['fee']
                                if rate_fee and rate_fee[0] and rate_fee[1]:
                                    rate = rate_fee[0]
                                    fee = rate_fee[1]
                                    global_transaction.parameters['fee'] = str(fee)
                                else:
                                    rate = float(global_transaction.parameters['amount_destination']) / float(global_transaction.parameters['amount_origin'])
                                    global_transaction.parameters['fee'] = str(fee)
                                new_origin_amount = float(item['Amount']) - float(global_transaction.parameters['fee'])
                                global_transaction.parameters['amount_origin'] = str(new_origin_amount)
                                new_amount_destination = str(round(float(new_origin_amount) * rate, 4))
                                global_transaction.parameters['amount_destination'] = new_amount_destination
                                global_transaction.save()
                                update_global_tx_parameters(
                                    global_tx_id=str(global_transaction.uuid),
                                    origin_amount=new_origin_amount,
                                    destination_amount=new_amount_destination,
                                    total=new_total_amount,
                                    rate=rate,
                                    collect_method_fee=fee
                                )
                                funding_instance.status = FundingTransactionStatus.success
                                funding_instance.save()
                                report = report + "AMMOUNT DOESNT MATCH INDICTATED AMMOUNT " + "\n" + f"INDICATED AMMOUNT : {str(float(old_total_amount))}"
                                report = report + "\n" + f"FOUND AMMOUNT : {float(item['Amount'])} " + "\n"
                                report = report + "------------" + "\n"
                    else:
                        report = report + "NO MATCHES FOR THIS TRANSFER" + '\n'
                partner.api_config['depositLastUpdate'] = check_deposits_end_time
                partner.save()
                apaylo.api_config['depositLastUpdate'] = check_deposits_end_time
                apaylo.save()
            elif not "Exception" in str(search_transfer[0]):
                report = report + '\n' + 'No messages found !'
                partner.api_config['depositLastUpdate'] = check_deposits_end_time
                partner.save()
                gmail.api_config['depositLastUpdate'] = check_deposits_end_time
                gmail.save()
            else:
                globalt_tx = None
                if global_transaction:
                    globalt_tx = global_transaction
                admin_alerts_service = SendAdminAlerts()
                admin_alerts_service.send_admin_alert_partner_failure(
                    global_tx=globalt_tx,
                    operation="funding_check_deposits_apaylo",
                    partner=partner.name,
                    params={
                        "failure_type": search_transfer[0]
                    }
                )
                report = report + f"EXCEPTION OCCURED {str(search_transfer[0])}" + item['Amount'] + "\n"
        elif partner and partner.name == 'Gmail' and partner.status == PartnerStatus.active:
            logger.info(f"START DATE {start_date}")
            logger.info(f"END DATE {end_date}")
            report = report + '\n' + 'Processor : GMAIL' + '\n'
            email_service = EmailService()
            service = email_service.get_service()
            logger
            mail = service.users().messages().list(userId='me', labelIds=['INBOX'], q=f'after: {start_date} before: {end_date}').execute()
            logger.info(mail)
            messages = mail.get('messages')
            if messages:
                report = report + f"FOUND {len(messages)} EMAILS " + '\n'
                i = 0
                user_query_set = User.objects.all()
                for msg in messages:
                    
                    message = service.users().messages().get(userId='me', id=msg['id'], format="full").execute()
                    pp = pprint
                    data = email_service.filterDepositEmailData(message, 'auto')
                    logger.info(data)
                    if isinstance(data[0], dict):
                        item = data[0]
                        ref_code = item.get('refCode', None)
                        client_email = item.get('clientEmail', None)
                        client_name = item.get("client", None)
                        match_threshold = gmail.api_config.get("match_threshold", None)
                        matched_user = find_similarity_match(
                            client_name=client_name,
                            client_email=client_email, 
                            user_query_set=user_query_set, 
                            match_threshold=match_threshold, 
                            amount=item.get('amount', None),
                            deposit_type=item.get('depositType', None)
                            )
                        logger.info(f"THE MATCHED USER {matched_user}")
                        matched_user = find_similarity_match(
                            client_name=client_name,
                            client_email=client_email, 
                            user_query_set=user_query_set, 
                            match_threshold=match_threshold, 
                            amount=item.get('amount', None),
                            deposit_type=item.get('depositType', None)
                            )
                        logger.info(f"THE MATCHED USER {matched_user}")
                        matching_report = copy.deepcopy({
                                    "emailSubject":item.get('email', None).get('subject', None),
                                    "emailDate": item.get('utctimestamp', None),
                                    "client": item.get("client", None),
                                    "clientEmail": item.get('clientEmail', None),
                                    "refCode": item.get('refCode', None),
                                    "amount": item.get("amount", None),
                                    "matchRatio": None,
                                    "matchedUserID": None,
                                    "multiple": None,
                                    "duplicates": None
                                })
                        logger.info(f"matched user data {matched_user}")
                        logger.info(type(matched_user))
                        if matched_user and matched_user.get("match", None):
                            logger.info("Got a match without duplicates")
                            user = matched_user.get('match')
                            matching_report['matchRatio'] = matched_user.get('ratio')
                            matching_report['matchedUserID'] = f"{str(user.first_name)} {str(user.last_name)} {client_email} ({str(user.username)})"
                        elif matched_user and matched_user.get('duplicates', None):
                            logger.info("Got a match with duplicates")
                            matching_report['matchRatio'] = matched_user['highest_ratio']
                            matching_report['matchedUserID'] = f"{matched_user['data']['user_fullname']} {matched_user['data']['best_match_email']} ({matched_user['data']['best_match_username']})"
                            matching_report['duplicates'] = [duplicate.get('uuid', None) for duplicate in matched_user['duplicates']]
                            matching_report['multiple'] = [multiple.get('uuid', None) for multiple in matched_user['duplicates']]
                            user = None
                        elif matched_user and matched_user.get('closest_match', None):
                            logger.info("Got no matches ")
                            matching_report['matchRatio'] = matched_user.get('ratio')
                            matching_report['matchedUserID'] = f"{str(matched_user['closest_match'].first_name)} {str(matched_user['closest_match'].last_name)} {matched_user['closest_match'].email} ({str(matched_user['closest_match'].username)})"
                            user = None
                        i += 1
                        report += "\n" + f"EMAIL N° {i}"
                        report += "\n" + json.dumps(matching_report, indent=4)
                        if user and ref_code and item.get('depositType', None) == 'auto':
                            logger.info('Found a match')
                            report = report + f"TRANSFER #{i}" + '\n'
                            report  = report + f"EMAIL DATA {item}" + "\n" + "-------------------------------------------" + "\n"
                            
                            global_transactions = apps.get_model('bemosenderrr.GlobalTransaction').objects.filter(user=user, 
                                    status=GlobalTransactionStatus.fundtransaction_in_progress, funding_transaction__reference_code=None).order_by('-created_at')
                            last_global_transaction = None
                            item = data[0]
                            logger.info(f"GLOBAL TRANSACTIONS {global_transactions}")
                            is_lesser_than_minimum_amount = False
                            if global_transactions:
                                report += "FOUND A MATCH " + "\n" + json.dumps(matching_report, indent=4)
                                last_global_transaction = global_transactions[0]
                                funding_instance = last_global_transaction.funding_transaction
                                if funding_instance:
                                    funding_instance.reference_code = ref_code
                                logger.info(f"THE GLOBAL TRANSACTION {last_global_transaction}")
                                # Client matches and amount matches !
                                if last_global_transaction and funding_instance and item and float(item['amount']) == float(last_global_transaction.parameters['total']):
                                    logger.info("THE AMOUNT MATCHES THE ORIGIN AMOUNT")
                                    report = report + "Amount matches " + item['amount'] + "\n"
                                    funding_instance.status = FundingTransactionStatus.success
                                    funding_instance.save()
                                # Client matches and amount doesn't match !

                                ## Amount received > Amount in global transaction
                                elif last_global_transaction and funding_instance and item and float(item['amount']) > float(last_global_transaction.parameters['total']):
                                    logger.info("THE AMOUNT IS BIGGER THAN THE ORIGIN AMOUNT")
                                    old_total_amount = last_global_transaction.parameters['total']
                                    new_total_amount = str(item['amount'])
                                    last_global_transaction.parameters['total'] = new_total_amount
                                    rate_fee = get_latest_rate_and_fee(
                                        origin_amount=item['amount'],
                                        country_origin=last_global_transaction.parameters['origin_country'],
                                        country_destination=last_global_transaction.parameters['destination_country'],
                                        collect_method=last_global_transaction.collect_method
                                        )
                                    fee = last_global_transaction.parameters['fee']
                                    if rate_fee and rate_fee[0] and rate_fee[1]:
                                        rate = rate_fee[0]
                                        fee = rate_fee[1]
                                        last_global_transaction.parameters['fee'] = str(fee)
                                    else:
                                        rate = float(last_global_transaction.parameters['amount_destination']) / float(last_global_transaction.parameters['amount_origin'])
                                        last_global_transaction.parameters['fee'] = str(fee)
                                    new_origin_amount = float(item['amount']) - float(last_global_transaction.parameters['fee'])
                                    last_global_transaction.parameters['amount_origin'] = str(new_origin_amount)
                                    new_amount_destination = str(round(float(new_origin_amount) * rate, 4))
                                    last_global_transaction.parameters['amount_destination'] = new_amount_destination
                                    last_global_transaction.save()
                                    update_global_tx_parameters(
                                        global_tx_id=str(last_global_transaction.uuid),
                                        origin_amount=new_origin_amount,
                                        destination_amount=new_amount_destination,
                                        total=new_total_amount,
                                        rate=rate,
                                        collect_method_fee=fee
                                    )
                                    funding_instance.status = FundingTransactionStatus.success
                                    funding_instance.save()
                                    report = report + "AMMOUNT DOESNT MATCH INDICTATED AMMOUNT " + "\n" + f"INDICATED AMMOUNT : {float(old_total_amount)}"
                                    report = report + "\n" + f"FOUND AMMOUNT : {float(item['amount'])} " + "\n"
                                    report = report + "------------" + "\n"
                                ## Amount received < Amount in global transaction
                                elif last_global_transaction and funding_instance and item and float(item['amount']) < float(last_global_transaction.parameters['total']):
                                    logger.info("THE AMOUNT IS SMALLER THAN THE ORIGIN AMOUNT")
                                    app_settings = AppSettings.objects.first()
                                    min_transaction_amount = None
                                    if app_settings:
                                        min_transaction_amount = float(app_settings.config.get('minTransactionValue', None).get(last_global_transaction.parameters["origin_country"]))
                                    if (float(item['amount']) - min_transaction_amount - float(last_global_transaction.parameters['fee'])) < 0:
                                        logger.info("THE AMOUNT IS SMALLER THAN THE ORIGIN AMOUNT AND SMALLER THAN THE MINIMUM AMOUNT")
                                        is_lesser_than_minimum_amount = True
                                        from pytz import timezone
                                        fmt = '%Y-%m-%d %H:%M:%S %Z%z'
                                        # define eastern timezone
                                        cet = timezone('CET')
                                        cet_datetime = datetime.datetime.strftime(datetime.datetime.now(cet), fmt)
                                        env = str(settings.CONFIG['env'])
                                        email_data = f"""
                                        Report Date: {cet_datetime}
                                        Environment: {env}
                                        Partner: {partner.display_name}

                                        SEND TO: {last_global_transaction.receiver_snapshot['first_name']} {last_global_transaction.receiver_snapshot['last_name']} {last_global_transaction.receiver_snapshot['phone_number']}
                                        BY: {last_global_transaction.user_snapshot['first_name']} {last_global_transaction.user_snapshot['last_name']} {last_global_transaction.user_snapshot['phone_number']}
                                        Amount: {format(float(last_global_transaction.parameters.get('amount_origin', 0)), ".2f")} {last_global_transaction.parameters['currency_origin']} - {format(float(last_global_transaction.parameters.get('amount_destination', 0)), ".2f")} {last_global_transaction.parameters['currency_destination']}

                                        Auto-deposit interrupted
                                        senderr tried to send an Interac transfer smaller than the minimum transaction amount ({min_transaction_amount} {last_global_transaction.parameters['currency_origin']}).
                                        """
                                        print(email_data)
                                        recipients = apps.get_model('bemosenderrr.AdminAlerts').objects.filter(can_receive_celery_exceptions=True)
                                        recipients_emails = []
                                        if recipients:
                                            for recipient in recipients:
                                                recipients_emails.append(recipient.user.email)
                                        else:
                                            recipients_emails = [settings.ADMINS[0][0][1]]
                                        result = send_mail(
                                            subject=f"<{env}>: Interac transfer invalid received amount ",
                                            message=email_data,
                                            from_email=str(settings.SERVER_EMAIL),
                                            recipient_list=recipients_emails,
                                            fail_silently=True
                                        )
                                        print(result)
                                    else:
                                        logger.info("THE AMOUNT IS SMALLER THAN THE ORIGIN AMOUNT AND BIGGER THAN THE MINIMUM AMOUNT")
                                        old_total_amount = last_global_transaction.parameters['total']
                                        new_total_amount = str(item['amount'])
                                        last_global_transaction.parameters['total'] = new_total_amount
                                        rate_fee = get_latest_rate_and_fee(
                                            origin_amount=item['amount'],
                                            country_origin=last_global_transaction.parameters['origin_country'],
                                            country_destination=last_global_transaction.parameters['destination_country'],
                                            collect_method=last_global_transaction.collect_method
                                            )
                                        fee = last_global_transaction.parameters['fee']
                                        if rate_fee and rate_fee[0] and rate_fee[1]:
                                            rate = rate_fee[0]
                                            fee = rate_fee[1]
                                            last_global_transaction.parameters['fee'] = str(fee)
                                        else:
                                            rate = float(last_global_transaction.parameters['amount_destination']) / float(last_global_transaction.parameters['amount_origin'])
                                            last_global_transaction.parameters['fee'] = str(fee)
                                        new_origin_amount = float(item['amount']) - float(last_global_transaction.parameters['fee'])
                                        last_global_transaction.parameters['amount_origin'] = str(new_origin_amount)
                                        new_amount_destination = str(round(float(new_origin_amount) * rate, 4))
                                        last_global_transaction.parameters['amount_destination'] = new_amount_destination
                                        last_global_transaction.save()
                                        update_global_tx_parameters(
                                            global_tx_id=str(last_global_transaction.uuid),
                                            origin_amount=new_origin_amount,
                                            destination_amount=new_amount_destination,
                                            total=new_total_amount,
                                            rate=rate,
                                            collect_method_fee=fee
                                        )
                                        funding_instance.status = FundingTransactionStatus.success
                                        funding_instance.save()
                                        report = report + "AMMOUNT DOESNT MATCH INDICTATED AMMOUNT " + "\n" + f"INDICATED AMMOUNT : {float(old_total_amount)}"
                                        report = report + "\n" + f"FOUND AMMOUNT : {float(item['amount'])} " + "\n"
                                        report = report + "------------" + "\n"
                            else:
                                report = report + "NO MATCHES FOR THIS TRANSFER" + '\n'
                        report += "\n----------------------------------\n"
                
            else:
                report = report + '\n' + 'No messages found !'
            partner.api_config['depositLastUpdate'] = check_deposits_end_time
            partner.save()
            apaylo.api_config['depositLastUpdate'] = check_deposits_end_time
            apaylo.save()
        else:
            report = report + '\n' + 'No active partners found !!!'
        if partner:
            report = report + '\n' + 'Last check deposits update : ' + str(partner.api_config['depositLastUpdate'])
            report = report + '\n' + 'End of Check Deposits Job.' + "\n" + "---------------------------------------------------"
            time_now = datetime.datetime.strftime(django_tz.now(), "%Y%m%d%H%M%S")
            env = ""
            logger.info(report)
            if settings.CONFIG and settings.CONFIG.get('env', None) in ['Dev-V3', None]:
                env = "dev"
            else:
                env = "prod"
            upload_to_s3(body=report, bucket='v3-reporting', key=f"{env}/transactions/funding/{time_now}-CheckDeposits.txt", content_type='text/plain')
            return report
    except Exception as e:
        import traceback
        traceback.print_exc()
        report = report + 'Check deposits failed due to :' + str(e.args)
        report = report + '\n' + 'End of Check Deposits Job.' + "\n" + "---------------------------------------------------"
        time_now = datetime.datetime.strftime(django_tz.now(), "%Y%m%d%H%M%S")
        env = ""
        if settings.CONFIG and settings.CONFIG.get('env', None) in ['Dev-V3', None]:
            env = "dev"
        else:
            env = "prod"
        admin_alerts_service = SendAdminAlerts()
        admin_alerts_service.send_admin_alert_partner_failure(
            operation="funding_check_deposits_error",
            partner=partner.name,
            params={
                "failure_type": e,
            }
        )
        send_email_celery_exception(exception=e)
        upload_to_s3(body=report, bucket='v3-reporting', key=f"{env}/transactions/funding/{time_now}-CheckDeposits.txt", content_type='text/plain')
        return report


@shared_task(bind=True)
@reversion.create_revision()
def authorize_deposits(self, start_date=None, end_date=None):
    
    report = ''
    report_success = ""
    success_count = 0
    failed_count = 0
    count_emails = 0
    retrieved_emails = ""
    report_failed = ""
    time_now = datetime.datetime.strftime(django_tz.now(), "%c")
    authorize_deposits_end_time = datetime.datetime.strftime(datetime.datetime.utcnow(), "%Y-%m-%d %H:%M:%S.%f")
    try:
        apaylo = Partner.objects.filter(name='Apaylo').first()
        if start_date or end_date:
            logger.info("MANUALLY TRIGGERED AUTHORIZE DEPOSITS")
        apaylo = Partner.objects.filter(name='Apaylo').first()
        logger.info('PASSED HERE')
        start_date_gmail = None
        end_date_gmail = None
        if start_date:
            try:
                start_date_gmail = str(datetime.datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S.%f").timestamp()).split(".")[0]
            except Exception as e:
                start_date_gmail = str(datetime.datetime.strptime(start_date, "%Y-%m-%d").timestamp()).split(".")[0]
        if end_date:
            try:
                end_date_gmail = datetime.datetime.strftime(end_date, "%Y-%m-%d %H:%M:%S.%f")
            except Exception as e:
                end_date_gmail = str(datetime.datetime.strptime(end_date, "%Y-%m-%d").timestamp()).split(".")[0]
        if apaylo.status == PartnerStatus.active and not start_date:
            partner = apaylo
            start_date = apaylo.api_config.get("authorizeLastUpdate", None)
            logger.info(f"START DATE APAYLO {start_date}")
            if start_date:
                start_date_gmail = str(datetime.datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=datetime.timezone.utc).timestamp()).split(".")[0]
                end_date_gmail = str(datetime.datetime.utcnow().timestamp()).split(".")[0]
        if not start_date and apaylo.status == PartnerStatus.active:
            start_date = datetime.datetime.strftime(datetime.datetime.utcnow() - datetime.timedelta(minutes=16), "%Y-%m-%d %H:%M:%S.%f")
        if not end_date and apaylo.status == PartnerStatus.active:
            end_date = datetime.datetime.strftime(datetime.datetime.utcnow(), "%Y-%m-%d %H:%M:%S.%f")
        iso_start_date = None
        iso_end_date = None
        if start_date:
            if "." in start_date:
                iso_start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=datetime.timezone.utc).isoformat()
            else:
                iso_start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).isoformat()
        else:
            tmp_start_date = apaylo.api_config.get("authorizeLastUpdate", None)
            iso_start_date = datetime.datetime.strptime(tmp_start_date, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=datetime.timezone.utc).isoformat()
        if end_date:
            if "." in end_date:
                iso_end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=datetime.timezone.utc).isoformat()
            else:
                iso_end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).isoformat()
        else:
            iso_end_date = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).isoformat()
        logger.info(f"ISO START DATE {iso_start_date}")
        logger.info(f"ISO END DATE {iso_end_date}")
        logger.info(f"START DATE {start_date}")
        logger.info(f"END DATE {end_date}")
        logger.info(f"START DATE GMAIL {start_date_gmail}")
        logger.info(f"END DATE GMAIL {end_date_gmail}")
        report = report + '\n' + 'Start Date :' + str(iso_start_date)
        report = report + '\n' + 'End Date : ' + str(iso_end_date)
        if apaylo.status == PartnerStatus.active:
            appsettings = AppSettings.objects.first()
            security_answer = appsettings.config.get('interacDeposit', None).get("secret", None).get('answer', None)
            report = report + '\n' + 'Starting Authorize Deposits Periodic Task ' + '\n' + '--------------------------------------' + "\n" + "RETRIVED EMAILS" + "\n"
            email_service = EmailService()
            service = email_service.get_service()
            mail = service.users().messages().list(userId='me', labelIds=['INBOX'], q=f'after: {start_date_gmail} before: {end_date_gmail}').execute()
            messages = mail.get('messages')
            api_config = copy.deepcopy(apaylo.api_config)
            credentials = apaylo.api_user.credentials
            api_config['credentials'] = credentials
            i = 0
            if messages:
                count_emails = len(messages)
                logger.info(len(messages))
                user_query_set = User.objects.all()
                for email in messages:
                    try:
                        result_email = ""
                        temp_report = ''
                        tmp_failed_count = 0
                        tmp_success_count = 0
                        message = service.users().messages().get(userId='me', id=email['id'], format="full").execute()
                        data = email_service.filterDepositEmailData(message)
                        i = i + 1
                        retrieved_emails += f"EMAIL N° {i} \n"
                        if isinstance(data[0], dict):
                            item = data[0]
                            logger.info(f"this is the client {item.get('client', None)}")
                            ref_code = item.get('refCode', None)
                            logger.info(ref_code)
                            logger.info(f"DEPOSIT TYPE {item.get('depositType', None)}")
                            logger.info(f"AMOUNT {item.get('amount', None)}")
                            client_email = item.get('clientEmail', None)
                            client_name = item.get("client", None)
                            match_threshold = api_config.get("match_threshold", None)
                            matched_user = find_similarity_match(
                                client_name=client_name,
                                client_email=client_email, 
                                user_query_set=user_query_set, 
                                match_threshold=match_threshold, 
                                amount=item.get('amount', None),
                                deposit_type=item.get('depositType', None)
                                )
                            logger.info(f"THE MATCHED USER {matched_user}")
                            matching_report = copy.deepcopy({
                                        "emailSubject":item.get('email', None).get('subject', None),
                                        "emailDate": item.get('utctimestamp', None),
                                        "client": item.get("client", None),
                                        "clientEmail": item.get('clientEmail', None),
                                        "refCode": item.get('refCode', None),
                                        "amount": format(float(item.get("amount", 0)), ".2f"),
                                        "matchRatio": None,
                                        "matchedUserID": None,
                                        "multiple": None,
                                        "duplicates": None
                                    })
                            logger.info(f"matched user data {matched_user}")
                            logger.info(type(matched_user))
                            if matched_user and matched_user.get("match", None):
                                logger.info("Got a match without duplicates")
                                user = matched_user.get('match')
                                matching_report['matchRatio'] = matched_user.get('ratio')
                                matching_report['matchedUserID'] = f"{str(user.first_name)} {str(user.last_name)} {client_email} ({str(user.username)})"
                            elif matched_user and matched_user.get('duplicates', None):
                                logger.info("Got a match with duplicates")
                                matching_report['matchRatio'] = matched_user['highest_ratio']
                                matching_report['matchedUserID'] = f"{matched_user['data']['user_fullname']} {matched_user['data']['best_match_email']} ({matched_user['data']['best_match_username']})"
                                matching_report['duplicates'] = [duplicate.get('uuid', None) for duplicate in matched_user['duplicates']]
                                matching_report['multiple'] = [multiple.get('uuid', None) for multiple in matched_user['duplicates']]
                                user = None
                            elif matched_user and matched_user.get('closest_match', None):
                                logger.info("Got no matches ")
                                matching_report['matchRatio'] = matched_user.get('ratio')
                                matching_report['matchedUserID'] = f"{str(matched_user['closest_match'].first_name)} {str(matched_user['closest_match'].last_name)} {matched_user['closest_match'].email} ({str(matched_user['closest_match'].username)})"
                                user = None
                            reference_code_query = apps.get_model('bemosenderrr.GlobalTransaction').objects.filter(funding_transaction__reference_code=ref_code).first()
                            retrieved_emails += json.dumps(matching_report, indent=4) + "\n"
                            temp_report += "\n" + f"EMAIL N° {i}"
                            if reference_code_query:
                                if ref_code != None:
                                    print("reference already exists")
                            
                            if user and ref_code and not reference_code_query:

                                global_transactions = apps.get_model('bemosenderrr.GlobalTransaction').objects.filter(status=GlobalTransactionStatus.fundtransaction_in_progress,
                                    user=user, funding_transaction__reference_code=None).order_by('-created_at')
                                # Found 1 match of the user
                                logger.info(f"length of globaltransactions {len(global_transactions)}")
                                last_global_transaction = None
                                funding_transaction = None
                                is_lesser_than_minimum_amount = False
                                if global_transactions:
                                    
                                    last_global_transaction = global_transactions[0]
                                    funding_transaction = last_global_transaction.funding_transaction
                                    if last_global_transaction  and item and float(item['amount']) == float(last_global_transaction.parameters['total']):
                                        logger.info("THE AMOUNT MATCHES THE ORIGIN AMOUNT")
                                        result_email = "THE AMOUNT MATCHES THE ORIGIN AMOUNT"
                                        pass
                                    # Client matches and amount doesn't match !

                                    ## Amount received > Amount in global transaction
                                    elif last_global_transaction and item and float(item['amount']) > float(last_global_transaction.parameters['total']):
                                        logger.info("THE AMOUNT IS BIGGER THAN THE ORIGIN AMOUNT")
                                        old_total_amount = last_global_transaction.parameters['total']
                                        new_total_amount = str(item['amount'])
                                        last_global_transaction.parameters['total'] = new_total_amount
                                        rate_fee = get_latest_rate_and_fee(
                                            origin_amount=item['amount'],
                                            country_origin=last_global_transaction.parameters['origin_country'],
                                            country_destination=last_global_transaction.parameters['destination_country'],
                                            collect_method=last_global_transaction.collect_method
                                            )
                                        fee = last_global_transaction.parameters['fee']
                                        if rate_fee and rate_fee[0] and rate_fee[1]:
                                            rate = rate_fee[0]
                                            fee = rate_fee[1]
                                            last_global_transaction.parameters['fee'] = str(fee)
                                        else:
                                            rate = float(last_global_transaction.parameters['amount_destination']) / float(last_global_transaction.parameters['amount_origin'])
                                            last_global_transaction.parameters['fee'] = str(fee)
                                        new_origin_amount = float(item['amount']) - float(last_global_transaction.parameters['fee'])
                                        last_global_transaction.parameters['amount_origin'] = str(new_origin_amount)
                                        new_amount_destination = str(round(float(new_origin_amount) * rate, 4))
                                        last_global_transaction.parameters['amount_destination'] = new_amount_destination
                                        last_global_transaction.save()
                                        update_global_tx_parameters(
                                            global_tx_id=str(last_global_transaction.uuid),
                                            origin_amount=new_origin_amount,
                                            destination_amount=new_amount_destination,
                                            total=new_total_amount,
                                            rate=rate,
                                            collect_method_fee=fee
                                        )
                                        result_email = f"AMOUNT DOESNT MATCH INITIAL TRANSACTION AMOUNT \nINITIAL AMOUNT : {float(old_total_amount)}\nFOUND AMOUNT : {float(item['amount'])}"
                                    ## Amount received < Amount in global transaction
                                    elif last_global_transaction and item and float(item['amount']) < float(last_global_transaction.parameters['total']):
                                        logger.info("THE AMOUNT IS SMALLER THAN THE ORIGIN AMOUNT")
                                        result_email = "THE AMOUNT IS SMALLER THAN THE ORIGIN AMOUNT"
                                        app_settings = AppSettings.objects.first()
                                        min_transaction_amount = None
                                        if app_settings:
                                            min_transaction_amount = float(app_settings.config.get('minTransactionValue', None).get(last_global_transaction.parameters["origin_country"]))
                                        if (float(item['amount']) - min_transaction_amount - float(last_global_transaction.parameters['fee'])) < 0:
                                            logger.info("THE AMOUNT IS SMALLER THAN THE ORIGIN AMOUNT AND SMALLER THAN THE MINIMUM AMOUNT")
                                            result_email = "THE AMOUNT IS SMALLER THAN THE ORIGIN AMOUNT AND SMALLER THAN THE MINIMUM AMOUNT"
                                            result_email = f"AMOUNT DOESNT MATCH INITIAL TRANSACTION AMOUNT \nINITIAL AMOUNT : {float(last_global_transaction.parameters['total'])}\nFOUND AMOUNT : {float(item['amount'])}"
                                            is_lesser_than_minimum_amount = True
                                            from pytz import timezone
                                            # define date format
                                            fmt = '%Y-%m-%d %H:%M:%S %Z%z'
                                            # define eastern timezone
                                            cet = timezone('CET')
                                            cet_datetime = datetime.datetime.strftime(datetime.datetime.now(cet), fmt)
                                            env = str(settings.CONFIG['env'])
                                            deposit_type = "Auto-Deposit" if item.get('depositType', None) == "auto" else "Manual-deposit"
                                            email_data = f"""
                                            Report Date: {cet_datetime}
                                            Environment: {env}
                                            Partner: {apaylo.display_name}

                                            SEND TO: {last_global_transaction.receiver_snapshot['first_name']} {last_global_transaction.receiver_snapshot['last_name']} {last_global_transaction.receiver_snapshot['phone_number']}
                                            BY: {last_global_transaction.user_snapshot['first_name']} {last_global_transaction.user_snapshot['last_name']} {last_global_transaction.user_snapshot['phone_number']}
                                            Amount: {format(float(last_global_transaction.parameters.get('amount_origin', 0)), ".2f")} {last_global_transaction.parameters['currency_origin']} - {format(float(last_global_transaction.parameters.get('amount_destination', 0)), ".2f")} {last_global_transaction.parameters['currency_destination']}

                                            {deposit_type} interrupted
                                            senderr tried to send an Interac transfer smaller than the minimum transaction amount ({min_transaction_amount} {last_global_transaction.parameters['currency_origin']}).
                                            """
                                            print(email_data)
                                            recipients = apps.get_model('bemosenderrr.AdminAlerts').objects.filter(can_receive_celery_exceptions=True)
                                            recipients_emails = []
                                            if recipients:
                                                for recipient in recipients:
                                                    recipients_emails.append(recipient.user.email)
                                            else:
                                                recipients_emails = [settings.ADMINS[0][0][1]]
                                            result = send_mail(
                                                subject=f"<{env}>: Interac transfer invalid received amount ",
                                                message=email_data,
                                                from_email=str(settings.SERVER_EMAIL),
                                                recipient_list=recipients_emails,
                                                fail_silently=True
                                            )
                                        else:
                                            logger.info("THE AMOUNT IS SMALLER THAN THE ORIGIN AMOUNT AND BIGGER THAN THE MINIMUM AMOUNT")
                                            
                                            old_total_amount = last_global_transaction.parameters['total']
                                            result_email = f"AMOUNT DOESNT MATCH INITIAL TRANSACTION AMOUNT \nINITIAL AMOUNT : {float(old_total_amount)}\nFOUND AMOUNT : {float(item['amount'])}"
                                            new_total_amount = str(item['amount'])
                                            last_global_transaction.parameters['total'] = new_total_amount
                                            rate_fee = get_latest_rate_and_fee(
                                                origin_amount=item['amount'],
                                                country_origin=last_global_transaction.parameters['origin_country'],
                                                country_destination=last_global_transaction.parameters['destination_country'],
                                                collect_method=last_global_transaction.collect_method
                                                )
                                            fee = last_global_transaction.parameters['fee']
                                            if rate_fee and rate_fee[0] and rate_fee[1]:
                                                rate = rate_fee[0]
                                                fee = rate_fee[1]
                                                last_global_transaction.parameters['fee'] = str(fee)
                                            else:
                                                rate = float(last_global_transaction.parameters['amount_destination']) / float(last_global_transaction.parameters['amount_origin'])
                                                last_global_transaction.parameters['fee'] = str(fee)
                                            new_origin_amount = float(item['amount']) - float(last_global_transaction.parameters['fee'])
                                            last_global_transaction.parameters['amount_origin'] = str(new_origin_amount)
                                            new_amount_destination = str(round(float(new_origin_amount) * rate, 4))
                                            last_global_transaction.parameters['amount_destination'] = new_amount_destination
                                            last_global_transaction.save()
                                            update_global_tx_parameters(
                                                global_tx_id=str(last_global_transaction.uuid),
                                                origin_amount=new_origin_amount,
                                                destination_amount=new_amount_destination,
                                                total=new_total_amount,
                                                rate=rate,
                                                collect_method_fee=fee
                                            )
                                            report = report + "AMMOUNT DOESNT MATCH INDICTATED AMMOUNT " + "\n" + f"INDICATED AMMOUNT : {float(old_total_amount)}"
                                            report = report + "\n" + f"FOUND AMMOUNT : {float(item['amount'])} " + "\n"
                                            report = report + "------------" + "\n"
                                else:
                                    print("NO MATCHES FOUND !!")
                                    result_email = "Skipping no match found"
                                    temp_report += "\nSkipping no match found\n"
                                    temp_report += "-------------------------------------\n"
                                    tmp_failed_count += 1
                                    report_failed += temp_report
                                    if item.get('depositType', None) == "auto":
                                        SendAdminAlerts().send_unmatched_deposit_email(
                                            params={
                                                "full_name": str(item.get("client", "")),
                                                "deposit_type": "Auto Deposit",
                                                "amount": item.get('amount', None),
                                                "email": item.get('clientEmail', None)
                                            }
                                        )
                                if last_global_transaction and funding_transaction and not is_lesser_than_minimum_amount:
                                    logger.info(f"THIS IS THE LAST GLOBAL TRANSACTION {last_global_transaction.uuid}")
                                    logger.info(f"THIS IS FUNDING TRANSACTION {funding_transaction}")
                                    logger.info(f"THIS IS REFERENCE CODE {item['refCode']}")
                                    funding_transaction.reference_code = item['refCode']
                                    funding_transaction.save()
                                response_get_incoming_transfer = None
                                if last_global_transaction and funding_transaction and item['depositType'] == 'manual' and not is_lesser_than_minimum_amount:
                                    logger.info('Found a match')
                                    temp_report = temp_report + '\n' + 'Apaylo: Get Incoming Transfer' + '\n' + 'REQUEST' + '\n'
                                    
                                    response_get_incoming_transfer = ApayloService().get_incoming_transfers(api_config, item['refCode'])
                                    temp_report = temp_report + json.dumps(response_get_incoming_transfer[1]) + '\n'
                                    temp_report = temp_report + 'RESPONSE ' + '\n' + json.dumps(response_get_incoming_transfer[0], indent=4) + '\n'
                                    if response_get_incoming_transfer[0].get('StatusCode', None) == 200 or response_get_incoming_transfer[0].get('IsError', True) == False:
                                        response_auth_transfer = None
                                        if response_get_incoming_transfer[0].get('Result', None) and response_get_incoming_transfer[0].get('Result', None).get("authenticationRequired", None) == 1:
                                            logger.info('Authentication required')
                                            logger.info('Authenticating')
                                            response_auth_transfer = ApayloService().authenticate_transfer(api_config, ref_number=item['refCode'],
                                                            security_answer=security_answer, hash_salt=response_get_incoming_transfer[0]['Result']['hashSalt']
                                                            )
                                            temp_report = temp_report + '\n' + 'Apaylo: Authorize Transfer' + '\n' + 'REQUEST' + '\n'
                                            temp_report = temp_report + json.dumps(response_auth_transfer[1]) + '\n'
                                            temp_report = temp_report + 'RESPONSE' + '\n' + json.dumps(response_auth_transfer[0]) + '\n'
                                        else:
                                            result_email = "Transfer Already authorized"
                                            temp_report += "\n Already authorized \n"
                                        response_complete_transfer = None
                                        if response_get_incoming_transfer and response_get_incoming_transfer[0].get('StatusCode', None) == 200 or response_get_incoming_transfer[0].get('IsError', True) == False :
                                            logger.info('Completing transfer')
                                            response_complete_transfer = ApayloService().complete_transfer(api_config, item['refCode'])
                                            temp_report = temp_report + '\n' + 'Apaylo: Complete Transfer' + '\n' + 'REQUEST' + '\n'
                                            temp_report = temp_report + json.dumps(response_complete_transfer[1]) + '\n'
                                            temp_report = temp_report + 'RESPONSE' + '\n' + json.dumps(response_complete_transfer[0]) + '\n'
                                        else:
                                            report_failed += 'Authorization error'
                                            funding_transaction.status = FundingTransactionStatus.auth_error
                                            admin_alerts_service = SendAdminAlerts()
                                            admin_alerts_service.send_admin_alert_partner_failure(
                                                global_tx=last_global_transaction,
                                                operation="funding_authorize_authenticate_transfer",
                                                partner=apaylo.name,
                                                params={
                                                    "failure_type": response_auth_transfer[0],
                                                    "time": item.get("utctimestamp", None)
                                                }
                                            )
                                            tmp_failed_count += 1
                                            result_email = "AuthorizeTransfer ERROR"
                                            report_failed += temp_report
                                        if response_complete_transfer and response_complete_transfer[0].get('StatusCode', None) == 200 or response_complete_transfer[0].get('IsError', True) == False:
                                            tmp_success_count += 1
                                            result_email = "Succesfulty deposited"
                                            report_success = report_success + temp_report
                                        else:
                                            funding_transaction.status = FundingTransactionStatus.complete_error
                                            admin_alerts_service = SendAdminAlerts()
                                            admin_alerts_service.send_admin_alert_partner_failure(
                                                global_tx=last_global_transaction,
                                                operation="funding_authorize_complete_transfer",
                                                partner=apaylo.name,
                                                params={
                                                    "failure_type": response_complete_transfer[0],
                                                    "time": item.get("utctimestamp", None)
                                                }
                                            )
                                            result_email = "CompleteTransafer ERROR"
                                            tmp_failed_count += 1
                                            report_failed += temp_report
                                    else:
                                        logger.info('GOT INCOMING TRANSFER ERROR')
                                        report_failed += "GET INCOMING TRANSFER ERROR"
                                        funding_transaction.status = FundingTransactionStatus.error
                                        admin_alerts_service = SendAdminAlerts()
                                        admin_alerts_service.send_admin_alert_partner_failure(
                                            global_tx=last_global_transaction,
                                            operation="funding_authorize_get_incoming_transfer",
                                            partner=apaylo.name,
                                            params={
                                                "failure_type": response_get_incoming_transfer[0],
                                                "time": item.get("utctimestamp", None)
                                            }
                                        )
                                        tmp_failed_count += 1
                                        result_email = "GetIncomingTransfer Error"
                                        report_failed += temp_report
                                    manual_deposits_report = copy.deepcopy({})
                                    manual_deposits_report['getTransfer'] = response_get_incoming_transfer[0]
                                    manual_deposits_report['authorizeTransfer'] = response_auth_transfer[0]
                                    manual_deposits_report['completeTransfer'] = response_complete_transfer[0]
                                    funding_transaction.partner_response = manual_deposits_report
                                    funding_transaction.save()
                                elif item['depositType'] == 'auto' and not is_lesser_than_minimum_amount:
                                    tmp_success_count += 1
                                    result_email = "\n SKIPPED AUTH AUTODEPOSIT EMAIL" + "\n" + "----------------------------" + "\n"
                            else:
                                if reference_code_query:
                                    logger.info('Skipping transfer reference code already exists')
                                    result_email = "Skipping transfer reference code already exists"
                                    temp_report += "\nSkipping transfer reference code already exists\n"
                                    temp_report += "-------------------------------------\n"
                                    tmp_failed_count += 1
                                    report_failed += temp_report
                                else:
                                    logger.info('Skipping transfer No match found')
                                    result_email = "Skipping No match found"
                                    temp_report += "\nSkipping No match found\n"
                                    temp_report += "-------------------------------------\n"
                                    tmp_failed_count += 1
                                    report_failed += temp_report
                        else:
                            if isinstance(data[0], list):
                                try:
                                    result_email = json.dumps({
                                        "emailSubject": data[0][0],
                                        'emailDate': data[0][1],
                                        "clientEmail": data[0][2]
                                    }, indent=4)
                                    result_email += "\nSkipping: Interac email not recognized \n"
                                except Exception as e:
                                    print('COULDNT PARSE EMAIL DATA')
                                    result_email = "Skipping: Interac email not recognized"
                    except Exception as e:
                        logger.info(f"Exception in email n° {i} {e}")
                        result_email = f"Exception in email n° {i} {e}"
                    retrieved_emails +=  result_email + "\n" + "------------------------\n"
                    if tmp_success_count > 0:
                        success_count += 1
                    if tmp_failed_count > 0:
                        failed_count += 1
                        
            else:
                report = report + '\n' + 'No emails found'
            apaylo.api_config['authorizeLastUpdate'] = authorize_deposits_end_time
            apaylo.save()
            report = report + retrieved_emails + "-------------------------------------------------------------------------" + f"\nSUCCESSFUL: {success_count}/{count_emails}\n" + \
                report_success + "\n-------------------------------------------------------------------------" + '\n' +f"FAILED: {failed_count}/{count_emails}\n" + report_failed \
                    + "\n-------------------------------------------------------------------------"
            report = report + '\n' + 'Last authorize deposits update : ' + str(apaylo.api_config['authorizeLastUpdate'])

        else:
            report = report + '\n' + 'Apaylo not active.'
        report = report + '\n' + 'End of Authorize Deposits Job.' + "\n" + "-------------------------------"
        logger.info(report)
        time_now = datetime.datetime.strftime(django_tz.now(), "%Y%m%d%H%M%S")
        env = ""
        if settings.CONFIG and settings.CONFIG.get('env', None) in ['Dev-V3', None]:
            env = "dev"
        else:
            env = "prod"
        upload_to_s3(body=report, bucket='v3-reporting', key=f"{env}/transactions/funding/{time_now}-AuthorizeDeposits.txt", content_type='text/plain')
        return report
    except Exception as e:
        report = report + 'Authorize deposits failed due to :' + str(e.args)
        report = report + '\n' + 'End of Authorize Deposits Job.' + "\n" + "-------------------------------"
        time_now = datetime.datetime.strftime(django_tz.now(), "%Y%m%d%H%M%S")
        env = ""
        if settings.CONFIG and settings.CONFIG.get('env', None) in ['Dev-V3', None]:
            env = "dev"
        else:
            env = "prod"
        admin_alerts_service = SendAdminAlerts()
        admin_alerts_service.send_admin_alert_partner_failure(
            operation="funding_authorize_deposits_error",
            partner=apaylo.name,
            params={
                "failure_type": e,
            }
        )
        send_email_celery_exception(exception=e)
        logger.info(report)
        upload_to_s3(body=report, bucket='v3-reporting', key=f"{env}/transactions/funding/{time_now}-AuthorizeDeposits.txt", content_type='text/plain')
        return report


@shared_task(bind=True)
def check_refunds(self, start_date=None, end_date=None):
    import datetime
    report = ''
    partner = None
    logger.info("starting check refunds")
    if settings.CONFIG and settings.CONFIG.get('env', None) in ['Dev-V3', None]:
        env = "dev"
    else:
        env = "prod"
    try:
        if start_date or end_date:
            logger.info("MANUALLY TRIGGERED CHECK REFUNDS")
        apaylo = Partner.objects.filter(name='Apaylo').first()
        time_now = datetime.datetime.utcnow()
        check_refunds_end_time = datetime.datetime.strftime(time_now, "%Y-%m-%d %H:%M:%S.%f")
        iso_tmp_start_date = None
        iso_tmp_end_date = None
        if start_date:
            iso_tmp_start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).isoformat()
        if end_date:
            iso_tmp_end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).isoformat()
        if apaylo.status == PartnerStatus.active:
            partner = apaylo
        if start_date and apaylo.status == PartnerStatus.active:
            iso_tmp_start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).isoformat()
            start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc) - datetime.timedelta(days=1)
            start_date = start_date.strftime("%Y-%m-%d")
        if apaylo.status == PartnerStatus.active and not start_date:
            partner = apaylo
            start_date = apaylo.api_config.get("refundLastUpdate", None)
            iso_tmp_start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=datetime.timezone.utc).isoformat()

            start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=datetime.timezone.utc) - datetime.timedelta(days=1)
            start_date = start_date.strftime("%Y-%m-%d %H:%M:%S.%f")
        if not start_date and apaylo.status == PartnerStatus.active:
            start_date = datetime.datetime.strftime(datetime.datetime.utcnow() - datetime.timedelta(minutes=16), "%Y-%m-%d %H:%M:%S.%f")
        if not end_date and apaylo.status == PartnerStatus.active:
            end_date = check_refunds_end_time
            iso_tmp_end_date = time_now.isoformat()
        iso_start_date = None
        iso_end_date = None
        logger.info(iso_tmp_start_date)
        logger.info(start_date)
        if start_date:
            iso_start_date = iso_tmp_start_date
        else:
            if partner:
                tmp_start_date = partner.api_config.get("depositLastUpdate", None)
                iso_start_date = datetime.datetime.strptime(tmp_start_date, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=datetime.timezone.utc).isoformat()
            else:
                pass
        if end_date:
            iso_end_date = iso_tmp_end_date
        else:
            iso_end_date = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).isoformat()
        logger.info(f"ISO START DATE {iso_start_date}")
        logger.info(f"ISO END DATE {iso_end_date}")
        logger.info(f"START DATE {start_date}")
        logger.info(f"END DATE {end_date}")
        report = report + '\n' + 'Refund Deposits Periodic Task Report' + '\n' + '---------------------------------'
        report = report + '\n' + 'Start Date :' + str(iso_start_date)
        report = report + '\n' + 'End Date : ' + str(iso_end_date)
        # 20-10-2022 REMOVED THE MILLISECONDS FROM SearchSendInteracEtransfer endpoint request body since it returns an error in the response
        if "." in str(start_date):
            start_date = str(start_date).split(".")[0]
        if "." in str(end_date):
            end_date = str(end_date).split(".")[0]
        if partner and partner.name == 'Apaylo' and partner.status == PartnerStatus.active:
            report = report + '\n' + 'Processor : Apaylo' + '\n'
            api_config = copy.deepcopy(partner.api_config)
            credentials = partner.api_user.credentials
            api_config['credentials'] = credentials
            search_send_transfers = ApayloService().search_send_interac_etransfers(api_config, start_date, end_date)
            report = report + 'APAYLO : SEARCH SEND INTERAC TRANSFERS :' + '\n'
            report = report + 'REQUEST' + "\n" + json.dumps(search_send_transfers[1], indent=4) + '\n'
            report = report + 'RESPONSE' + "\n" + json.dumps(search_send_transfers[0], indent=4) + '\n'
            if search_send_transfers and search_send_transfers[0] and search_send_transfers[0].get('StatusCode', None) == 200 and search_send_transfers[0].get('IsError', True) == False:
                items = search_send_transfers[0].get('Result', None)
                i = 1
                report += f"FOUND {len(items)} REFUND TRANSFER \n"
                for item in items:
                    report += f"TRANSFER {i}"
                    transaction_number = item.get('TransactionNumber', None)
                    funding_transaction = apps.get_model('bemosenderrr.FundingTransaction').objects.filter(refund_reference_code=transaction_number).first()
                    if funding_transaction:
                        report += "FOUND A MATCH\n"
                        global_tx = funding_transaction.globaltransaction_set.all().first()
                        if global_tx and global_tx.status == GlobalTransactionStatus.refundtransaction_in_progress:
                            global_tx.status = GlobalTransactionStatus.refunded
                            global_tx.save()
                            report += "TRANSACTION SUCCESFULLY REFUNDED\n"
                        else:
                            report += " TRANSACTION ALREDAY REFUNDED\n"
                            logger.info("GLOBAL TRANSACTION ALREADY REFUNDED")
                    else:
                        report += "Skipping no match found\n"
                    report += "------------------------------\n"
            else:
                report = report + '\n' + 'No refund transfers found !'
            partner.api_config['refundLastUpdate'] = check_refunds_end_time
            partner.save()
        else:
            print("Apaylo not active")
        logger.info(report)
        upload_to_s3(body=report, bucket='v3-reporting', key=f"{env}/transactions/funding/{time_now}-CheckRefunds.txt", content_type='text/plain')
        return report
    
    except Exception as e:
        report = report + 'Check Refunds failed due to :' + str(e.args)
        report = report + '\n' + 'End of Check Refunds Job.' + "\n" + "-------------------------------"
        time_now = datetime.datetime.strftime(django_tz.now(), "%Y%m%d%H%M%S") 
        admin_alerts_service = SendAdminAlerts()
        admin_alerts_service.send_admin_alert_partner_failure(
            operation="funding_check_refunds_error",
            partner=apaylo.name,
            params={
                "failure_type": e,
            }
        )
        send_email_celery_exception(exception=e)
        logger.info(report)
        upload_to_s3(body=report, bucket='v3-reporting', key=f"{env}/transactions/funding/{time_now}-CheckRefunds.txt", content_type='text/plain')
        return report

@shared_task(bind=True)
@reversion.create_revision()
def send_invoice_task(self, global_tx=None, *args, **kwargs):
    global_tx = apps.get_model('bemosenderrr.GlobalTransaction').objects.get(uuid=global_tx)
    invoice_service = SendInvoice()
    invoice_service.send_invoice(global_tx)


@shared_task(bind=True)
def update_pending_sign_up_flinks(self):
    try:
        time_now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        queryset = UserBankVerificationRequest.objects.filter(created_at__gte=time_now-datetime.timedelta(minutes=30), user__isnull=False, status=VerificationStatus.unverified).select_related("user")
        print(queryset)
        flinks = Partner.objects.filter(name__icontains="flinks").first()
        flinks_service = None
        if flinks:
            url = flinks.api_config.get('url', None)
            flinks_service = FlinksService(url=url, api_config=flinks.api_config, )
        if flinks_service:
            for bank_verification in queryset:
                try:
                    query_response = bank_verification.partner_response.get('query', None)
                    if query_response:
                        request_id = query_response.get('RequestId', None)
                        if request_id:
                            parameters = {
                                "login_id": bank_verification.partner_parameters.get('login_id', None),
                                "account_id": bank_verification.partner_parameters.get('account_id', None),
                                "request_id": str(request_id)
                            }
                            result = flinks_service.async_get_details(request_id=request_id, parameters=parameters)
                            user_data = result[1]
                            status = result[0]
                            logger.info(f"THE RESULT {'Verified' if status else 'Not verified'}")
                            if user_data.get('response_formatted', None):
                                result = sync_flinks_signup_data(user=bank_verification.user, data=user_data)
                                logger.info(f"RESULT UPDATING FLINKS SIGN UP DATA {result}")
                            else:
                                logger.info("FAILED TO GET USER DETAILS")
                                logger.info(user_data)
                            bank_verification.partner_response = user_data
                            if status:
                                bank_verification.status = VerificationStatus.verified
                            else:
                                bank_verification.status = VerificationStatus.unverified
                            bank_verification.save()
                            logger.info(f"THE RESULT {result}")

                except Exception as e:
                    logger.info(f'ERROR OCCURED DURING UPDATE PENDING SIGNUP FLINKS {e}')
        else:
            print('FLINKS INACTIVE')
    except Exception as e:
        logger.info(f'ERROR OCCURED DURING UPDATE PENDING SIGNUP FLINKS {e}')

