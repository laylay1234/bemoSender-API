import boto3
from django.conf import settings


def verify_cognito_user(user=None):
    try:
        if user:
            client = boto3.client('cognito-idp', region_name="us-west-1")
            username = user.phone_number
            response = client.admin_update_user_attributes(
                UserPoolId=settings.COGNITO_USER_POOL,
                Username=username,
                UserAttributes=[
                    {
                        'Name': 'email_verified',
                        'Value': 'true'
                    },
                ],
            )
            print(response)
            if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                return True
            else:
                return False
        else:
            return False
    except Exception as e:
        print(f"VERIFYING COGNITO USER {user} failed due to {e.args}")
        return False