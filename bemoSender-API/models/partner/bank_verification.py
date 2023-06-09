from gql import gql
from celery.app import shared_task
from django.db import models
from loguru import logger
from bemoSenderr.models.base import VerificationStatus
from bemoSenderr.models.partner.base import AbstractVerificationRequest
from django.utils import timezone
import sys
from django.apps import apps

from bemoSenderr.utils.appsync import make_client
from bemoSenderr.utils.mutation_queries import UPDATE_USER_MUTATION
from bemoSenderr.utils.sync_flinks_signup_data import sync_flinks_signup_data


"""
login_id     | The token returned by the Frontend Widget to send to the Auth API in the client's name.
account_id   | The Account's ID returned by the Frontend Widget following the selection of a specific account.
"""
"""
This module is for handling User Bank Verification, the verify celery task is invoked in bemoSenderr/views/UserVerificationByBankViewSet class 
in perform_create function.
"""
class UserBankVerificationRequest(AbstractVerificationRequest):
    partner_parameters = models.JSONField(help_text='account_id and frontend_request_id', null=True, blank=True)
    
    def init(self):
        super(UserBankVerificationRequest, self).init()

    def reconciliation(self):
        super(UserBankVerificationRequest, self).reconciliation()

    def ping(self):
        super(UserBankVerificationRequest, self).ping()

    @shared_task(bind=True)
    @logger.catch
    def verify(self, api_config=None, uuid=None):
        report = ''
        status = False
        try:
            
            time_now = timezone.now().strftime('%c')
            report += 'USER BANK VERIFICATION REQUEST FOR '
            user_bank_verification = apps.get_model('bemoSenderr', 'UserBankVerificationRequest')
            instance = user_bank_verification.objects.get(uuid=uuid)
            report += f"USER BANK VERIFICATION REQUEST UUID {str(uuid)}" + "\n" + f"USER : {str(instance.user)}" + "\n"
            report += 'TIME : ' + time_now + "\n"
            
            """
            Check if the Partner has a service in the api_config.
            """
            if api_config.get('serviceClass', None) and instance.partner:
                service = api_config['serviceClass']
                partner_service = getattr(sys.modules['bemoSenderr.models.partner.services'], service)(url=api_config['url'], api_config=api_config)
                user_snapshot = instance.user_snapshot
                parameters = instance.partner_parameters
                parameters['user_snapshot'] = user_snapshot
                parameters['api_config'] = api_config
                logger.info(parameters)
                result = partner_service.get_user_details(parameters=parameters)
                status = result[0]
                partner_response = result[1]
                instance.partner_response = partner_response
                if status:
                    instance.status = VerificationStatus.verified
                else:
                    instance.status = VerificationStatus.unverified
                instance.save()
                logger.info(report)
                if status and partner_response.get('response_formatted', None):
                    if instance.user:
                        sync_flinks_signup_data(user=instance.user, data=partner_response.get('response_formatted', None))
                    return partner_response.get('response_formatted', None)
                elif partner_response.get('query', None) and partner_response.get('query', None).get('RequestId', None):
                    return partner_response.get('query', None).get('RequestId', None)
                else:
                    logger.info('an error occured in bank verification sync function')
                    return False
                
        except Exception as e:
            report += f"GOT AN EXCEPTION IN BANK VERIFICATION {str(e)}"
            logger.info(report)
            return False
        
