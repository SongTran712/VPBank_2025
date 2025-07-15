import boto3
from strands.models import BedrockModel
from botocore.config import Config as BotocoreConfig
from strands import Agent
from dotenv import load_dotenv
import os

import chartool


os.environ["BYPASS_TOOL_CONSENT"] = "true"

# Load the .env file
load_dotenv()
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")



class FinancialAgent:
    def __init__(self):
        self.session = boto3.Session(
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name = 'ap-southeast-1'
        )

        self.boto_config = BotocoreConfig(
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=60
        )

        self.model = BedrockModel(
            model_id="arn:aws:bedrock:ap-southeast-1:389903776084:inference-profile/apac.anthropic.claude-3-5-sonnet-20240620-v1:0",
            boto_session=self.session,
            temperature=0.3,
            top_p=0.8,
            stop_sequences=["###", "END"],
            # boto_client_config=self.boto_config,
        )

        self.system_prompt = """
You are a financial analysis expert.

You can use the analyze_financial_data tool to calculate key financial metrics such as ROE, ROA, ROS, Debt Ratio,...  automatically generate insightful analytical charts.

You are provided with the company’s full quarterly financial data in the form of a JSON list. For example:

[
  {
    "quy": "Q1/2025",
    "tong_tai_san": 1000000,
    "tong_no": 800000,
    "von_chu_so_huu": 200000,
    "tong_doanh_thu": 500000,
    "loi_nhuan_sau_thue": 25000,
    "loi_nhuan_truoc_thue": 30000,
    "loi_nhuan_gop": 80000,
    "tong_tai_san_luu_dong_ngan_han": 400000,
    "no_ngan_han": 250000
  },
  ...
]

Your task includes the following:

    Calculate and report key financial indicators (ROE, ROA, ROS, Debt Ratio, CurrentRatio, GrossProfitMargin, AssetTurnoverRatio, etc.) for each quarter.

    Generate charts to visualize trends and changes over time.

    Provide a clear and structured financial analysis, highlighting:

        Significant changes between quarters.

        Strengths and weaknesses in the company’s financial position.

        Potential risks based on financial ratios and trends.

Your report should be accurate, insightful, and visually supported by charts for better decision-making.
Report in Vietnamese with well structured and clearly.

"""

        self.agent = Agent(
            tools=[chartool.analyze_financial_data],
            model=self.model,
            system_prompt=self.system_prompt,
        )

    def compute(self, query: str) -> str:
        results = self.agent(query)
        output = results.message.get('content', [])[0].get('text', '')
        return output

if __name__=="__main__":
    company_info_agent = FinancialAgent()
    print(company_info_agent.compute("""
['{"quy": "Q2/2024", "tong_tai_san_cuoi_quy": 212146243168, "loi_nhuan_sau_thue": 10588556972, "loi_nhuan_gop": 2283265819, "tong_doanh_thu": 42083671325, "tong_tai_san": 212146243168, "tong_no": 44883639493, "gia_von_hang_ban": 39800405506, "loi_nhuan_gop_ve_BH_va_CCDV": 2283265819, "loi_nhuan_tai_chinh": 189638689, "loi_nhuan_truoc_thue": 13259726458, "tong_tai_san_luu_dong_ngan_han": 145623535885, "no_ngan_han": 44883639493}',
 '{"quy": "Q3/2024", "tong_tai_san_cuoi_quy": 227375689868, "loi_nhuan_sau_thue": 13875548792, "loi_nhuan_gop": 1791245409, "tong_doanh_thu": 41977528911, "tong_tai_san": 227375689868, "tong_no": 46237537401, "gia_von_hang_ban": 40186283502, "loi_nhuan_gop_ve_BH_va_CCDV": 1791245409, "loi_nhuan_tai_chinh": 834803115, "loi_nhuan_truoc_thue": 17204922944, "tong_tai_san_luu_dong_ngan_han": 162255806260, "no_ngan_han": 46237537401}',
 '{"quy": "Q4/2024", "tong_tai_san_cuoi_quy": 229773312284, "loi_nhuan_sau_thue": -3809126900, "loi_nhuan_gop": 2114408986, "tong_doanh_thu": 62287700880, "tong_tai_san": 229773312284, "tong_no": 52444286717, "gia_von_hang_ban": 60173291894, "loi_nhuan_gop_ve_BH_va_CCDV": 2114408986, "loi_nhuan_tai_chinh": 617879595, "loi_nhuan_truoc_thue": -513742519, "tong_tai_san_luu_dong_ngan_han": 164800586261, "no_ngan_han": 52444286717}',
 '{"quy": "Q1/2025", "tong_tai_san_cuoi_quy": 236156479630, "loi_nhuan_sau_thue": 1116027647, "loi_nhuan_gop": 2304572679, "tong_doanh_thu": 60107916752, "tong_tai_san": 236156479630, "tong_no": 57711426416, "gia_von_hang_ban": 57803344073, "loi_nhuan_gop_ve_BH_va_CCDV": 2304572679, "loi_nhuan_tai_chinh": 622690374, "loi_nhuan_truoc_thue": 1402037633, "tong_tai_san_luu_dong_ngan_han": 172374527886, "no_ngan_han": 57711426416}']
                                     """))