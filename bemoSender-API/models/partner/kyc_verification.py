import json
from time import sleep
from celery.app import shared_task
from django.db import models
from loguru import logger
from bemosenderrr.models.base import VerificationStatus
from bemosenderrr.models.partner.base import  AbstractVerificationRequest
from bemosenderrr.models.partner.services.state_code_gen import StateCodeGenerator
from bemosenderrr.utils.appsync import make_client
from bemosenderrr.utils.log import debug
from django.apps import apps
import sys
from django.utils import timezone
from gql import gql

from bemosenderrr.utils.mutation_queries import UPDATE_ADDRESS_MUTATION


class KycVerificationRequest(AbstractVerificationRequest):
    query_counter = models.CharField(max_length=255, help_text='Current verification request counter', null=True, blank=True)#TODO check if needed
    custom_transaction_id = models.CharField(max_length=255, help_text='An internally created transaction ID', null=True, blank=True)#TODO check if needed

    def init(self):
        super(KycVerificationRequest, self).init()

    def reconciliation(self):
        super(KycVerificationRequest, self).reconciliation()

    def ping(self):
        super(KycVerificationRequest, self).ping()

    @shared_task(bind=True)
    @logger.catch
    def verify(self, api_config=None, uuid=None):
        report = ''
        status = False
        try:
            
            time_now = timezone.now().strftime('%c')
            report += 'KYC VERIFICATION REQUEST FOR '
            kyc_verification_model = apps.get_model('bemosenderrr', 'KycVerificationRequest')
            instance = kyc_verification_model.objects.filter(uuid=uuid).select_related("user", "partner").first()
            try:
                logger.info(f"UPDATING USER STATE CODE")
                user = instance.user
                state = update_user_state_code(user=user)
                logger.info(f"UPDATE USER STATE CODE STATUS : {state}")
            except Exception as e:
                logger.info(f"FAILED TO SYNC USER STATE CODE {e}")
            report += f"KYC VERIFICATION REQUEST UUID {str(uuid)}" + "\n" + f"USER : {str(instance.user)}  with UUID : {str(instance.user.uuid)}" + "\n"
            report += 'TIME : ' + time_now + "\n"
            """
            Check if the Partner has a service in the api_config.
            """
            if api_config.get('serviceClass', None) and instance.partner:
                service = api_config['serviceClass']
                """
                *** Very important to instanciate the class with () #partner_service so the flow doesn't break. ***
                """
                partner_service = getattr(sys.modules['bemosenderrr.models.partner.services'], service)()
                user_snapshot = instance.user_snapshot
                """
                The verifying function has to be named "verify_individual" to keep this feature dynamic for new partners.
                this function must return a list containing 4 elements:
                    1. result[0]  is the status of the KYC verification.
                    2. result[1] is the report (can be an empty string "").
                    3. result[2] is the partner response.
                    4. result[3] is the custom_transaction_id if the partner has one (can be set to null).
                """
                result = partner_service.verify_individual(api_config=api_config, user_snapshot=user_snapshot)
                status = result[0]
                report += f"Partner : {str(instance.partner.name)}" + "\n"
                report += "\n" + result[1] + "\n"
                response = result[2]
                logger.info(response)
                cust_transaction_id = result[3]
                if status:
                    instance.status = VerificationStatus.verified
                else:
                    instance.status = VerificationStatus.unverified
                if response and response.data:
                    instance.partner_response = response.data
                if cust_transaction_id:
                    instance.custom_transaction_id = cust_transaction_id
                instance.save()
                report += "\n" + "END OF REPORT "
            else:
                report += "\n" + "No Active KYC Partners found !"
                report += "\n" + "END OF REPORT "
                logger.info('No Active KYC Partners found !')
                
        except Exception as e:
            report += f"GOT AN EXCEPTION {str(e)}"
            logger.exception(str(e))
        logger.info(report)
        debug(self)
        return status

def update_user_state_code(user=None):

        if user:
            params = {
                "id": str(user.username)
            }
            query = """
                    query MyQuery($input: ID!) {
                        getUser(id: $input) {
                            profileID origin_country_iso
                        }
                    }
                    """
            client = make_client()
            response_user = client.execute(gql(query), variable_values=json.dumps({'input': params['id']}))
            i = 1
            while not response_user.get('getUser', None) and i < 5:
                sleep(3)
                logger.info('Sleeping 3 seconds !') # This to await user to be saved in the datastore .
                response_user = client.execute(gql(query), variable_values=json.dumps({'input': params['id']}))
                logger.info(f"Current i : {i}")
                logger.info(f"response_user {response_user}")
                logger.info('-----------------------')
                i += 1
            logger.info(f"RESPONSE USER {response_user}")
            origin_country = response_user.get('getUser', None).get('origin_country_iso', None)
            print('response user', response_user)
            if response_user:
                profile_id = response_user.get('getUser', None).get('profileID')
                if profile_id:
                    params = {
                        "id": str(profile_id)
                    }
                    query = """
                            query GetProfile($input: ID!) {
                                getProfile(id: $input) {
                                    addressID
                                }
                            }
                            """
                    response_profile = client.execute(gql(query), variable_values=json.dumps({'input': params['id']}))
                    print('response profile', response_profile)
                    if response_profile:
                        address_id = response_profile.get("getProfile", None).get("addressID", None)
                        if address_id:
                            params = {
                                'id': str(address_id)
                            }
                            query = """
                                query GetAddress($input: ID!) {
                                    getAddress(id: $input) {
                                        postal_code
                                    }
                                }
                            """
                            response_address = client.execute(gql(query), variable_values=json.dumps({'input': params['id']}))
                            print("response get address", response_address)
                            zip_code = response_address.get('getAddress', None).get('postal_code', None)
                            state_code = StateCodeGenerator().get_state_code(postalCode=zip_code, countryCode=origin_country)
                            print('THIS IS THE STATE CODE OF USER : ', user.username, state_code)
                            if state_code:
                                params['state'] = str(state_code)
                            query = UPDATE_ADDRESS_MUTATION
                            response_address = client.execute(gql(query), variable_values=json.dumps({'input': params}))
                            print("response mutation address", response_address)
                            return True
                        else:
                            print("ADDRESSID IS NONE!")
                            return False
                    else:
                        print("RESPONSE PROFILE IS NONE!")
                        return False
                else:
                    print("PROFILEID IS NONE!")
                    return False
            else:
                print("RESPONSE USER EMPTY")
                return False
        else:
            print('MUTATE UPDATE STATE CODE, USER IS NONE !')
            return False