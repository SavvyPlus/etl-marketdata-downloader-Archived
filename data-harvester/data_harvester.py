# @Author: Dex
# @Email: ykydxt@gmail.com

import boto3
import json
import os
import datetime

'''
Environment Variable：
    queue_name (string): the name of SQS queue
    source_bucket (string): the bucket of the source csv file
    source_key (string): the key of the source csv file
    interval (string): the interval of target sources
'''

sqs = boto3.client('sqs')
s3 = boto3.client('s3')
queue_url = f'https://sqs.ap-southeast-2.amazonaws.com/547051082101/{os.environ["queue_name"]}'

def handler(event, context):
	'''
    Read source info(of certain interval) from a csv file in S3 bucket
    This handler should be triggered by scheduled event at certain interval 
    '''
    source_data = s3.get_object(Bucket=os.environ['source_bucket'], Key=os.environ['source_key'])['Body'].read().decode('utf-8')
    source_ls = source_data.split('\r\n')
    source_list = map(lambda x: x.split(','), source_ls)
    for source in source_list:
    	# source[4] belongs to header "Active",value 0 means inactive, 1 means active, 2 means something wrong with the source and needs fix
        if (source[4] == "1") & (source[2] == os.environ['interval']):
            utc_offset_hours = int(source[9])
            run_time = datetime.datetime.utcnow()+datetime.timedelta(hours=utc_offset_hours)
            source[8] = source[8].format(year=run_time.strftime('%Y'), month=run_time.strftime('%m'), lastmonth=f'0{int(run_time.strftime("%m"))-1}', day=run_time.strftime('%d'), hour=run_time.strftime('%H'), minute=run_time.strftime('%M'))
            source[1] = source[1].format(year=run_time.strftime('%Y'), month=run_time.strftime('%m'), lastmonth=f'0{int(run_time.strftime("%m"))-1}', day=run_time.strftime('%d'), hour=run_time.strftime('%H'), minute=run_time.strftime('%M'))
            print(f'Appending: {source[1]}')
            msg = json.dumps({ "ID": source[0], "URL": source[1], "TYPE": source[7], "PATTERN": source[8], "UTC": source[9]})
            response = sqs.send_message(QueueUrl=queue_url, MessageBody=msg)
