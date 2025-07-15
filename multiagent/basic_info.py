

import boto3
from strands.models import BedrockModel
from botocore.config import Config as BotocoreConfig
from strands import Agent
from pydantic import BaseModel
from dotenv import load_dotenv
import os
from strands_tools import use_browser
from strands import Agent, tool
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
from selenium.webdriver.support.ui import WebDriverWait
from gnews import GNews
import crawl
from upload import upload_json_to_s3, upload_text_to_s3, read_json_from_s3
import json
from typing import List

from dataclasses import dataclass, asdict
os.environ["BYPASS_TOOL_CONSENT"] = "true"

# Load the .env file
load_dotenv()
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
OPENAI_SECRET_KEY = os.getenv("OPENAI_API_KEY")

# Define the

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
            model_id="arn:aws:bedrock:ap-southeast-1:389903776084:inference-profile/apac.amazon.nova-pro-v1:0",
            boto_session=session,
            temperature=0.3,
            top_p=0.8,
            stop_sequences=["###", "END"],
            # boto_client_config=self.boto_config,
        )

structure_model = BedrockModel(
            model_id="arn:aws:bedrock:ap-southeast-1:389903776084:inference-profile/apac.anthropic.claude-3-5-sonnet-20240620-v1:0",
            boto_session=session,
            temperature=0.3,
            top_p=0.8,
            stop_sequences=["###", "END"],
            # boto_client_config=self.boto_config,
        )

def get_basic_info( query: str) -> str:
    
    system_prompt = """
You are a helpful personal assistant specializing in searching, collecting, verifying, and analyzing information about companies.

You can use the following tools:

    fetch_company_info and fetch_company_person to obtain company information. When the tool return None, you can try it again for about 3 times, before use get_gg_search or get_gg_news for information alternatively.

    get_gg_search and get_gg_news to search for company-related information on Google

    crawl_news to access and extract data from news links

Your task is to provide the following company information in Vietnamese, in a clear and organized format:

    Tên công ty (Company Name)

    Website, số điện thoại, email của công ty (Website, phone number, email)

    Mã số thuế (Tax code)

    Lĩnh vực hoạt động (Industry/Field of operation)

    Ban lãnh đạo / Hội đồng quản trị (Board of Directors / Executive Board)

    Sản phẩm hoặc dịch vụ chính của công ty (Main products or services)

    Tập đoàn mẹ, công ty con(Parent group or major holding company). Ghi rõ ra công ty nào có mối quan hệ gì
    
    Công ty hợp tác, đối tác, tài trợ (partner). Ghi rõ công ty nào có mối quan hệ gì

You can make more research in company field, main products, parent or major holding, board of directors of company for more insight of company

Additional Requirements:

    Conduct deeper research to provide more insightful details about:

        The industry the company operates in

        Its main products or services

        Its parent group or major shareholder

 Report the output in fluent Vietnamese, using a clean and consistent format as shown above

"""
    agent = Agent(
            tools=[crawl.fetch_company_info, crawl.fetch_company_person, crawl.get_gg_news, crawl.get_gg_search, crawl.crawl_news],
            model=model,
            system_prompt=system_prompt,
        )
    results =agent(query)
    output = results.message.get('content', [])[0].get('text', '')
    return output

class CongTyCrawl(BaseModel):
    status: bool
    error: str
    ten_cty: str
    linh_vuc_hoat_dong: str
    sanpham: str
    tap_doan_me_so_huu: str
    ban_lanh_dao: str

structure_agent= Agent(model = structure_model)

def company_crawl_agent(bucket='testworkflow123', prefix='info_agent/companyInfo.json'):
    try:
        # Step 1: Read data from S3
        try:
            data = read_json_from_s3(bucket=bucket, prefix=prefix)
            if not data:
                raise ValueError("No data found in S3.")
        except Exception as e:
            return f"Error reading JSON from S3: {e}"

        # Step 2: Get basic company info
        try:
            company_info = get_basic_info(str(data))
        except Exception as e:
            return f"Error during company_info_agent processing: {e}"

        # Step 3: Structure and validate data
        try:
            company_crawl_info = structure_agent.structured_output(CongTyCrawl, f"""
Analyze and reorganize the data crawled from the company.

Return status: False if the tool is missing field like Tên công ty, Mã số thuế, Ban lãnh đạo / Hội đồng quản trị, Lĩnh vực hoạt động, or the data you crawl on web different from the data given.

Return error: the specific error or field missing

Return the following structured fields:

    ten_cty: the company name

    linh_vuc_hoat_dong: the company’s main business area or industry

    sanpham: the company’s primary products

    tap_doan_me_so_huu: related entities, such as parent companies or subsidiaries
base on this information:
{company_info}
""")
            if not company_crawl_info.status:
                return f"Error: {company_crawl_info.error}"
        except Exception as e:
            return f"Error structuring company crawl info: {e}"

        # Step 4: Upload structured data to S3
        try:
            upload_json_to_s3(json.dumps({
                "Tên công ty": company_crawl_info.ten_cty,
                "Lĩnh vực hoạt động": company_crawl_info.linh_vuc_hoat_dong,
                "Sản phẩm chủ đạo": company_crawl_info.sanpham,
                "Công ty mẹ, công ty sở hữu": company_crawl_info.tap_doan_me_so_huu,
                "Ban lãnh đạo": company_crawl_info.ban_lanh_dao
            }, ensure_ascii=False), bucket, 'info_crawl_agent/', 'companyInfo.json')
        except Exception as e:
            return f"Error uploading structured JSON to S3: {e}"

        # Step 5: Upload raw info text to S3
        try:
            upload_text_to_s3(bucket, 'content/basic_info/info_data.txt', company_info)
        except Exception as e:
            return f"Error uploading text info to S3: {e}"

        return company_info

    except Exception as e:
        return f"Unhandled error in company_crawl_agent: {e}"

if __name__=="__main__":
    print(company_crawl_agent())