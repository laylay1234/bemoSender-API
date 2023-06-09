import json
import boto3
from loguru import logger
from bemoSenderr.utils.mutation_queries import UPDATE_ADDRESS_MUTATION, UPDATE_PROFILE_MUTATION, UPDATE_USER_MUTATION
from bemoSenderr.utils.appsync import make_client
from gql import gql
from django.conf import settings


def sync_flinks_signup_data(user=None, data=None):
    try:
        try:
            if not user.phone_number:
                client_gql = make_client()
                params = {
                    "id": str(user.username)
                }
                query = """
                        query MyQuery($input: ID!) {
                            getUser(id: $input) {
                                phone_number
                            }
                        }
                        """
                response = client_gql.execute(gql(query), variable_values=json.dumps({'input': params['id']}))
                if response.get('getUser', None):
                    phone_number = response.get('getUser', None).get('phone_number', None)
                    if phone_number:
                        user.phone_number = phone_number
                        user.save()
            if user and user.phone_number:
                client = boto3.client('cognito-idp', region_name="us-west-1")
                username = user.phone_number
                user_attributes = []
                if data.get("email", None):
                    user_attributes.append({
                            'Name': 'email',
                            'Value': data.get("email", None)
                        })
                if data.get('first_name', None):
                    user_attributes.append({
                            'Name': 'first_name',
                            'Value': data.get("first_name", None)
                        })
                if data.get('last_name', None):
                    user_attributes.append({
                            'Name': 'last_name',
                            'Value': data.get("last_name", None)
                        })
                response = client.admin_update_user_attributes(
                    UserPoolId=settings.CONFIG.get('COGNITO_USER_POOL', None),
                    Username=username,
                    UserAttributes=user_attributes
                )
                print(response)
        except Exception as e:
            print(f"ERROR UPDATING COGNITO USER {user} failed due to {e}")
        if data and user:
            client = make_client()
            profile_id = None
            address_id = None
            params_get_user = {
                    "id": str(user.username)
                }
            query_get_user = """
                    query MyQuery($input: ID!) {
                        getUser(id: $input) {
                            profileID
                        }
                    }
                    """
            response_get_user = client.execute(gql(query_get_user), variable_values=json.dumps({'input': params_get_user['id']}))
            i = 1
            if response_get_user.get('getUser', None):
                print('GOT USER')
                profile_id = response_get_user.get('getUser', None).get('profileID', None)
                if profile_id:
                    params_get_profile = {
                        "id": str(profile_id)
                    }
                    query_get_profile = """
                            query GetProfile($input: ID!) {
                                getProfile(id: $input) {
                                    addressID
                                }
                            }
                            """
                    response_get_profile = client.execute(gql(query_get_profile), variable_values=json.dumps({'input': params_get_profile['id']}))
                    if response_get_profile.get("getProfile", None):
                        print('GOT PROFILE')
                        address_id = response_get_profile.get("getProfile", None).get("addressID", None)
                        if address_id:
                            params_update_user = {
                                "id": str(user.username)
                            }
                            if data.get('email', None):
                                params_update_user['email'] = data.get('email')
                            query_update_user = UPDATE_USER_MUTATION
                            response_update_user = client.execute(gql(query_update_user), variable_values=json.dumps({'input': params_update_user}))
                            logger.info(f"response update user {response_update_user.get('updateUser', None)}")
    
                            params_update_profile = {
                                "id": str(profile_id)
                            }
                            if data.get("first_name", None) and data.get("last_name", None):
                                params_update_profile['first_name'] = data.get("first_name")
                                params_update_profile['last_name'] = data.get("last_name")
                            query_update_profile = UPDATE_PROFILE_MUTATION
                            response_update_profile = client.execute(gql(query_update_profile), variable_values=json.dumps({'input': params_update_profile}))
                            logger.info(f"response update profile {response_update_profile.get('updateProfile', None)}")
    
                            params_update_address = {
                                "id": str(address_id)
                            }
                            if data.get("address_1", None):
                                params_update_address['address_line_1'] = data.get("address_1")
                            if data.get("zip_code", None):
                                params_update_address['postal_code'] = data.get("zip_code")
                            if data.get("state", None):
                                params_update_address['state'] = data.get("state")
                            if data.get("city", None):
                                params_update_address['city'] = data.get("city")
                            query_update_address = UPDATE_ADDRESS_MUTATION
                            response_update_address = client.execute(gql(query_update_address), variable_values=json.dumps({'input': params_update_address}))
                            logger.info(f"response update address {response_update_address.get('updateAddress', None)}")
                            return True
        else:
            logger.info("NO DATA")
            return False
    except Exception as e:
        logger.info(f"FAILED TO UPDATE FLINKS DATA TO USER {e}")
        return False