
import json
from django.apps import apps

from loguru import logger
from bemoSenderr.models.base import GlobalTransactionStatus, VerificationStatus
from bemoSenderr.utils.appsync import make_client
from gql import gql
from bemoSenderr.utils.mutation_queries import CREATE_APPSETTINGS_MUTATION, CREATE_COLLECT_TX_MUTATION, CREATE_COUNTRY_MUTATION, CREATE_CURRENCY_MUTATION, UPDATE_APPSETTINGS_MUTATION, UPDATE_COLLECT_TX_MUTATION, UPDATE_COUNTRY_MUTATION, UPDATE_CURRENCY_MUTATION, UPDATE_GLOBAL_TX_MUTATION, UPDATE_USER_MUTATION

from bemoSenderr.utils.notifications import NotificationsHandler
from bemoSenderr.utils.pinpoint import PinpointWrapper
import boto3
from django.conf import settings



"""
TODO USING API KEY MEANING THAT RESPONSE WILL HAVE DATA KEY TO ENCAPSULATE THE BODY
"""
"""
This module is for creating mutations to sync data in the datastore.
"""



class CountryService(object):
    def __init__(self):
        self.client = make_client()

    """
    Sync country and update the datastore
    """
    def sync_country(self, country):
        try:
            params = {
                "id": str(country.uuid),
                "name": str(country.name),
                "iso_code": str(country.iso_code),
                "enabled_as_origin": country.enabled_as_origin,
                "enabled_as_destination": country.enabled_as_destination,
                "active": country.active,
                "calling_code": country.calling_code
            }
            query = UPDATE_COUNTRY_MUTATION
            try:
                response = self.client.execute(gql(query), variable_values=json.dumps({'input': params}))
                print('successfully updated country', country)
            except Exception as e:
                print(e)
                print("Exception! Country doesnt exist in Dynamodb")
                query = CREATE_COUNTRY_MUTATION
                response = self.client.execute(gql(query), variable_values=json.dumps({'input': params}))
                print("successfully created country", country)
        except Exception as e:
            print(e.args)


class CurrencyService(object):
    def __init__(self):
        self.client = make_client()

    def sync_currency(self, currency):
        """
        Sync currency and update the datastore
        """
        try:
            params = {
                "id": str(currency.uuid),
                "name": str(currency.name),
                "iso_code": str(currency.iso_code),
                "sign": currency.sign,
                "short_sign": currency.short_sign
            }
            query = UPDATE_CURRENCY_MUTATION
            try:
                response = self.client.execute(gql(query), variable_values=json.dumps({'input': params}))
                print(response)
            except Exception as e:
                print(e)
                print("Exception! Currency doesnt exist in Dynamodb")
                query = CREATE_CURRENCY_MUTATION
                response = self.client.execute(gql(query), variable_values=json.dumps({'input': params}))
                print(response)

        except Exception as e:
            print(e.args)


class SyncCollectTransactions():

    def __init__(self):
        self.client = make_client()

    """
    Sync CollectTransactions when the collect_code is available(collect_ready status)
    """
    def sync_created_collect_transaction(self, collect_tx_uuid=None):
        try:
            logger.info(f"Syncing collect_transaction with UUID : {collect_tx_uuid}")
            instance = apps.get_model('bemoSenderr.CollectTransaction').objects.get(uuid=collect_tx_uuid)
            partner_name = instance.partner.display_name
            items = instance.partner.api_config.get('img_urls', list())
            img_urls = list()
            global_tx = instance.globaltransaction_set.all().first()
            """
            Get partner url images
            """
            for img_url in items:
                img_urls.append(str(img_url['img_url']))
            try:
                params = {
                    "id": str(instance.uuid),
                    "status": str(instance.status),
                    "globalTransactionID": str(global_tx.uuid),
                    "partner_name": str(partner_name),
                    "collect_code": str(instance.collect_code) if instance.collect_code else "",
                    "img_urls": img_urls
                }

                query = CREATE_COLLECT_TX_MUTATION
                response = self.client.execute(gql(query), variable_values=json.dumps({'input': params}))
            except Exception as e:
                logger.info(str(e))
        except Exception as e:
            logger.info(e.args)

    def sync_updated_collect_transaction(self, collect_tx_uuid=None, status=None):
        try:
            logger.info(f"Syncing collect_transaction with UUID : {collect_tx_uuid}")
            instance = apps.get_model('bemoSenderr.CollectTransaction').objects.get(uuid=collect_tx_uuid)
            try:
                params = {
                    "id": str(instance.uuid),
                    "status": str(status),
                }
                query = UPDATE_COLLECT_TX_MUTATION
                response = self.client.execute(gql(query), variable_values=json.dumps({'input': params}))
                logger.info(f"Instance Status {status}")
                logger.info(f"Synced CollectTransaction Status {response.get('updateCollectTransaction').get('status', None)}")
            except Exception as e:
                logger.info(str(e))
        except Exception as e:
            logger.info(e.args)

"""
Sync email verification status to datastore to make the user email verified
"""
@logger.catch
def sync_email_verification(user):
    try:
        params = {
            "id": str(user.username)
        }
        print(params)
        print(params['id'])
        query = """
                query MyQuery($input: ID!) {
                    getUser(id: $input) {
                         user_status
                    }
                }
                """
        client = make_client()
        response = client.execute(gql(query), variable_values=json.dumps({'input': params['id']}))
        user_status = response.get('getUser', None).get('user_status', None)
        if user_status:
            print(response)
            params = {
                "id": str(user.username),
                "user_status": "CONFIRMED"
            }
            query = UPDATE_USER_MUTATION
            response = client.execute(gql(query), variable_values=json.dumps({'input': params}))
            print(response)
            return user_status
    except Exception as e:
        logger.info(str(e))
        return {"Exception": f"Exception caught {str(e)}"}



"""
Sync GlobalTransaction status to datastore 
(cancelled, new) are not taken into consideration because the cancelled status comes from a frontend call to prevent a signal loop and new is the initial status of the object.
"""
@logger.catch
def push_globaltx_datastore(instance=None, status=None):
    response = None
    if instance and status not in [GlobalTransactionStatus.new,]: 
        print(f"pushing globaltransaction status  {instance.status}")
        global_tx = apps.get_model('bemoSenderr.GlobalTransaction').objects.get(uuid=instance.uuid)
        try:
            client = make_client()
            params = {
                "id": str(instance.uuid),
                "status": str(status)
            }
            query = UPDATE_GLOBAL_TX_MUTATION
            response = client.execute(gql(query), variable_values=json.dumps({'input': params}))
            logger.info(f"Instance Status {status}")
            logger.info(f"Synced GlobalTransaction Status {response.get('updateGlobalTransaction').get('status', None)}")
            print("Successfully synced Global Transaction with UUID", global_tx.uuid)
        except Exception as e:
            logger.info(str(e))
            return {"Exception": f"Exception caught {str(e)}"}
    else:
        print(instance)
        print(instance.status)
        print(instance.uuid)
    return response


"""
Sync bank_verification_status and update kyc_level field in the datastore
"""
@logger.catch
def sync_bank_verification_status(user, instance):
    try:
        params = {
            "id": str(user.username)
        }
        query = """
                query MyQuery($input: ID!) {
                    getUser(id: $input) {
                        kyc_level bank_verification_status
                    }
                }
                """
        client = make_client()
        response = client.execute(gql(query), variable_values=json.dumps({'input': params['id']}))
        print(response)
        kyc_level = response.get('getUser', None).get('kyc_level', None)
        bank_verification_status = response.get('getUser', None).get('bank_verification_status', None)
        if bank_verification_status == "VERIFIED":
            print("Already verified with flinks!")
        else:
            user_tier = 0
            params = {
                "id": str(user.username),
                "bank_verification_status": "NOT_VERIFIED",
                "kyc_level": user_tier,
            }
            logger.info(kyc_level)
            if kyc_level is not None and instance.status == VerificationStatus.verified:
                logger.info('IS VERIFIED')
                user_tier = int(kyc_level) + 1
                params['bank_verification_status'] = "VERIFIED"
            elif kyc_level is not None and instance.status == VerificationStatus.unverified:
                logger.info('IS NOT VERIFIED')
                user_tier = kyc_level
            else:
                logger.info('THE ELSE')
                kyc_level = 0
                user_tier = 0
            logger.info(user_tier)
            logger.info(params)
            params['kyc_level'] = user_tier
            query = UPDATE_USER_MUTATION
            response = client.execute(gql(query), variable_values=json.dumps({'input': params}))
            try:
                language = user.locale
                error = False if instance.status == VerificationStatus.verified  else True
                if not language:
                    language = "FR"
                notif_service = NotificationsHandler()
                push_notif_data = notif_service.get_bank_verif_complete_push(status=instance.status, lang=language, vars=[user.first_name])
                pinpoint_service = PinpointWrapper()
                status_push = pinpoint_service.send_push_notifications_and_data(user_snapshot=instance.user_snapshot, user=instance.user, type="user_tier", data=push_notif_data, error=error,
                        new_user_tier_level=str(user_tier), old_user_tier_level=str(kyc_level))
                print("BANK VERIFICATION STATUS PUSH : ",status_push)
            except Exception as e:
                print(e.args)
        
            print(response)
            return response
    except Exception as e:
        print(str(e))
        return {"Exception": f"Exception caught {str(e)}"}


"""
Sync kyc_verification_status and update kyc_level in the datastore
"""
@logger.catch
def sync_kyc_verification_status(user, status):
    try:
        params = {
            "id": str(user.username)
        }
        query = """
                query MyQuery($input: ID!) {
                    getUser(id: $input) {
                        kyc_level 
                    }
                }
                """
        client = make_client()
        instance = apps.get_model('bemoSenderr.KycVerificationRequest').objects.filter(user=user).latest('created_at')
        user_snapshot = instance.user_snapshot
        phone_number = user_snapshot['phone_number']
        cognito_client = boto3.client(
                    region_name="us-west-1",
                    service_name='cognito-idp',
                )
        response = cognito_client.admin_get_user(
                            UserPoolId=settings.CONFIG.get('COGNITO_USER_POOL', None),
                            Username=phone_number
                        )
        user_attributes = response.get('UserAttributes', None)
        nickname = None
        if user_attributes:
            for attr in user_attributes:
                if attr.get('Name', None) == "nickname":
                    nickname = attr.get('Value', None)
                    break
        
            kyc_verification_instances = apps.get_model('bemoSenderr.KycVerificationRequest').objects.filter(user=user)
            if len(kyc_verification_instances) <= 1 and nickname:
                print('this is a migrated user')
                return
        response = client.execute(gql(query), variable_values=json.dumps({'input': params['id']}))
        logger.info(response)
        kyc_level = response.get('getUser', None).get('kyc_level', None)

        print(response)
        user_tier = 0
        params = {
            "id": str(user.username),
            "kyc_level": user_tier,
        }
        if kyc_level is not None and status == VerificationStatus.verified:
            user_tier = int(kyc_level) + 1
            verified_instances = apps.get_model('bemoSenderr.KycVerificationRequest').objects.filter(user=user, status=VerificationStatus.verified)
            if len(verified_instances) > 1:
                user_tier = int(kyc_level)
        elif kyc_level is not None and status == VerificationStatus.unverified:
            user_tier = kyc_level
        else:
            user_tier = 0
        params['kyc_level'] = user_tier

        query = UPDATE_USER_MUTATION
        response = client.execute(gql(query), variable_values=json.dumps({'input': params}))
        logger.info(response)
        return response
    except Exception as e:
        logger.info(str(e))
        return {"Exception": f"Exception caught {str(e)}"}


"""
Sync appsettings to the datastore
"""
@logger.catch
def sync_app_settings(instance):
    try:
        if instance:
            config = instance.config
            config['fundingExpTime'] = str(config['fundingExpTime'])
            params = {
                "id": str(instance.uuid),
                "content": json.dumps(config),

            }
            client = make_client()
            try:
                query = UPDATE_APPSETTINGS_MUTATION
                client = make_client()
                response = client.execute(gql(query), variable_values=json.dumps({'input': params}))
                print(response)
                print('successfully updated appsettings')
            except Exception as e:
                print("appsettings doesn't exist in dynamodb", e)
                query = CREATE_APPSETTINGS_MUTATION
                response = client.execute(gql(query), variable_values=json.dumps({'input': params}))
                print(response)
                    
    except Exception as e:
        print(e)
