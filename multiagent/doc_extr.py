import os
import io
import json
import time
import base64
import fitz  # PyMuPDF
from PIL import Image
from dotenv import load_dotenv
import boto3

# Load environment variables
load_dotenv(".env", override=True)

session = boto3.Session(
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_KEY'),
    region_name='ap-southeast-1'
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

