import aioboto3
import json
import boto3
import os
import base64
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
s3 = boto3.client('s3')
access = os.getenv('accesskey')
secret = os.getenv('serectkey')

def test_s3_connection(access, secret, region):
    """Test connection to AWS Bedrock service"""
    print("\n🔍 Testing S3 connection...")
    
    try:
        load_dotenv()
        
        # Create Bedrock client
        client = boto3.client(
            's3',
            region_name=region,
            aws_access_key_id=access,
            aws_secret_access_key=secret
        )
        # s3.list_buckets()
        print("✅ S3 client created successfully")
        return client
        
    except NoCredentialsError:
        print("❌ AWS credentials not found")
        return None
    except PartialCredentialsError:
        print("❌ Incomplete AWS credentials")
        return None
    except Exception as e:
        print(f"❌ Error creating Bedrock client: {e}")
        return None
    
async def upload_json_to_s3_async(data, bucket, key, access_key, secret_key, region):
    if isinstance(data, dict):
        json_str = json.dumps(data)
    elif isinstance(data, str):
        try:
            json.loads(data)
            json_str = data
        except json.JSONDecodeError:
            raise ValueError("Provided string is not valid JSON.")
    else:
        raise TypeError("Data must be a dict or a valid JSON string.")
    session = aioboto3.Session()
    async with session.client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region
    ) as s3:
        await s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=json_str,
            ContentType='application/json'
        )

    return f"success s3://{bucket}/{key}"

data={'test':'hong-tran-tren-doi-canh-tay'}
# asyncio.run(upload_json_to_s3_async(data,'vpbank-team91','Song-test/test.json',access,secret,'ap-southeast-1'))
async def main():
    data = {"project": "AIOps", "status": "ok"}
    result = await upload_json_to_s3_async(
        data,'vpbank-team91','Song-test/test.json',access,secret,'ap-southeast-1'
    )
    print(result)



def upload_json_to_s3_safe(data, bucket, key, access, secret, region):
    # Initialize S3 client using provided credentials
    s3=test_s3_connection(access,secret,region)

    # Validate data
    if isinstance(data, dict):
        json_str = json.dumps(data)
    elif isinstance(data, str):
        try:
            json.loads(data)  # Validate it's proper JSON
            json_str = data
        except json.JSONDecodeError:
            raise ValueError("Provided string is not valid JSON.")
    else:
        raise TypeError("Data must be a dict or a valid JSON string.")

    # Upload to S3
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json_str,
        ContentType='application/json'
    )

    return f"success s3://{bucket}/{key}"

if __name__=='__name__':
    import asyncio
    asyncio.run(main())

