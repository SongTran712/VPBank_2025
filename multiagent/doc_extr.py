import os
import io
import json
import time
import base64
import fitz  # PyMuPDF
from PIL import Image
from dotenv import load_dotenv
import boto3
from upload import upload_json_to_s3
from strands import Agent, tool
from strands.models import BedrockModel
from botocore.config import Config as BotocoreConfig
from typing import List
from pydantic import BaseModel

from dataclasses import dataclass, asdict
# Load environment variables
load_dotenv(".env", override=True)

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
s3 = session.client("s3")
client = session.client("bedrock-runtime")


def get_pdfs_from_s3(bucket: str, prefix: str, expected_count=4):
    response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    pdf_keys = [item["Key"] for item in response.get("Contents", []) if item["Key"].endswith(".pdf")]

    if len(pdf_keys) != expected_count:
        raise ValueError(f"❌ Bucket `{bucket}`/`{prefix}` phải chứa đúng {expected_count} file PDF, nhưng tìm thấy {len(pdf_keys)}.")

    pdf_files = []
    for key in sorted(pdf_keys):
        file_obj = s3.get_object(Bucket=bucket, Key=key)
        pdf_bytes = file_obj['Body'].read()
        pdf_files.append((key, io.BytesIO(pdf_bytes)))

    return pdf_files


def retry_invoke_claude(payload, model_id, retries=3, delay=2):
    for attempt in range(retries):
        try:
            response = client.invoke_model(
                modelId=model_id,
                contentType='application/json',
                accept='application/json',
                body=json.dumps(payload)
            )
            response_body = json.loads(response['body'].read())
            text = response_body["content"][0]["text"]
            if not text.strip():
                raise ValueError("Claude trả về nội dung rỗng.")
            return text
        except Exception as e:
            print(f"[ERROR] Gọi Claude thất bại (lần {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise RuntimeError(f"❌ Thất bại sau {retries} lần gọi Claude API: {e}")


def get_fina_info_from_s3(bucket: str, prefix: str):
    pdf_files = get_pdfs_from_s3(bucket, prefix, expected_count=4)

    claude_output = []
    for key, pdf_file in pdf_files:
        try:
            doc = fitz.open("pdf", pdf_file.read())
        except Exception as e:
            print(f"[ERROR] Không thể mở file {key}: {e}")
            continue

        image_contents = []
        for page_number in range(0, 19):
            if page_number >= len(doc):
                break
            try:
                page = doc.load_page(page_number)
                pix = page.get_pixmap(dpi=200)
                img_data = Image.open(io.BytesIO(pix.tobytes("png")))

                buffered = io.BytesIO()
                img_data.save(buffered, format="JPEG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

                image_contents.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": img_base64
                    }
                })
            except Exception as e:
                print(f"[ERROR] Lỗi khi xử lý trang {page_number} trong file {key}: {e}")
                continue

        image_contents.append({
            "type": "text",
            "text": """Hãy đọc báo cáo tài chính và trích xuất chỉ số tài chính sau đây theo từng quý, nếu có:
            Tổng tài sản cuối quý, Lợi nhuận sau thuế, Lợi nhuận gộp, Vốn chủ sở hữu, Tổng doanh thu, Tổng tài sản, Tổng nợ,  Giá vốn hàng bán,Lợi nhuận gộp về BH và CCDV, Lợi nhuận tài chính, Lợi nhuận trước thuế, Tổng tài sản lưu động ngắn hạn, Tổng tài sản, Nợ ngắn hạn
        Hãy trả kết quả dưới dạng JSON. Ví dụ như sau:
        {
        "quy": "Qx/YYYY",
        "tong_tai_san_cuoi_quy": ...,
        "loi_nhuan_sau_thue": ...,
        ...
        }
        Nếu một trường không tìm thấy, hãy ghi là `null`. Không cần giải thích, chỉ xuất JSON kết quả."""
        })

        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "temperature": 0,
            "system": "Bạn là chuyên gia tài chính, hãy trích thông tin chính xác từ ảnh báo cáo tài chính.",
            "messages": [
                {
                    "role": "user",
                    "content": image_contents
                }
            ]
        }

        try:
            response_text = retry_invoke_claude(payload, model_id='arn:aws:bedrock:ap-southeast-1:389903776084:inference-profile/apac.anthropic.claude-3-5-sonnet-20240620-v1:0')
            claude_output.append(response_text)
        except Exception as e:
            print(f"[ERROR] Claude API thất bại hoàn toàn với file {key}: {e}")
            claude_output.append(json.dumps({"error": str(e), "file": key}))

    return claude_output


def get_cmpy_info_from_s3(bucket: str, prefix: str):
    pdf_files = get_pdfs_from_s3(bucket, prefix, expected_count=4)

    try:
        doc = fitz.open("pdf", pdf_files[0][1].read())
    except Exception as e:
        raise RuntimeError(f"[ERROR] Không thể mở file {pdf_files[0][0]}: {e}")

    image_contents = []
    for page_number in range(0, 19):
        if page_number >= len(doc):
            break
        try:
            page = doc.load_page(page_number)
            pix = page.get_pixmap(dpi=200)
            img_data = Image.open(io.BytesIO(pix.tobytes("png")))

            buffered = io.BytesIO()
            img_data.save(buffered, format="JPEG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

            image_contents.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": img_base64
                }
            })
        except Exception as e:
            print(f"[ERROR] Lỗi khi xử lý trang {page_number} trong file {pdf_files[0][0]}: {e}")
            continue

    image_contents.append({
        "type": "text",
        "text": """Hãy đọc báo cáo tài chính và trích xuất các thông tin của công ty, với các trường dưới đây:
            Tên công ty, Mã chứng khoán, Địa chỉ trụ sở, Số điện thoại, Email, Lĩnh vực kinh doanh.
        Hãy trả kết quả dưới dạng JSON. Ví dụ như sau:
        {
        "TenCongTy": "Abc",
        "MaChungKhoan": ...,
        "DiaChi": ...,
        ...
        }
        Nếu một trường không tìm thấy, hãy ghi là `null`. Không cần giải thích, chỉ xuất JSON kết quả."""
    })

    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "temperature": 0,
        "system": "Bạn là chuyên gia tài chính, hãy trích thông tin chính xác từ ảnh báo cáo tài chính.",
        "messages": [
            {
                "role": "user",
                "content": image_contents
            }
        ]
    }

    try:
        response_text = retry_invoke_claude(payload, model_id='arn:aws:bedrock:ap-southeast-1:389903776084:inference-profile/apac.anthropic.claude-3-5-sonnet-20240620-v1:0')
        return response_text
    except Exception as e:
        raise RuntimeError(f"[ERROR] Claude API thất bại hoàn toàn khi lấy thông tin công ty: {e}")


def doc_extr_s3(bucket: str, prefix: str):
    try:
        company_str = get_cmpy_info_from_s3(bucket, prefix)
        company_data = json.loads(company_str)
    except Exception as e:
        print(f"[ERROR] Không thể lấy thông tin công ty: {e}")
        company_data = {"error": str(e)}
        return None, company_data

    try:
        json_strings = get_fina_info_from_s3(bucket, prefix)
        bctc_data = [json.loads(item) for item in json_strings]
    except Exception as e:
        print(f"[ERROR] Không thể lấy thông tin tài chính: {e}")
        bctc_data = [{"error": str(e)}]
        return None, company_data

    final_data = {
        "company": company_data,
        "bctc": bctc_data
    }

    return final_data, None

structure_agent = Agent(model = bedrock_model)
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
    
if __name__ == "__main__":
    output = extract_document()
    print(output)