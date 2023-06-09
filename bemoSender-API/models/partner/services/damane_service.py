from loguru import logger
import requests
import json
from bemosenderrr.models.base import CollectTransactionStatus
from bemosenderrr.models.partner.partner import Country
from bemosenderrr.models.partner.services.utils import getTransactionId
from django.apps import apps

class DamaneService():

    @logger.catch
    def handle_response(self, response=None):
        try:
            if not response:
                return {
                    'yx-message': 'partner-server-error',
                    'partner-response': str(response)
                }
            else:
                return response.json()

        except Exception as e:
            logger.info(e)
            return {
                'yx-message': 'partner-server-error',
                'partner-response': str(response)
            }


    @logger.catch
    def create_order(self, api_config=None, user_snapshot=None, receiver_snapshot=None, parameters=None, collect_uuid=None, collect_code=None, dirham_transaction_code=None):
        response = damaneTxId = payload = damane_nen_code = damane_headers = None
        try:
            url = api_config["url"]
            damaneTxId = getTransactionId(9)
            request_id = "yx" + str(collect_uuid)
            collect_transaction_model = apps.get_model(
                'bemosenderrr', 'CollectTransaction')
            instance = collect_transaction_model.objects.get(uuid=collect_uuid)
            delivery_method = instance.globaltransaction_set.all().first().collect_method
            if "cash" in str(delivery_method).lower():
                delivery_method = "Cash Pick-Up"
            user_country = Country.objects.get(iso_code=parameters['origin_country']).iso_code
            receiver_country = Country.objects.get(iso_code=parameters['destination_country']).iso_code
            delivery_methods = {
                "cashAtm": 0, 			# Both ATM and agencies
                "Cash Pick-Up": 1, 		# To agencies only
                "atm": 2, 			    # To ATM only
                "bankCard": 3, 			# Directed to bankcards
                "Bank Transfer": 4, 	    # Direct to bank account
                "mobileAccount": 5 	    # Direct to mobile account
            }
            destinationCurrencyCode = instance.globaltransaction_set.all(
            ).first().parameters['currency_destination']
            senderrIdentificationDocument = user_snapshot['document']['type']
            if str(senderrIdentificationDocument).lower() in 'passport':
                senderrIdentificationDocument = 'INTERNATIONAL_PASSEPORT'
            elif str(senderrIdentificationDocument).lower() in str("Driver's license").lower():
                senderrIdentificationDocument = "DRIVING_LICENCE"
            elif str(senderrIdentificationDocument).lower() in str('ID card').lower():
                senderrIdentificationDocument = 'NATIONAL_ID_CARD'
            elif str(senderrIdentificationDocument).lower() in str('Others').lower():
                pass
            elif str(senderrIdentificationDocument).lower() in str('O').lower():
                senderrIdentificationDocument = 'FOREIGNER_ID_CARD'
            else:
                senderrIdentificationDocument = 'FOREIGNER_ID_CARD'
            # TODO parse user_data to variables
            senderr_phone_number = str(user_snapshot['phone_number'])
            if senderr_phone_number[0] == '+':
                senderr_phone_number = senderr_phone_number.replace('+', '00')
            receiver_phone_number = str(user_snapshot['phone_number'])
            if receiver_phone_number[0] == '+':
                receiver_phone_number = receiver_phone_number.replace('+', '00')
            payload = {
                "TASK_ID": 213,
                "IDENT": {"LOGIN": f"{api_config['credentials']['DamaneLogin']}", "PASSWORD": f"{api_config['credentials']['DamanePassword']}", "PIN": ""},
                "REQUESTID": request_id,
                "VARIABLES": {
                    "VARIABLE1": str(damaneTxId),  # transaction_id
                    # Amount in MAD
                    "VARIABLE2": parameters['amount_destination'],
                    # (MME or MR) Title of the senderr
                    "VARIABLE3": "MR" if (user_snapshot['gender'] == 'Male') else 'MME',
                    "VARIABLE4": user_snapshot['first_name'],
                    "VARIABLE5": "",
                    "VARIABLE6": user_snapshot['last_name'],
                    "VARIABLE7": "",
                    "VARIABLE8": senderr_phone_number,
                    "VARIABLE9": "Montreal",  # senderr address 1
                    "VARIABLE10": "",
                    "VARIABLE11": "H1H1H1",
                    "VARIABLE12": "Montreal",  # senderr city name
                    "VARIABLE13": user_country,  # ISO CODE
                    # senderr identificatio document type (FOREIGNER_ID_CARD, NATIONAL_ID_CARD, INTERNATIONAL_PASSEPORT, DRIVING_LICENCE)
                    "VARIABLE14": senderrIdentificationDocument,
                    # senderr Identification document number
                    "VARIABLE15": user_snapshot['document']['number'],
                    # (MME or MR) Title of the receiver
                    "VARIABLE16": "MR" if (receiver_snapshot['gender'] == 'Male') else 'MME',
                    "VARIABLE17": receiver_snapshot['first_name'],
                    "VARIABLE18": "",
                    "VARIABLE19": receiver_snapshot['last_name'],
                    "VARIABLE20": "",
                    # starts with 00
                    "VARIABLE21": receiver_phone_number,
                    # receiver identification document type (FOREIGNER_ID_CARD, NATIONAL_ID_CARD, INTERNATIONAL_PASSEPORT, DRIVING_LICENCE)
                    "VARIABLE22": "",
                    "VARIABLE23": "",  # receiver Identification document number
                    # (0 or 1) SMS Fund Delivery Confirmation
                    "VARIABLE24": "0",
                    # (0 to 5) Directed to Channel (0: Both ATM and agencies, 1: To agencies only, 2: To ATM only, 3: Directed to bankcards, 4: Direct to bank account, 5: Direct to mobile account)
                    "VARIABLE25": delivery_methods[delivery_method],
                    # Origin country ISO code
                    "VARIABLE26": user_country,
                    # Destination Country ISO code
                    "VARIABLE27": receiver_country,
                    # (Variable25 = 3 then 16ch. Variable25 = 4 then 26ch) Bank account or card number
                    "VARIABLE28": "",
                    "VARIABLE29": destinationCurrencyCode,  # Destination currency ISO code
                    # Message to view in the cash out receipt
                    "VARIABLE30": "Message to show in the cash receipt",
                    # (1: set available, 2: set blocked) Initial POST ORDER status available only if Variable25 =  0, 1 or 2
                    "VARIABLE31": "1",
                    # (string 255, FAMILY_HELP, BUSINESS, CHARITY, MEDICAL_ASSISTANCE) Reason of transfer
                    "VARIABLE32": parameters['reason_of_transfer'],
                    "VARIABLE33": "en",  # SMS Language,
                    "VARIABLE34": 0
                }
            }
            headers = {
                'User-Agent': 'request',
                'Content-Type': 'application/json'
            }
            response = requests.post(url=url, headers=headers, data=json.dumps(payload))
            response = self.handle_response(response)
            #logger.info(
            #    f'The headers {response.headers.__dict__}   {type(response.headers)}')
            #damane_headers = json.dumps(response.headers.__dict__['_store'])
            # damane_nen_code = damane_headers.get('FUNDEX-NEN-CODE', None) // TODO FOR PRODUCTION.
            damane_headers = response.get('response', None).get('headers', None)
            damane_nen_code = damane_headers.get('fundex-nen-code', None)
            status = CollectTransactionStatus.error
            print("response for create order ", response)
            del payload["IDENT"]
            response_with_headers = {
                "request": payload,
                "response": response,
                "damane_order_number": damaneTxId,
                "collect_code": damane_nen_code,
                "headers": damane_headers
            }
            if damane_headers.get('fundex-response-code', None) == "T215-20008":
                status = CollectTransactionStatus.not_found
            elif damane_nen_code and damane_headers.get('fundex-response-code', None) == "0":
                status = CollectTransactionStatus.collect_ready
            return [status, response_with_headers]
            """
            DAMANE STATUSES
            ===============
            (comes from `fundex-nen-status`)
            Availaible  --> collect_ready
            Blocked   --> blocked
            Cancelled  -->cancelled
            Paid   --> collected
            NotFound (fundex-response-code = `T215-20008`)  --> not_found
            """
        except Exception as e:
            logger.info(str(e))
            response = self.handle_response(response)
            response_with_headers = {
                "request": payload,
                "response": response,
                "damane_order_number": damaneTxId,
                "collect_code": damane_nen_code,
                "headers": damane_headers
            }
            status = CollectTransactionStatus.error
            return [status, response_with_headers]


    # TODO check wich parameters to add here for every service
    # Should be the same parameters for every service
    @logger.catch
    def check_status(self, params=None):
        try:
            url = params['api_config']['url']
            request_id = "yx" + str(params['collect_uuid'])
            amount = params['damane_amount_mad']
            # TODO check which fields of the user_data are these variables
            payload = {
                "TASK_ID": 215,
                "IDENT": {"LOGIN": f"{params['api_config']['credentials']['DamaneLogin']}", "PASSWORD": f"{params['api_config']['credentials']['DamanePassword']}", "PIN": ""},
                "REQUESTID": request_id,
                "VARIABLES": {
                    # fundex-nen-code
                    "VARIABLE1": params["damane_order_number"],
                    "VARIABLE2": amount,  # amount in MAD
                }
            }
            headers = {
                'Content-Type': 'application/json'
            }
            response = requests.post(url=url, headers=headers, data=json.dumps(payload))
            response = self.handle_response(response)
            #logger.info("Damane response")
            #logger.info(response)
            damane_headers = response.get('response', None).get('headers', None)
            damane_nen_status = damane_headers.get('fundex-nen-status', None)
            #logger.info(f"DAMANE NEN STATUS  {damane_nen_status}")
            status = CollectTransactionStatus.error
            if damane_nen_status == 'Available':
                logger.info('AVAILABLE WORKING..')
                status = CollectTransactionStatus.collect_ready
            elif damane_nen_status == 'Blocked':
                status = CollectTransactionStatus.blocked
            elif damane_nen_status == 'Cancelled':
                status = CollectTransactionStatus.canceled
            elif damane_nen_status == 'Paid':
                status = CollectTransactionStatus.collected
            elif damane_headers.get('fundex-response-code', None) and damane_headers.get('fundex-response-code', None) == 'T215-20008':
                status = CollectTransactionStatus.not_found
            return status
            """
            DAMANE STATUSES
            ===============
            (comes from `fundex-nen-status`)
            Availaible  --> collect_ready
            Blocked   --> blocked
            Cancelled  -->cancelled
            Paid   --> collected
            NotFound (fundex-response-code = `T215-20008`)  --> not_found
            """
        except Exception as e:
            #TODO RETURN THE APPROPRIATE OBJECT
            logger.info(e.args)
            return CollectTransactionStatus.error

    @logger.catch
    def cancel_order(self, parameters=None):
        response = {}
        try:
            url = parameters['api_config']["url"]
            request_id = "yx" + str(parameters['collect_uuid'])
            amount = parameters['damane_amount_mad']
            api_config = parameters['api_config']
            # TODO check which fields of the user_data are these variables
            payload = {
                "TASK_ID": 214,
                "IDENT": {"LOGIN": f"{api_config['credentials']['DamaneLogin']}", "PASSWORD": f"{api_config['credentials']['DamanePassword']}", "PIN": ""},
                "REQUESTID": request_id,
                "VARIABLES": {
                    "VARIABLE1": parameters["damane_order_number"],  # transaction_id
                    "VARIABLE2": amount,  # amount in MAD
                }
            }
            headers = {
                'Content-Type': 'application/json'
            }
            response = requests.post(url=url, headers=headers, data=json.dumps(payload))
            response = self.handle_response(response)
            #logger.info("Damane response")
            #logger.info(response)
            damane_headers = response.get('response', None).get('headers', None)
            damane_nen_status = damane_headers.get('fundex-nen-status', None)
            #logger.info(f"DAMANE NEN STATUS  {damane_nen_status}")
            status = CollectTransactionStatus.error
            if damane_nen_status == '0' or not damane_nen_status:
                #logger.info('Succesfully cancelled Damane Transaction')
                status = CollectTransactionStatus.canceled
            else:
                status = CollectTransactionStatus.error

            return [status, response]
        except Exception as e:
            #TODO RETURN THE APPROPRIATE OBJECT
            logger.info(str(e))
            return [CollectTransactionStatus.error, response]

