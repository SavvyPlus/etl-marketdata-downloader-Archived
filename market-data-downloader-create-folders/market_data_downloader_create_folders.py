import json
import boto3
import botocore
import os
from botocore.vendored import requests

client = boto3.client('s3')
s3 = boto3.resource('s3')

def handler(event, context):
    """
    Handle the event to create the correct folders
    """
    try:
        rootBucket = os.environ['BucketName']
        bucket = s3.Bucket(rootBucket)

        print("Creating folders for lambdas")
        if bucket and can_access_bucket(bucket):
            client.put_object(Bucket=rootBucket, Key='in/')
            client.put_object(Bucket=rootBucket, Key='processing/')
            client.put_object(Bucket=rootBucket, Key='done/')

        print("Finished creating folders")

        sendResponseCfn(event, context, "SUCCESS")
    except Exception as e:
        print(e)
        sendResponseCfn(event, context, "FAILED")

def can_access_bucket(bucket):
    """
    Is the input bucket accessable
    """
    try:
        s3.meta.client.head_bucket(Bucket=bucket.name)
        return True
    except botocore.exceptions.ClientError as e:
        # If a client error is thrown, then check that it was a 404 error.
        # If it was a 404 error, then the bucket does not exist.
        error_code = int(e.response['Error']['Code'])
        if error_code == 403:
            print("Private Bucket. Forbidden Access!")
        elif error_code == 404:
            print("Bucket Does Not Exist!")

        return False

def sendResponseCfn(event, context, responseStatus):
    """
    Creates the correct response for Cloudformation
    """
    response_body = {'Status': responseStatus,
                     'Reason': 'Log stream name: ' + context.log_stream_name,
                     'PhysicalResourceId': context.log_stream_name,
                     'StackId': event['StackId'],
                     'RequestId': event['RequestId'],
                     'LogicalResourceId': event['LogicalResourceId'],
                     'Data': json.loads("{}")}

    requests.put(event['ResponseURL'], data=json.dumps(response_body).encode("utf8"))
