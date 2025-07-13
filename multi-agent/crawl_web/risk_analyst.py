from crawl import fetch_company_info, fetch_company_person, get_gg_search, get_gg_news, crawl_news
import boto3
from strands.models import BedrockModel
from botocore.config import Config as BotocoreConfig
from strands import Agent
from pydantic import BaseModel
from dotenv import load_dotenv
import os
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
You are an intelligent personal assistant, specialized in searching, collecting, and analyzing information about companies in Vietnam.

You have access to the following tools:
- `get_gg_news`: Search for relevant news articles about the company using Google News.
- `get_gg_search`: search for relevant inforation using Google search.
- `crawl_news`: Extract and retrieve detailed content from news article URLs.

Your task is to gather data and assess the company's risks and potential based on the following criteria:

1. **Identify positive and negative news** about the company within the past year.
2. **Analyze the company's main products and services** in relation to its industry sector.
3. **Evaluate how well the company’s policies and operations align** with Vietnamese laws and regulations.
4. **Assess the company’s strengths and weaknesses** within its industry.

Instructions:
- Respond in a **clear and structured format**.
- All output must be in **Vietnamese**.
"""

agent = Agent(tools = [get_gg_news, get_gg_search, crawl_news]
              , model = bedrock_model, system_prompt = system_prompt)



results = agent("""
Tên công ty: CÔNG TY CỔ PHẦN NHỰA AN PHÁT XANH (An Phát Bioplastics)
Ngành nghề/lĩnh vực kinh doanh: 
- Sản xuất và kinh doanh các sản phẩm nhựa
- Sản xuất bao bì nhựa, bao bì nhựa phân hủy sinh học
- Sản xuất tấm sàn nhựa và hạt nhựa compound
- Đầu tư và phát triển khu công nghiệp
Sản phẩm hoặc dịch vụ chính của công ty:
- Bao bì nhựa
- Bao bì nhựa phân hủy sinh học
- Tấm sàn nhựa SPC (xuất khẩu chính sang thị trường Mỹ)
- Hạt nhựa compound
- Phát triển khu công nghiệp (KCN Lương Điền Ngọc An)
""")
