import boto3
from strands.models import BedrockModel
from botocore.config import Config as BotocoreConfig
from strands import Agent
from dotenv import load_dotenv
import os
from upload import upload_folder_to_s3, upload_text_to_s3, upload_json_to_s3, read_json_from_s3
import chartool
from pydantic import BaseModel
import json

os.environ["BYPASS_TOOL_CONSENT"] = "true"

# Load the .env file
load_dotenv()
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")

session = boto3.Session(
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name = 'ap-southeast-1'
        )

boto_config = BotocoreConfig(
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=60
        )

model = BedrockModel(
            model_id="arn:aws:bedrock:ap-southeast-1:389903776084:inference-profile/apac.anthropic.claude-3-5-sonnet-20240620-v1:0",
            boto_session = session,
            temperature=0.3,
            top_p=0.8,
            stop_sequences=["###", "END"],
            # boto_client_config=self.boto_config,
        )


system_prompt = """
Bạn là 1 agent hỗ trợ trong việc hoàn thành tờ trình tín dụng, nhưng không nhất thiết phải điền thẳng mà thông qua các trường trong dữ liệu json.

Dữ liệu JSON gồm các trường ứng với:
{
    "customer": chứa thông tin chung của khách hàng chứa tại 
}


"""




output_agent = Agent(model = model, system_prompt = system_prompt)