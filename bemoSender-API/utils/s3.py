import boto3
from django.conf import settings

from bemosenderrr.logger import send_email_celery_exception

def make_s3_client():
    s3_client = boto3.client('s3')
    return s3_client

def upload_to_s3(body=None, bucket=None, key=None, content_type=None):
    try:
        s3_client = make_s3_client()
        s3_client.put_object(Body=body, Bucket=bucket, Key=key, ContentType=content_type)
    except Exception as e:
        send_email_celery_exception(e)
        print("Unable to upload report to S3", e)