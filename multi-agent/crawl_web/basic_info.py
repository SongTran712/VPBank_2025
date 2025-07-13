

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
from . import crawl

os.environ["BYPASS_TOOL_CONSENT"] = "true"

# Load the .env file
load_dotenv()
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
OPENAI_SECRET_KEY = os.getenv("OPENAI_API_KEY")

# Define the company info model
class CompanyInfo(BaseModel):
    name: str
    tax: str
    webpage: str
    email: str
    phone: str
    address: str
    industry_field: str
    lanhdao_hoidongquantri: str
    parent_and_holding_company: str

class CompanyInfoRetriever:
    def __init__(self):
        self.session = boto3.Session(
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
        )

        self.boto_config = BotocoreConfig(
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=60
        )

        self.model = BedrockModel(
            model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
            boto_session=self.session,
            temperature=0.3,
            top_p=0.8,
            stop_sequences=["###", "END"],
            boto_client_config=self.boto_config,
        )

        self.system_prompt = """
You are a helpful personal assistant specializing in searching, collecting, verifying, and analyzing information about companies.

You can use the following tools:

    fetch_company_info and fetch_company_person to obtain basic company information

    get_gg_search and get_gg_news to search for company-related information on Google

    crawl_news to access and extract data from news links

Your task is to provide the following basic company information in Vietnamese, in a clear and organized format:

    Tên công ty (Company Name)

    Website, số điện thoại, email của công ty (Website, phone number, email)

    Mã số thuế (Tax code)

    Lĩnh. vực hoạt động (Industry/Field of operation)

    Ban lãnh đạo / Hội đồng quản trị (Board of Directors / Executive Board)

    Sản phẩm hoặc dịch vụ chính của công ty (Main products or services)

    Tập đoàn mẹ hoặc công ty nắm giữ chính (Parent group or major holding company)

You can make more research in company field, main products, parent or major holding, board of directors of company for more insight of company

Additional Requirements:

    Conduct deeper research to provide more insightful details about:

        The industry the company operates in

        Its main products or services

        Its parent group or major shareholder

        Its board of directors or executive team

    Present the output in fluent Vietnamese, using a clean and consistent format as shown above

    If any information is unavailable, clearly indicate with: "(Chưa có thông tin)"

Web Search Reliability Notice:

    Because these tools rely on live web search and dynamic web content, you may:

        Retry the tool if it returns an error or None

        Attempt alternative search queries or pages if needed to complete the task

"""

        self.agent = Agent(
            tools=[crawl.fetch_company_info, crawl.fetch_company_person, crawl.get_gg_news, crawl.get_gg_search, crawl.crawl_news],
            model=self.model,
            system_prompt=self.system_prompt,
        )

    def get_basic_info(self, query: str) -> str:
        results = self.agent(query)
        output = results.message.get('content', [])[0].get('text', '')
        return output

if __name__=="__main__":
    company_info_agent = CompanyInfoRetriever()
    print(company_info_agent.get_basic_info("CÔNG TY CỔ PHẦN VIMC LOGISTICS"))