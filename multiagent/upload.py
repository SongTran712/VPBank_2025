import json
import boto3
import os
from datetime import datetime
from dotenv import load_dotenv
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError

# Load environment variables
# Load environment variables
load_dotenv(".env", override=True)

session = boto3.Session(
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_KEY'),
    region_name='ap-southeast-1'
)
s3 = session.client("s3")

        
def upload_json_to_s3(data: dict, bucket: str, prefix: str, filename: str = "output.json"):
    if hasattr(data, "dict"):
        data = data.dict()
    elif hasattr(data, "__dict__"):
        data = data.__dict__
    s3_key = f"{prefix.rstrip('/')}/{filename}"
    json_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
    
    s3.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=json_bytes,
        ContentType="application/json"
    )
    print(f"✅ JSON uploaded to s3://{bucket}/{s3_key}")

def read_json_from_s3(bucket = 'testworkflow123', prefix = 'info_agent/companyInfo.json'):
    try:
        response = s3.get_object(Bucket=bucket, Key=prefix)
        content = response['Body'].read().decode('utf-8')
        return json.loads(content)
    except ClientError as e:
        print(f"S3 ClientError: {e}")
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    return None

def upload_folder_to_s3(local_folder, bucket_name, s3_prefix=''):
    for root, dirs, files in os.walk(local_folder):
        for file in files:
            local_path = os.path.join(root, file)
            # Create relative path from the base local folder
            relative_path = os.path.relpath(local_path, local_folder)
            # Create full S3 path using the prefix
            s3_key = os.path.join(s3_prefix, relative_path).replace("\\", "/")  # for Windows

            print(f"Uploading {local_path} to s3://{bucket_name}/{s3_key}")
            s3.upload_file(local_path, bucket_name, s3_key)

def upload_text_to_s3(bucket: str, prefix: str, text: str):
    """
    Uploads a text string to an S3 bucket with a given prefix.

    Args:
        bucket (str): The name of the S3 bucket.
        prefix (str): The key prefix (simulated folder path).
        filename (str): The name of the file to upload.
        text (str): The content to upload.

    Returns:
        str: The full S3 URI of the uploaded file.
    """
    
    try:
        s3.put_object(Bucket=bucket, Key=prefix, Body=text)
        s3_uri = f"s3://{bucket}/{prefix}"
        print(f"✅ Uploaded successfully to {s3_uri}")
        return s3_uri
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return None

if __name__ == "__main__":
    print(read_json_from_s3(bucket = 'testworkflow123', prefix = 'info_agent/companyInfo.json'))