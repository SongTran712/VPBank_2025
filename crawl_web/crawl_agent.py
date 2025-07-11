from crawl import fetch_company_info, fetch_company_person
import boto3
from strands.models import BedrockModel
from botocore.config import Config as BotocoreConfig
from strands import Agent
from pydantic import BaseModel

class CompanyInfo(BaseModel):
    name: str
    tax: str
    address: str
    industry_field: str
    lanhdao_hoidongquantri: str
    

# Create a custom boto3 session
session = boto3.Session(
    aws_access_key_id='',
    aws_secret_access_key='',
)

boto_config = BotocoreConfig(
    retries={"max_attempts": 3, "mode": "standard"},
    connect_timeout=5,
    read_timeout=60
)

# Create a Bedrock model with the custom session
bedrock_model = BedrockModel(
    model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
    boto_session=session,
    temperature=0.3,
    top_p=0.8,
    stop_sequences=["###", "END"],
    boto_client_config=boto_config,
)

system_prompt = """You are a helpful personal assistant that specializes in search or crawl information about company like: Company Name, Tax Identification Number, Industry, Leadership/Board of Directors.
You have acess to in fetch company information tool. Response clearly in structure format and in Vietnamese.
"""

agent = Agent(tools = [fetch_company_info, fetch_company_person]
              , model = bedrock_model, system_prompt = system_prompt)

results = agent("Công ty Cổ phần Nhựa An Phát Xanh")

agent = Agent(model= bedrock_model)

results = agent.structured_output(CompanyInfo,results)

print(results)