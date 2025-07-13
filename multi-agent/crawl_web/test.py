import boto3
from strands.models import BedrockModel
from botocore.config import Config as BotocoreConfig
from strands import Agent
from pydantic import BaseModel
import dotenv
import os
from strands import Agent, tool
# from toool_test import get_cty, get_tc

dotenv.load_dotenv(".env", override=True)
# Create a custom boto3 session
session = boto3.Session(
    aws_access_key_id= os.environ.get('AWS_ACCESS_KEY'),
    aws_secret_access_key= os.environ.get('AWS_SECRET_KEY'),
)
boto_config = BotocoreConfig(
    retries={"max_attempts": 3, "mode": "standard"},
    connect_timeout=5,
    read_timeout=60
)
# Create a Bedrock model with the custom session
bedrock_model = BedrockModel(
    model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
    boto_session=session,
    temperature=0.3,
    top_p=0.8,
    stop_sequences=["###", "END"],
    boto_client_config=boto_config,
)

from strands import Agent, tool

@tool
def get_cty() -> str:
    return """{"ten_cong_ty": "CÔNG TY CỔ PHẦN TẬP ĐOÀN DUA FAT",
"ma_chung_khoan": null,
"dia_chi_tru_so_chinh": "Số 15, Liền kề 10, Khu đô thị Xa La, P. Phúc La, Q. Hà Đông, TP Hà Nội, Việt Nam",
"so_dien_thoai_hoac_email": null,
"linh_vuc_kinh_doanh_chinh": "Phá dỡ các kết cấu công trình và cầu kiện xây dựng"
}"""

@tool
def get_tc() -> str:
    return """{
    "quy": "Q1/2025",
    "tong_tai_san_cuoi_quy": 3242801930898,
    "loi_nhuan_sau_thue": -116915411380,
    "loi_nhuan_gop": -61372849620,
    "von_chu_so_huu": 119953583407,
    "tong_doanh_thu": 74478217583,
    "tong_tai_san": 3242801930898,
    "tong_no": 3122848347491,
    "gia_von_hang_ban": 135851067203,
    "loi_nhuan_gop_ve_BH_va_CCDV": -61372849620,
    "loi_nhuan_tai_chinh": -53217597991,
    "loi_nhuan_truoc_thue": -116888181727,
    "tong_tai_san_luu_dong_ngan_han": 2285669507340,
    "no_ngan_han": 2524167001622
    }"""
    

    
from pydantic import BaseModel
class CtyInfo(BaseModel):
    ten_cong_ty: str
    linh_vuc_kinh_doanh_chinh: str
    dia_chi_tru_so_chinh: str
    tong_tai_san_cuoi_quy: int
    loi_nhuan_sau_thue: int
    loi_nhuan_gop: int

agent = Agent(model = bedrock_model, tools=[get_cty, get_tc])

system_prompt = """
You are an intelligent personal assistant, specialized formatiing information about companies in Vietnam.

You have access to the following tools:
- get_cty: Get the general information about company.
- get_tc: Get the financial information about company.

Your task is to gather data with the following steps:
1. Call get_cty to get general information about company
2. Call get_tc to get general information about company

Instructions:
- Respond in a *clear and structured format*.
- All output must be in *Vietnamese*.

"""

result = agent("Hãy sử dụng tool get_cty và get_tc đê lấy dữ liệu và trích xuất dữ liệu")
result = agent.structured_output(CtyInfo, result)

print(result.tencongty)
print(result.linh_vuc_kinh_doanh_chinh)
print(result.dia_chi_tru_so_chinh)
print(result.tong_tai_san_cuoi_quy)
print(result.loi_nhuan_sau_thue)
print(result.loi_nhuan_gop)