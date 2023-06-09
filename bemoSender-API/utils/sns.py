import json
import boto3
from django.conf import settings

from bemosenderrr.models.user import UserToken


"""
This class is for publishing messages (push notifications and sms) using AWS SNS
"""

"""
----------------------------
GCM(FCM) NOTIFICATION FORMAT
----------------------------
{
"GCM": "{ \"notification\": { \"title\": \"test title\", \"body\": \"test body\"}, \"data\": { \"key_1\": \"value_1\":} }"
}

------------------------
APNS NOTIFICATION FORMAT
------------------------
{
  "APNS_SANDBOX": "{\"aps\":{\"alert\":{ \"title\": \"test title\", \"body\": \"test body\"}}, \"data\": { \"key_1\": \"value_1\":} }"    #APNS for production use
}
"""
"""
There are 2 types of data in the message data payload:
notification message and message data in this format: for FCM for ex:
        "notification": {
            "title": title,
            "body": data,
            "sound": "default",
        },
        "data": {
            "type": "user_tier",
            "bank_verification_status" = False,
            'click_action': 'FLUTTER_NOTIFICATION_CLICK'
        }
The type key in data['type'] is to distinguish the type of the notifications to be handled by the frontend
We currently have 2 values
    1. "user_tier" --> For Bank Verification notifications
        for this type we add "error" key to indicate if the bank verification is successful or not
    2. "transaction"  this value is to indicate for the frontend that this is Transaction notification
        for this type we add a a key "transaction" to the message data where we put the GlobalTransaction UUID associated so the frontend reroutes to the
            appropriate view or state in the app.

"""


class SNSNotificationService():
    def __init__(self):
        self.client = boto3.client('sns', region_name="us-west-1")


    """
    Get device tokens of a specific user
    returns a list [ios_token, android_token] depending on the devices of the user (UserToken model)
    """
    def get_device_tokens(self, user=None):
        if user:
            user_tokens = UserToken.objects.filter(user=user)
            tokens = {}
            if user_tokens:
                for user_token in user_tokens:
                    if str(user_token.device_type).lower() == "android" and user_token.device_token:
                        tokens['android'] = user_token.device_token
                    elif str(user_token.device_type).lower() == "ios" and user_token.device_token:
                        tokens['ios'] = user_token.device_token
            return tokens
        else:
            return []

    """
    Get or create user application endpoint arn
    returns a list [user_ios_endpoint, user_android_endpoint] depending on the devices of the user (UserToken model)
    """
    def get_or_create_mobile_enpoints(self, user=None):
        try: 
            device_tokens = self.get_device_tokens(user)
            endpoints = []
            print(device_tokens)
            if device_tokens:
                for key, value in device_tokens.items():
                    platform_arn = ""
                    device_token = ""
                    if key == "android":
                        platform_arn = settings.SNS_GCM_PLATFORM_ARN
                        device_token = value
                    elif key == "ios":
                        platform_arn = settings.SNS_APNS_PLATFORM_ARN
                        device_token = value
                    print("platform arn :", platform_arn)
                    print("device_token", device_token)
                    try:
                        response = self.client.create_platform_endpoint(
                            PlatformApplicationArn=platform_arn,
                            Token=device_token,
                        )
                        print(response)
                        endpoints.append({key: response.get('EndpointArn')})
                    except Exception as e:
                        print(e.args)
                        return f"error getting or creating endpoint: {e.args}"
                return endpoints
            else:
                return "error missing device token"
        except Exception as e:
            print(e.args)
            return "error missing device token"


    """
    Send a push notification with both notification and messagepayload.
    payload['data'] used for handling the notification in the mobile app to route or process according to the payload.
    args:
        - user: associated user
        - data: message to show in the body of the notification.
        - type: enum("transaction", "user_tier"), the type of notification used in payload['data'] used to handle the notification according to its type defined in the mobile app.
        - global_tx_uuid: global transaction uuid (optional), only required when type == "transaction".
        - error: only used when type == "user_tier" (optional), indicates if there is an error in bank_verification.
    returns Boolean, based on the status of the response.(If the user has 2 devices and one of them failed return False)
    """
    def send_push_notifications_and_data(self, user=None, data=None, type=None, title="bemosenderrr", global_tx_uuid="", error=None):
        try:
            endpoints = []
            if user:
                endpoints = self.get_or_create_mobile_enpoints(user=user) # Get application endpoints for all user devices
            else:
                return False
            print(endpoints)
            status = []
            if endpoints and isinstance(endpoints, list) :
                for endpoint_arn in endpoints:
                    """------------------------------------ANDROID---------------------------------------------"""
                    if endpoint_arn.get('android', None):
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
                                'click_action': 'FLUTTER_NOTIFICATION_CLICK'
                            }
                        }
                        if type == "user_tier" and error:
                            payload["data"]["bank_verification_status"] = "error"
                            del payload["data"]["transaction"]
                        elif type == "user_tier" and not error:
                            payload["data"]["bank_verification_status"] = "success"
                            del payload["data"]["transaction"]
                        data_str = json.dumps(payload)
                        message = {
                            "default": data_str,
                            "GCM": data_str
                        }
                        response_android = self.client.publish(
                            TargetArn=endpoint_arn["android"],
                            Message=json.dumps(message),
                            MessageStructure='json'
                        )
                        print(response_android)
                        status.append(response_android.get("ResponseMetadata", None).get("HTTPStatusCode", None) == 200)
                    
                    elif endpoint_arn.get('ios', None):
                        """------------------------------------IOS---------------------------------------------"""
                        payload = {
                            "aps":{
                                "alert": {
                                    "title": title,
                                    "body": data,
                                    "sound": "default",
                                    "badge":"1"
                                },
                                "data": {
                                    "type": type,
                                    "transaction": global_tx_uuid,
                                    'click_action': 'FLUTTER_NOTIFICATION_CLICK'
                                }
                            }
                        }
                        if type == "user_tier" and error:
                            payload["data"]["bank_verification_status"] = "error"
                            del payload["data"]["transaction"]
                        elif type == "user_tier" and not error:
                            payload["data"]["bank_verification_status"] = "success"
                            del payload["data"]["transaction"]
                        data_str = json.dumps(payload)
                        message = {
                            "default":data_str,
                            "APNS_SANDBOX": data_str
                            #"{\"aps\":{\"alert\":\"Sample message for iOS development endpoints\"}}"
                        }
                        response_ios = self.client.publish(
                            TargetArn=endpoint_arn.get['ios'],
                            Message=json.dumps(message),
                            MessageStructure='json'
                        )
                        print(response_ios)
                        status.append(response_android.get("ResponseMetadata", None).get("HTTPStatusCode", None) == 200)
                if status:   
                    return all(status)
                else:
                    return False
            else:
                print("SEND PUSH NOTIFICATIONS FAILED NO ENDPOINTS FOUND OR CREATED")
                return False
        except Exception as e:
            print(f"SEND PUSH NOTIFICATIONS FAILED WITH TYPE {type} and os ")
            print(e.args)
            return False


    """
    Send sms message to the user(s). (Users* SMS can be sent to both receiver and admins who can receive sms, based on AdminAlert objects and their permissions can_get_receiver_sms == True)
    args:
        - phone_number: list, list of phone_numbers to receive the message.
        - message: str, message body of the sms.
    returns Boolean, based on the status of the response.
    """
    # This is working properly.
    def send_sms(self, phone_number=None, message=None):
        try:
            if isinstance(phone_number, list):
                response = False
                statuses = []
                for phone in phone_number:
                    response = self.client.publish(
                        PhoneNumber=str(phone),
                        Message=message
                    )
                    statuses.append(response.get("ResponseMetadata", None).get(
                        "HTTPStatusCode", None) == 200)
                if any(statuses):
                    return True
                else:
                    return False
            else:
                response = self.client.publish(
                    PhoneNumber=str(phone_number),
                    Message=message
                )
                return response.get("ResponseMetadata", None).get("HTTPStatusCode", None) == 200
        except Exception as e:
            print(e.args)
            return False


if __name__ == '__main__':
    service = SNSNotificationService()
