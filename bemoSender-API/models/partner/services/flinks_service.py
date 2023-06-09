from time import sleep
from loguru import logger
import requests
import json
import re
import traceback
from bemosenderrr.logger import send_email_celery_exception


class FlinksService():

    def __init__(self, url=None, api_config=None):
        if api_config:
            self.time_interval_async = api_config.get('timeIntervalAsync', 10)
            self.time_limit_async = api_config.get('timeLimitAsync', 1800)
        else:
            self.time_interval_async = 10
            self.time_limit_async = 1800
        print(self.time_interval_async)
        print(self.time_limit_async)
        self.partner_name = "Flinks"
        self.url = url

    @logger.catch
    def handle_server_response(self, partner_name="Flinks", service=None, data=None):
        response_data = None
        try:
            response_data = data
            if not response_data:
                raise Exception
        except Exception as e:
            logger.info(f"{partner_name} ERR: Unable to retrieve response body\n {e.args}")
            response_data = {
            'yx-message': 'partner-server-error',
            'partner-response': data
            }
        logger.info(f"{partner_name} \n {service} \n {response_data}")
        return response_data

    
    def async_get_details(self, request_id=None, parameters=None):
        service = "GetAccountsDetail_Async"
        logger.info(request_id)
        is_verified = False
        headers = {
            'Content-Type': 'application/json',
        }
        partner_resp = {
            "auth": {},
            "query": {}
        }
        serverRes = requests.get(f"{self.url}/BankingServices/GetAccountsDetailAsync/{request_id}", headers=headers)
        partner_resp['query'] = self.handle_server_response("Flinks", service, serverRes.json())
        logger.info(partner_resp)
        if (partner_resp['query']["HttpStatusCode"] and partner_resp['query']["HttpStatusCode"] == 202):
            logger.info(f"{'Flinks'}: GetAccountsDetailAsync is still pending...retry")
            return [is_verified, partner_resp]
        elif partner_resp['query']["HttpStatusCode"] and partner_resp['query']["HttpStatusCode"] == 200:
            logger.info(f"{'Flinks'}: Got AccountsDetailAsync...return")
            if (partner_resp['query'].get('yx-message', None) or partner_resp['query'].get('HttpStatusCode', None) != 200):
                response_err = {
                    "9114":{
                        "partner_response": partner_resp
                    }
                }
                return [is_verified, response_err]
            
            logger.info(f"TEST FLINKS QUERY RES \n {partner_resp['query']}")
            
            account = partner_resp['query'].get('Accounts', None)[0]
            account_type = partner_resp.get('Login', None)
            formatted_resp = {}
            if account:
                client = account['Holder']
                clientName = str(re.sub(r"^(mme|mlle|mrs|mr|miss|ms|m)\.?\s{1}", "", client['Name'])).split(' ')
                formatted_resp = {
                    "first_name": clientName[0],
                    "last_name": " ".join(clientName[1:]),
                    "address_1": str(client.get('Address', None).get('CivicAddress', None)),
                    "city": str(client.get('Address', None).get('City', None)),
                    "state": str(client.get('Address', None).get('Province', None)).upper(),
                    "zip_code": str(client.get('Address', None).get('PostalCode', None)).replace(' ', ''),
                    "country_code": str(client.get('Address', None).get('Country', None)),
                    "email": str(client.get('Email', None)),
                    "phone_number": str(client.get('PhoneNumber',None))
                }
            if formatted_resp:
                is_verified = True
            response = {
                "partner_response": partner_resp,
                "response_formatted": formatted_resp
            }
            return [is_verified, response]
        else:
            return [is_verified, partner_resp]

    @logger.catch
    def authorize(self, login_id=None, request_time_limit=None):
        try:
            url = self.url
            logger.info('Initiate a session with Flinks API')
            headers = {
                'Content-Type': 'application/json',
            }
            json_data = {
                'LoginId': str(login_id),
                'MostRecentCached': True,
            }

            response = requests.post(f'{url}/BankingServices/Authorize', headers=headers, json=json_data)
            userData = self.handle_server_response("Flinks", "Authorize", response.json())
            return userData
        except Exception as e:
            return {"error": str(e)}

    @logger.catch
    def get_user_details(self, parameters=None):
        logger.info(self.url)
        login_id = parameters.get('login_id', None)
        account_id = parameters.get('account_id', None) 
        request_time_limit = parameters.get('request_time_limit', None)
        service = 'GetAccountsDetail'
        logger.info(f"Sync Request Account Data with Flinks API for {login_id}{(' wt account ' + account_id) if  account_id else ''}")
        is_verified = False
        partner_resp = {
            "auth": {},
            "query": {}
        }
        try:
            # DO THE COMPLETE AUTH FLOW
            # AUTHORIZE REQUEST
            partner_resp['auth'] = self.authorize(login_id, request_time_limit)
    
            # REJECT IF MISSING PARAMS
            logger.info(partner_resp)
            reqID = partner_resp["auth"].get('RequestId', None)
            accountType = partner_resp['auth']['Login']['Type'] or '' if partner_resp['auth'].get('Login', None) else ''
            if not reqID:
                missing_param_error = {
                    "1111":{
                        "params": ['requestID'],
                        "partner_response": partner_resp
                    }
                }
                return [is_verified, missing_param_error]
            if (str(accountType).lower() == 'business'):
                missing_param_error = {
                    "1112":{
                        "params": ['requestID'],
                        "partner_response": partner_resp
                    }
                }
                return [is_verified, missing_param_error]
            
            # PREPARE REQUEST
            body = {
                "RequestId": reqID,
                "WithAccountIdentity": True, # account infos like type, category, etc.
                "WithKYC": True, # account holder informations
                "WithTransactions": False,
                "WithBalance": True,
            }
            # ADD ACCOUNT ID FILTERING, if defined
            if (account_id):
                body['AccountsFilter'] = [account_id]
            # REQUEST ACCOUNT DETAILS
            logger.info(f"{service} for {reqID}\n {body}")
            headers = {
                'Content-Type': 'application/json',
            }
            data = requests.post(url=f"{self.url}/BankingServices/GetAccountsDetail", headers=headers, data=json.dumps(body))
            
            partner_resp['query'] = self.handle_server_response("Flinks", service, data.json())
            
            # IF OPERATION PENDING, DO ASYNC REQUEST
            # If timeout occurs during the async request, the function return an error which is caught by the `catch` statement
            if (partner_resp['query'].get("HttpStatusCode", None) and partner_resp['query'].get("HttpStatusCode", None) == 202):
                return [is_verified, partner_resp]
            # REJECT IF RESPONSE IS INVALID
            if (partner_resp['query'].get('yx-message', None) or partner_resp['query'].get('HttpStatusCode', None) != 200):
                response_err = {
                    "9114":{
                        "partner_response": partner_resp
                    }
                }
                return [is_verified, response_err]
            
            logger.info(f"TEST FLINKS QUERY RES \n {partner_resp['query']}")
            
            account = partner_resp['query'].get('Accounts', None)[0]
            account_type = partner_resp.get('Login', None)
            formatted_resp = {}
            if account:
                client = account['Holder']
                clientName = str(re.sub(r"^(mme|mlle|mrs|mr|miss|ms|m)\.?\s{1}", "", client['Name'])).split(' ')
                formatted_resp = {
                    "first_name": clientName[0],
                    "last_name": " ".join(clientName[1:]),
                    "address_1": str(client.get('Address', None).get('CivicAddress', "")),
                    "city": str(client.get('Address', None).get('City', "")),
                    "state": str(client.get('Address', None).get('Province', "")).upper(),
                    "zip_code": str(client.get('Address', None).get('PostalCode', "")).replace(' ', ''),
                    "country_code": str(client.get('Address', None).get('Country', "")),
                    "email": str(client.get('Email', "")),
                    "phone_number": str(client.get('PhoneNumber',""))
                }
            if formatted_resp:
                is_verified = True
            response = {
                "partner_response": partner_resp,
                "response_formatted": formatted_resp
            }
            return [is_verified, response]
        except Exception as e:
            getAccountDetailsErr = {}
            send_email_celery_exception(e)
            if (not e):
                errData = {
                "message": str(e) if e else 'An unknown error occurred',
                "error": traceback.format_exc()
                }
                getAccountDetailsErr ={
                    "9113":{
                        errData
                    }
                }
            getAccountDetailsErr["data"] = {}
            getAccountDetailsErr['data']['partner_resp'] = partner_resp
            logger.exception(f"{'Flinks'} ERR: An error occurred during {service}\n {getAccountDetailsErr}")
            return [is_verified, getAccountDetailsErr]
    