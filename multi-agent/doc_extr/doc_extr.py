import fitz  # PyMuPDF
from PIL import Image
import io
import base64
import json
import boto3
import os
import dotenv
import time

# Load environment variables
dotenv.load_dotenv(".env", override=True)

session = boto3.Session(
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_KEY'),
    # region_name='ap-southeast-1'
)
client = session.client("bedrock-runtime")


def validate_pdf_count(folder_path: str, expected_count=4):
    pdf_files = [f for f in os.listdir(folder_path) if f.endswith(".pdf")]
    if len(pdf_files) != expected_count:
        raise ValueError(f"❌ Thư mục '{folder_path}' phải chứa đúng {expected_count} file PDF, nhưng tìm thấy {len(pdf_files)}.")
    return [os.path.join(folder_path, f) for f in pdf_files]


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
            return response_body["content"][0]["text"]
        except Exception as e:
            print(f"[ERROR] Gọi Claude thất bại (lần {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise RuntimeError(f"❌ Thất bại sau {retries} lần gọi Claude API: {e}")


def get_fina_info(folder_path: str):
    pdf_files = validate_pdf_count(folder_path, expected_count=4)

    claude_output = []
    for i, path in enumerate(pdf_files):
        try:
            doc = fitz.open(path)
        except Exception as e:
            print(f"[ERROR] Không thể mở file {path}: {e}")
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
                print(f"[ERROR] Lỗi khi xử lý trang {page_number} trong file {path}: {e}")
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
            response_text = retry_invoke_claude(payload, model_id='anthropic.claude-3-5-sonnet-20240620-v1:0')
            claude_output.append(response_text)
        except Exception as e:
            print(f"[ERROR] Claude API thất bại hoàn toàn với file {path}: {e}")
            claude_output.append(json.dumps({"error": str(e), "file": path}))

    return claude_output


def get_cmpy_info(folder_path: str):
    pdf_files = validate_pdf_count(folder_path, expected_count=4)

    try:
        doc = fitz.open(pdf_files[0])
    except Exception as e:
        raise RuntimeError(f"[ERROR] Không thể mở file {pdf_files[0]}: {e}")

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
            print(f"[ERROR] Lỗi khi xử lý trang {page_number} trong file {pdf_files[0]}: {e}")
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
        response_text = retry_invoke_claude(payload, model_id='anthropic.claude-3-5-sonnet-20240620-v1:0')
        return response_text
    except Exception as e:
        raise RuntimeError(f"[ERROR] Claude API thất bại hoàn toàn khi lấy thông tin công ty: {e}")


def doc_extr(folder_path):
    try:
        company_str = get_cmpy_info(folder_path)
        company_data = json.loads(company_str)
    except Exception as e:
        print(f"[ERROR] Không thể lấy thông tin công ty: {e}")
        company_data = {"error": str(e)}

    try:
        json_strings = get_fina_info(folder_path)
        bctc_data = [json.loads(item) for item in json_strings]
    except Exception as e:
        print(f"[ERROR] Không thể lấy thông tin tài chính: {e}")
        bctc_data = [{"error": str(e)}]

    final_data = {
        "company": company_data,
        "bctc": bctc_data
    }

    return final_data


if __name__ == "__main__":
    pdf_dir = "../../pdf/vlg/"
    result = doc_extr(pdf_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
