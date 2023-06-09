from django.apps import apps
from loguru import logger
import requests
import json
from random import random
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
import datetime
from bemoSenderr.models.partner.services.state_code_gen import StateCodeGenerator


class SidniService():

    @logger.catch
    def generate_reference_number(self):
        number = int(random() * 99999999999)
        kyc_verification_model = apps.get_model('bemoSenderr', 'KycVerificationRequest')
        sidni_queryset = kyc_verification_model.objects.filter(partner_response__contains={"userReference": f"{number}"})
        if len(sidni_queryset) > 0:
            logger.info('USER REFERENCE EXISTS RETRYING')
            return self.generate_reference_number()
        else:
            return number

    @logger.catch
    def get_cust_kyc_id(self):
        try:
            number = int(random() * 99999999999)
            kyc_verification_model = apps.get_model('bemoSenderr', 'KycVerificationRequest')
            sidni_cust_id_queryset = kyc_verification_model.objects.filter(custom_transaction_id=str(number))
            sidni_user_ref_queryset = kyc_verification_model.objects.filter(partner_response__contains={"userReference": f"{number}"})
            logger.info(f'sidni cust id queryset : {sidni_cust_id_queryset}')
            logger.info(f'sidni user ref queryset : {sidni_user_ref_queryset}')
            if len(sidni_cust_id_queryset) > 0 and len(sidni_user_ref_queryset) > 0:
                logger.info('CUSTOMER TRANSACTION ID EXISTS RETRYING')
                return self.get_cust_kyc_id()
            else:
                number = str(f"00000000000{number}")[-11:]
                return number
        except Exception as e:
            logger.info(e.args)

    @logger.catch
    def verify_kyc_sources(self, data_sources=None):
        is_verified = False
        for data_source in data_sources:
            if data_source['type'] == 'CREDIT_FILE':
                is_verified = is_verified if is_verified else data_source['verifiedNameAndDOB'] and data_source['verifiedNameAndAddress']
                logger.info(f'FINAL VERIFICATION FROM SOURCES {is_verified}')
                break
        return is_verified

    @logger.catch
    def handle_missing_fields(self, user_snapshot=None, cust_transaction_id=None):
        missing_fields = ""
        first_name = user_snapshot.get('first_name', False)
        last_name = user_snapshot.get('last_name', False)
        address_1 = user_snapshot.get('address_1', False)  # Street Address
        city = user_snapshot.get('city', False)
        zip_code = user_snapshot.get('zip_code', False)
        phone_number = user_snapshot.get('phone_number', False)
        birth_date = user_snapshot.get('birth_date', False)
        country = user_snapshot.get('country', False)  # Country iso code
        state_code_service = StateCodeGenerator()
        state_code = None
        state_code = state_code_service.get_state_code(zip_code, country)
        logger.info(f'This is the state code : {state_code}')
        if state_code in ['Unknown error! Please try again later.', 'Unable to retrieve the[STATE_NAME] code.', 'Missing parameters', 'Invalid parameters', ]:
            state_code = None
        address_type = 'Current'
        phone_type = 'Mobile'
        ref_number = self.generate_reference_number()
        if not first_name or not last_name or not address_type \
            or not address_1 or not city or not state_code \
            or not zip_code or not phone_number or not phone_type or not birth_date or not country:
            if not first_name:
                missing_fields += "" if len(
                    missing_fields) == 0 else ", " + "First Name"
            if not last_name:
                missing_fields += "" if len(
                    missing_fields) == 0 else ", " + "Last Name"
            if not address_type:
                missing_fields += "" if len(
                    missing_fields) == 0 else ", " + "Address Type"
            if not address_1:
                missing_fields += "" if len(
                    missing_fields) == 0 else ", " + "Street"
            if not city:
                missing_fields += "" if len(
                    missing_fields) == 0 else ", " + "City"
            if not state_code:
                missing_fields += "" if len(missing_fields) == 0 else ", " + \
                    "State/Province Code"
            if not country:
                missing_fields += "" if len(
                    missing_fields) == 0 else ", " + "Country Code"
            if not phone_type:
                missing_fields += "" if len(
                    missing_fields) == 0 else ", " + "Phone Type"
            if not phone_number:
                missing_fields += "" if len(
                    missing_fields) == 0 else ", " + "Phone Number"
            if not birth_date:
                missing_fields += "" if len(
                    missing_fields) == 0 else ", " + "Date of Birth"
            return [True, Response({
                "error": 400,
                "message": 'Missing parameters: ' + missing_fields if missing_fields else 'NONE',
                "payload": {
                    "customer": {
                        "custTransactionId": "UNDEFINED" if not cust_transaction_id else cust_transaction_id,
                        "userReference": ref_number,
                        "consentGranted": True,
                        "language": "en-CA"
                    },
                    "name": {
                        "firstName": 'UNDEFINED' if not first_name else first_name,
                        "lastName": 'UNDEFINED' if not last_name else last_name
                    },
                    "address": [
                        {
                            "addressType": 'UNDEFINED' if not address_type else address_type,
                            "addressLine": 'UNDEFINED' if not address_1 else address_1,
                            "city": 'UNDEFINED' if not city else city,
                            "province": 'UNDEFINED' if not state_code else state_code,
                            "postalCode": 'UNDEFINED' if not zip_code else zip_code,
                            "country": 'UNDEFINED' if not country else country
                        }
                    ],
                    "phone": [
                        {
                            "type": 'UNDEFINED' if not phone_type else phone_type,
                            "number": 'UNDEFINED' if not phone_number else phone_number
                        }
                    ],
                    "dateOfBirth": 'UNDEFINED' if not birth_date else birth_date
                }
            }, status=status.HTTP_400_BAD_REQUEST)]
        else:
            return [False, ref_number]

    @logger.catch
    def verify_individual(self, api_config=None, user_snapshot=None):
        try:
            report = ""
            time_now = datetime.datetime.strftime(timezone.now(), "%c")
            report += "SIDNI KYC VERIFICATION "
            report +=''
            cust_transaction_id = None
            cust_transaction_id = self.get_cust_kyc_id()
            errors = self.handle_missing_fields(
                user_snapshot, cust_transaction_id)
            response = None
            if errors[0]:
                return [False, report, errors[1], cust_transaction_id]
            elif not errors[0]:
                ref_number = errors[1]
                url = api_config["url"]
                api_key = api_config['credentials']["api_key"]
                phone_number = str(user_snapshot['phone_number'])[len(user_snapshot['phone_number']) - 10 : ]
                birth_date = str(user_snapshot.get('birth_date', "")).split(" ")[0]
                logger.info(f'this the birthdate {birth_date}')
                state_code_service = StateCodeGenerator()
                state_code = None
                state_code = state_code_service.get_state_code(user_snapshot['zip_code'], user_snapshot['country'])
                logger.info(f'This is the state code : {state_code}')
                if state_code in ['Unknown error! Please try again later.', 'Unable to retrieve the[STATE_NAME] code.', 'Missing parameters', 'Invalid parameters', ]:
                    state_code = None
                postal_code = str(user_snapshot['zip_code']).replace(' ', '')
                payload = {
                    "customer": {
                        "custTransactionId": cust_transaction_id,
                        "userReference": ref_number,
                        "consentGranted": True,
                        "language": "en-CA"
                    },
                    "name": {
                        "firstName": user_snapshot['first_name'],
                        "lastName": user_snapshot['last_name']
                    },
                    "address": [
                        {
                            "addressType": "Current",
                            "addressLine": user_snapshot['address_1'],
                            "city": user_snapshot['city'],
                            "province":state_code,
                            "postalCode":postal_code,
                            "country":user_snapshot['country']
                        }
                    ],
                    "phone": [
                        {
                            "type": "Mobile",
                            "number": phone_number
                        }
                    ],
                    "dateOfBirth": birth_date
                }
                if not cust_transaction_id:
                    payload['customer'].pop('custTransactionId')
                headers = {
                    'Content-Type': 'application/json',
                    'User-Agent': 'request'
                }
                response = requests.post(url=url, headers=headers, auth=(api_key, ""), data=json.dumps(payload))
                logger.info(f"Response from sidni {response.json()}")
                is_verified = False
                report += "REQUEST :" + "\n" + json.dumps(payload) + "\n"
                if not response:
                    return [is_verified, report, Response({
                        "error": 500,
                        "message": 'KYC Query error'
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    , cust_transaction_id]
                elif response and response.status_code != 200:
                    return [is_verified, report, Response({
                        "error": response.status_code,
                        "message": response.reason,
                        "body": response.json(),
                        "payload": payload
                    }, status=response.status_code)
                    , cust_transaction_id]
                
                if response and response.json():
                    verified_by_sources = self.verify_kyc_sources(response.json()['dataSources'])
                    is_verified = response.json().get('verified', False) or verified_by_sources
                    logger.info(f"IS VERIFIED : {is_verified if is_verified else 'FAILED'}")
                    report += f"SIDNI RESULT : {is_verified if is_verified else 'FAILED'}"
                return [is_verified, report, Response(response.json(), status=response.status_code), cust_transaction_id]
        except Exception as e:
            logger.info(e.args)
            report  += "\n" + str(e)
            return [False, report, response, cust_transaction_id]
            