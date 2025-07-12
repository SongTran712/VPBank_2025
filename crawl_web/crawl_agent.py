from crawl import fetch_company_info, fetch_company_person, get_news, crawl_news
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
os.environ["BYPASS_TOOL_CONSENT"] = "true"
google_news = GNews(language='vi', 
                    country='VN',
                    max_results=5,
                    period='1y',
                    
                    )

# Load the .env file
load_dotenv()
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
OPENAI_SECRET_KEY = os.getenv("OPENAI_API_KEY")
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--headless=new")  # newer headless mode
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-software-rasterizer")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--log-level=3")
class CompanyInfo(BaseModel):
    name: str
    tax: str
    address: str
    industry_field: str
    lanhdao_hoidongquantri: str

# Create a custom boto3 session
session = boto3.Session(
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
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

system_prompt = """
You are a helpful personal assistant, specialized in searching for, gathering, and analyzing information about companies.
You can use fetch_company_info and fetch_company_person for basic information of company. Moreover, use the get_news for information you want to search and crawl_news to access and retrieve information from that url
Your tasks is providing basic information:

    1. Company name

    2. Tax identification number

    3. Industry/business sector

    4. Leadership / Board of Directors

    5. The company’s main products or services

Respond clearly with structured format in Vietnamese

"""

agent = Agent(tools = [fetch_company_info, fetch_company_person, get_news, crawl_news]
              , model = bedrock_model, system_prompt = system_prompt)

results = agent("Công ty Cổ phần Nhựa An Phát Xanh")
