import aioboto3
import json
import boto3
import os
import base64
from datetime import datetime
from dotenv import load_dotenv
import re
import io
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

# data={'test':'hong-tran-tren-doi-canh-tay'}
# asyncio.run(upload_json_to_s3_async(data,'vpbank-team91','Song-test/test.json',access,secret,'ap-southeast-1'))
async def main():
    data = {"project": "AIOps", "status": "ok"}
    result = await upload_json_to_s3_async(
        data,'vpbank-team91','Song-test/test.json',access,secret,'ap-southeast-1'
    )
    print(result)


def is_base64(s):
    """Check if string is valid base64"""
    try:
        if isinstance(s, str):
            # Remove data URI prefix if present
            if s.startswith("data:"):
                s = re.sub("^data:.*?base64,", "", s)
            base64.b64decode(s, validate=True)
            return True
        return False
    except Exception:
        return False

def upload_to_s3_safe(data, bucket, key, access, secret, region, content_type=None):
    """
    Uploads JSON, base64, bytes, or file-like object to S3 safely.

    :param data: dict, JSON string, base64 string, bytes, or BytesIO
    :param bucket: Target S3 bucket name
    :param key: S3 object key (e.g., 'path/file.png')
    :param access: AWS access key
    :param secret: AWS secret key
    :param region: AWS region
    :param content_type: MIME type (optional)
    :return: S3 URL or error
    """

    # Initialize S3 client
    s3 = boto3.client(
        "s3",
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        region_name=region
    )

    try:
        # Determine body and content type
        if isinstance(data, dict):
            body = json.dumps(data).encode("utf-8")
            final_content_type = content_type or "application/json"

        elif isinstance(data, str):
            if is_base64(data):
                # Remove data URI prefix if present
                base64_data = re.sub("^data:.*?base64,", "", data)
                body = base64.b64decode(base64_data)
                final_content_type = content_type or "application/octet-stream"
            else:
                try:
                    json.loads(data)  # Validate JSON string
                    body = data.encode("utf-8")
                    final_content_type = content_type or "application/json"
                except json.JSONDecodeError:
                    raise ValueError("String is neither valid JSON nor base64.")

        elif isinstance(data, bytes):
            body = data
            final_content_type = content_type or "application/octet-stream"

        elif isinstance(data, io.IOBase):
            data.seek(0)
            body = data.read()
            final_content_type = content_type or "application/octet-stream"

        else:
            raise TypeError("Unsupported data type for upload.")

        # Upload to S3
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType=final_content_type
        )

        return f"✅ success s3://{bucket}/{key}"

    except Exception as e:
        return f"❌ Error: {str(e)}"

if __name__=='__name__':
    import asyncio
    asyncio.run(main())

def is_image_file(key):
    ext = os.path.splitext(key)[1].lower()
    return ext in ['.png', '.jpg', '.jpeg']

def fetch_and_encode_image(s3_client, bucket, key):
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        content = response['Body'].read()
        return base64.b64encode(content).decode('utf-8')
    except Exception as e:
        print(f"❌ Error fetching {key}: {e}")
        return None

def encode_images_from_s3_folder(bucket, prefix, access_key, secret_key, region):
    """
    Fetches all .png/.jpg images from the given S3 folder and returns base64-encoded versions.

    :param bucket: S3 bucket name
    :param prefix: S3 folder path, e.g. 'charts_output/'
    :param access_key: AWS Access Key
    :param secret_key: AWS Secret Key
    :param region: AWS region
    :return: dict of {filename: base64_encoded_string}
    """
    s3 = init_s3_client(access_key, secret_key, region)
    result = {}

    try:
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        for obj in response.get('Contents', []):
            key = obj['Key']
            if is_image_file(key):
                encoded = fetch_and_encode_image(s3, bucket, key)
                if encoded:
                    filename = os.path.basename(key)
                    result[filename] = encoded
                    print(f"✅ Encoded: {filename}")
    except Exception as e:
        print(f"❌ Failed to list or process objects: {e}")

    return result


import mimetypes
def images_as_base64_blocks(
    bucket: str,
    prefix: str,
    access_key: str,
    secret_key: str,
    region: str = "ap-southeast-1"
):
    """
    Return images from S3 under `prefix` as a list of dicts:
    {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": "<BASE64_STRING>"
        }
    }
    """
    s3 = boto3.client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )

    blocks = []

    try:
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                ext = os.path.splitext(key)[1].lower()
                if ext not in {".png", ".jpg", ".jpeg"}:
                    continue

                # download
                body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
                b64   = base64.b64encode(body).decode("utf-8")

                # guess MIME type from extension
                mime  = mimetypes.guess_type(key)[0] or "application/octet-stream"

                blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime,
                        "data": b64,
                    }
                })
                print(f"✅ encoded {key} → {mime}")

    except Exception as err:
        print(f"❌ error processing images: {err}")

    return blocks
