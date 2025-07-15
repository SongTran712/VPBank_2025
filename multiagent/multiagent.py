import boto3
from strands.models import BedrockModel
from botocore.config import Config as BotocoreConfig
from strands import Agent
from pydantic import BaseModel
import dotenv
import os
from strands import Agent, tool
from pydantic import BaseModel
from typing import List
import json
from dataclasses import dataclass, asdict
from finance_agent import FinancialAgent
from basic_info import CompanyInfoRetriever
from risk_analyst import RiskAnalyst
from doc_extr import doc_extr_s3
from upload import upload_json_to_s3, read_json_from_s3, upload_folder_to_s3, upload_text_to_s3
import time
from botocore.exceptions import ClientError

dotenv.load_dotenv(".env", override=True)
# Create a custom boto3 session
session = boto3.Session(
    aws_access_key_id= os.environ.get('AWS_ACCESS_KEY'),
    aws_secret_access_key= os.environ.get('AWS_SECRET_KEY'),
    region_name= 'ap-southeast-1'
    
)
boto_config = BotocoreConfig(
    retries={"max_attempts": 3, "mode": "standard"},
    connect_timeout=5,
    read_timeout=60
)
# Create a Bedrock model with the custom session
bedrock_model = BedrockModel(
    model_id="arn:aws:bedrock:ap-southeast-1:389903776084:inference-profile/apac.anthropic.claude-3-5-sonnet-20241022-v2:0",
    boto_session=session,
    temperature=0.3,
    top_p=0.8,
    stop_sequences=["###", "END"],
    # boto_client_config=boto_config,
)
structure_agent = Agent(model =bedrock_model)
fin_agent = FinancialAgent()
company_info_agent = CompanyInfoRetriever()
risk_agent = RiskAnalyst()
@dataclass
class CompanyInfo:
    ten_cty: str
    ma_ck: str
    dia_chi: str
    so_dt: str
    email: str
    linhvuckinhdoanh: str

@dataclass
class BctcItem:
    quy: str
    tong_tai_san_cuoi_quy: int
    loi_nhuan_sau_thue: int
    loi_nhuan_gop: int
    tong_doanh_thu: int
    tong_tai_san: int
    tong_no: int
    gia_von_hang_ban: int
    loi_nhuan_gop_ve_BH_va_CCDV: int
    loi_nhuan_tai_chinh: int
    loi_nhuan_truoc_thue: int
    tong_tai_san_luu_dong_ngan_han: int
    no_ngan_han: int

class CongTy(BaseModel):
    status: bool
    error: str
    companyInfo: CompanyInfo
    bctc: List[BctcItem]

class CongTyCrawl(BaseModel):
    status: bool
    error: str
    content: str
    ten_cty: str
    linh_vuc_hoat_dong: str
    sanpham: str
    tap_doan_me_so_huu: str

class TaiChinh(BaseModel):
    status: bool
    error: str
    content: str
    thongso: str
    diemmanh: str
    diemyeu: str
    ruiro: str
    ketluan: str


def extract_document(bucket = 'testworkflow123', prefix = 'pdf/vlg'):
    try:
        try:
            output, err = doc_extr_s3(bucket, prefix)
        except Exception as e:
            return f"Error during document extraction from S3: {str(e)}"

        if not output:
            return f"Error when processing pdf: {err}"

        try:
            out = json.dumps(output, ensure_ascii=False)
        except Exception as e:
            return f"Error serializing output to JSON: {str(e)}"

        try:
            cty_extract = structure_agent.structured_output(CongTy, f"""
Hãy phân tích và sắp xếp dữ liệu lại đặc biệt về dữ liệu báo cáo tài chính, sắp xếp lại theo list các quý ứng với các biến sắp xếp theo chiều tăng dần về thời gian.
Trả về status: False khi không trích xuất được đủ trường cho 4 quý, và error khi status là False sẽ chỉ ra các trường còn thiếu. 
{out}
""")
        except Exception as e:
            return f"Error during structured output extraction: {str(e)}"

        try:
            print(cty_extract.status)
            print(cty_extract.companyInfo)
        except Exception as e:
            return f"Error printing structured output fields: {str(e)}"

        if not cty_extract.status:
            return cty_extract.error

        try:
            company_info_dict = json.dumps(asdict(cty_extract.companyInfo), ensure_ascii=False)
        except Exception as e:
            return f"Error converting companyInfo to JSON: {str(e)}"

        try:
            company_bctc_dict = [json.dumps(asdict(item), ensure_ascii=False) for item in cty_extract.bctc]
        except Exception as e:
            return f"Error converting bctc items to JSON: {str(e)}"

        try:
            upload_json_to_s3(company_info_dict, 'testworkflow123', 'info_agent/', 'companyInfo.json')
            upload_json_to_s3(company_bctc_dict, 'testworkflow123', 'info_agent/', 'companyBctc.json')
        except Exception as e:
            return f"Error when uploading JSON to S3: {str(e)}"

        return out

    except Exception as e:
        return f"Unexpected error in extract_document: {str(e)}"


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
            company_info = company_info_agent.get_basic_info(str(data))
        except Exception as e:
            return f"Error during company_info_agent processing: {e}"

        # Step 3: Structure and validate data
        try:
            company_crawl_info = structure_agent.structured_output(CongTyCrawl, f"""
Analyze and reorganize the data crawled from the company.

Return status: False if the tool is missing field like Tên công ty, Mã số thuế, Ban lãnh đạo / Hội đồng quản trị, Lĩnh vực hoạt động

Return error: the specific error or field missing

Return the following structured fields:

    ten_cty: the company name

    linh_vuc_hoat_dong: the company’s main business area or industry

    sanpham: the company’s primary products

    tap_doan_me_so_huu: related entities, such as parent companies or subsidiaries

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
                "Công ty mẹ, công ty sở hữu": company_crawl_info.tap_doan_me_so_huu
            }, ensure_ascii=False), bucket, 'info_crawl_agent/', 'companyInfo.json')
        except Exception as e:
            return f"Error uploading structured JSON to S3: {e}"

        # Step 5: Upload raw info text to S3
        try:
            upload_text_to_s3(bucket, 'content/info_data.txt', company_info)
        except Exception as e:
            return f"Error uploading text info to S3: {e}"

        return company_info

    except Exception as e:
        return f"Unhandled error in company_crawl_agent: {e}"

def finance_agent(bucket='testworkflow123', prefix='info_agent/companyBctc.json'):
    try:
        # Step 1: Read financial data from S3
        try:
            data = read_json_from_s3(bucket, prefix)
            if not data:
                raise ValueError("No financial data found in S3.")
        except Exception as e:
            return f"Error reading financial JSON from S3: {e}"

        # Step 2: Preprocess data and calculate "vốn chủ sở hữu"
        try:
            result = []
            for item in data:
                entry = json.loads(item)  # each item is assumed to be a JSON string
                if not all(k in entry for k in ["tong_tai_san", "tong_no"]):
                    raise ValueError(f"Missing keys in entry: {entry}")
                entry["von_chu_so_huu"] = entry["tong_tai_san"] - entry["tong_no"]
                result.append(entry)

            final_string = json.dumps(result, indent=2, ensure_ascii=False)
        except Exception as e:
            return f"Error processing financial entries: {e}"

        # Step 3: Run financial analysis
        try:
            fin_data = fin_agent.compute(final_string)
        except Exception as e:
            return f"Error in financial analysis agent: {e}"

        # Step 4: Structure financial output
        try:
            structured_fin_data = structure_agent.structured_output(TaiChinh, f"""
Hãy phân tích và sắp xếp lại dữ liệu phân tích từ báo cáo tài chính
Trả về status: False nếu không có các thông số đáng lưu ý về tài chính của công ty được tính hay phân tích sâu về rủi ro cũng như tình hình tài chính. Trả về error là lỗi gặp phải khi vấn đề xảy ra
Trả về thongso: thông số tài chính của công ty; diemmanh: những mặt tốt từ báo cáo tài chính; diemyeu: những mặt xấu từ báo cáo tài chính; ruiro: những phân tích rủi ro tình hình tài chính của công ty
{fin_data}
""")
            if not structured_fin_data.status:
                return f"Error in structured data: {structured_fin_data.error}"
        except Exception as e:
            return f"Error structuring financial data: {e}"

        # Step 5: Upload structured JSON
        try:
            upload_json_to_s3(json.dumps({
                "Điểm tốt": structured_fin_data.diemmanh,
                "Điểm yếu": structured_fin_data.diemyeu,
                "Rủi ro tiềm ẩn": structured_fin_data.ruiro,
                "Tổng quan": structured_fin_data.ketluan
            }, ensure_ascii=False), bucket, 'fin_agent/', 'fin_data.json')
        except Exception as e:
            return f"Error uploading structured JSON: {e}"

        # Step 6: Upload charts and raw financial text
        try:
            upload_folder_to_s3('charts', bucket, 'content/fin_charts/')
        except Exception as e:
            return f"Error uploading chart folder to S3: {e}"

        try:
            upload_text_to_s3(bucket, 'content/fin_data.txt', fin_data)
        except Exception as e:
            return f"Error uploading financial text to S3: {e}"

        return fin_data

    except Exception as e:
        return f"Unhandled error in finance_agent: {e}"


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
            risk_data = risk_agent.analyze_company(report_data)
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