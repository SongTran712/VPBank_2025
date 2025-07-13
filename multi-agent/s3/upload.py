import json
import boto3
import os
from datetime import datetime
from dotenv import load_dotenv
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError

# Load environment variables
load_dotenv()
access = os.getenv('accesskey')
secret = os.getenv('secretkey')  # corrected from 'serectkey'
region = 'ap-southeast-1'
bucket_name = 'vpbank-team91'
s3_key = 'Song-test/test.json'

def test_s3_connection(access, secret, region):
    """Test connection to AWS S3 service"""
    print("\n🔍 Testing S3 connection...")
    try:
        client = boto3.client(
            's3',
            region_name=region,
            aws_access_key_id=access,
            aws_secret_access_key=secret
        )
        # Attempt to list buckets (minimal call to verify)
        client.list_buckets()
        print("✅ S3 connection established.")
        return client
    except NoCredentialsError:
        print("❌ AWS credentials not found.")
    except PartialCredentialsError:
        print("❌ Incomplete AWS credentials.")
    except ClientError as e:
        print(f"❌ AWS client error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    return None

def upload_json_to_s3(data, bucket, key, access_key, secret_key, region):
    """Synchronously upload JSON to S3"""
    if isinstance(data, dict):
        json_str = json.dumps(data)
    elif isinstance(data, str):
        try:
            json.loads(data)  # Validate JSON
            json_str = data
        except json.JSONDecodeError:
            raise ValueError("❌ Provided string is not valid JSON.")
    else:
        raise TypeError("❌ Data must be a dict or a valid JSON string.")

    try:
        client = boto3.client(
            's3',
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=json_str,
            ContentType='application/json'
        )
        print(f"✅ Uploaded to s3://{bucket}/{key}")
    except ClientError as e:
        print(f"❌ Failed to upload to S3: {e}")
    except Exception as e:
        print(f"❌ Unexpected error during upload: {e}")

def upload(data):
    if not access or not secret:
        print("❌ Missing AWS credentials in environment variables.")
        return

    client = test_s3_connection(access, secret, region)
    if not client:
        return

    try:
        upload_json_to_s3(data, bucket_name, s3_key, access, secret, region)
    except (ValueError, TypeError) as e:
        print(e)

def main():
    # Example JSON data to upload
    sample_data = {
        "message": "Hello, world!",
        "timestamp": datetime.now().isoformat()
    }

    upload(sample_data)

if __name__ == '__main__':
    main()
