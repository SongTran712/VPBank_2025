import os
from dotenv import load_dotenv
import boto3
from botocore.config import Config as BotocoreConfig
from strands.models import BedrockModel
from strands import Agent
from gnews import GNews
import json
from upload import read_json_from_s3, upload_text_to_s3
from crawl import fetch_company_info, fetch_company_person, get_gg_search, get_gg_news, crawl_news

load_dotenv()
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
OPENAI_SECRET_KEY = os.getenv("OPENAI_API_KEY")

google_news = GNews(
            language='vi',
            country='VN',
            max_results=5,
            period='1y',
        )

boto_config = BotocoreConfig(
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=60
        )
session = boto3.Session(
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name = "ap-southeast-1"
        )

bedrock_model = BedrockModel(
            model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
            boto_session=session,
            temperature=0.3,
            top_p=0.8,
            stop_sequences=["###", "END"],
            # boto_client_config=boto_config,
        )


def get_risk_data(company_description: str) -> str:
    
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

    risk_agent = Agent(
            tools=[get_gg_news, get_gg_search, crawl_news],
            model= bedrock_model,
            system_prompt=system_prompt,
        )
    results = risk_agent(company_description)
    output = results.message.get('content', [])[0].get('text', '')
    return output




def generate_company_report(json1: dict, json2: dict) -> str:
    text = []

    # Company Info
    text.append("🏢 THÔNG TIN DOANH NGHIỆP")
    text.append(f"- Tên công ty: {json1['Tên công ty']}")
    text.append(f"- Lĩnh vực hoạt động: {json1['Lĩnh vực hoạt động']}")
    text.append("- Sản phẩm chủ đạo:")
    for line in json1['Sản phẩm chủ đạo'].split('\n'):
        text.append(f"  {line}")
    text.append(f"- Công ty mẹ / sở hữu: {json1['Công ty mẹ, công ty sở hữu']}")

    text.append("\n📊 PHÂN TÍCH DOANH NGHIỆP")

    # Good Points
    text.append("\n✅ Điểm tốt:")
    for line in json2['Điểm tốt'].split('\n'):
        text.append(f"  {line}")

    # Weaknesses
    text.append("\n⚠️ Điểm yếu:")
    for line in json2['Điểm yếu'].split('\n'):
        text.append(f"  {line}")

    # Risks
    text.append("\n🚨 Rủi ro tiềm ẩn:")
    for line in json2['Rủi ro tiềm ẩn'].split('\n'):
        text.append(f"  {line}")

    # Summary
    text.append("\n🧾 TỔNG QUAN:")
    for line in json2['Tổng quan'].split('\n'):
        text.append(f"  {line}")

    return '\n'.join(text)
def risk_report_agent(bucket='testworkflow123', prefixs= ['info_crawl_agent/companyInfo.json', 'fin_agent/fin_data.json']):

    
    try:
        # Step 1: Read company data
        try:
            company_data_raw = read_json_from_s3(bucket, prefixs[0])
            if not company_data_raw:
                raise ValueError("Company data not found.")
            company_data = json.loads(company_data_raw)
        except Exception as e:
            return f"Error reading or parsing company info: {e}"

        # Step 2: Read financial data
        try:
            fin_data_raw = read_json_from_s3(bucket, prefixs[1])
            if not fin_data_raw:
                raise ValueError("Financial data not found.")
            fin_data = json.loads(fin_data_raw)
        except Exception as e:
            return f"Error reading or parsing financial info: {e}"

        # Step 3: Generate input report for risk analysis
        try:
            report_data = generate_company_report(company_data, fin_data)
        except Exception as e:
            return f"Error generating company report: {e}"

        # Step 4: Run risk analysis
        try:
            risk_data = analyze_company(report_data)
        except Exception as e:
            return f"Error analyzing risk data: {e}"

        # Step 5: Upload to S3 (optional but catchable)
        try:
            upload_text_to_s3(bucket, 'content/risk_data.txt', risk_data)
        except Exception as e:
            print(f"Warning: Failed to upload risk data to S3: {e}")

        return risk_data

    except Exception as e:
        return f"Unhandled error in risk_report_agent: {e}"

if __name__ == "__main__":
    output = risk_report_agent()
    print(output)