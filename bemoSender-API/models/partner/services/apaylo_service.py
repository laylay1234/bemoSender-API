from datetime import datetime
from os import stat
from django.apps import apps
from loguru import logger
import requests
import json
import hashlib
import base64
from bemoSenderr.models.base import GlobalTransactionStatus, PartnerStatus

from bemoSenderr.models.partner.partner import Partner


class ApayloService():

    @logger.catch
    def generate_signature(self, api_key=None, shared_secret=None):
        if api_key and shared_secret:
            date_now = datetime.utcnow().strftime('%Y-%m-%d')
            concatenated_string = str(api_key) + str(shared_secret) + str(date_now)
            hash512_digest = hashlib.sha512(concatenated_string.encode('utf-8')).digest()
            signature = base64.b64encode(hash512_digest).decode()
            #print(signature)
            return signature
        else:
            return None

    @logger.catch
    def authenticate_transfer(self, api_config=None, ref_number=None, security_answer=None, hash_salt=None):
        signature = self.generate_signature(api_key=api_config['credentials']['api_key'], shared_secret=api_config['credentials']['shared_secret'])
        if not signature:
            return
        payload = {}
        try:
            url = api_config["url"] + "/Merchant/AuthenticateTransfer"
            payload = {
                "ReferenceNumber": ref_number,
                "SecurityAnswer": security_answer,
                "HashSalt": hash_salt
            }
            headers = {
                'Content-Type': 'application/json',
                'Key': api_config['credentials']['api_key'],
                'Signature': signature
            }
            response = requests.post(url=url, headers=headers, data=json.dumps(payload))
            return [response.json(), payload]
        except Exception as e:
            print(e.args)
            return [{"response":f"Exception caught {str(e)}"}, payload]

    def search_incoming_transfers(self, api_config=None, start_date=None, end_date=None):
        payload = {}
        signature = self.generate_signature(api_key=api_config['credentials']['api_key'], shared_secret=api_config['credentials']['shared_secret'])
        try:
            url = api_config["url"] + "/Merchant/SearchInteracEtransfers"
            account_number = api_config['credentials']['account_id']
            payload = {
                "StartDate": start_date,
                "EndDate": end_date,
                "AccountNumber": account_number
            }
            headers = {
                'Content-Type': 'application/json',
                'Key': api_config['credentials']['api_key'],
                'Signature': signature
            }
            response = requests.post(url=url, headers=headers, data=json.dumps(payload))
            return [response.json(), payload]
        except Exception as e:
            print(e.args)
            return [{"response":f"Exception caught {str(e)}"}, payload]

    @logger.catch
    def get_incoming_transfers(self, api_config=None, ref_number=None):
        payload = {}
        signature = self.generate_signature(api_key=api_config['credentials']['api_key'], shared_secret=api_config['credentials']['shared_secret'])
        try:
            url = api_config["url"] + "/Merchant/GetIncomingTransfers"
            payload = {
                "ReferenceNumber": ref_number
            }
            headers = {
                'Content-Type': 'application/json',
                'Key': api_config['credentials']['api_key'],
                'Signature': signature
            }
            response = requests.post(url=url, headers=headers, data=json.dumps(payload))
            return [response.json(), payload]
        except Exception as e:
            print(e.args)
            return [{"response":f"Exception caught {str(e)}"}, payload]

    @logger.catch
    def complete_transfer(self, api_config=None, ref_number=None):
        payload = {}
        signature = self.generate_signature(api_key=api_config['credentials']['api_key'], shared_secret=api_config['credentials']['shared_secret'])
        try:
            url = api_config["url"] + "/Merchant/CompleteTransfer"
            payload = {
                "ReferenceNumber": ref_number
            }
            headers = {
                'Content-Type': 'application/json',
                'Key': api_config['credentials']['api_key'],
                'Signature': signature
            }
            response = requests.post(url=url, headers=headers, data=json.dumps(payload))
            return [response.json(), payload]
        except Exception as e:
            print(e.args)
            return [{"response":f"Exception caught {str(e)}"}, payload]


    @logger.catch
    def send_interac_transfer(self, api_config=None, params=None):
        try:
            payload = {}
            signature = self.generate_signature(api_key=api_config['credentials']['api_key'], shared_secret=api_config['credentials']['shared_secret'])
            url = api_config["url"] + "/Merchant/SendInteracEtransfer"
            payload = {
                "CustomerName": params.get('full_name', None),
                "CustomerEmail": params.get('email', None),
                "Amount": float(params.get('amount', None)),
                "SecurityQuestion": params.get("security_question", None),
                "SecurityQuestionAnswer": params.get("security_answer", None),
                "Description": "Refund for invoice #" + params.get('description', None)
            }
            headers = {
                'Content-Type': 'application/json',
                'Key': api_config['credentials']['api_key'],
                'Signature': signature
            }
            response = requests.post(url=url, headers=headers, data=json.dumps(payload))
            return [response.json(), payload]
        except Exception as e:
            print(e.args)
            return [{"response":f"Exception caught {str(e)}"}, payload]


    @logger.catch
    def refund_interac_transfer(self, api_config=None, instance_uuid=None):
        try:
            apaylo = Partner.objects.filter(name="Apaylo").first()
            if apaylo and apaylo.status == PartnerStatus.active:
                api_config = apaylo.api_config
                global_transaction = apps.get_model("bemoSenderr.GlobalTransaction").filter(uuid=instance_uuid).select_related("user").first()
                description_counter = 1
                user_transactions_count = apps.get_model("bemoSenderr.GlobalTransaction").objects.filter(
                    status=GlobalTransactionStatus.refunded,
                    user=global_transaction.user
                ).count()
                app_settings = apps.get_model("bemoSenderr.AppSettings").objects.first()
                security_answer = app_settings.config.get('interacDeposit', None).get("secret", None).get('answer', None)
                security_question = app_settings.config.get('interacDeposit', None).get("secret", None).get('question', None)
                if user_transactions_count:
                    description_counter = user_transactions_count + 1
                params = {
                    "full_name": str(global_transaction.user.first_name) + " " + str(global_transaction.user.last_name),
                    "email": str(global_transaction.user.email),
                    "amount": str(global_transaction.parameters.get('total', None)),
                    "description": description_counter,
                    "security_question": security_question,
                    "security_answer": security_answer
                }
                return self.send_interac_transfer(api_config=api_config, params=params)[0]
        except Exception as e:
            print('exception caught while sending refund interac', e)
            return None

    @logger.catch
    def search_send_interac_etransfers(self, api_config=None, start_date=None, end_date=None):
        try:
            payload = {}
            signature = self.generate_signature(api_key=api_config['credentials']['api_key'], shared_secret=api_config['credentials']['shared_secret'])
            url = api_config["url"] + "/Merchant/SearchSendInteracEtransfer"
            payload = {
                "StartDate": start_date,
                "EndDate": end_date
            }
            headers = {
                'Content-Type': 'application/json',
                'Key': api_config['credentials']['api_key'],
                'Signature': signature
            }
            response = requests.post(url=url, headers=headers, data=json.dumps(payload))
            return [response.json(), payload]
        except Exception as e:
            print(e.args)
            return [{"response":f"Exception caught {str(e)}"}, payload]