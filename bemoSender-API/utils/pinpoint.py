import datetime
import json
import boto3
from django.conf import settings
from loguru import logger
from pyfcm import FCMNotification
from bemosenderrr.models.user import UserToken


"""
----------------------------------------------------------------------------
This module is for sending notifications to the mobile app via AWS Pinpoint:
----------------------------------------------------------------------------
Currently Amplify flutter doesnt support notifications with pinpoint.
The current hack is as follows:
-On the mobile app:
    Register the device_token of the user with Pinpoint Analytics.
    There is a 100 char limit per user attribute so we split the token to n attributes depending on the length of the token.
-On the backend:
    Concatenate the device_token parts for each device of a user (done with get_device_token() method).
    Update the user endpoints for each address with the device_token attributes.
    Delete old endpoints(which are inactive and nor registered) because there is a limit of 15 endpoints per user and they get changed after every uninstall or data clearance.

"""

class PinpointWrapper():
    def __init__(self):
        self.application_id = settings.CONFIG.get("PINPOINT_APP_ID", "4b00bd44e2ac4c4ea5bd41693ec8de49")#"4b00bd44e2ac4c4ea5bd41693ec8de49"
        self.client = boto3.client(
            'pinpoint',
            region_name=settings.CONFIG.get("PINPOINT_REGION","us-west-2")
        )
                    

    def send_push_notifications_and_data(self, fcm_token=None, user_snapshot=None, user=None, status=None, data=None, type=None, title="bemosenderrr", global_tx_uuid="", error=None, new_user_tier_level=None, old_user_tier_level=None):
        try:
            #device_tokens = self.get_user_tokens(user_snapshot=user_snapshot, user_id=user.username)
            #print('THE DEVICE TOKENS', device_tokens)
            android_user_token = UserToken.objects.filter(user=user, device_type="android").first()
            ios_user_token = UserToken.objects.filter(user=user, device_type="ios").first()
            android_token = None
            ios_token = None
            if android_user_token:
                android_token = android_user_token.device_token
            if ios_user_token:
                ios_token = ios_user_token.device_token
            # This is for testing through /v1/test-push
            if fcm_token:
                ios_token = fcm_token
            if android_token or ios_token:
                payload = {
                    "notification": {
                        "title": title,
                        "body": data,
                        "sound": "default",
                        "badge":"1"
                    },
                    "data": {
                        "type": type,
                        "transaction": global_tx_uuid,
                        "click_action": "FLUTTER_NOTIFICATION_CLICK",
                        "status": status
                    }
                }
                if type == "user_tier" and error:
                    payload["data"]["bank_verification_status"] = "error"
                    payload["data"]['old_user_tier_level'] = old_user_tier_level
                    payload["data"]['new_user_tier_level'] = new_user_tier_level
                    del payload["data"]["transaction"]
                    del payload["data"]["status"]
                elif type == "user_tier" and not error:
                    payload["data"]["bank_verification_status"] = "success"
                    payload["data"]['old_user_tier_level'] = old_user_tier_level
                    payload["data"]['new_user_tier_level'] = new_user_tier_level
                    del payload["data"]["transaction"]
                    del payload["data"]["status"]
                push_service = FCMNotification(api_key=settings.CONFIG.get('GCM_KEY', None))
                result_android = False
                result_ios = False
                if android_token:
                    registration_id = android_token
                    result_android = push_service.notify_single_device(
                        registration_id=registration_id,
                        message_title=title,
                        message_body=data,
                        sound=True,
                        data_message=payload["data"],
                        content_available=True,
                        badge=1
                    )
                    print("response android", result_android)
                    if result_android.get('success', None) == 1:
                        result_android = True
                if ios_token:
                    registration_id = ios_token
                    result_ios = push_service.notify_single_device(
                        registration_id=registration_id,
                        message_title=title,
                        message_body=data,
                        sound=True,
                        data_message=payload["data"],
                        content_available=True,
                        badge=1
                    )
                    print("response ios", result_ios)
                    if result_ios.get('success', None) == 1:
                        result_ios = True
            return result_ios or result_android
        except Exception as e:
            print("SEND PUSH NOTIFICATIONS AND DATA FAILED DUE TO :", e)
            return False

    def send_sms(self, destination_number=None, origination_number=None, message=None):
        try:
            if destination_number and origination_number and message:
                message_request={
                        'MessageConfiguration': {
                            'SMSMessage': {
                                'Body': message,
                                'MessageType': "TRANSACTIONAL",
                                'OriginationNumber': origination_number}
                        }
                }
                message_request["Addresses"] = {}
                for number in destination_number:
                    number_formatted = number
                    if "+" not in number_formatted:
                        number_formatted = "+" + number_formatted
                    message_request["Addresses"][number_formatted] =  {'ChannelType': 'SMS'}
                
                response = self.client.send_messages(
                    ApplicationId=self.application_id,
                    MessageRequest=message_request
                )
                logger.info(f'SMS RESPONSE {response}')
                return response.get("ResponseMetadata", None).get("HTTPStatusCode", None) == 200
            else:
                print("Missing parameters for send sms !")
                return False
        except Exception as e:
            print("SEND SMS FAILED DUE TO :", e)
            return False
