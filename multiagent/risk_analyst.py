import os
from dotenv import load_dotenv
import boto3
from botocore.config import Config as BotocoreConfig
from strands.models import BedrockModel
from strands import Agent
from gnews import GNews
import json
from upload import read_json_from_s3, upload_text_to_s3, upload_json_to_s3
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

model = BedrockModel(
            model_id="arn:aws:bedrock:ap-southeast-1:389903776084:inference-profile/apac.amazon.nova-pro-v1:0",
            boto_session=session,
            temperature=0.3,
            top_p=0.8,
            # stop_sequences=["###", "END"],
            # boto_client_config=self.boto_config,
        )

structure_model = BedrockModel(
            model_id="arn:aws:bedrock:ap-southeast-1:389903776084:inference-profile/apac.anthropic.claude-sonnet-4-20250514-v1:0",
            boto_session=session,
            temperature=0.3,
            top_p=0.8,
            # stop_sequences=["###", "END"],
            # boto_client_config=self.boto_config,
        )


def get_risk_data(company_description: str) -> str:
    
    system_prompt = """
You are an intelligent personal assistant, specialized in deep searching, collecting, validating, and analyzing information about companies in Vietnam across various industries.

You have access to the following tools:

    get_gg_news: Search for recent and relevant news articles about a company using Google News.

    get_gg_search: Search for general web information using Google Search (e.g., official websites, financial data, business directories, government sites). Deep dive to research about same topic in 5-10 times and there is no result just return no information

    crawl_news: Extract and retrieve the full content of news articles given their URLs.
    
    Language Requirement:
All outputs must be written in Vietnamese, regardless of the source language of the articles or documents.

Information Validation:

    Prioritize official, reputable, or multi-source-verified information.

    Flag any suspicious, unverified, or biased content, and clearly indicate uncertainty if needed.

Depth over Speed:
Your priority is accuracy and depth of insight, not speed. Only respond when enough quality information is collected and verified.
"""

    risk_agent = Agent(
            tools=[get_gg_search, crawl_news, get_gg_news],
            model= model,
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

def risk_report_agent( risk_problem = 'Tài chính'):

    try:

        try:
            risk_data = get_risk_data(risk_problem)
        except Exception as e:
            return f"Error analyzing risk data: {e}"
        return risk_data

    except Exception as e:
        return f"Unhandled error in risk_report_agent: {e}"
    

def setup_risk_topic(bucket='testworkflow123', prefixs= ['info_crawl_agent/companyInfo.json', 'fin_agent/fin_data.json']):
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
    ten_cty = company_data.get('Tên công ty')
    ban_ld = company_data.get('Ban lãnh đạo')
    cty_me_con = company_data.get('Công ty mẹ, công ty sở hữu')
    sanpham = company_data.get("Sản phẩm chủ đạo")
    thitruong = company_data.get('Lĩnh vực hoạt động')
    lsu = risk_report_agent(f"""
Your mission is to findout about history of {ten_cty}, you can reference following {cty_me_con} for more details but priority still be {ten_cty}
    """)
    
    sp_out = risk_report_agent(f"""
Phân tích về sản phẩm chủ đạo {sanpham} của công ty {ten_cty}, sự nổi trội và hạn chế của sản phẩm so với các sản phẩm khác trong thị trường {thitruong}
                                """)
    mohinh_quanly = risk_report_agent(f""""
Phân tích các thành viên {ban_ld} trong công ty {ten_cty}. Đưa ra mô hình quản lý và tìm hiểu sơ yếu lý lịch và đưa ra những đóng góp hay những tổn thất họ gây ra với xã hội đặc biệt tại Việt Nam 
                                          """)
    taichinh = risk_report_agent(f"""
Phân tích tình hình tài chính của công ty {ten_cty} dựa trên {fin_data} và tìm hiểu thêm về tình hình nợ với các ngân hàng bên ngoài hay về dòng tiền của công ty 
                                 """)
    ruiro = risk_report_agent(f"""
Phân tích tất các rủi ro khi cho {ten_cty} vay mượn. Bao gồm: 
Rủi ro chiến lược (rủi ro về tầm nhìn công ty, rủi ro về cạnh tranh, rủi ro kinh doanh )
Rủi ro hoạt động (rủi ro công bố thông tin, rủi ro về nguồn nhân lực, rủi ro bảo mật)
Rủi ro luật định (những rủi ro liên quan đến chính sách, pháp luật).

Phân tích giải pháp khả thi chó các rủi ro đó
                                 """)
    
    final = f"""
Lịch sử hình thành: {lsu}
Sản phảm chủ đạo: {sp_out}
Mô hình quản lý: {mohinh_quanly}
Tài chính rủi ro: {taichinh}
Rủi ro khác: {ruiro}
    """
    upload_text_to_s3(bucket, 'content/risk_analyst/lichsu.txt', lsu)
    upload_text_to_s3(bucket, 'content/risk_analyst/spchuyeu.txt', sp_out)
    upload_text_to_s3( bucket, 'content/risk_analyst/mohinhquanly.txt', mohinh_quanly)
    upload_text_to_s3( bucket,  'content/risk_analyst/ruirotaichinh.txt', taichinh)
    upload_text_to_s3(bucket, 'content/risk_analyst/ruiro.txt', ruiro)

    return final



if __name__ == "__main__":
    output = setup_risk_topic()
    print(output)