import copy
from datetime import datetime, time
import datetime as dt
import json
from django.utils import timezone
from rest_framework.response import Response
from bemoSenderr.models.partner.base import PartnerApiCallType
from bemoSenderr.models.partner.partner import APICollectToken, APIRequestMonitoring, AppSettings, Partner, PartnerSettlementAccount, TransactionMethod, TransactionMethodAvailability
from bemoSenderr.services import push_globaltx_datastore
from bemoSenderr.utils.notifications import NotificationsHandler
from bemoSenderr.utils.pinpoint import PinpointWrapper
from bemoSenderr.bemoSenderr_api.bemoSenderr_api_codes import bemoSenderr_API_MESSAGE_CODES
from bemoSenderr.models.partner.transactions import CollectTransaction
from bemoSenderr.models.base import CollectTransactionStatus, PartnerType
from jsonschema import validate
from bemoSenderr.bemoSenderr_api.request_schemas import get_payment_schema, confirm_payment_schema, rollback_payment_schema, get_daily_account_statement_schema
from secrets import token_hex
from bemoSenderr.models.base import GlobalTransactionStatus
from rest_framework import status as http_status
from django.apps import apps


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def gen_payment_token():
    token = token_hex(24)
    tokens_query = APICollectToken.objects.filter(token=token).first()
    if tokens_query:
        return gen_payment_token()
    else:
        return token

def compare_data(dict_1, dict_2):
    difference = list()
    if dict_1 == dict_2:
        print("identiacal")
    else:
        for k, v in dict_1.items():
            current_val = dict_2.get(k, None)
            if current_val != "" and  v != "" and v == current_val:
                print('not empty')
            elif current_val == "" and  v == "" and v == current_val:
                print('empty')
            else:
                difference.append(k)
    return difference

def last_day_of_month(date):
    if date.month == 12:
        return date.replace(day=31)
    return date.replace(month=date.month+1, day=1) - dt.timedelta(days=1)

def bemoSenderr_api(request=None, request_object=None):
    time_stamp = datetime.strftime(timezone.now(),"%c")
    req_body = None
    response = {}
    response['response'] = {}
    response['response']['code'] = ""
    response['response']['message'] = ""
    response['response']['data'] = {}
    resp_db = {}
    req_db = {}
    req_db['url'] = request.path
    req_db['params'] = ""
    req_db['query'] = ""
    req_db['method'] = request.method
    req_db['headers'] = request.headers.__dict__
    req_db['ip'] = get_client_ip(request)
    req_db['timestamp'] = time_stamp 
    request_body = request.data
    if request.data:
        req_body = copy.deepcopy(request_object)
        if req_body.get('request', None) and req_body.get('request', None).get('request', None):
            req_body = req_body.get('request')
        partner = Partner.objects.filter(api_user=request.user, type=PartnerType.collect).first()
        print("Current Partner ", partner)
        other_partners = Partner.objects.exclude(api_user=request.user).filter(type=PartnerType.collect)
        print("Other Partners ", other_partners)
        if req_body:
            """
            GetPayment Service:
            the codes:
            2000 1000 1005 2104 2200 2203 2213 2300 2400 2600 2601 2602 2604 2605 2606
            """
            if req_body.get('request', None).get('service', None).get('name', None) == "GetPayment":
                print('-------------- GetPayment Service -------------')
                reqBodySchema = get_payment_schema
                try:
                    try:
                        validate(instance=req_body, schema=reqBodySchema)
                    except:
                        response['response']['code'] = 1005
                        response['response']['message'] = bemoSenderr_API_MESSAGE_CODES[1005]
                        response['response']['data'] = ""
                        resp_db['httpStatus'] = http_status.HTTP_400_BAD_REQUEST
                        resp_db['jsonResponse'] = response
                        resp_db['timestamp'] = datetime.strftime(timezone.now(), "%c")
                        APIRequestMonitoring.objects.create(method=request.method, path=request.path, api_user=request.user, body=request_body,
                            request=req_db, response=resp_db
                        )
                        return Response(response, status=http_status.HTTP_400_BAD_REQUEST)
                    payment_orders = req_body.get('request', None).get('service', None).get('data', None).get('paymentOrders', None)
                    print("Payment orders : ", payment_orders)
                    print('length of payment orders ',len(payment_orders))
                    if len(payment_orders) <= 10:
                        if payment_orders :
                            response['response']['data']['paymentOrders'] = list()
                            response['response']['code'] = 2000
                            response['response']['message'] = bemoSenderr_API_MESSAGE_CODES[2000]
                            print('Response code ', 2000)
                            for payment in payment_orders:
                                
                                code = payment.get('payment', None).get('code', None)
                                if code:
                                    print("Processing payment code : ", code)
                                    payment_order = {}
                                    collect_transaction = CollectTransaction.objects.filter(collect_code=code, partner=partner).prefetch_related("globaltransaction_set").first()
                                    print("Collect Transaction ", collect_transaction)
                                    global_tx = None
                                    
                                    api_collect_token = None
                                    collect_transactions = None
                                    if collect_transaction:
                                        time_now = timezone.now()
                                        global_tx = collect_transaction.globaltransaction_set.all().first()
                                        print(global_tx)
                                        api_collect_token = APICollectToken.objects.filter(global_transaction=global_tx).first()
                                        collect_transactions = global_tx.collect_transactions.all().filter(status=CollectTransactionStatus.collected)
                                        print("succesful collect transaction", collect_transactions)
                                    # The payment already requested by another payer...
                                    if api_collect_token and collect_transactions:
                                        if api_collect_token and api_collect_token.api_user == request.user and global_tx.status == GlobalTransactionStatus.success:
                                            print('The order is paid ', 2605)
                                            payment_order['order'] = {
                                                "reference": str(code),
                                                "code": 2601,
                                                "message": bemoSenderr_API_MESSAGE_CODES[2601]
                                            }
                                        elif api_collect_token and api_collect_token.api_user != request.user:
                                            print('The payment already requested by another payer... ', 2605)
                                            payment_order['order'] = {
                                                "reference": str(code),
                                                "code": 2605,
                                                "message": bemoSenderr_API_MESSAGE_CODES[2605]
                                            }
                                        elif api_collect_token and api_collect_token.api_user == request.user and global_tx.status == GlobalTransactionStatus.collectransaction_in_progress:
                                            print('The payment already requested by another payer...??? ', 2605)
                                            payment_order['order'] = {
                                                "reference": str(code),
                                                "code": 2605,
                                                "message": bemoSenderr_API_MESSAGE_CODES[2605]
                                            }
                                    # The payment isn't requested by any payer yet..
                                    else:
                                        print("The payment isn't requested by any payer yet..")
                                        if collect_transaction:
                                            country_origin  = str(collect_transaction.globaltransaction_set.all().first().parameters["origin_country"]).upper()
                                            amount_origin = str(collect_transaction.globaltransaction_set.all().first().parameters["amount_origin"]).upper()
                                            currency_origin = str(collect_transaction.globaltransaction_set.all().first().parameters["currency_origin"]).upper()
                                            country_destination = str(collect_transaction.globaltransaction_set.all().first().parameters["destination_country"]).upper()
                                            amount_destination = str(collect_transaction.globaltransaction_set.all().first().parameters["amount_destination"]).upper()
                                            currency_destination = str(collect_transaction.globaltransaction_set.all().first().parameters["currency_destination"]).upper()
                                            print(collect_transaction.updated_at)
                                            date = str(datetime.strftime(collect_transaction.updated_at, "%Y-%m-%d %H:%M:%S.%f"))
                                            sender = collect_transaction.globaltransaction_set.all().first().user_snapshot
                                            recipient = collect_transaction.globaltransaction_set.all().first().receiver_snapshot
                                            delivery_method = collect_transaction.globaltransaction_set.all().first().collect_method
                                            partner_method = TransactionMethod.objects.filter(name=delivery_method).first()
                                            delivery = TransactionMethodAvailability.objects.filter(partner=partner, partner_method=partner_method).first()
                                            if delivery:
                                                delivery = delivery.api_code
                                            status = collect_transaction.status
                                            print(status)
                                            if status == CollectTransactionStatus.collect_ready:
                                                api_collect_token = APICollectToken.objects.filter(api_user=request.user, global_transaction=global_tx).first()
                                                time_now = timezone.now()
                                                token = ""
                                                if api_collect_token and api_collect_token.api_user == request.user and time_now > api_collect_token.expires_at:
                                                    token = gen_payment_token()
                                                    api_collect_token.token = token
                                                    api_collect_token.expires_at = time_now
                                                    api_collect_token.save()
                                                elif api_collect_token and api_collect_token.api_user == request.user and time_now < api_collect_token.expires_at:
                                                    token = api_collect_token.token
                                                elif not api_collect_token:
                                                    token = gen_payment_token()
                                                    APICollectToken.objects.create(token=token, api_user=partner.api_user, global_transaction=global_tx)
                                                else:
                                                    token = gen_payment_token()
                                                print('Collect transaction started ', collect_transaction.status)
                                                payment_order['order'] = {
                                                    "reference": str(payment['payment']['code']),
                                                    "date": date,
                                                    "country": country_origin,
                                                    "currency": currency_origin,
                                                    "amountOrigin": amount_origin
                                                }
                                                payment_order['payment'] = {
                                                    "status": "sent",
                                                    "code": collect_transaction.collect_code,
                                                    "token": token, 
                                                    "country": country_destination,
                                                    "currency": currency_destination,
                                                    "amountDest": amount_destination,
                                                    "delivery": delivery,
                                                    "payer": partner.active_payer.code,
                                                    "accountNumber": ""
                                                }
                                                payment_order['sender'] ={
                                                    "firstName": sender['first_name'],
                                                    "middlename": "",
                                                    "lastName": sender['last_name'],
                                                    "address1": sender['address_1'],
                                                    "address2": "",
                                                    "city": sender['city'],
                                                    "state": sender['state'],
                                                    "zipcode": sender['first_name'],
                                                    "country": country_destination,
                                                    "phone1": sender['phone_number'],
                                                    "phone2": "",
                                                    "document": {
                                                        "type": sender['document']['type'],
                                                        "number": sender['document']['number'],
                                                        "country": str(sender['document']['country']).upper()
                                                    }
                                                }
                                                payment_order['recipient'] = {
                                                    "firstName": recipient['first_name'],
                                                    "middlename": "",
                                                    "lastName": recipient['last_name'],
                                                    "address1": recipient['address_1'],
                                                    "address2": "",
                                                    "city": recipient['city'],
                                                    "state": recipient['state'],
                                                    "zipcode": recipient['zip_code'],
                                                    "country": country_destination,
                                                    "phone1": recipient['phone_number'],
                                                    "phone2": ""
                                                }
                                            elif status == CollectTransactionStatus.canceled:
                                                print('Collect transaction cancelled ', collect_transaction.status)
                                                print('Code is 2602')
                                                payment_order['order'] = {
                                                    "reference": str(payment['payment']['code']),
                                                    "code": 2602,
                                                    "message": bemoSenderr_API_MESSAGE_CODES[2602]
                                                }
                                                payment_order['payment'] = {
                                                    "code": str(collect_transaction.collect_code), ##TODO what is this ??
                                                    "date": ""
                                                }
                                                payment_order['partner'] = {
                                                    "name": "",
                                                    "agencyId": "",
                                                    "country": ""
                                                }
                                            elif status == CollectTransactionStatus.collected:
                                                print('Collect transaction completed ', collect_transaction.status)
                                                print('Code is 2601')
                                                payment_order['order'] = {
                                                    "reference": str(payment['payment']['code']),
                                                    "code": 2601,
                                                    "message": bemoSenderr_API_MESSAGE_CODES[2601]
                                                }
                                            elif status == CollectTransactionStatus.new:
                                                print("Transaction is NEW")
                                                pass
                                        else:
                                            print('Order not found : 2600')
                                            payment_order = {}
                                            payment_order['order'] = {
                                                "reference": str(payment['payment']['code']),
                                                "code": 2600,
                                                "message": bemoSenderr_API_MESSAGE_CODES[2600]
                                            }
                                response['response']['data']['paymentOrders'].append(payment_order)
                        resp_db['httpStatus'] = http_status.HTTP_200_OK
                        resp_db['jsonResponse'] = response
                        resp_db['timestamp'] = datetime.strftime(timezone.now(), "%c")
                        APIRequestMonitoring.objects.create(method=request.method, path=request.path, api_user=request.user, body=request_body,
                            request=req_db, response=resp_db
                        )
                        return Response(response, status=http_status.HTTP_200_OK)
                    elif len(payment_orders) > 10:
                        response['response']['code'] = 2213
                        response['response']['message'] = bemoSenderr_API_MESSAGE_CODES[2213]
                        response['response']['data'] = ""
                        resp_db['httpStatus'] = http_status.HTTP_400_BAD_REQUEST
                        resp_db['jsonResponse'] = response
                        resp_db['timestamp'] = datetime.strftime(timezone.now(), "%c")
                        APIRequestMonitoring.objects.create(method=request.method, path=request.path, api_user=request.user, body=request_body,
                            request=req_db, response=resp_db
                        )
                        return Response(response, status=http_status.HTTP_400_BAD_REQUEST)
                         
                except Exception as e:
                    print("Exception caught ", e)
                    response['response']['code'] = 1000
                    response['response']['message'] = bemoSenderr_API_MESSAGE_CODES[1000]
                    response['response']['data'] = ""
                    resp_db['httpStatus'] = http_status.HTTP_500_INTERNAL_SERVER_ERROR
                    resp_db['jsonResponse'] = response
                    resp_db['timestamp'] = datetime.strftime(timezone.now(), "%c")
                    APIRequestMonitoring.objects.create(method=request.method, path=request.path, api_user=request.user, body=request_body,
                        request=req_db, response=resp_db
                    )
                    return Response(response, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)
               
            """
            ConfirmPayment Service:
            the codes:
            2000 1000 1005 2200 2202 2210 2211 2212 2400 2401 2402 2403 2404 2405
            2406 2407 2408 2409 2410 2411 2412 2413 2414 2600 2601 2602 2603 2700 
            2701 702 2703 
            """
            if req_body.get('request', None).get('service', None).get('name', None) == "ConfirmPayment":
                print('-------------- ConfirmPayment Service -------------')
                reqBodySchema = confirm_payment_schema
                try:
                    try:
                        validate(instance=req_body, schema=reqBodySchema)
                    except:
                        response['response']['code'] = 1005
                        response['response']['message'] = bemoSenderr_API_MESSAGE_CODES[1005]
                        response['response']['data'] = ""
                        resp_db['httpStatus'] = http_status.HTTP_400_BAD_REQUEST
                        resp_db['jsonResponse'] = response
                        resp_db['timestamp'] = datetime.strftime(timezone.now(), "%c")
                        APIRequestMonitoring.objects.create(method=request.method, path=request.path, api_user=request.user, body=request_body,
                            request=req_db, response=resp_db
                        )
                        return Response(response, status=http_status.HTTP_400_BAD_REQUEST)
                    code = req_body.get('request', None).get('service', None).get('data', None).get('paymentOrder', None).get('payment', None).get('code')
                    token = req_body.get('request', None).get('service', None).get('data', None).get('paymentOrder', None).get('payment', None).get('token')
                    if code and token:
                        print("Processing payment code : ", code)
                        payment_order = {}
                        collect_transaction = CollectTransaction.objects.filter(collect_code=code, partner=partner).prefetch_related("globaltransaction_set").first()
                        print("Collect Transaction ", collect_transaction)
                        global_tx = None
                        if collect_transaction:
                            global_tx = collect_transaction.globaltransaction_set.all().first()
                            api_collect_token = APICollectToken.objects.filter(api_user=request.user, global_transaction=global_tx).first()
                            time_now = timezone.now()
                            date_str = datetime.strftime(time_now, "%Y-%m-%d %H:%M:%S.%f")
                            print(global_tx)
                            ## Token expired !!
                            if time_now > api_collect_token.expires_at:
                                response['response']['code'] = 2211
                                response['response']['message'] = bemoSenderr_API_MESSAGE_CODES[2211]
                                response['response']['data'] = ""
                                resp_db['httpStatus'] = http_status.HTTP_400_BAD_REQUEST
                                resp_db['jsonResponse'] = response
                                resp_db['timestamp'] = datetime.strftime(timezone.now(), "%c")
                                APIRequestMonitoring.objects.create(method=request.method, path=request.path, api_user=request.user, body=request_body,
                                    request=req_db, response=resp_db
                                )
                                return Response(response, status=http_status.HTTP_400_BAD_REQUEST)
                            elif time_now < api_collect_token.expires_at and token == api_collect_token.token:
                                recipient_snapshot = global_tx.receiver_snapshot
                                recipient_data = req_body.get('request', None).get('service', None).get('data', None).get('paymentOrder', None).get('recipient', None)
                                if recipient_data:
                                    recipient_data.pop('document', None)
                                    formatted_recipient = {
                                        "firstName": recipient_snapshot['first_name'],
                                        "middlename": "",
                                        "lastName": recipient_snapshot['last_name'],
                                        "phone1": recipient_snapshot['phone_number'],
                                        "phone2": "",
                                        "zipcode": recipient_snapshot['zip_code'],
                                        "city": recipient_snapshot['city'],
                                        "state": recipient_snapshot['state'],
                                        "address1": recipient_snapshot['address_1'],
                                        "address2": ""
                                    }
                                    difference = compare_data(formatted_recipient, recipient_data)
                                    if difference:
                                        key = difference[0]
                                        resp_code = None
                                        if key == "firstName":
                                            resp_code = 2400
                                        elif key == "lastName":
                                            resp_code = 2402
                                        elif key == "phone1":
                                            resp_code = 2409
                                        elif key == "zipcode":
                                            resp_code = 2407
                                        elif key == "city":
                                            resp_code = 2405
                                        elif key == "state":
                                            resp_code = 2406
                                        elif key == "address1":
                                            resp_code = 2403
                                        else:
                                            resp_code = 2000
                                        response['response']['code'] = resp_code
                                        response['response']['message'] = bemoSenderr_API_MESSAGE_CODES[resp_code]
                                        response['response']['data'] = ""
                                        resp_db['httpStatus'] = http_status.HTTP_400_BAD_REQUEST
                                        resp_db['jsonResponse'] = response
                                        resp_db['timestamp'] = datetime.strftime(timezone.now(), "%c")
                                        APIRequestMonitoring.objects.create(method=request.method, path=request.path, api_user=request.user, body=request_body,
                                            request=req_db, response=resp_db
                                        )
                                        return Response(response, status=http_status.HTTP_400_BAD_REQUEST)
                                    else:
                                        collect_transaction.status = CollectTransactionStatus.collected
                                        collect_transaction.save()
                                        response['response']['code'] = 2000
                                        response['response']['message'] = bemoSenderr_API_MESSAGE_CODES[2000]
                                        response['response']['data'] = {
                                            "paymentOrder":{
                                                "payment":{
                                                    "code": str(code),
                                                    "status": "done",
                                                    "date": date_str
                                                }
                                            }
                                        }
                                        print(request_body)
                                        resp_db['httpStatus'] = http_status.HTTP_200_OK
                                        resp_db['jsonResponse'] = response
                                        resp_db['timestamp'] = datetime.strftime(timezone.now(), "%c")
                                        APIRequestMonitoring.objects.create(method=request.method, path=request.path, api_user=request.user, body=request_body,
                                            request=req_db, response=resp_db
                                        )
                                        return Response(response, status=http_status.HTTP_200_OK)
                            elif token != api_collect_token.token:
                                response['response']['code'] = 2210
                                response['response']['message'] = bemoSenderr_API_MESSAGE_CODES[2210]
                                response['response']['data'] = ""
                                resp_db['httpStatus'] = http_status.HTTP_400_BAD_REQUEST
                                resp_db['jsonResponse'] = response
                                resp_db['timestamp'] = datetime.strftime(timezone.now(), "%c")
                                APIRequestMonitoring.objects.create(method=request.method, path=request.path, api_user=request.user, body=request_body,
                                    request=req_db, response=resp_db
                                )
                                return Response(response, status=http_status.HTTP_400_BAD_REQUEST)
                        ## Collect Code not found
                        else:
                            response['response']['code'] = 2202
                            response['response']['message'] = bemoSenderr_API_MESSAGE_CODES[2202]
                            response['response']['data'] = ""
                            resp_db['httpStatus'] = http_status.HTTP_400_BAD_REQUEST
                            resp_db['jsonResponse'] = response
                            resp_db['timestamp'] = datetime.strftime(timezone.now(), "%c")
                            APIRequestMonitoring.objects.create(method=request.method, path=request.path, api_user=request.user, body=request_body,
                                request=req_db, response=resp_db
                            )
                            return Response(response, status=http_status.HTTP_400_BAD_REQUEST)
                except Exception as e:
                    print(e)
                    print("Exception caught ", e)
                    response['response']['code'] = 1000
                    response['response']['message'] = bemoSenderr_API_MESSAGE_CODES[1000]
                    response['response']['data'] = ""
                    resp_db['httpStatus'] = http_status.HTTP_500_INTERNAL_SERVER_ERROR
                    resp_db['jsonResponse'] = response
                    resp_db['timestamp'] = datetime.strftime(timezone.now(), "%c")
                    APIRequestMonitoring.objects.create(method=request.method, path=request.path, api_user=request.user, body=request_body,
                        request=req_db, response=resp_db
                    )
                    return Response(response, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)
            """
            RollbackPayment Service:
            the codes:
            2000 1000 1005 2200 2202 2210 2211 2212 2400 2401 2402 2403 2404 2405 
            2406 2407 2408 2409 2410 2411 2412 2413 2414 2600 2601 2602 2603 
            """
            if req_body.get('request', None).get('service', None).get('name', None) == "RollbackPayment":
                print('-------------- RollBackPayment Service -------------')
                reqBodySchema = rollback_payment_schema
                print("Client IP", get_client_ip(request))
                try:
                    try:
                        validate(instance=req_body, schema=reqBodySchema)
                    except Exception as e:
                        response['response']['code'] = 1005
                        response['response']['message'] = bemoSenderr_API_MESSAGE_CODES[1005]
                        response['response']['data'] = ""
                        resp_db['httpStatus'] = http_status.HTTP_400_BAD_REQUEST
                        resp_db['jsonResponse'] = response
                        resp_db['timestamp'] = datetime.strftime(timezone.now(), "%c")
                        APIRequestMonitoring.objects.create(method=request.method, path=request.path, api_user=request.user, body=request_body,
                            request=req_db, response=resp_db
                        )
                        return Response(response, status=http_status.HTTP_400_BAD_REQUEST)
                    code = req_body.get('request', None).get('service', None).get('data', None).get('paymentOrder', None).get('payment', None).get('code')
                    token = req_body.get('request', None).get('service', None).get('data', None).get('paymentOrder', None).get('payment', None).get('token')
                    if code and token:
                        print("Processing payment code : ", code)
                        payment_order = {}
                        collect_transaction = CollectTransaction.objects.filter(collect_code=code, partner=partner).prefetch_related("globaltransaction_set").first()
                        print("Collect Transaction ", collect_transaction)
                        global_tx = None
                        
                        if collect_transaction:
                            global_tx = collect_transaction.globaltransaction_set.all().first()
                            receiver_phone_number = str(global_tx.receiver_snapshot.get('phone_number', "UNDEFINED"))
                            notif_service = NotificationsHandler()
                            language = global_tx.user.locale
                            if not language:
                                language = "FR"
                            global_tx_user = global_tx.user
                            
                            notif_data = notif_service.get_tx_delayed_sender_push(lang=language, vars=[partner.display_name])
                            client_support = AppSettings.objects.all().first()
                            print(f"CLIENT SUPPORT {client_support}")
                            if client_support:
                                client_support_help_desk = client_support.config.get('clientHelpDesk', None)
                                print(f"CLIENT SUPPORT N 2 {client_support}")
                                if client_support_help_desk:
                                    client_support = client_support_help_desk.get(global_tx.parameters.get('destination_country'), "")
                            else:
                                client_support = ""
                            lang_receiver = global_tx.receiver_snapshot.get('language', "FR")
                            if lang_receiver == "french":
                                lang_receiver = "FR"
                            elif lang_receiver == "english":
                                lang_receiver = "EN"
                            sms_data = notif_service.get_tx_delayed_receiver_sms(lang=lang_receiver, vars=[partner.display_name, client_support])
                            pinpoint_service = PinpointWrapper()
                            admin_phone_numbers = notif_service.get_staff_users_phone_numbers()
                            if admin_phone_numbers:
                                admin_phone_numbers.append(receiver_phone_number)
                                receiver_phone_number = admin_phone_numbers
                            status_sms = pinpoint_service.send_sms(origination_number="+123", destination_number=receiver_phone_number, message=sms_data)
                            print("ROLLBACK PAYMENT ADMINALERT AND RECEIVER STATUS",status_sms)
                            status_push = pinpoint_service.send_push_notifications_and_data(user_snapshot=global_tx.user_snapshot, status=global_tx.status, user=global_tx_user, data=notif_data, type="transaction", global_tx_uuid=str(global_tx.uuid))
                            api_collect_token = APICollectToken.objects.filter(api_user=request.user, global_transaction=global_tx).first()
                            time_now = timezone.now()
                            date_str = datetime.strftime(time_now, "%Y-%m-%d %H:%M:%S.%f")
                            print(global_tx)
                            ## Token expired !!
                            api_collect_token = APICollectToken.objects.filter(api_user=partner.api_user, global_transaction=global_tx).first()
                            if api_collect_token and time_now > api_collect_token.expires_at and token == api_collect_token.token:
                                api_collect_token.expires_at = time_now
                                api_collect_token.save()
                            if token == api_collect_token.token:
                                recipient_snapshot = global_tx.receiver_snapshot
                                recipient_data = req_body.get('request', None).get('service', None).get('data', None).get('paymentOrder', None).get('recipient', None)
                                if recipient_data:
                                    recipient_data.pop('document', None)
                                    formatted_recipient = {
                                        "firstName": recipient_snapshot['first_name'],
                                        "middlename": "",
                                        "lastName": recipient_snapshot['last_name'],
                                        "phone1": recipient_snapshot['phone_number'],
                                        "phone2": "",
                                        "zipcode": recipient_snapshot['zip_code'],
                                        "city": recipient_snapshot['city'],
                                        "state": recipient_snapshot['state'],
                                        "address1": recipient_snapshot['address_1'],
                                        "address2": ""
                                    }
                                    difference = compare_data(formatted_recipient, recipient_data)
                                    print(difference)
                                    if difference:
                                        key = difference[0]
                                        resp_code = None
                                        if key == "firstName":
                                            resp_code = 2400
                                        elif key == "lastName":
                                            resp_code = 2402
                                        elif key == "phone1":
                                            resp_code = 2409
                                        elif key == "zipcode":
                                            resp_code = 2407
                                        elif key == "city":
                                            resp_code = 2405
                                        elif key == "state":
                                            resp_code = 2406
                                        elif key == "address1":
                                            resp_code = 2403
                                        else:
                                            resp_code = 2000
                                        response['response']['code'] = resp_code
                                        response['response']['message'] = bemoSenderr_API_MESSAGE_CODES[resp_code]
                                        response['response']['data'] = ""
                                        resp_db['httpStatus'] = http_status.HTTP_400_BAD_REQUEST
                                        resp_db['jsonResponse'] = response
                                        resp_db['timestamp'] = datetime.strftime(timezone.now(), "%c")
                                        APIRequestMonitoring.objects.create(method=request.method, path=request.path, api_user=request.user, body=request_body,
                                            request=req_db, response=resp_db
                                        )
                                        return Response(response, status=http_status.HTTP_400_BAD_REQUEST)
                                    else:
                                        collect_transactions = global_tx.collect_transactions.all().filter(partner__api_call_type=PartnerApiCallType.inbound)
                                        if collect_transactions:
                                            for collect_tx in collect_transactions:
                                                collect_tx.status = CollectTransactionStatus.collect_ready
                                                collect_tx.save()
                                            global_tx_model = apps.get_model('bemoSenderr.GlobalTransaction').objects.filter(uuid=global_tx.uuid).update(status=GlobalTransactionStatus.collectransaction_in_progress)
                                            push_globaltx_datastore(instance=global_tx, status=GlobalTransactionStatus.collectransaction_in_progress)
                                        response['response']['code'] = 2000
                                        response['response']['message'] = bemoSenderr_API_MESSAGE_CODES[2000]
                                        response['response']['data'] = {
                                            "paymentOrder":{
                                                "payment":{
                                                    "code": str(code),
                                                    "status": "done",
                                                    "date": date_str
                                                }
                                            }
                                        }
                                        resp_db['httpStatus'] = http_status.HTTP_200_OK
                                        resp_db['jsonResponse'] = response
                                        resp_db['timestamp'] = datetime.strftime(timezone.now(), "%c")
                                        APIRequestMonitoring.objects.create(method=request.method, path=request.path, api_user=request.user, body=request_body,
                                            request=req_db, response=resp_db
                                        )
                                        return Response(response, status=http_status.HTTP_200_OK)
                            elif token != api_collect_token.token:
                                response['response']['code'] = 2210
                                response['response']['message'] = bemoSenderr_API_MESSAGE_CODES[2210]
                                response['response']['data'] = ""
                                resp_db['httpStatus'] = http_status.HTTP_400_BAD_REQUEST
                                resp_db['jsonResponse'] = response
                                resp_db['timestamp'] = datetime.strftime(timezone.now(), "%c")
                                APIRequestMonitoring.objects.create(method=request.method, path=request.path, api_user=request.user, body=request_body,
                                    request=req_db, response=resp_db
                                )
                                return Response(response, status=http_status.HTTP_400_BAD_REQUEST)
                        ## Collect Code not found
                        else:
                            response['response']['code'] = 2202
                            response['response']['message'] = bemoSenderr_API_MESSAGE_CODES[2202]
                            response['response']['data'] = ""
                            resp_db['httpStatus'] = http_status.HTTP_400_BAD_REQUEST
                            resp_db['jsonResponse'] = response
                            resp_db['timestamp'] = datetime.strftime(timezone.now(), "%c")
                            APIRequestMonitoring.objects.create(method=request.method, path=request.path, api_user=request.user, body=request_body,
                                request=req_db, response=resp_db
                            )
                            return Response(response, status=http_status.HTTP_400_BAD_REQUEST)
                except Exception as e:
                    print(e)
                    print("Exception caught ", e)
                    response['response']['code'] = 1000
                    response['response']['message'] = bemoSenderr_API_MESSAGE_CODES[1000]
                    response['response']['data'] = ""
                    resp_db['httpStatus'] = http_status.HTTP_500_INTERNAL_SERVER_ERROR
                    resp_db['jsonResponse'] = response
                    resp_db['timestamp'] = datetime.strftime(timezone.now(), "%c")
                    APIRequestMonitoring.objects.create(method=request.method, path=request.path, api_user=request.user, body=request_body,
                        request=req_db, response=resp_db
                    )
                    return Response(response, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)

            """
            GetDailyAccountStatement Service:
            the codes:
            2000 1000 1001 1002 1003 1005 2500 2501 2503 
            """
            if req_body.get('request', None).get('service', None).get('name', None) == "GetDailyAccountStatement":
                print('-------------- GetDailyAccountStatement Service -------------')
                reqBodySchema = get_daily_account_statement_schema
                print("Client IP", get_client_ip(request))
                try:
                    try:
                        validate(instance=req_body, schema=reqBodySchema)
                    except:
                        response['response']['code'] = 1005
                        response['response']['message'] = bemoSenderr_API_MESSAGE_CODES[1005]
                        response['response']['data'] = ""
                        resp_db['httpStatus'] = http_status.HTTP_400_BAD_REQUEST
                        resp_db['jsonResponse'] = response
                        resp_db['timestamp'] = datetime.strftime(timezone.now(), "%c")
                        APIRequestMonitoring.objects.create(method=request.method, path=request.path, api_user=request.user, body=request_body,
                            request=req_db, response=resp_db
                        )
                        return Response(response, status=http_status.HTTP_400_BAD_REQUEST)
                    statements = req_body.get('request', None).get('service', None).get('data', None).get('statements', None)
                    ## Statements exist and len(statements) <= 0
                    if statements and len(statements) <= 2:
                        response['response']['code'] = 2000
                        response['response']['message'] = bemoSenderr_API_MESSAGE_CODES[2000]
                        response['response']['data']['statements'] = list()
                        for statement in statements:
                            account = statement.get('account', None)
                            date = statement.get('date', None)
                            
                            statement_data = response['response']['data']['statements']
                            data = {}
                            if account:
                                # Account not missing 
                                if date:
                                    # Date not missing
                                    print('Processing account ', account)
                                    print("Date ", date)
                                    partner_sett_acc = PartnerSettlementAccount.objects.filter(partner=partner, account_number=account).first()
                                    print('partner settlement account ', partner_sett_acc)
                                    if partner_sett_acc and partner_sett_acc.active:
                                        # Partner settlement account exists and active
                                        print('Partner settlement account exists and active ')
                                        
                                        date = datetime.strptime(date,"%Y-%m-%d")
                                        statement_date = date
                                        end_of_day = timezone.make_aware(datetime.combine(date, time.max), timezone.get_current_timezone())
                                        start_of_day = timezone.make_aware(datetime.combine(date, time.min), timezone.get_current_timezone())
                                        print('Start of day ', start_of_day)
                                        print('End of day ', end_of_day)
                                        req_end_month = datetime.combine(date, time.max)
                                        req_start_month = date.replace(day=1)
                                        req_start_month = datetime.combine(req_start_month, time.min)
                                        req_start_month = timezone.make_aware(req_start_month, timezone.get_current_timezone())
                                        req_end_month = timezone.make_aware(req_end_month, timezone.get_current_timezone())
                                        req_end_month = last_day_of_month(req_end_month)
                                        print("requested start of the month ", req_start_month)
                                        print("requested end of the month ", req_end_month)
                                        date_formatted = date.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]+"Z"
                                        data['account'] = account
                                        data['date'] = date_formatted
                                        data['entries'] = list()
                                        
                                        entry = {}
                                        tx_list = CollectTransaction.objects.filter(partner=partner, status=CollectTransactionStatus.collected).prefetch_related("globaltransaction_set")
                                        i = 0
                                        global_transactions = list()
                                        if tx_list:
                                            for tx in tx_list:
                                                global_tx = tx.globaltransaction_set.all().first()
                                                print(global_tx.payment_date)
                                                if global_tx.payment_date >= req_start_month and global_tx.payment_date <= req_end_month and global_tx.status == GlobalTransactionStatus.success:
                                                    global_transactions.append({
                                                        "collect_code": tx.collect_code,
                                                        "exchange_rate_snapshot": tx.exchange_rate_snapshot,
                                                        "global_tx": tx.globaltransaction_set.all().first()
                                                        }
                                                    )
                                            ## Build BALANCE Response 
                                            entry_balance = {}
                                            entry_balance['row'] = 0
                                            entry_balance['orderDate'] = date_formatted
                                            entry_balance['type'] = 'BALANCE'
                                            entry_balance['totalDailyBalanceAmount'] = 0
                                            entry_balance['totalMonthlyBalanceAmount'] = 0
                                            entry_balance['totalDailyCommissionAmount'] = 0
                                            entry_balance['totalMonthlyCommissionAmount'] = 0
                                            entry_balance['currency'] = str(partner.currency.iso_code).upper()
                                            entries = list()
                                            for tx in global_transactions:
                                                ## Build COMMISSION Response 
                                                i = i + 1
                                                entry = {}
                                                created_at = datetime.strftime(tx['global_tx'].created_at, "%Y-%m-%d %H:%M:%S.%f")
                                                converted_amount = float(tx['global_tx'].parameters['amount_destination']) / float(tx['exchange_rate_snapshot']['settlement_to_destination_rate'])
                                                print(converted_amount)
                                                entry["row"] = i
                                                entry["orderDate"] =  str(created_at)
                                                entry["paymentDate"] = datetime.strftime(tx['global_tx'].payment_date, "%Y-%m-%d %H:%M:%S.%f")
                                                entry["type"] = "COMMISSION"
                                                entry["paymentCode"] = tx['collect_code']
                                                entry["amount"] = float(tx['exchange_rate_snapshot']['commission_percentage']) * converted_amount
                                                entry["currency"] = str(partner.currency.iso_code).upper()
                                                entries.append(entry)
                                                ## Build TRANSFER Response 
                                                entry = {}
                                                i = i + 1
                                                entry['row'] = i
                                                entry['orderDate'] = str(created_at)
                                                entry['paymentDate'] = datetime.strftime(tx['global_tx'].payment_date, "%Y-%m-%d %H:%M:%S.%f")
                                                entry['type'] = 'TRANSFER'
                                                entry['paymentCode'] = tx['collect_code']
                                                entry['amount'] = tx['global_tx'].parameters['amount_destination']
                                                entry['currency'] = str(partner.currency.iso_code).upper()
                                                entry['rate'] = str(tx['exchange_rate_snapshot']['settlement_to_destination_rate'])
                                                entry['convertedAmount'] = converted_amount
                                                entry['recipient'] = tx['global_tx'].receiver_snapshot['first_name'] + " " + tx['global_tx'].receiver_snapshot['last_name']
                                                print('Entry : ', entry)
                                                entries.append(entry)
                                                entry_balance['totalMonthlyBalanceAmount'] = entry_balance['totalMonthlyBalanceAmount'] + converted_amount
                                                tx_commission = float(tx['exchange_rate_snapshot']['commission_percentage']) * converted_amount
                                                entry_balance['totalMonthlyCommissionAmount'] = entry_balance['totalMonthlyCommissionAmount'] + tx_commission
                                                if tx['global_tx'].payment_date <= end_of_day and tx['global_tx'].payment_date >= start_of_day: 
                                                    print('Adding daily balance and commission')
                                                    entry_balance['totalDailyBalanceAmount'] = float(entry_balance['totalDailyBalanceAmount']) + converted_amount
                                                    entry_balance['totalDailyCommissionAmount'] = float(entry_balance['totalDailyCommissionAmount']) + tx_commission
                                            entries.insert(0, entry_balance)
                                            data['entries'] = entries
                                    elif partner_sett_acc and not partner_sett_acc.active:
                                        print("account not active")
                                        data['account'] = account
                                        data['code'] = 2502
                                        data['message'] = bemoSenderr_API_MESSAGE_CODES[2502] 
                                    else:
                                        print('Partner Settlement account does not exist')
                                        data['account'] = account
                                        data['code'] = 2500
                                        data['message'] = bemoSenderr_API_MESSAGE_CODES[2500]
                                        
                                else:
                                    print('date missing or invalid')
                                    data['account'] = account
                                    data['code'] = 2501
                                    data['message'] = bemoSenderr_API_MESSAGE_CODES[2501]
                            
                            else:
                                print('account missing or invalid')
                                data['account'] = account
                                data['code'] = 2500
                                data['message'] = bemoSenderr_API_MESSAGE_CODES[2500]
                            response['response']['data']['statements'].append(data)
                    # Too many statements. 
                    else:
                        print('Too many statements .')
                        response['response']['code'] = 2503
                        response['response']['message'] = bemoSenderr_API_MESSAGE_CODES[2503]
                        response['response']['data'] = ""
                        response = dict(sorted(response.items()))
                        resp_db['httpStatus'] = http_status.HTTP_400_BAD_REQUEST
                        resp_db['jsonResponse'] = response
                        resp_db['timestamp'] = datetime.strftime(timezone.now(), "%c")
                        APIRequestMonitoring.objects.create(method=request.method, path=request.path, api_user=request.user, body=request_body,
                            request=req_db, response=resp_db
                        )
                        return Response(response, status=http_status.HTTP_400_BAD_REQUEST)
                    response = dict(sorted(response.items()))
                    resp_db['httpStatus'] = http_status.HTTP_200_OK
                    resp_db['jsonResponse'] = response
                    resp_db['timestamp'] = datetime.strftime(timezone.now(), "%c")
                    APIRequestMonitoring.objects.create(method=request.method, path=request.path, api_user=request.user, body=request_body,
                        request=req_db, response=resp_db
                    )
                    return Response(response, status=http_status.HTTP_200_OK)
                except Exception as e:
                    print(e)
                    print("Exception caught ", e)
                    response['response']['code'] = 1000
                    response['response']['message'] = bemoSenderr_API_MESSAGE_CODES[1000]
                    response['response']['data'] = ""
                    resp_db['httpStatus'] = http_status.HTTP_500_INTERNAL_SERVER_ERROR
                    resp_db['jsonResponse'] = response
                    resp_db['timestamp'] = datetime.strftime(timezone.now(), "%c")
                    APIRequestMonitoring.objects.create(method=request.method, path=request.path, api_user=request.user, body=request_body,
                        request=req_db, response=resp_db
                    )
                    return Response(response, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)

            else:
                response['response']['code'] = 1002
                response['response']['message'] = bemoSenderr_API_MESSAGE_CODES[1002]
                response['response']['data'] = ""
                resp_db['httpStatus'] = http_status.HTTP_400_BAD_REQUEST
                resp_db['jsonResponse'] = response
                resp_db['timestamp'] = datetime.strftime(timezone.now(), "%c")
                APIRequestMonitoring.objects.create(method=request.method, path=request.path, api_user=request.user, body=request_body,
                    request=req_db, response=resp_db
                )
                return Response(response, status=http_status.HTTP_400_BAD_REQUEST)
    else:
        response['response']['code'] = 1005
        response['response']['message'] = bemoSenderr_API_MESSAGE_CODES[1005]
        response['response']['data'] = ""
        resp_db['httpStatus'] = http_status.HTTP_400_BAD_REQUEST
        resp_db['jsonResponse'] = response
        resp_db['timestamp'] = datetime.strftime(timezone.now(), "%c")
        APIRequestMonitoring.objects.create(method=request.method, path=request.path, api_user=request.user, body=request_body,
            request=req_db, response=resp_db
        )
        return Response(response, status=http_status.HTTP_400_BAD_REQUEST)
