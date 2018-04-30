import boto3
import botocore.vendored.requests
import urllib
import fnmatch
import json
import os
import csv
from bs4 import BeautifulSoup

sqs = boto3.client('sqs')
s3 = boto3.client('s3')
sns = boto3.client('sns')

queue_url = f'https://sqs.ap-southeast-2.amazonaws.com/547051082101/{os.environ["queue_name"]}'

def handle_error(e_id, e_url, e_message, msg_receipt):
    try:
        source_data = s3.get_object(Bucket=os.environ['source_bucket'], Key=os.environ['source_key'])['Body'].read().decode("utf-8").splitlines(True)
        csv_writer = csv.writer(open(f'/tmp/{os.environ["source_key"]}', 'w'))
        sources = list(csv.reader(source_data))
        for n, source in enumerate(sources):
            if source[0] == e_id:
                sources[n][4] = 2
            csv_writer.writerow(source)
        s3.upload_file(f'/tmp/{os.environ["source_key"]}', 'dex.test', f'ttt/{os.environ["source_key"]}')
    except Exception as e:
        print(f'Error when modifying source file: {e}')
    finally:
        e_message = str(e_message).replace('"', "'")
        msg = f'{{"ID": "{e_id}", "URL": "{e_url}", "REASON": "{e_message}"}}, "MESSAGE": "The URL in the source file should has been labelled as Active: 2 "'
        sns.publish(TopicArn='arn:aws:sns:ap-southeast-2:547051082101:dex_test',
                        Message=msg,
                        Subject='Error from Marketdata Downloader!')
        print("SNS topic sent")
        sqs.delete_message(QueueUrl=queue_url,ReceiptHandle=msg_receipt)
        print("Message in the SQS is deleted")

def link_files(source,msg_receipt, overwrite = False):
    source_url = source['URL']
    print(f'Start handling ID: {source["ID"]}, URL: {source["URL"]} ')
    try:
        file_page = urllib.request.urlopen(source_url)
        file_page = BeautifulSoup(file_page, 'html.parser')
    except Exception as e:
        print(f'Error when reading page: {e}')
        handle_error(source['ID'], source['URL'], e, msg_receipt)
    else:
        print('Starting downloading files')
        try:
            for f in file_page.find_all('a'):
                file_url = urllib.parse.urljoin(source_url, f.get('href'))
                file_name = file_url.split('/')[-1]
                if file_name:
                    urllib.request.urlretrieve(file_url, f'/tmp/{file_name}')
                    if overwrite:
                        s3.upload_file(f'/tmp/{file_name}', 'dex.test', f'POC/LINKS_OVER/{file_name}')
                    else:
                        s3.upload_file(f'/tmp/{file_name}', 'dex.test', f'POC/LINK/{file_name}')
                    sqs.delete_message(QueueUrl=queue_url,ReceiptHandle=msg_receipt)
                    os.remove(f'/tmp/{file_name}')
        except Exception as e:
            print(f'Error when handling file: {e}')
        else:
            print(f'Finished: {source["ID"]}')

def dlinks_files(source, msg_receipt):
    print(f'Start handling ID: {source["ID"]}, URL: {source["URL"]} ')
    file_name = source['PATTERN']
    try:
        print("Start downloading a file")
        urllib.request.urlretrieve(source['URL'], f'/tmp/{file_name}')
        s3.upload_file(f'/tmp/{file_name}', 'dex.test', f'POC/LINKS_DIRECT/{file_name}')
        sqs.delete_message(QueueUrl=queue_url,ReceiptHandle=msg_receipt)
        os.remove(f'/tmp/{file_name}')
    except Exception as e:
        print(f'Error when handling file: {e}')
        handle_error(source['ID'], source['URL'], e, msg_receipt)
    else:
        print(f'Finished: {source["ID"]}')

def ftp_files(source, msg_receipt):
    print(f'Start handling ID: {source["ID"]}, URL: {source["URL"]} ')
    try:
        response = urllib.request.urlopen(source['URL'])
        file_list = response.read().decode().split('\r\n')[0: -1]
        files =  map(lambda x: x.split()[-1], file_list)
        fnames = fnmatch.filter(files, source['PATTERN'])
    except Exception as e:
        print(f'Error when reading directory: {e}')
        handle_error(source['ID'], source['URL'], e, msg_receipt)
    else:
        print("Start downloading files")
        try:
            for file_name in fnames:
                file_url = urllib.parse.urljoin(source['URL'], file_name)
                urllib.request.urlretrieve(file_url, f'/tmp/{file_name}')
                s3.upload_file(f'/tmp/{file_name}', 'dex.test', f'POC/FTP_FILES/{file_name}')
                sqs.delete_message(QueueUrl=queue_url,ReceiptHandle=msg_receipt)
                os.remove(f'/tmp/{file_name}')
        except Exception as e:
            print(f'Error when handling file: {e}')
        else:
            print(f'Finished: {source["ID"]}')

def dftp_files(source,  msg_receipt):
    print(f'Start handling ID: {source["ID"]}, URL: {source["URL"]} ')
    file_name = source['PATTERN']
    try:
        print("Start downloading a file")
        urllib.request.urlretrieve(source['URL'], f'/tmp/{file_name}')
        s3.upload_file(f'/tmp/{file_name}', 'dex.test', f'POC/FTP_FILE/{file_name}')
        sqs.delete_message(QueueUrl=queue_url,ReceiptHandle=msg_receipt)
        os.remove(f'/tmp/{file_name}')
    except Exception as e:
        print(f'Error when handling file: {e}')
        handle_error(source['ID'], source['URL'], e, msg_receipt)
    else:
        print(f'Finished: {source["ID"]}')

def handler(event, context):
    count = 5
    print("Attempt to receive 5 messages")
    for i in range(0, count):
        response1 = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=1)
        if 'Messages' in response1:
            msg_receipt = response1['Messages'][0]['ReceiptHandle']
            msg_content = json.loads(response1['Messages'][0]['Body'])
            if (msg_content['TYPE'] == "LINKS"):
                link_files(msg_content,msg_receipt)
            elif(msg_content['TYPE'] == "LINKS_OVERWRITE"):
                link_files(msg_content, msg_receipt, overwrite = True)
            elif(msg_content['TYPE'] == "DIRECT"):
                dlinks_files(msg_content, msg_receipt)
            elif(msg_content['TYPE'] == "DIRECT_FTP"):
                dftp_files(msg_content, msg_receipt)
            elif(msg_content['TYPE'] == "FTP_FILES"):
                ftp_files(msg_content, msg_receipt)
            else:
                print("FILE TYPE ERROR")
