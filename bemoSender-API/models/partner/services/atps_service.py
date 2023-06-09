import json
from random import random
from loguru import logger
import requests
from django.apps import apps
from bemoSenderr.logger import send_email_celery_exception
from bemoSenderr.models.base import CollectTransactionStatus
from datetime import datetime
from django.core.mail import EmailMultiAlternatives

from bemoSenderr.models.partner.partner import Country


class ATPSService():
    def __init__(self) -> None:
        self.alpha_3_code = {
            "CI": "CIV",
            "ML": "MLI",
            "NE": "NER",
            "SN": "SEN",
            "CA": "CAN",
            "US": "USA"
        }
        self.status_map = {
            "cash": {
                "0":{
                    "2000": CollectTransactionStatus.collected,
                    "2001": CollectTransactionStatus.collect_ready,
                    "2003": CollectTransactionStatus.canceled
                },
                "10023": CollectTransactionStatus.error,
                "7000": CollectTransactionStatus.error
            },
            "mobile": {
                "0":{
                    "2000": CollectTransactionStatus.collect_ready,
                    "2001": CollectTransactionStatus.collected,
                    "2005": CollectTransactionStatus.canceled,
                    "2004": CollectTransactionStatus.on_hold
                },
                "10023": CollectTransactionStatus.error,
                "7000": CollectTransactionStatus.error
            }
        }
        #self.url = os.environ.get(f"ATPS_URL")

    def handle_status(self, code_etat=None, code_retour=None, delivery_method=None):
        if "cash" in str(delivery_method).lower():
            if code_retour == "0":
                return self.status_map["cash"]["0"][code_etat]
            elif code_retour == "10023":
                return self.status_map["cash"]['10023']
            else:
                return self.status_map["cash"]['7000']
        elif "mobile" in str(delivery_method).lower():
            if code_retour == "0":
                return self.status_map["mobile"]["0"][code_etat]
            elif code_retour == "10023":
                return self.status_map["mobile"]['10023']
            else:
                return self.status_map["mobile"]['7000']

    def handle_response(self, response=None):
        try:
            if not response:
                return {
                    'yx-message': 'partner-server-error',
                    'partner-response': str(response)
                }
            else:
                logger.info(response)
                return response.json()
        except Exception as e:
            logger.info(e)
            return {
                'yx-message': 'partner-server-error',
                'partner-response': str(response)
            }

    def get_country_credentials(self, iso_code=None, api_config=None):
        country_code = self.get_country_long_code(iso_code=iso_code)
        credentials = {
            "username": api_config['credentials'][f'username_{country_code}'],#os.environ.get(f"ATPS_LOGIN_{country_code}"),
            "password": api_config['credentials'][f'password_{country_code}']#os.environ.get(f"ATPS_PASSWORD_{country_code}"),
        }
        return credentials

    def get_country_long_code(self, iso_code=None):
        country = Country.objects.filter(iso_code=iso_code).first()
        if country:
            return country.alpha_3_code
        else:
            return self.alpha_3_code.get(str(iso_code).upper())

    def generate_reference_code(self):
        number = int(random() * 99999999999)
        atps_partner_queryset = apps.get_model(
            'bemoSenderr', 'CollectTransaction').objects.filter(partner__api_config__contains={"serviceClass": "ATPSService"}, collect_code=number)
        logger.info(f'ATPS queryset{atps_partner_queryset}')
        if len(atps_partner_queryset) > 0:
            logger.info('ATPS COLLECT CODE EXISTS RETRYING')
            return self.generate_reference_code()
        else:
            return str(number)

    def get_auth_token(self, iso_code=None, api_config=None):
        token = ""
        try:
            credentials = self.get_country_credentials(iso_code=iso_code, api_config=api_config)
            url = api_config['url']
            payload = {
                "platerfome": "WEB",
                "version": "2"
            }
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'request'
            }
            response = requests.post(url=f"{url}/api/auth/token", auth=(
                credentials['username'], credentials['password']), headers=headers, data=json.dumps(payload))
            response = self.handle_response(response=response)
            if not response.get('yx-message', None) and response.get('codeRetour', None) == "0":
                token = response.get('token')
            else:
                token = response
            return token
        except Exception as e:
            logger.info(f'ATPS GET AUTH TOKEN FAILED DUE TO {e}')
            response = self.handle_response(response=f'ATPS GET AUTH TOKEN FAILED DUE TO {e}')
            return response
    
    def get_partner_tx_fee(self, api_config=None,amount_destination=None, destination_iso_code=None, origin_iso_code=None):
        try:
            token = ""
            response = {}
            url = api_config['url']
            token = self.get_auth_token(iso_code=destination_iso_code, api_config=api_config)
            if isinstance(token, dict):
                return token
            destination_country = self.get_country_long_code(iso_code=destination_iso_code)
            origin_country = self.get_country_long_code(iso_code=origin_iso_code)
            payload = {
                "paysExpediteur": origin_country,
                "montant": str(amount_destination),
                "paysDestinataire": destination_country
            }
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'request',
                'Authorization': f"Bearer {token}"
            }
            response = requests.post(url=f"{url}/api/international/transfert/proxicash/tarif", headers=headers, data=json.dumps(payload))
            response = self.handle_response(response=response)
            if response.get('yx-message', None):
                return response
            else:
                montant_tarif = response.get("montantTarif", None)
                if montant_tarif:
                    return montant_tarif
                else:
                    return response
        except Exception as e:
            logger.info(f"ATPS GET PARTNER FX RATE FAILED DUE TO {e}")
            response = self.handle_response(response=f"ATPS GET PARTNER FX RATE FAILED DUE TO {e}")
            return response

    def getDocumentTypeID(self, doc_id=None):
        if str(doc_id).lower() in 'passport':
            doc_id = 'PP'
        elif str(doc_id).lower() in str("Driver's license").lower():
            doc_id = "PC"
        elif str(doc_id).lower() in str('ID card').lower():
            doc_id = 'CNI'
        elif str(doc_id).lower() in str('Others').lower():
            doc_id = 'PR'
        elif str(doc_id).lower() in str('O').lower():
            doc_id = 'PR'
        else:
            doc_id = 'PR'
        return doc_id


    def create_order(self, api_config=None, user_snapshot=None, receiver_snapshot=None, parameters=None, collect_uuid=None, collect_code=None, dirham_transaction_code=None):
        try:
            token = ""
            response_data = {
                "response": {},
                "request": {}
            }
            response = {}
            payload = {}
            url = api_config['url']
            destination_country_iso_code = parameters.get('destination_country')
            destination_country = self.get_country_long_code(iso_code=destination_country_iso_code)
            origin_country_iso_code = parameters.get('origin_country')
            reference_code = self.generate_reference_code()
            amount_destination = parameters.get('amount_destination')
            amount_destination_fee = self.get_partner_tx_fee(api_config=api_config, amount_destination=amount_destination, destination_iso_code=destination_country_iso_code, 
                origin_iso_code=origin_country_iso_code)
            
            if not amount_destination_fee or isinstance(amount_destination_fee, dict):
                logger.info(f"THIS IS THE AMOUNT DESTINATION FEE: {amount_destination_fee}")
                response_data['response'] = amount_destination_fee
                return [CollectTransactionStatus.error, response_data]
            type_piece = self.getDocumentTypeID(user_snapshot['document']['type'])
            instance = apps.get_model('bemoSenderr', 'CollectTransaction').objects.get(uuid=collect_uuid)
            global_tx = instance.globaltransaction_set.all().first()
            dateDelivrancePiece = global_tx.user.created_at
            dateDelivrancePiece = dateDelivrancePiece.strftime("%Y-%m-%d")
            delivery_method = global_tx.collect_method
            
            service_url = ""
            if "mobile" in str(delivery_method).lower():
                service_url = "/api/v2.0/transaction"
                canal = receiver_snapshot.get('mobile_network', None)
                phone_number = receiver_snapshot.get('phone_number', None)
                phone_number = str(phone_number).replace('+', "")
                phone_number = "00" + phone_number
                channel = apps.get_model('bemoSenderr', 'MobileNetwork').objects.filter(display_name=receiver_snapshot.get('mobile_network')).first()
                receiver_network = None
                if channel:
                    receiver_network = channel.partner_api_code_mapping.get('ATPSService')
                if not channel and not receiver_network:
                    response_data['response'] = {
                        "error": "Error in MobileNetwork Model"
                    }
                    return [CollectTransactionStatus.error, response_data]
                payload = {
					"reference": reference_code,
					"montant": float(amount_destination),
					"canal": receiver_network,
					"expediteur": {
						"prenom": user_snapshot['first_name'],
						"nom": user_snapshot['last_name'],
						"pays": self.get_country_long_code(iso_code=origin_country_iso_code)
					},
					"beneficiaire": {
						"prenom": receiver_snapshot['first_name'],
						"nom": receiver_snapshot['last_name'],
						"telephone": phone_number,
						"pays": destination_country
					}
				}
            else:
                service_url = "/api/international/transfert/proxicash/envoi"
                payload = {
                    "transactionOrigine": reference_code,
                    "montantEnvoi": amount_destination,
                    "montantFrais": amount_destination_fee,
                    "expediteur": {
                        "prenom": user_snapshot['first_name'],
                        "nom": user_snapshot['last_name'],
                        "telephone": user_snapshot['phone_number'],
                        "pays": self.get_country_long_code(iso_code=origin_country_iso_code),
                        "typePiece": type_piece,
                        "numeroPiece": user_snapshot['document']['number'],
                        "adresse": user_snapshot['address_1'], # TODO: Should address include City ?
                        "dateNaissance": str(user_snapshot['birth_date']).split(' ')[0],
                        "paysNaissance": str(user_snapshot.get('birth_country', destination_country)),
                        "dateDelivrancePiece":dateDelivrancePiece,
                        "dateExpirationPiece": str(user_snapshot['document']['expiration_date']).split(' ')[0]
                    },
                    "beneficiaire": {
                        "prenom": receiver_snapshot['first_name'],
                        "nom": receiver_snapshot['last_name'],
                        "telephone": receiver_snapshot['phone_number'],
                        "pays": destination_country,
                        "adresse": receiver_snapshot['address_1']
                    }
                }
            logger.info(payload)
            token = self.get_auth_token(iso_code=destination_country_iso_code, api_config=api_config)
            if isinstance(token, dict):
                response = self.handle_response(response=token)
                response_data['request'] = payload
                response_data['response'] = response
                return [CollectTransactionStatus.error, response_data]
            else:
                headers = {
                    'Content-Type': 'application/json',
                    'User-Agent': 'request',
                    'Authorization': f"Bearer {token}"
                }
                response_data['request'] = payload
                response = requests.post(url=f"{url}{service_url}", headers=headers, data=json.dumps(payload))
                response = self.handle_response(response=response)
                logger.info(response)
                if response.get('yx-message', None):
                    response_data['response'] = response
                    return [CollectTransactionStatus.error, response_data]
                else:
                    if response.get('codeRetour', None) == "0":
                        if response.get('codeTransfert', None):
                            
                            response_data['response'] = response
                            if "mobile" in str(delivery_method).lower():
                                atps_transaction_code = response.get('reference', None)
                            else:
                                atps_transaction_code = response.get('codeTransfert', None)
                            response_data['atps_transaction_code'] = atps_transaction_code
                            response_data['collect_code'] = atps_transaction_code
                            return [CollectTransactionStatus.collect_ready, response_data]
                        else:
                            response_data['response'] = response
                            return [CollectTransactionStatus.error, response_data]
                    else:
                        response_data['response'] = response
                        return [CollectTransactionStatus.error, response_data]
        except Exception as e:
            logger.info(f"ATPS CREATE ORDER FAILED DUE TO {e}")
            response_data['response'] = self.handle_response(response=f"ATPS CREATE ORDER FAILED DUE TO {e}")
            response_data['request'] = payload
            return [CollectTransactionStatus.error, response_data]

    def check_status(self, params=None):
        try:
            atps_transaction_code = params.get('atps_transaction_code', None)
            api_config = params['api_config']
            url = params['api_config']['url']
            if not atps_transaction_code:
                logger.info('NO ATPS TRANSFER CODE ASSIGNED')
                return  CollectTransactionStatus.error
            else:
                instance = apps.get_model('bemoSenderr', 'CollectTransaction').objects.get(uuid=params['collect_uuid'])
                global_tx = instance.globaltransaction_set.all().first()
                destination_country_iso_code = global_tx.parameters.get('destination_country')
                token = self.get_auth_token(iso_code=destination_country_iso_code, api_config=api_config)
                if isinstance(token, dict):
                    logger.info(token)
                    logger.info('FAILED TO GET AUTH TOKEN IN CHECK STATUS')
                    return CollectTransactionStatus.error
                headers = {
                    'Content-Type': 'application/json',
                    'User-Agent': 'request',
                    'Authorization': f"Bearer {token}"
                }
                delivery_method = global_tx.collect_method
                delivery_key = ""
                check_url = ""
                if "mobile" in str(delivery_method).lower():
                    check_url = "/api/v2.0/transaction/status?reference="
                    delivery_key = "mobile"
                else:
                    check_url = "/api/international/transfert/proxicash/status?codeTransfert="
                    delivery_key = "cash"
                response = requests.get(url=f"{url}{check_url}{atps_transaction_code}", headers=headers)
                logger.info(response.json())
                response = self.handle_response(response=response)
                if response.get('yx-message', None):
                    return CollectTransactionStatus.error
                else:
                    code_retour = response.get('codeRetour')
                    code_etat = response.get('codeEtat')
                    
                    status = self.handle_status(code_retour=code_retour, code_etat=code_etat, delivery_method=delivery_key)
                    logger.info(f"ATPS STATUS {status}")
                    if status:
                        return status
                    else:
                        return CollectTransactionStatus.error

        except Exception as e:
            logger.info(f"ATPS CHECK ORDER STATUS FAILED DUE TO {e}")
            return CollectTransactionStatus.error

    def cancel_order(self, parameters=None):
        try:
            api_config = parameters['api_config']
            _from = api_config['cancelEmails']['from']
            to = api_config['cancelEmails']['to']
            cc = api_config['cancelEmails']['cc']
            atps_transaction_code = parameters.get('atps_transaction_code', None)
            if not atps_transaction_code:
                logger.info('CANCEL ORDER FAILED ATPS_TRANSACTION_NOT_FOUND')
                return CollectTransactionStatus.not_found
            instance = apps.get_model('bemoSenderr', 'CollectTransaction').objects.get(uuid=parameters['collect_uuid'])
            global_tx = instance.globaltransaction_set.all().first()
            created_at = datetime.strftime(instance.updated_at,"%Y-%m-%dT%H:%M:%S.%fZ")
            user_snapshot = global_tx.user_snapshot
            sender_full_name = str(user_snapshot.get('first_name', "UNDEFINED")) + " " + str(user_snapshot.get('last_name', "UNDEFINED"))
            receiver_snapshot = global_tx.receiver_snapshot
            receiver_full_name = str(receiver_snapshot.get('first_name', "UNDEFINED")) + " " + str(receiver_snapshot.get('last_name', "UNDEFINED"))
            amount_destination = global_tx.parameters.get('amount_destination')
            logger.info(f"CREATED AT {created_at}")
            body = f"""
            Date: {created_at}
            Expéditeur: {sender_full_name}
            Bénéficiaire: {receiver_full_name}
            Code Proxicash: {atps_transaction_code}
            Montant: {amount_destination}
            """
            email = EmailMultiAlternatives(
                subject="Annulation code Proxicash",
                body=body,
                from_email=_from,
                to=to,
                cc=cc,
                reply_to=_from
            )
            status_email = email.send(fail_silently=True)
            logger.info(f"ATPS CANCELATION STATUS {status_email}")
            if status_email:
                logger.info(f"ATPS CANCELATION EMAIL SENT !!")
                return [CollectTransactionStatus.canceled, {}]
            else:
                logger.info(f"ATPS CANCELATION EMAIL FAILED !!")
                return [CollectTransactionStatus.error, {}]
        
        except Exception as e:
            logger.info(f"ATPS CANCEL ORDER  FAILED DUE TO {e}")
            return [CollectTransactionStatus.error, {}]
