import boto3
from django.conf import settings
from gql import gql
from gql.client import Client
from gql.transport.requests import RequestsHTTPTransport
from requests_aws4auth import AWS4Auth
import requests


def graphql_operation(query,input_params):
        api_key = settings.CONFIG['APPSYNC_API_KEY']
        session = requests.Session()
        APPSYNC_API_ENDPOINT_URL = settings.CONFIG['GRAPHQL_ENDPOINT']
        response = session.request(
            url=APPSYNC_API_ENDPOINT_URL,
            method='POST',
            headers={'x-api-key': api_key},
            json={'query': query,'variables':{"input":input_params}}
        )
        return response.json()



def make_client():
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    # Initiate a BOTO3 session
    session = boto3.session.Session(region_name=settings.CONFIG['region'])
    # Get credentials
    credentials = session.get_credentials().get_frozen_credentials()
    auth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        session.region_name,
        'appsync',
        session_token=credentials.token,
    )
    # Create a GraphQL client
    transport = RequestsHTTPTransport(url=settings.CONFIG['GRAPHQL_ENDPOINT'],
                                      headers=headers,
                                      auth=auth)
    client = Client(transport=transport,
                    fetch_schema_from_transport=True)
    return client

