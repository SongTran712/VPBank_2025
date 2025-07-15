import os
from dotenv import load_dotenv
import boto3
from botocore.config import Config as BotocoreConfig
from strands.models import BedrockModel
from strands import Agent
from gnews import GNews

from crawl import fetch_company_info, fetch_company_person, get_gg_search, get_gg_news, crawl_news

class RiskAnalyst:
    def __init__(self):
        os.environ["BYPASS_TOOL_CONSENT"] = "true"
        self._load_env()
        self._init_google_news()
        self._init_bedrock_model()
        self._init_agent()

    def _load_env(self):
        load_dotenv()
        self.AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
        self.AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
        self.OPENAI_SECRET_KEY = os.getenv("OPENAI_API_KEY")

    def _init_google_news(self):
        self.google_news = GNews(
            language='vi',
            country='VN',
            max_results=5,
            period='1y',
        )

    def _init_bedrock_model(self):
        boto_config = BotocoreConfig(
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=60
        )
        session = boto3.Session(
            aws_access_key_id=self.AWS_ACCESS_KEY,
            aws_secret_access_key=self.AWS_SECRET_KEY,
            region_name = "ap-southeast-1"
        )

        self.bedrock_model = BedrockModel(
            model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
            boto_session=session,
            temperature=0.3,
            top_p=0.8,
            stop_sequences=["###", "END"],
            # boto_client_config=boto_config,
        )

    def _init_agent(self):
        system_prompt = """
You are an intelligent personal assistant, specialized in searching, collecting, and analyzing information about companies in Vietnam.

You have access to the following tools:
- `get_gg_news`: Search for relevant news articles about the company using Google News.
- `get_gg_search`: Search for relevant information using Google Search.
- `crawl_news`: Extract and retrieve detailed content from news article URLs.

Your task is to gather and analyze data to evaluate the company’s risks and opportunities. Focus on the following areas:

1. **Identify both positive and negative news** about the company within the past year.
2. **Analyze the company’s core products and services** in relation to its industry sector.
3. **Evaluate the company's compliance** with Vietnamese laws and regulations in its policies and operations.
4. **Assess the company’s strengths and weaknesses** compared to competitors in the same industry.
5. **Analyze the financial situation** of the company, highlighting any potential risks or concerns.
6. **Investigate the company’s relationship with banks**, including creditworthiness, outstanding debts, or financial dependencies.

Instructions:
- Provide your assessment in a **clear, well-organized, and structured format**.
- All responses must be in **Vietnamese**.
"""
        self.agent = Agent(
            tools=[get_gg_news, get_gg_search, crawl_news],
            model=self.bedrock_model,
            system_prompt=system_prompt,
        )

    def analyze_company(self, company_description: str) -> str:
        return self.agent(company_description)

# Usage Example
if __name__ == "__main__":
    analyst = RiskAnalyst()
    company_input = """
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
"""
    result = analyst.analyze_company(company_input)
    print(result)
