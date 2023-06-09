from loguru import logger
import requests
import json
from bemoSenderr.models.base import CollectTransactionStatus
from bemoSenderr.models.partner.partner import Country, PartnerSettlementAccount
from bemoSenderr.models.partner.services.utils import getPaymentCode, getTransactionId
from django.apps import apps
from django.utils import timezone
from datetime import datetime


class DirhamService():

    @logger.catch
    def handle_response(self, response=None):
        try:
            if not response:
                return {
                    'yx-message': 'partner-server-error',
                    'partner-response': str(response)
                }
            else:
                logger.info(response.json())
                return response.json()

        except Exception as e:
            logger.info(e)
            return {
                'yx-message': 'partner-server-error',
                'partner-response': str(response)
            }


    @logger.catch
    def create_order(self, api_config=None, user_snapshot=None, receiver_snapshot=None, parameters=None, collect_uuid=None, collect_code=None, dirham_transaction_code=None):
        response = paymentCode = transaction_code = payload = None
        try:
            url = api_config["url"]
            # TODO Should be taken from the CollectTransactionAvailabilty model
            
            transaction_code = dirham_transaction_code
            paymentCode = collect_code
            collect_transaction_model = apps.get_model(
                'bemoSenderr', 'CollectTransaction')
            instance = collect_transaction_model.objects.get(uuid=collect_uuid)
            settlement_account = PartnerSettlementAccount.objects.filter(partner=instance.partner, active=True).first()
            origin_currency = parameters['currency_origin']
            if settlement_account:
                origin_currency = settlement_account.currency.iso_code
            payer = instance.partner.active_payer.name
            
            global_tx = instance.globaltransaction_set.all().first()
            DELIVERY = {
                "cash": 1, 		# To agencies only
                "bank": 2, 	# Direct to bank account
            }
            delivery_method = "cash"
            if "cash" in str(global_tx.collect_method).lower():
                delivery_method = DELIVERY["cash"]
            elif "bank" in str(global_tx.collect_method).lower():
                delivery_method = DELIVERY['bank']
            else:
                delivery_method = DELIVERY["cash"]
            logger.info(f'This is the delivery method : {delivery_method}')
            time_now = datetime.strftime(timezone.now(), "%Y-%m-%d %H:%M:%S")
            destination_currency = str(parameters['currency_destination']).upper()
            user_country = Country.objects.get(iso_code=parameters['origin_country']).iso_code
            receiver_country = Country.objects.get(iso_code=parameters['destination_country']).iso_code
            senderIdentificationDocument = user_snapshot['document']['type']
            if str(senderIdentificationDocument).lower() in 'passport':
                senderIdentificationDocument = 'INTERNATIONAL_PASSEPORT'
            elif str(senderIdentificationDocument).lower() in str("Driver's license").lower():
                senderIdentificationDocument = "DRIVING_LICENCE"
            elif str(senderIdentificationDocument).lower() in str('ID card').lower():
                senderIdentificationDocument = 'NATIONAL_ID_CARD'
            elif str(senderIdentificationDocument).lower() in str('Others').lower():
                pass
            elif str(senderIdentificationDocument).lower() in str('O').lower():
                senderIdentificationDocument = 'FOREIGNER_ID_CARD'
            else:
                senderIdentificationDocument = 'FOREIGNER_ID_CARD'
            payer_data = {
                "BMCE": 1001,
                "BARID": 1002
            }
            payload = {
                "request": {
                    "credentials": {
                        "partnerid": api_config['credentials']['Dirham_Partner_id'],
                        "password": api_config['credentials']['Dirham_Partner_Password']
                    },
                    "service": {
                        "name": "CreateOrder",
                        "version": "1.0",
                        "checksum": "",
                        "data": {
                            "paymentorders": {
                                "paymentorder": [
                                    {
                                        "order": {
                                            "reference": transaction_code,
                                            "date": time_now,  # dateTime.now() "2020-11-09 09:00:00"
                                            # iso code for origin counter
                                            "country": user_country,
                                            # origin currency
                                            "currency": origin_currency
                                        },
                                        "payment": {
                                            "code": paymentCode,  # What is this ??
                                            # iso code for destination country
                                            "country": receiver_country,
                                            "currency": destination_currency,  # destination currency
                                            "amount": parameters['amount_destination'],
                                            "delivery": delivery_method,  # validate theis
                                            "payer": str(payer_data.get(payer, None)) if payer else "",
                                            "accountnumber": ""
                                        },
                                        "sender": {
                                            "firstname": user_snapshot['first_name'],
                                            "middlename": "",
                                            "lastname": user_snapshot['last_name'],
                                            "address_1": user_snapshot['address_1'],
                                            "address_2": "",
                                            "city": user_snapshot['city'],
                                            "state": user_snapshot['state'],
                                            "zipcode": user_snapshot['zip_code'],
                                            "country": user_country,
                                            "phone1": user_snapshot['phone_number'],
                                            "phone2": "",
                                            "document": {
                                                "type": user_snapshot['document']['type'],
                                                "number": user_snapshot['document']['number'],
                                                "country": user_snapshot['document']['country'],
                                                "expirationdate": user_snapshot['document']['expiration_date']
                                            }
                                        },
                                        "recipient": {
                                            "firstname": receiver_snapshot['first_name'],
                                            "middlename": "",
                                            "lastname": receiver_snapshot['last_name'],
                                            "address_1": receiver_snapshot['address_1'],
                                            "address_2": "",
                                            "city": receiver_snapshot['city'],
                                            "state": receiver_snapshot['state'],
                                            "zipcode": receiver_snapshot['zip_code'],
                                            "country": receiver_country,
                                            "phone1": receiver_snapshot['phone_number'],
                                            "phone2": ""
                                        }
                                    }
                                ]
                            }
                        }
                    }
                }
            }
            if delivery_method == DELIVERY["bank"] and receiver_snapshot.get("account_number", None):
                payload['request']['service']['data']['paymentorders']['paymentorder'][0]['payment']['accountnumber'] = receiver_snapshot["account_number"]
                logger.info('BANK TRANSFER DIRHAM')
            headers = {
                'Content-Type': 'application/json'
            }
            response = requests.post(url=url, headers=headers, data=json.dumps(payload))
            response = self.handle_response(response)
            response_with_headers = {
                "request": payload,
                "response": response,
                "dirham_payment_code": paymentCode,  # paymentCode of Dirham
                "dirham_transaction_code": transaction_code,  # txCode of Dirham
                "collect_code": paymentCode
            }
            logger.info(response)
            payment_order = response.get('response', None).get('data', None).get('paymentorders', None).get('paymentorder', None)
            #payment_order = response.get('data', None).get('paymentorders', None).get('paymentorder', None) // TODO FOR PROD
            code = None
            status = None
            logger.info(payment_order)
            logger.info(payment_order.get('code', None))
            """
            DIRHAM STATUSES
            ===============
            not found   --> not_found
            blocked   --> blocked
            rejected   --> rejected
            amlblocked   --> aml_blocked
            onhold   --> on_hold (a bank transfer mostly)
            topay = sent  --> collect_ready
            topost = sent --> collect_ready
            reqpay = sent --> collect_ready
            canceled   -->  cancelled
            paid = done  --> collected
            posted = done  --> collected
            """
            if delivery_method == DELIVERY["bank"] and payment_order:
                status = CollectTransactionStatus.in_progress
                code = payment_order.get('code', None)
                if code == "2000":
                    status = CollectTransactionStatus.on_hold
                else:
                    status = CollectTransactionStatus.canceled
                return [status, response_with_headers]

            if payment_order:
                status = CollectTransactionStatus.in_progress
                code = payment_order.get('code', None) # TODO In production use this status[0].get('code', None)
                if code == '2000':
                    status = CollectTransactionStatus.collect_ready
                elif code != '2000':
                    status = CollectTransactionStatus.error
                    if code == '1000':
                        status = CollectTransactionStatus.on_hold
            else:
                status = CollectTransactionStatus.error
            return [status, response_with_headers]
        except Exception as e:
            logger.exception(e)
            status = CollectTransactionStatus.error
            response = self.handle_response(response)
            response_with_headers = {
                "request": payload,
                "response": response,
                "dirham_payment_code": paymentCode,  # paymentCode of Dirham
                "dirham_transaction_code": transaction_code,  # txCode of Dirham
                "collect_code": paymentCode
            }
            return [status, response_with_headers]


    @logger.catch
    def check_status(self, params=None):
        try:
            url = params['api_config']['url']
            payload = {
                "request": {
                    "credentials": {
                        "partnerid": params['api_config']['credentials']['Dirham_Partner_id'],
                        "password": params['api_config']['credentials']['Dirham_Partner_Password']
                    },
                    "service": {
                        "name": "CheckStatus",
                        "version": "1.0",
                        "checksum": "",
                        "data": {
                            "paymentorders": {
                                "paymentorder": [
                                    {
                                        "order": {
                                            # What is this ?
                                            "reference": params['dirham_transaction_code']
                                        },
                                        "payment": {
                                            # What is this ?
                                            "code": params['dirham_payment_code']
                                        }
                                    }
                                ]
                            }
                        }
                    }
                }
            }
            headers = {
                'Content-Type': 'application/json'
            }
            response = requests.post(url=url, headers=headers, data=json.dumps(payload))
            logger.info('IM HEREEEEEE')
            response = self.handle_response(response)
            # TODO figure out which status to use to return True
            # for now it's onhold (weird but yeah)
            ###
            """
            TODO
            For PRODUCTION use the appropriate STATUS
            """
            code = response.get('response', None).get('code', None)
            status = response.get('response', None).get('data', None).get('paymentorders',
                                                    None).get('paymentorder', None).get('payment', None).get('status', None)
            #status = response.get('data', None).get('paymentorders',None).get('paymentorder', None).get('payment', None).get('status', None) ##TODO FOR PROD!
            # TODO IN PRODUCTION paymentorders is a list() use this! 
            # payment_order = response.get('data', None).get('paymentorders',
            #                                        None).get('paymentorder', None).get('payment', None).get('status', None)
            logger.info(f'CODE {code}')
            logger.info(f'STATUS {status}')
            #TODO for production validate the status to use
            #if code == "2000" and status == 'posted': 
            #TODO TODO TODO 
            #TODO HANDLE OTHER STATUSES
            """
            not found
            onhold
            topay
            blocked
            reqpay
            paid
            canceled
            rejected
            
            """
            """
            in check status it's   'posted' and 'paid'  if paid return success else return in_progress
            """
            if code == "2000" and status in ['topay', 'topost', 'reqpay']:
                return CollectTransactionStatus.collect_ready
            elif code == "2000" and status in ['paid', 'posted']:
                return CollectTransactionStatus.collected
            elif code and status == "onhold":
                return CollectTransactionStatus.on_hold
            elif code  and status == "not found":
                return CollectTransactionStatus.not_found
            elif code and status == "blocked":
                return CollectTransactionStatus.blocked
            elif code and status == "amlblocked":
                return CollectTransactionStatus.aml_blocked
            elif code and status == "canceled":
                return CollectTransactionStatus.canceled
            elif code and status == "rejected":
                return CollectTransactionStatus.rejected
            else:
                logger.info(f'DIRHAM STATUS COULDNT BE FOUND ! code:{code} | status:{status}')
                return CollectTransactionStatus.error
            """
            DIRHAM STATUSES
            ===============
            not found
            blocked
            rejected
            amlblocked
            onhold
            topay = sent
            topost = sent
            reqpay = sent
            canceled
            paid = done
            posted = done
            """
            """
            DIRHAM API DOCS NOT UPDATED

            elif code and status == 'blocked':
                return CollectTransactionStatus.blocked
            elif code and status in ['topay', 'reqpay']:
                return CollectTransactionStatus.in_progress
            elif code and status == 'paid':
                return CollectTransactionStatus.collected
            elif code and status == 'not found':
                return CollectTransactionStatus.not_found
            elif code and status == 'rejected':
                return CollectTransactionStatus.aml_blocked
            """
        except Exception as e:
            logger.info(e)
            return CollectTransactionStatus.error


    @logger.catch
    def cancel_order(self, parameters=None):
        response = {}
        try:
            url = parameters['api_config']['url']
            payload = {
                "request": {
                    "credentials": {
                        "partnerid": parameters['api_config']['credentials']['Dirham_Partner_id'],
                        "password": parameters['api_config']['credentials']['Dirham_Partner_Password']
                    },
                    "service": {
                        "name": "CancelOrder",
                        "version": "1.0",
                        "checksum": "",
                        "data": {
                            "paymentorders": {
                                "paymentorder": [
                                    {
                                        "order": {
                                            # What is this ?
                                            "reference": parameters['dirham_transaction_code']
                                        },
                                        "payment": {
                                            # What is this ?
                                            "code": parameters['dirham_payment_code']
                                        }
                                    }
                                ]
                            }
                        }
                    }
                }
            }
            headers = {
                'Content-Type': 'application/json'
            }
            response = requests.post(url=url, headers=headers, data=json.dumps(payload))
            response = self.handle_response(response)
            """
            TODO
            For PRODUCTION use the appropriate STATUS
            """
            logger.info(response)
            code = response.get('response', None).get('code', None)
            status = response.get('response', None).get('data', None).get('paymentorders',
                                                    None).get('paymentorder', None).get('payment', None).get('status', None)
            ##status = response.get('data', None).get('paymentorders',None).get('paymentorder', None).get('payment', None).get('status', None) TODO FOR PROD!!
            # TODO IN PRODUCTION paymentorders is a list() use this! 
            # payment_order = paymentresponse.get('response', None).get('response', None).get('data', None).get('paymentorders',
            #                                        None).get('paymentorder', None).get('payment', None).get('status', None)
            logger.info(f'CODE {code}')
            logger.info(f'STATUS {status}')
            #TODO for production validate the status to use
            if code == "2000" and status == 'canceled':
                logger.info('Succesfully cancelled Dirham transaction')
                return [CollectTransactionStatus.canceled, response]
            elif code and status in ['topay', 'topay', 'reqpay', 'paid', 'rejected', 'blocked', 'not found', 'amlblocked', 'onhold', 'posted']:
                logger.info(f'CANNOT CANCEL DIRHAM ORDER STATUS {status}')
                return [CollectTransactionStatus.error, response]
            else:
                return [CollectTransactionStatus.error, response]
        except Exception as e:
            logger.info(f"Error occured with Dirham CancelOrder {e}")
            return [CollectTransactionStatus.error, response]


    @logger.catch
    def get_fx_rate(self, api_config=None):
        response = None
        try:
            url = api_config['url']
            payload = {
                "request": {
                    "credentials": {
                        "partnerid": api_config['credentials']['Dirham_Partner_id'],
                        "password": api_config['credentials']['Dirham_Partner_Password']
                    },
                    "service": {
                        "name": "GetFxRate",
                        "version": "1.0",
                        "checksum": "",
                        "data": {}
                    }
                }
            }
            headers = {
                'Content-Type': 'application/json'
            }
            response = requests.post(url=url, headers=headers, data=json.dumps(payload))
            logger.info(f"this is the response {response}")
            response = self.handle_response(response)
            return response
        except Exception as e:
            #TODO RETURN THE APPROPRIATE OBJECT
            logger.info(response)
            response = self.handle_response(response)
            return response

    @logger.catch
    def get_daily_account_statement(self, api_config=None, start_date=None, end_date=None):
        try:
            url = api_config['url']
            payload = {
                "request": {
                    "credentials": {
                        "partnerid": api_config['credentials']['Dirham_Partner_Password'],
                        "password": api_config['credentials']['Dirham_Partner_Password']
                    },
                    "service": {
                        "name": "GetDailyAccountStatement",
                        "version": "1.0",
                        "checksum": "",
                        "data": {
                            "statements": {
                                "statement": [
                                    {
                                        "account": api_config['credentials']['Dirham_Account_ID'],
                                        "date": start_date
                                    },
                                    {
                                        "account": api_config['credentials']['Dirham_Account_ID'],
                                        "date": end_date
                                    }
                                ]
                            }
                        }
                    }
                }
            }
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f"Basic {api_config['credentials']['token']}"
            }
            response = requests.request("POST", url, headers=headers, data=json.dumps(payload))
            response = self.handle_response(response)
            return response
        except Exception as e:
            logger.info(response)
            response = self.handle_response(response)
            return response

