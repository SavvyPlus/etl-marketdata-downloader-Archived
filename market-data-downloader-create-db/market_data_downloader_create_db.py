import boto3
import os
import json
import cfnresponse
import cfnresponse3

def handler(event, context):
    response_data = {}
    try:
        stack_name = os.environ['StackName']
        # athena db name cannot contain hyphens
        database_name = os.environ['DatabaseName'].replace('-', '_')
        print("stack_name: " + stack_name)
        print("database_name: " + database_name)
        print(event)
        client = boto3.client('athena', region_name='ap-southeast-2')

        # s3 bucket name cannot contain underscores..
        s3_bucket = os.environ['BucketName']
        config = {
            'OutputLocation': 's3://' + s3_bucket + '/' + database_name.replace('_','-'),
            'EncryptionConfiguration': {'EncryptionOption': 'SSE_S3'}
        }

        # Query Execution Parameters
        sql = 'CREATE DATABASE IF NOT EXISTS ' + database_name

        client.start_query_execution(QueryString = sql,
                                     ResultConfiguration = config)

        response_data['Success'] = 'Create database started'
        cfnresponse3.send(event, context, cfnresponse3.SUCCESS, None, response_data, stack_name)
    except Exception as e:
        print(e)
        response_data['Failure'] = 'Create database failed'
        cfnresponse3.send(event, context, cfnresponse3.FAILED, None, response_data, stack_name)
