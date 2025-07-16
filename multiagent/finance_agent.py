

import boto3
from strands.models import BedrockModel
from botocore.config import Config as BotocoreConfig
from strands import Agent
from dotenv import load_dotenv
import os
from upload import upload_folder_to_s3, upload_text_to_s3, upload_json_to_s3, read_json_from_s3
import chartool
from pydantic import BaseModel
import json

os.environ["BYPASS_TOOL_CONSENT"] = "true"

# Load the .env file
load_dotenv()
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")

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
            model_id="arn:aws:bedrock:ap-southeast-1:389903776084:inference-profile/apac.anthropic.claude-3-5-sonnet-20240620-v1:0",
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


def get_finance_data(query: str) -> str:
    
    
    system_prompt = """
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

    fin_agent = Agent(
            tools=[chartool.analyze_financial_data],
            model= model,
            system_prompt=system_prompt,
        )
    results = fin_agent(query)
    output = results.message.get('content', [])[0].get('text', '')
    return output

class TaiChinh(BaseModel):
    status: bool
    error: str
    thongso: str
    diemmanh: str
    diemyeu: str
    ruiro: str
    ketluan: str

structure_agent = Agent(model = structure_model)


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
            fin_data = get_finance_data(final_string)
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
            upload_folder_to_s3('charts', bucket, 'content/fin_analyst/fin_charts/')
        except Exception as e:
            return f"Error uploading chart folder to S3: {e}"

        try:
            upload_text_to_s3(bucket, 'content/fin_analyst/fin_data.txt', fin_data)
        except Exception as e:
            return f"Error uploading financial text to S3: {e}"

        return fin_data

    except Exception as e:
        return f"Unhandled error in finance_agent: {e}"
    
if __name__=="__main__":
    output = finance_agent()
    print(output)
    