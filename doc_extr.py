import fitz  # PyMuPDF
from PIL import Image
import io
import base64
import json
import boto3
import os
import dotenv

dotenv.load_dotenv(".env", override=True)

session = boto3.Session(
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key= os.environ.get('AWS_SECRET_ACCESS_KEY'),
    region_name= os.environ.get('AWS_REGION')
)
client = session.client("bedrock-runtime")

def get_fina_info(folder_path: str):
    pdf_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith(".pdf")]
    claude_output = []
    for i, path in enumerate(pdf_files):
        doc = fitz.open(path)
        image_contents = []
        for page_number in range(0, 19):  # page 10 to 30 → index 9 to 29
            if page_number >= len(doc):
                break  # avoid out-of-bounds error
    
            page = doc.load_page(page_number)
            pix = page.get_pixmap(dpi=200)

            # Convert to PIL Image
            img_data = Image.open(io.BytesIO(pix.tobytes("png")))

            # Encode to base64
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

        # === Add your question ===
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

        # === Claude payload ===
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
        # === Gửi tới Claude ===
        response = client.invoke_model(
            modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
            contentType='application/json',
            accept='application/json',
            body=json.dumps(payload)
        )
        # === Step 6: In kết quả ===
        response_body = json.loads(response['body'].read())
        
        response_text = response_body["content"][0]["text"]
        claude_output.append(response_text)
    
    return claude_output

    
def get_cmpy_info(folder_path: str):
    pdf_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith(".pdf")]
    doc = fitz.open(pdf_files[0])
    image_contents = []
    for page_number in range(0, 19):  # page 10 to 30 → index 9 to 29
        if page_number >= len(doc):
            break  # avoid out-of-bounds error

        page = doc.load_page(page_number)
        pix = page.get_pixmap(dpi=200)

        # Convert to PIL Image
        img_data = Image.open(io.BytesIO(pix.tobytes("png")))

        # Encode to base64
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
    # === Add your question ===
    image_contents.append({
        "type": "text",
        "text": """Hãy đọc báo cáo tài chính và trích xuất các thông tin của công ty, với các trường dưới đây:
            Tên công ty, Mã chứng khoán, Địa chỉ trụ sở, Số điện thoại, Email, Lĩnh vực kinh doanh.
        Hãy trả kết quả dưới dạng JSON. Ví dụ như sau:
        {
        "TenCongTy": "Abc",
        "MaChungKhoan": ...,
        "DiaTri": ...,
        ...
        }
        Nếu một trường không tìm thấy, hãy ghi là `null`. Không cần giải thích, chỉ xuất JSON kết quả."""
    })

    # === Claude payload ===
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
    # === Gửi tới Claude ===
    response = client.invoke_model(
        modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
        contentType='application/json',
        accept='application/json',
        body=json.dumps(payload)
    )
    # === Step 6: In kết quả ===
    response_body = json.loads(response['body'].read())
    # claude_output = ""
    response_text = response_body["content"][0]["text"]
    return response_text
    

def doc_extr(folder_path):
    company_str = get_cmpy_info(folder_path)
    company_data = json.loads(company_str)
    result = {
    "company": company_data  # from your parsed company string
    }
    json_strings = get_fina_info(folder_path)
    bctc_data = [json.loads(item) for item in json_strings]
    result2 = {
        "bctc": bctc_data  # from your parsed list of financials
    }
    # Merge them into one dictionary
    final_data = {**result, **result2}

    # Save to a single JSON file
    with open("final_output.json", "w", encoding="utf-8") as f:
        json.dump(final_data, f, indent=2, ensure_ascii=False)


pdf_dir = "./pdf/vlg/"
doc_extr(pdf_dir)